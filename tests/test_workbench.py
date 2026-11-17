from __future__ import annotations

import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.agent_workbench import AgentWorkbench
from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobStore
from prompt_hub.creative import CreativeStore
from prompt_hub.dataset_workspace import DatasetWorkspaceStore
from prompt_hub.gallery import GalleryStore
from prompt_hub.model_connections import ModelConnectionStore
from prompt_hub.online_gallery import (
    OnlineGallery,
    matches,
    permutation_index,
    public_url,
    request_headers,
)
from prompt_hub.studio_providers import ImageProviderStore, novelai_images
from prompt_hub.studio_service import StudioService
from prompt_hub.studio_store import StudioError, StudioStore, normalize_recipe
from prompt_hub.workflow_profiles import WorkflowProfileStore


def picture(color="blue"):
    output = io.BytesIO()
    Image.new("RGB", (128, 192), color).save(output, "PNG")
    return output.getvalue()


def test_donmai_requests_use_the_launcher_client_identity():
    for host in ("danbooru.donmai.us", "safebooru.donmai.us", "cdn.donmai.us"):
        headers = request_headers(f"https://{host}/posts.json")
        assert headers["User-Agent"] == "NAI-Launcher/1.0"
        assert headers["Referer"] == f"https://{host}/"


def test_online_image_headers_preserve_source_referers_and_cookie():
    assert (
        request_headers("https://ai-img.10118899.xyz/img/test.webp")["Referer"]
        == "https://aitag.win/"
    )
    assert request_headers("https://aitag.win/api/work/1")["Referer"] == "https://aitag.win/"
    gelbooru = request_headers("https://img4.gelbooru.com/images/example.jpg")
    assert gelbooru["Referer"] == "https://gelbooru.com/"
    assert gelbooru["Cookie"] == "fringeBenefits=yup"


def test_online_media_proxy_caches_verified_images_and_rejects_other_hosts(store, monkeypatch):
    import prompt_hub.online_gallery as module  # noqa: PLC0415 - test setup

    requests = []
    monkeypatch.setattr(module, "public_url", lambda url: url)
    monkeypatch.setattr(
        module, "fetch_bytes", lambda url, _maximum: requests.append(url) or picture()
    )
    gallery = OnlineGallery(store.settings.library_root, store.gallery)
    url = "https://ai-img.10118899.xyz/image.webp"
    path, media_type = gallery.media(url)
    assert path.is_file()
    assert media_type == "image/png"
    assert gallery.media(url) == (path, media_type)
    assert requests == [url]
    with pytest.raises(StudioError, match="已接入"):
        gallery.media("https://unrelated.example/image.png")
    monkeypatch.setattr(module, "fetch_bytes", lambda _url, _maximum: b"<html>access denied</html>")
    with pytest.raises(StudioError, match="可讀取的圖片"):
        gallery.media("https://assets.quicktagcloud.com/invalid.jpg")


def test_safebooru_hostname_failure_uses_same_database_with_general_rating(store, monkeypatch):
    from urllib.error import HTTPError  # noqa: PLC0415 - test setup
    from urllib.parse import parse_qs, urlsplit  # noqa: PLC0415 - test setup

    import prompt_hub.online_gallery as module  # noqa: PLC0415 - test setup

    requests = []

    def response(url):
        requests.append(url)
        if urlsplit(url).hostname == "safebooru.donmai.us":
            msg = "HTTP 403"
            raise StudioError(msg) from HTTPError(url, 403, "Forbidden", {}, None)
        return [{"id": 123, "rating": "g"}]

    monkeypatch.setattr(module, "fetch_json", response)
    gallery = OnlineGallery(store.settings.library_root, store.gallery)
    result = gallery.cached(
        "https://safebooru.donmai.us/posts.json?tags=landscape+rating:e&limit=36"
    )
    assert result == [{"id": 123, "rating": "g"}]
    assert urlsplit(requests[1]).hostname == "danbooru.donmai.us"
    assert parse_qs(urlsplit(requests[1]).query)["tags"] == ["landscape rating:g"]


@pytest.fixture
def store(settings):
    projects = CreativeStore(settings.database_path)
    projects.initialize()
    gallery = GalleryStore(settings)
    gallery.initialize()
    BackgroundJobStore(settings.database_path).initialize()
    result = StudioStore(settings, projects, gallery)
    result.initialize()
    return result


@pytest.mark.parametrize(("source", "query"), [("danbooru", "rating:g"), ("safebooru", "")])
def test_popular_results_apply_rating_filters_even_when_upstream_ignores_tags(
    store, monkeypatch, source, query
):
    gallery = OnlineGallery(store.settings.library_root, store.gallery)
    monkeypatch.setattr(
        gallery,
        "cached",
        lambda *_args: [
            {"id": 1, "rating": "g", "tag_string": "landscape"},
            {"id": 2, "rating": "e", "tag_string": "landscape"},
        ],
    )
    result = gallery.query(source, query, "popular", 1, 1, "day", "", "")
    assert [item["id"] for item in result["items"]] == ["1"]


def test_generation_drafts_are_atomic_isolated_and_not_datasets(store):
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: store.generation_draft("comfyui")["project_id"], range(8)))
    assert len(set(ids)) == 1
    assert store.generation_draft("novelai")["project_id"] != ids[0]
    assert (
        store.generation_draft("agent-novelai")["project_id"]
        != store.generation_draft("novelai")["project_id"]
    )
    dataset = store.create_project("dataset", "moss")
    assert [p["project_id"] for p in store.list_projects()] == [dataset["project_id"]]


def test_generated_provenance_survives_dataset_assignment(store):
    draft = store.generation_draft("comfyui")
    provenance = {
        "job_id": "job-1",
        "backend": "comfyui",
        "recipe": {"body": "original"},
        "prompt": {"body": "resolved", "positive": "resolved"},
        "request": {"graph": {"1": {"inputs": {"text": "resolved"}}}},
    }
    image = store.add_image(draft["project_id"], picture(), "result.png", provenance=provenance)
    dataset = store.create_project("target", "anima")
    store.add_image(
        dataset["project_id"], picture(), "result.png", provenance={"source": "gallery"}
    )
    asset = store.gallery.require_asset(image["asset_id"])
    assert asset["hub_generation"] == provenance
    assert store.gallery.list_assets(backend="comfyui")["total"] == 1
    assert store.gallery.list_assets(backend="novelai")["total"] == 0
    second = {
        **provenance,
        "job_id": "job-2",
        "backend": "openai",
        "recipe": {"creation_origin": "agent"},
    }
    store.gallery.record_generation(image["asset_id"], second)
    assert store.gallery.list_assets(backend="comfyui")["total"] == 1
    assert store.gallery.list_assets(backend="agent")["total"] == 1
    assert len(store.gallery.require_asset(image["asset_id"])["hub_generations"]) == 2


def test_add_gallery_assets_repeated_submission_is_idempotent(settings):
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/studio/projects", json={"title": "A", "target": "moss"}).json()
        asset = client.post(
            "/api/gallery/import?filename=blue.png&kind=work",
            content=picture(),
            headers={"Content-Type": "image/png"},
        ).json()
        endpoint = "/api/workbench/datasets/" + project["project_id"] + "/assets"
        first = client.post(endpoint, json={"asset_ids": [asset["asset_id"], asset["asset_id"]]})
        second = client.post(endpoint, json={"asset_ids": [asset["asset_id"]]})
        assert first.status_code == second.status_code == 200
        assert first.json()["added"] == 1
        assert second.json()["added"] == 0
        assert (
            len(client.get("/api/studio/projects/" + project["project_id"]).json()["images"]) == 1
        )


def test_invalid_asset_batch_does_not_partially_add_images(settings):
    with TestClient(create_app(settings)) as client:
        project = client.post("/api/studio/projects", json={"title": "A", "target": "moss"}).json()
        asset = client.post("/api/gallery/import?filename=blue.png", content=picture()).json()
        response = client.post(
            "/api/workbench/datasets/" + project["project_id"] + "/assets",
            json={"asset_ids": [asset["asset_id"], "missing"]},
        )
        assert response.status_code == 404
        assert client.get("/api/studio/projects/" + project["project_id"]).json()["images"] == []


def test_local_styles_sync_preserves_marks_and_uses_complete_ordered_previews(settings, tmp_path):
    root = tmp_path / "styles"
    node = tmp_path / "node"
    previews = root / "catalogs" / "krea2" / "previews"
    previews.mkdir(parents=True)
    (node / "styles").mkdir(parents=True)
    (root / "catalogs.json").write_text("{}", encoding="utf-8")
    (root / "custom.json").write_text("[]", encoding="utf-8")
    document = [{"id": "sample/style", "name": "sample", "nl": "style text", "negative": "bad"}]
    source = node / "styles" / "sample.json"
    source.write_text(json.dumps(document), encoding="utf-8")
    for name in ["one.jpg", "two.jpg"]:
        Image.new("RGB", (40, 60), "blue").save(previews / name)
    (previews / "manifest.json").write_text(
        json.dumps(
            {
                "sample_style": {
                    "name": "sample",
                    "cover": "two.jpg",
                    "shots": [{"file": "one.jpg"}, {"file": "two.jpg"}],
                }
            }
        ),
        encoding="utf-8",
    )
    with TestClient(create_app(settings)) as client:
        assert (
            client.put(
                "/api/local-styles/settings", json={"root": str(root), "node_root": str(node)}
            ).status_code
            == 200
        )
        assert client.post("/api/local-styles/sync").json()["entries"] == 1
        entry = client.get("/api/search?source_id=neons-local-krea2").json()["results"][0]
        assert len(entry["visuals"]) == 2
        assert entry["visuals"][0]["original_url"].endswith("two.jpg")
        assert client.get(entry["visuals"][0]["original_url"]).status_code == 200
        client.put(
            "/api/marks",
            json={
                "source_id": entry["source_id"],
                "external_id": entry["external_id"],
                "favorite": True,
                "note": "keep",
            },
        )
        document[0]["nl"] = "updated text"
        source.write_text(json.dumps(document), encoding="utf-8")
        client.post("/api/local-styles/sync")
        updated = client.get("/api/search?source_id=neons-local-krea2").json()["results"][0]
        assert updated["favorite"]
        assert updated["user_note"] == "keep"
        assert updated["content"] == "updated text"


@pytest.mark.parametrize("length", [1, 2, 3, 17, 99, 1000])
def test_launcher_feistel_traversal_covers_every_entry_once(length):
    indices = [permutation_index(i, length, 1234) for i in range(length)]
    assert sorted(indices) == list(range(length))
    assert indices == [permutation_index(i, length, 1234) for i in range(length)]


@pytest.mark.parametrize(
    ("query", "expected"),
    [("blue_hair -hat", True), ("blue_hair hat", False), ("-blue_hair", False), ("rating:g", True)],
)
def test_online_client_filter_respects_positive_negative_and_rating(query, expected):
    assert matches({"tags": ["blue_hair"], "rating": "g"}, query) == expected


def test_online_remote_urls_reject_local_network_and_unsafe_protocol(monkeypatch):
    monkeypatch.setattr(
        "prompt_hub.online_gallery.socket.getaddrinfo",
        lambda *_: [(None, None, None, None, ("127.0.0.1", 443))],
    )
    with pytest.raises(StudioError):
        public_url("https://example.test/image.png")
    with pytest.raises(StudioError):
        public_url("file:///C:/private.png")


def test_known_online_sources_work_with_local_fake_ip_proxy(monkeypatch):
    monkeypatch.setattr(
        "prompt_hub.online_gallery.socket.getaddrinfo",
        lambda *_: [(None, None, None, None, ("198.18.0.94", 443))],
    )
    assert public_url("https://aitag.win/api/config").startswith("https://aitag.win")
    with pytest.raises(StudioError):
        public_url("https://untrusted.example/image.png")


def test_agent_image_proposal_is_idempotent_across_reload(settings, store):
    providers = ImageProviderStore(settings.library_root)
    providers.save(
        {
            "provider": {
                "id": "image-test",
                "kind": "openai",
                "label": "test",
                "model": "gpt-image-1",
                "base_url": "https://example.test",
                "api_key": "test",
            }
        }
    )
    service = StudioService(store, providers, WorkflowProfileStore(settings.workflow_profiles_root))
    agent = AgentWorkbench(settings.library_root, ModelConnectionStore(settings), store)
    chat = agent.create()
    chat["messages"] = [
        {"role": "user", "content": "generate"},
        {"role": "assistant", "content": "", "proposals": [{"prompt": "a portrait"}]},
    ]
    from prompt_hub.studio_store import write_json  # noqa: PLC0415 - test setup

    write_json(agent.path(chat["id"]), chat)
    first = agent.prepare_image(
        service, chat["id"], {"message_index": 1, "proposal_index": 0, "provider_id": "image-test"}
    )
    restored = AgentWorkbench(settings.library_root, ModelConnectionStore(settings), store)
    second = restored.prepare_image(
        service, chat["id"], {"message_index": 1, "proposal_index": 0, "provider_id": "image-test"}
    )
    assert first == second
    with store.projects.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM background_jobs").fetchone()[0] == 1


def test_existing_dataset_import_preserves_sidecars_and_can_resume(settings, tmp_path):
    source = tmp_path / "existing"
    source.mkdir()
    (source / "one.png").write_bytes(picture())
    (source / "one.txt").write_text("original caption", encoding="utf-8")
    workspaces = DatasetWorkspaceStore(settings)
    workspaces.initialize()
    workspace = workspaces.register(source, name="existing")
    with TestClient(create_app(settings)) as client:
        first = client.post(
            "/api/workbench/workspaces/" + workspace["workspace_id"] + "/import",
            json={"target": "anima"},
        ).json()
        second = client.post(
            "/api/workbench/workspaces/" + workspace["workspace_id"] + "/import",
            json={"target": "anima"},
        ).json()
        assert first["project_id"] == second["project_id"]
        images = client.get("/api/studio/projects/" + first["project_id"]).json()["images"]
        assert len(images) == 1
        assert images[0]["caption"]["long"] == "original caption"
        assert images[0]["caption_confirmed"] is False
    assert (source / "one.txt").read_text(encoding="utf-8") == "original caption"


def test_online_popular_capabilities_are_enforced(store, tmp_path):
    online = OnlineGallery(tmp_path, store.gallery)
    for source in ("gelbooru", "quicktagcloud"):
        with pytest.raises(StudioError):
            online.query(source, "", "popular", 1, 1)


@pytest.fixture
def capture_novelai(monkeypatch):
    requests = []

    def respond(request, **_):
        requests.append(json.loads(request.data))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("image.png", picture())
        return stream.getvalue()

    monkeypatch.setattr("prompt_hub.studio_providers.read_response", respond)
    return requests


@pytest.mark.parametrize("model", ["nai-diffusion-4-5-full", "nai-diffusion-5-full"])
@pytest.mark.parametrize("mode", ["ai", "custom"])
def test_character_position_mode_reaches_both_novelai_request_flags(capture_novelai, model, mode):
    recipe = normalize_recipe(
        {
            "backend": "novelai",
            "character_position_mode": mode,
            "characters": [
                {"name": "Left", "prompt": "girl, coat", "negative": "text", "x": 0.2, "y": 0.7},
                {"prompt": "boy", "enabled": False},
            ],
        }
    )
    novelai_images(
        {"kind": "novelai", "model": model, "base_url": "https://example.test", "api_key": "test"},
        recipe,
        {"positive": "garden", "negative": "blur", "seed": 12},
        [],
    )
    parameters = capture_novelai[0]["parameters"]
    assert parameters["use_coords"] is (mode == "custom")
    assert parameters["v4_prompt"]["use_coords"] is (mode == "custom")
    assert len(parameters["characterPrompts"]) == 1
    assert parameters["characterPrompts"][0]["uc"] == "text"
    assert parameters["characterPrompts"][0]["center"] == {"x": 0.2, "y": 0.7}


def test_existing_character_coordinates_keep_custom_mode():
    legacy = normalize_recipe({"characters": [{"prompt": "girl", "x": 0.2, "y": 0.8}]})
    assert legacy["character_position_mode"] == "custom"
    assert normalize_recipe({})["character_position_mode"] == "ai"
    with pytest.raises(StudioError, match="位置模式"):
        normalize_recipe({"character_position_mode": []})


def test_saved_character_library_is_searchable_and_repeat_save_updates_one_entry(settings):
    with TestClient(create_app(settings)) as client:
        character = {
            "id": "character-qa",
            "name": "Character QA",
            "prompt": "girl, coat",
            "negative": "text",
            "gender": "female",
        }
        first = client.post("/api/workbench/characters/library", json=character)
        assert first.status_code == 200, first.text
        character["prompt"] = "girl, blue coat"
        assert client.post("/api/workbench/characters/library", json=character).status_code == 200
        found = client.get("/api/search", params={"source_id": first.json()["source_id"]}).json()[
            "results"
        ]
        assert len(found) == 1
        assert found[0]["content"] == "girl, blue coat"
        assert found[0]["negative_content"] == "text"
        assert found[0]["metadata"]["gender"] == "female"


def test_precise_references_override_vibe_and_invert_fidelity(tmp_path, capture_novelai):
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    first.write_bytes(picture())
    second.write_bytes(picture("red"))
    recipe = normalize_recipe({"backend": "novelai", "novelai_mode": "mixed"})
    recipe["_reference_options"] = [
        {"mode": "vibe", "strength": 0.1},
        {"mode": "precise", "strength": 0.8, "fidelity": 0.7},
    ]
    novelai_images(
        {
            "kind": "novelai",
            "model": "nai-diffusion-4-5-full",
            "base_url": "https://example.test",
            "api_key": "test",
        },
        recipe,
        {"positive": "test", "negative": "", "seed": 12},
        [("style", first), ("identity", second)],
    )
    params = capture_novelai[0]["parameters"]
    assert "reference_image_multiple" not in params
    assert len(params["director_reference_images"]) == 1
    assert params["director_reference_strength_values"] == [0.8]
    assert params["director_reference_secondary_strength_values"] == pytest.approx([0.3])
    assert "director_reference_images" not in recipe["_effective_request"]["parameters"]
    assert "test" not in json.dumps(recipe["_effective_request"].get("Authorization", {}))


def test_novelai_outpaint_sends_infill_and_expanded_size(tmp_path, capture_novelai):
    image = tmp_path / "source.png"
    image.write_bytes(picture())
    recipe = normalize_recipe(
        {
            "backend": "novelai",
            "novelai_mode": "outpaint",
            "outpaint": {"left": 64, "top": 0, "right": 0, "bottom": 0},
        }
    )
    novelai_images(
        {
            "kind": "novelai",
            "model": "nai-diffusion-4-5-full",
            "base_url": "https://example.test",
            "api_key": "test",
        },
        recipe,
        {"positive": "test", "negative": "", "seed": 12},
        [("identity", image)],
    )
    request = capture_novelai[0]
    assert request["action"] == "infill"
    assert request["model"].endswith("-inpainting")
    assert (request["parameters"]["width"], request["parameters"]["height"]) == (192, 192)
    assert "mask" in request["parameters"]
    assert "mask" not in recipe["_effective_request"]["parameters"]


def test_empty_inpaint_mask_is_rejected_before_paid_request(tmp_path, capture_novelai):
    image, mask = tmp_path / "source.png", tmp_path / "mask.png"
    image.write_bytes(picture())
    mask.write_bytes(picture("black"))
    with pytest.raises(StudioError, match="遮罩為空"):
        novelai_images(
            {
                "kind": "novelai",
                "model": "nai-diffusion-4-5-full",
                "base_url": "https://example.test",
                "api_key": "test",
            },
            normalize_recipe({"backend": "novelai", "novelai_mode": "infill"}),
            {"positive": "test", "negative": "", "seed": 12},
            [("identity", image), ("mask", mask)],
        )
    assert capture_novelai == []


def test_agent_installs_skill_scripts_and_reports_invalid_dsh_entry(settings, store):
    agent = AgentWorkbench(settings.library_root, ModelConnectionStore(settings), store)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("skill/SKILL.md", "---\nname: prompt-helper\n---\nUse concise prompts.")
        z.writestr("skill/tool.py", "raise RuntimeError('must not execute')")
    package = agent.install(archive.getvalue(), "skill.zip")
    assert package["status"] == "ready"
    assert package["tool_files"] == ["tool.py"]
    plugin = agent.install(b"ctx.tools.register({});", "dsh.js")
    assert plugin["status"] == "runtime_error"
    assert plugin["runtime_error"]


def test_agent_model_error_keeps_message_and_retry_does_not_duplicate(settings, store, monkeypatch):
    models = ModelConnectionStore(settings)
    endpoint = models.save_endpoint(
        {
            "label": "test",
            "provider": "openai_compatible",
            "base_url": "https://example.test/v1",
            "api_key": "private-value",
        }
    )
    models.save_endpoint_models(endpoint["id"], [{"name": "test-model", "enabled": True}])
    agent = AgentWorkbench(settings.library_root, models, store)
    chat = agent.create()
    model = models.list_model_options()[0]["id"]

    def fail(*_, **__):
        msg = "private-value"
        raise OSError(msg)

    monkeypatch.setattr("prompt_hub.agent_workbench.urlopen", fail)
    with pytest.raises(StudioError):
        agent.chat(chat["id"], {"text": "test", "model": model})
    assert len(agent.read(chat["id"])["messages"]) == 1
    assert "private-value" not in json.dumps(agent.read(chat["id"]))
    response = io.BytesIO(json.dumps({"choices": [{"message": {"content": "done"}}]}).encode())
    monkeypatch.setattr("prompt_hub.agent_workbench.urlopen", lambda *_, **__: response)
    restored = agent.chat(chat["id"], {"text": "test", "model": model, "retry": True})
    assert [m["role"] for m in restored["messages"]] == ["user", "assistant"]
    assert not restored["pending"]
