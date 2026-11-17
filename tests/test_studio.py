from __future__ import annotations

import base64
import io
import json
import sqlite3
import zipfile
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobRunner, BackgroundJobStore
from prompt_hub.creative import CREATIVE_SCHEMA, CreativeStore
from prompt_hub.gallery import GalleryStore
from prompt_hub.studio_annotations import import_annotations
from prompt_hub.studio_prompts import prepare_batch
from prompt_hub.studio_providers import ImageProviderStore, novelai_images, openai_images
from prompt_hub.studio_service import StudioService
from prompt_hub.studio_store import StudioError, StudioStore, normalize_recipe
from prompt_hub.studio_workflows import compile_graph, infer_bindings
from prompt_hub.web import INDEX_HTML
from prompt_hub.workflow_profiles import WorkflowProfileStore


@pytest.fixture
def studio(settings):
    projects = CreativeStore(settings.database_path)
    projects.initialize()
    gallery = GalleryStore(settings)
    gallery.initialize()
    jobs = BackgroundJobStore(settings.database_path)
    jobs.initialize()
    store = StudioStore(settings, projects, gallery)
    store.initialize()
    return StudioService(
        store,
        ImageProviderStore(settings.library_root),
        WorkflowProfileStore(settings.workflow_profiles_root),
    )


def picture(color="blue"):
    output = io.BytesIO()
    Image.new("RGB", (128, 192), color).save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize("target", ["moss", "anima", "krea2", "h3"])
def test_project_targets_and_noop_save(studio, target):
    project = studio.store.create_project("測試", target)
    saved = studio.store.save_project(project["project_id"], {"studio": project["studio"]})
    assert saved["revision"] == project["revision"]
    assert saved["target_profile"] == target


def test_old_database_migration_preserves_data_and_is_repeatable(settings):
    old = CREATIVE_SCHEMA.replace("'anima', 'krea2', 'moss', 'h3'", "'anima',\n 'krea2'")
    with sqlite3.connect(settings.database_path) as connection:
        connection.executescript(old)
    projects = CreativeStore(settings.database_path)
    project = projects.create_project({"title": "old", "target_profile": "anima"})
    projects.initialize()
    assert projects.get_project(project["project_id"])["title"] == "old"
    assert projects.create_project({"target_profile": "moss"})["target_profile"] == "moss"


def test_batch_locks_and_independent_seeds(studio):
    recipe = normalize_recipe(
        {
            "count": 20,
            "body": "{standing|sitting|walking}",
            "suffix": "{sun|moon|stars}",
            "locks": {"body": True},
            "seed": 100,
            "text_seed": 1,
        }
    )
    rows = prepare_batch(studio.store, recipe, {})
    assert len({row["body"] for row in rows}) == 1
    assert len({row["suffix"] for row in rows}) > 1
    assert [row["seed"] for row in rows] == list(range(100, 120))
    recipe["locked_values"] = {"body": "pinned"}
    assert all(row["body"] == "pinned" for row in prepare_batch(studio.store, recipe, {}))


def test_existing_creative_project_keeps_its_compiled_prompt(studio):
    project = studio.store.projects.create_project(
        {
            "title": "existing",
            "target_profile": "anima",
            "slots": {"character": "1girl, red hair"},
        }
    )
    restored = studio.store.require_project(project["project_id"])
    assert "red hair" in restored["studio"]["body"]
    assert restored["studio"]["text_mode"] == "manual"


def test_same_text_and_novelai_seed_range(studio):
    recipe = normalize_recipe(
        {
            "backend": "novelai",
            "count": 10,
            "batch_mode": "same_text",
            "seed": 2**32 - 1,
            "body": "{a|b|c}",
        }
    )
    rows = prepare_batch(studio.store, recipe, {})
    assert rows[1]["seed"] == 0
    assert len({row["positive"] for row in rows}) == 1


@pytest.mark.parametrize(
    "values",
    [
        {"cfg": "bad"},
        {"prefix_rows": [None]},
        {"bindings": {"body": [3]}},
        {"locked_values": {"body": 5}},
        {"characters": [{"x": 2}]},
        {"strength": float("nan")},
    ],
)
def test_invalid_recipe_is_a_validation_error(values):
    with pytest.raises(StudioError):
        normalize_recipe(values)


def test_atomic_enqueue_prevents_concurrent_duplicate_batches(studio):
    project = studio.store.create_project("batch", "moss")["project_id"]
    payloads = [{"project_id": project, "prompt": {"index": index}} for index in range(8)]
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: studio.store.enqueue_batch("preview-1", project, payloads), range(8)
            )
        )
    assert all(result == results[0] for result in results)
    jobs = BackgroundJobStore(studio.store.settings.database_path)
    assert len(jobs.list_jobs(project_id=project)) == 8


def test_image_dedup_caption_revision_and_external_import(studio):
    project = studio.store.create_project("images", "moss")["project_id"]
    first = studio.store.add_image(project, picture(), "reference.png")
    assert studio.store.add_image(project, picture(), "renamed.png")["item_id"] == first["item_id"]
    result = import_annotations(
        studio.store,
        project,
        [
            {
                "sha256": first["sha256"],
                "annotation": {
                    "caption": {"long": "visible person", "short": "person"},
                    "tags": ["1girl"],
                },
            }
        ],
    )
    assert result["item_ids"] == [first["item_id"]]
    studio.store.update_image(
        project, first["item_id"], {"caption": {"long": "reviewed"}, "caption_confirmed": True}
    )
    with studio.store.projects.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM studio_caption_revisions").fetchone()[0] == 1
        )
    result = import_annotations(
        studio.store, project, [{"sha256": first["sha256"], "annotation": {"long": "overwrite"}}]
    )
    assert result["errors"]
    assert studio.store.image(project, first["item_id"])["caption"]["long"] == "reviewed"


def workflow():
    return {
        "1": {
            "class_type": "String Literal",
            "_meta": {"title": "前綴"},
            "inputs": {"string": "old style"},
        },
        "2": {
            "class_type": "ImpactWildcardProcessor",
            "_meta": {"title": "正文"},
            "inputs": {"wildcard_text": "old body", "seed": 2, "mode": "populate"},
        },
        "3": {"class_type": "KSampler", "inputs": {"seed": 3, "steps": 20, "cfg": 4.0}},
        "4": {"class_type": "FaceDetailer", "inputs": {"image": ["5", 0]}},
        "5": {"class_type": "VAEDecode", "inputs": {}},
        "6": {"class_type": "SaveImage", "inputs": {"images": ["4", 0]}},
    }


def test_generic_workflow_compile_preserves_original_and_bypasses_image_branch():
    original = workflow()
    recipe = normalize_recipe(
        {
            "body": "new body",
            "prefix": "new prefix",
            "bindings": infer_bindings(original),
            "branches": {"4": False},
        }
    )
    prompt = {
        "prefix": "expanded prefix",
        "body": "expanded body",
        "negative": "",
        "suffix": "",
        "positive": "expanded prefix\n\nexpanded body",
        "seed": 100,
        "text_seed": 200,
    }
    graph = compile_graph(original, recipe, prompt)
    assert graph["1"]["inputs"]["string"] == "expanded prefix"
    assert graph["2"]["inputs"]["seed"] == 200
    assert graph["2"]["inputs"]["mode"] == "fixed"
    assert graph["3"]["inputs"]["seed"] == 100
    assert graph["6"]["inputs"]["images"] == ["5", 0]
    assert "4" in original
    assert original["2"]["inputs"]["wildcard_text"] == "old body"


def test_openai_multi_image_and_negative_prompt(monkeypatch, tmp_path):
    captured = []

    def response(request, **_kwargs):
        captured.append(request)
        return json.dumps({"data": [{"b64_json": base64.b64encode(picture()).decode()}]}).encode()

    monkeypatch.setattr("prompt_hub.studio_providers.read_response", response)
    path = tmp_path / "ref.png"
    path.write_bytes(picture())
    provider = {
        "kind": "openai",
        "model": "gpt-image-1",
        "base_url": "https://example.com/v1",
        "api_key": "test-key",
        "capabilities": {"references": True},
    }
    recipe = normalize_recipe({"backend": "openai", "width": 1024, "height": 1536})
    assert (
        len(
            openai_images(
                provider,
                recipe,
                {"positive": "person", "negative": "text"},
                [("identity", path), ("outfit", path)],
            )
        )
        == 1
    )
    assert captured[0].full_url.endswith("/images/edits")
    assert captured[0].data.count(b'name="image[]"') == 2
    assert b"supplies outfit" in captured[0].data
    assert b"Avoid: text" in captured[0].data
    assert b'"seed"' not in captured[0].data


@pytest.mark.parametrize("mode", ["vibe", "precise", "img2img"])
def test_novelai_reference_protocols(monkeypatch, tmp_path, mode):
    requests = []
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("image.png", picture())

    def response(request, **_kwargs):
        requests.append(request)
        return b"encoded-vibe" if request.full_url.endswith("encode-vibe") else output.getvalue()

    monkeypatch.setattr("prompt_hub.studio_providers.read_response", response)
    path = tmp_path / "reference.png"
    path.write_bytes(picture())
    provider = {
        "kind": "novelai",
        "model": "nai-diffusion-4-5-full",
        "base_url": "https://image.novelai.net",
        "api_key": "test",
        "capabilities": {"references": True},
    }
    recipe = normalize_recipe(
        {
            "backend": "novelai",
            "width": 832,
            "height": 1216,
            "novelai_mode": mode,
            "characters": [{"prompt": "red hair", "negative": "hat", "x": 0.3, "y": 0.5}],
        }
    )
    assert novelai_images(
        provider, recipe, {"positive": "person", "negative": "", "seed": 1}, [("identity", path)]
    )
    body = json.loads(requests[-1].data)
    assert (
        body["parameters"]["v4_prompt"]["caption"]["char_captions"][0]["char_caption"] == "red hair"
    )
    if mode == "vibe":
        assert requests[0].full_url.endswith("/ai/encode-vibe")
        assert body["parameters"]["reference_image_multiple"] == [
            base64.b64encode(b"encoded-vibe").decode()
        ]
    elif mode == "precise":
        assert (
            body["parameters"]["director_reference_descriptions"][0]["caption"]["base_caption"]
            == "character"
        )
    else:
        assert body["action"] == "img2img"


def test_native_moss_export_is_readable_and_versioned(studio, tmp_path):
    dataset_module = pytest.importorskip("kohakugbc_data.dataset")

    project = studio.store.create_project("native export", "moss")
    identifier = project["project_id"]
    studio.store.save_project(
        identifier, {"studio": {**project["studio"], "trigger": "style_test"}}
    )
    image = studio.store.add_image(identifier, picture(), "training.png")
    studio.store.update_image(
        identifier,
        image["item_id"],
        {
            "review": "approved",
            "caption_confirmed": True,
            "caption": {
                "long": "A blue image.",
                "short": "Blue.",
                "tags": ["blue"],
                "regions": [
                    {"name": "center", "caption": "Blue center.", "bbox": [0.1, 0.1, 0.9, 0.9]}
                ],
            },
        },
    )
    result = studio.export(identifier, "gbc")
    archive_path = (
        studio.store.settings.dataset_exports_root
        / "studio"
        / identifier
        / (result["version"] + ".zip")
    )
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(tmp_path / "readback")
        assert "kohakumoss_data.py" in archive.namelist()
        assert json.loads(archive.read("verification.json"))["caption_roundtrip"]
    dataset = dataset_module.GbcDataset(tmp_path / "readback" / "gbc_dataset")
    restored = dataset[image["item_id"]]
    assert restored.image == picture()
    assert restored.meta["style_trigger"] == "style_test"
    assert restored.graph.prompt_dag().to_dict()["vertices"]["image"]["text"] == "A blue image."
    assert studio.exports(identifier)[0]["download_url"] == result["download_url"]


def test_caption_concurrent_update_keeps_the_manual_edit(studio):
    project = studio.store.create_project("captions", "moss")["project_id"]
    image = studio.store.add_image(project, picture(), "image.png")
    studio.store.update_image(project, image["item_id"], {"caption": {"long": "manual edit"}})
    with pytest.raises(StudioError, match="更新"):
        studio.store.update_image(
            project,
            image["item_id"],
            {
                "caption": {"long": "stale model result"},
                "expected_updated_at": image["updated_at"],
            },
        )
    assert studio.store.image(project, image["item_id"])["caption"]["long"] == "manual edit"


def test_pixai_and_gbc_import_preserves_regions_and_tags(studio):
    from prompt_hub.studio_annotations import normalize_annotation  # noqa: PLC0415 - test setup
    from prompt_hub.studio_export import caption_graph  # noqa: PLC0415 - test setup

    graph = caption_graph(
        {
            "long": "A person.",
            "short": "Person.",
            "tags": ["1girl"],
            "regions": [
                {"name": "person", "caption": "A visible person.", "bbox": [0.1, 0.2, 0.8, 0.9]}
            ],
        },
        "a.png",
        (128, 192),
    )
    normalized = normalize_annotation(graph)
    assert normalized["long"] == "A person."
    assert normalized["regions"][0]["bbox"] == [0.1, 0.2, 0.8, 0.9]
    project = studio.store.create_project("import", "moss")["project_id"]
    image = studio.store.add_image(project, picture(), "a.v1.png")
    result = import_annotations(
        studio.store,
        project,
        [
            {"filename": "a.v1.json", "annotation": graph},
            {
                "sha256": image["sha256"],
                "annotation": {"result": {"general": {"1girl": 0.9, "uncertain": 0.1}}},
            },
        ],
    )
    assert not result["errors"]
    caption = studio.store.image(project, image["item_id"])["caption"]
    assert caption["long"] == "A person."
    assert caption["tags"] == ["1girl"]


def test_provider_secrets_are_redacted_and_blank_key_preserves_existing(studio):
    settings = {
        "provider": {
            "kind": "openai",
            "base_url": "https://example.com/v1",
            "model": "gpt-image-1",
            "api_key": "private-placeholder",
            "label": "test",
        }
    }
    public = studio.providers.save(settings)
    identifier = public["providers"][0]["id"]
    assert "private-placeholder" not in json.dumps(public)
    settings["provider"].update({"id": identifier, "api_key": ""})
    studio.providers.save(settings)
    assert studio.providers.require(identifier, "openai")["api_key"] == "private-placeholder"


def test_caption_worker_returns_results_through_its_existing_environment(studio, monkeypatch):
    from prompt_hub.studio_captions import StudioCaptioner  # noqa: PLC0415 - test setup

    project = studio.store.create_project("worker", "moss")["project_id"]
    image = studio.store.add_image(project, picture(), "a.png")
    root = studio.store.root
    executable = root / "python.exe"
    executable.write_bytes(b"test")
    model = root / "pixai"
    model.mkdir()
    studio.providers.save(
        {"caption_worker": {"python": str(executable), "pixai_model": str(model), "device": "cpu"}}
    )

    class Process:
        def __init__(self, *_args, **_kwargs):
            self.stdin = io.BytesIO()
            self.returncode = 0
            output = root / "caption-workers" / "job-test"
            output.mkdir(parents=True, exist_ok=True)
            (output / (image["item_id"] + ".pixai.json")).write_text(
                '{"result":{"general":{"1girl":0.9}}}', encoding="utf-8"
            )

        def poll(self):
            return 0

    class Context:
        job_id = "job-test"

        def update(self, *args):
            pass

    monkeypatch.setattr("prompt_hub.studio_captions.subprocess.Popen", Process)
    captioner = StudioCaptioner(studio.store, None)
    result = captioner.job(
        {"project_id": project, "item_ids": [image["item_id"]], "method": "pixai"}, Context()
    )
    assert result["item_ids"] == [image["item_id"]]
    assert studio.store.image(project, image["item_id"])["caption"]["tags"] == ["1girl"]


def test_api_end_to_end_and_validation(settings, monkeypatch):
    monkeypatch.setattr(BackgroundJobRunner, "start", lambda _self: None)
    with TestClient(create_app(settings)) as client:
        project = client.post(
            "/api/studio/projects", json={"title": "API", "target": "moss"}
        ).json()
        identifier = project["project_id"]
        assert (
            client.put(
                f"/api/studio/projects/{identifier}", json={"studio": {"cfg": "bad"}}
            ).status_code
            == 422
        )
        assert client.post("/api/studio/workflows", content=b"{}").status_code == 422
        imported = client.post(
            "/api/studio/workflows?target=moss", content=json.dumps(workflow())
        ).json()
        assert imported["generic"]
        recipe = {
            **project["studio"],
            "workflow_id": imported["profile_id"],
            "bindings": imported["bindings"],
            "body": "{one|two}",
            "count": 3,
        }
        assert (
            client.put(f"/api/studio/projects/{identifier}", json={"studio": recipe}).status_code
            == 200
        )
        preview = client.post(f"/api/studio/projects/{identifier}/preview", json={}).json()
        first = client.post(
            f"/api/studio/projects/{identifier}/generate",
            json={"preview_id": preview["preview_id"]},
        )
        second = client.post(
            f"/api/studio/projects/{identifier}/generate",
            json={"preview_id": preview["preview_id"]},
        )
        assert first.status_code == 202
        assert first.json() == second.json()
        assert len(first.json()["job_ids"]) == 3
        assert (
            client.get(f"/api/studio/projects/{identifier}").json()["project"]["studio"]["body"]
            == "{one|two}"
        )


def test_all_rendered_buttons_have_explicit_semantics_and_links_have_destinations():
    class Audit(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            if tag == "button":
                assert attributes.get("type") in {"button", "submit", "reset"}
            if tag == "a" and "href" in attributes:
                assert attributes["href"] not in {"", "#"}

    Audit().feed(INDEX_HTML)


def test_home_preserved_and_navigation_uses_unified_creation_gallery_and_datasets():
    assert '<section class="home-page" id="homePage">' in INDEX_HTML
    assert 'id="homeFirstGuide"' in INDEX_HTML
    assert 'class="home-lead"' in INDEX_HTML
    assert 'class="home-guide"' in INDEX_HTML
    for view in (
        "creative",
        "prompts",
        "discover",
        "gallery",
        "characters",
        "datasets",
        "lora",
    ):
        assert f'data-view="{view}"' in INDEX_HTML
    assert 'id="studioProjectsPage" hidden' in INDEX_HTML
    assert 'data-start="projects"' in INDEX_HTML
    navigation = INDEX_HTML.split('<nav class="app-nav"', 1)[1].split("</nav>", 1)[0]
    assert 'data-view="comfy"' not in navigation
    assert 'data-view="projects"' not in navigation
    assert navigation.index('data-view="gallery"') < navigation.index('data-view="prompts"')
    assert 'id="workbenchDatasets"' in INDEX_HTML
    assert 'id="homeDataVersion"' not in INDEX_HTML
    assert "$('#homeDataVersion')" not in INDEX_HTML


def test_dark_palette_uses_the_existing_moss_studio_colors():
    from prompt_hub.web_resources import read_web_asset  # noqa: PLC0415 - test setup

    css = read_web_asset("theme.css")
    dark = css.split('html[data-theme="dark"] {', 1)[1].split("}", 1)[0]
    assert "--ink: #e8e5d9;" in dark
    assert "--paper: #1b1d19;" in dark
    assert "--studio-selected: #d7e455;" in dark
    assert "--studio-action: #9a321f;" in dark
    assert "--studio-border: #68735f;" in dark


def test_workspace_read_recovers_from_transient_windows_file_sharing(monkeypatch, tmp_path):
    from pathlib import Path  # noqa: PLC0415 - test setup

    from prompt_hub.dataset_workspace import _load_json  # noqa: PLC0415 - test setup

    attempts = []

    def read(path, **_kwargs):
        attempts.append(path)
        if len(attempts) < 3:
            msg = "file replacement in progress"
            raise PermissionError(msg)
        return '{"workspace_id":"test"}'

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr("prompt_hub.dataset_workspace.time.sleep", lambda _delay: None)
    assert _load_json(tmp_path / "workspace.json")["workspace_id"] == "test"
    assert len(attempts) == 3


def test_accepted_comfy_job_recovers_without_submitting_again(studio, monkeypatch):
    project = studio.store.create_project("resume", "moss")
    payload = {
        "project_id": project["project_id"],
        "recipe": project["studio"],
        "prompt": {},
        "references": [],
    }
    studio.store.save_execution(
        "job-resume", project["project_id"], payload, "owned-prompt", "accepted"
    )

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def queue_prompt(self, *_args, **_kwargs):
            pytest.fail("Recovered task must use its stored prompt id")

        def history(self, identifier):
            assert identifier == "owned-prompt"
            return {
                "status": {"completed": True},
                "outputs": {"save": {"images": [{"filename": "a.png", "type": "output"}]}},
            }

        def download_output(self, _image):
            return picture()

    class Context:
        job_id = "job-resume"

        def update(self, *args):
            pass

    monkeypatch.setattr("prompt_hub.studio_service.ComfyUIClient", Client)
    result = studio.generation_job(payload, Context())
    assert len(result["item_ids"]) == 1
    assert studio.generation_job(payload, Context()) == result
    assert len(studio.store.images(project["project_id"], "candidate")) == 1


def test_saved_cloud_response_recovers_without_another_api_call(studio, monkeypatch):
    from prompt_hub.studio_store import write_json  # noqa: PLC0415 - test setup

    project = studio.store.create_project("cloud resume", "moss")
    recipe = {**project["studio"], "backend": "openai"}
    payload = {"project_id": project["project_id"], "recipe": recipe, "prompt": {}}
    studio.store.save_execution("job-cloud", project["project_id"], payload, state="submitting")
    write_json(
        studio.store.root / "responses" / "job-cloud.json", [base64.b64encode(picture()).decode()]
    )
    monkeypatch.setattr(
        "prompt_hub.studio_service.openai_images",
        lambda *_args: pytest.fail("Response is already stored"),
    )

    class Context:
        job_id = "job-cloud"

        def update(self, *args):
            pass

    assert len(studio.generation_job(payload, Context())["item_ids"]) == 1
