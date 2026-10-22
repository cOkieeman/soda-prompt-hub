from __future__ import annotations

import hashlib
import json
import re
from io import BytesIO
from threading import RLock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from soda_storyboard.production.state import PageState

from prompt_hub.comfy_results import ComfyResultStore
from prompt_hub.storyboard_generation import StoryboardGenerationError, StoryboardGenerationService
from prompt_hub.storyboard_routes import create_storyboard_router
from prompt_hub.storyboard_safety import local_path
from prompt_hub.workflow_profiles import RULES, WorkflowProfileError, WorkflowProfileStore
from prompt_hub.workflow_routes import create_workflow_router


class FakeStoryboardStore:
    def __init__(self, root):
        self.root = root
        self.lock = RLock()
        self.project = root / "projects" / "book"
        (self.project / "pages").mkdir(parents=True)
        (self.project / "characters").mkdir()
        (self.project / "project.json").write_text(
            json.dumps({"format": "soda-storyboard-project-v1", "name": "Test"}),
            encoding="utf-8",
        )
        (self.project / "pages" / "page.json").write_text(
            json.dumps(
                {
                    "format": "soda-storyboard-page-v1",
                    "id": "page",
                    "canvas_width": 512,
                    "canvas_height": 768,
                    "panels": [],
                }
            ),
            encoding="utf-8",
        )

    def project_path(self, project_id):
        candidate = local_path(self.root, f"projects/{project_id}")
        if not candidate.is_dir():
            message = "missing project"
            raise ValueError(message)
        return candidate

    def project_lock(self, _project_id):
        return self.lock

    def get_page(self, project_id, page_id):
        path = local_path(self.project_path(project_id), f"pages/{page_id}.json")
        return {"page": json.loads(path.read_text(encoding="utf-8")), "version": "fake-version"}

    def compile_page(self, project_id, page_id):
        local_path(self.project_path(project_id), f"pages/{page_id}.json")
        return {
            "moss": {"summary": {"caption": "a comic page"}, "items": []},
            "width": 512,
            "height": 768,
            "lora": None,
            "warnings": [],
        }


class FakeRemote:
    def __init__(self, root):
        self.root = root
        self.root.mkdir()
        self.writable = True
        self.tasks = {}
        self.outputs = []
        self.verified = True
        self.receipts = []

    def diagnostics(self, _node_id):
        return {"bridge_root": str(self.root), "bridge_writable": self.writable}

    def submit_task(self, _node_id, payload):
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}", payload["workspace_id"])
        task_id = f"task-{len(self.tasks)}"
        task = {"task_id": task_id, **payload}
        self.tasks[task_id] = task
        return task

    def get_task(self, _node_id, task_id):
        return {"local_task": self.tasks[task_id]}

    def verify_returned_task(self, _node_id, _task_id):
        return {"verified": self.verified, "outputs": self.outputs}

    def mark_task_received(self, _node_id, task_id, *, receipt_kind):
        self.receipts.append((task_id, receipt_kind))
        return {"received_at": "2026-10-23T00:00:00Z"}

    def complete(self, task_id):
        stream = BytesIO()
        Image.new("RGB", (32, 48), "orange").save(stream, format="PNG")
        raw = stream.getvalue()
        relative = f"inbox/{task_id}/result.png"
        path = self.root / relative
        path.parent.mkdir(parents=True)
        path.write_bytes(raw)
        self.outputs = [
            {
                "kind": "image",
                "relative_path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
            }
        ]


@pytest.fixture
def generation(tmp_path):
    store = FakeStoryboardStore(tmp_path / "storyboard")
    profiles = WorkflowProfileStore(tmp_path / "workflows")
    profiles.initialize()
    remote = FakeRemote(tmp_path / "bridge")
    results = ComfyResultStore(tmp_path / "results")
    results.initialize()
    service = StoryboardGenerationService(store, profiles, remote, results)
    return service, store, profiles, remote, results


def _v2_workflow():
    workflow = {
        identifier: {"class_type": class_type, "inputs": {}}
        for identifier, class_type in RULES["moss-soda-v2"].required_nodes.items()
    }
    workflow["620"]["inputs"] = {"string": "{}"}
    workflow["622"]["inputs"] = {"any_02": ["620", 0]}
    workflow["77"]["inputs"] = {
        "loras": {"__value__": [{"name": "old", "active": True}]},
        "text": "old lora",
    }
    workflow["152:225"]["inputs"] = {"any_02": ["148:139", 0]}
    workflow["152:343"]["inputs"] = {"any_02": ["148:139", 0]}
    return workflow


def test_minimal_submission_uses_worker_contract_and_core_graph(generation, monkeypatch):
    service, store, _profiles, remote, _results = generation
    observed = {}

    def fake_graph(prompt, **options):
        observed.update(prompt=prompt, options=options)
        return {"6": {"class_type": "CLIPTextEncode", "inputs": {"text": ""}}}

    monkeypatch.setattr("prompt_hub.storyboard_generation.minimal_graph", fake_graph)
    outcome = service.submit("book", "page", options={"seed": 42, "negative": "blur"})
    task = remote.tasks[outcome["task"]["task_id"]]
    package_path = remote.root / task["payload"]["generation_package"]
    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert observed["options"]["seed"] == 42
    assert observed["options"]["width"] == 512
    assert json.loads(observed["prompt"])["summary"]["caption"] == "a comic page"
    assert package["api_prompt"]["6"]["inputs"]["text"] == "blur"
    assert task["task_type"] == "comfyui_generate"
    assert task["payload"]["workflow_id"] == package["workflow_id"]
    assert task["manifest"][0]["sha256"] == hashlib.sha256(package_path.read_bytes()).hexdigest()
    assert list((store.root / "generation-runs").glob("*.json"))
    assert not (store.project / "generation-runs").exists()


def test_returned_images_join_review_store_and_core_selection(generation):
    service, store, _profiles, remote, results = generation
    submitted = service.submit("book", "page", options={"seed": 44})
    task_id = submitted["task"]["task_id"]
    remote.complete(task_id)
    outcome = service.import_results("book", "page", task_id)
    result_id = outcome["results"][0]["result"]["result_id"]
    assert outcome["image_count"] == 1
    assert outcome["results"][0]["result_id"] == result_id
    assert outcome["results"][0]["thumbnail_url"] == results.get(result_id)["thumbnail_url"]
    assert results.get(result_id)["disposition"] == "unreviewed"
    assert results.get(result_id)["associations"][0]["kind"] == "storyboard-page"
    assert results.get(result_id)["origins"][0]["import_batch_id"] == task_id
    state = PageState(store.project, "page")
    assert "selected_render" not in state.production
    render = state.production["renders"][0]
    assert render["seed"] == 44
    with Image.open(store.project / render["path"]) as image:
        assert image.size == (512, 768)
    assert service.list_results("book", "page")[0]["selected"] is False
    selected = service.select_result("book", "page", result_id)
    assert selected["result"]["disposition"] == "candidate"
    assert PageState(store.project, "page").production["selected_render"] == render["path"]
    assert service.list_results("book", "page")[0]["selected"] is True
    service.import_results("book", "page", task_id)
    assert len(PageState(store.project, "page").production["renders"]) == 1
    assert remote.receipts[-1] == (task_id, "comfyui_images")


def test_v2_rule_requires_json_pass_through_and_core_maps_nodes(generation):
    service, _store, profiles, remote, _results = generation
    workflow = _v2_workflow()
    wrong = json.loads(json.dumps(workflow))
    wrong["622"]["inputs"]["any_01"] = ["620", 0]
    with pytest.raises(WorkflowProfileError, match="JSON 直通"):
        profiles.import_bytes(
            "moss-soda-v2", json.dumps(wrong).encode(), label="Wrong", filename="wrong.json"
        )
    profiles.import_bytes(
        "moss-soda-v2", json.dumps(workflow).encode(), label="MOSS", filename="moss.json"
    )
    submitted = service.submit(
        "book",
        "page",
        options={
            "backend": "moss-soda-v2",
            "preset": "final",
            "seed": 5,
            "negative": "blur",
            "model_overrides": {"diffusion_model": "MOSS/custom.safetensors"},
        },
    )
    task = submitted["task"]
    graph = json.loads(
        (remote.root / task["payload"]["generation_package"]).read_text(encoding="utf-8")
    )["api_prompt"]
    assert json.loads(graph["620"]["inputs"]["string"])["summary"]["caption"] == "a comic page"
    assert json.loads(graph["150"]["inputs"]["resolution_json"])["height"] == 768
    assert graph["84"]["inputs"]["seed"] == 5
    assert graph["75"]["inputs"]["string"] == "blur"
    assert graph["135:111"]["inputs"]["unet_name"] == "MOSS/custom.safetensors"
    assert graph["135:105"]["inputs"]["int"] == 50
    assert graph["77"]["inputs"]["loras"] == {"__value__": []}
    assert graph["81"]["inputs"]["path"] == "PromptHub/storyboard"


@pytest.mark.parametrize(
    "options",
    [
        {"backend": "unknown"},
        {"workflow_profile_id": "other"},
        {"preset": "unknown"},
        {"seed": -1},
        {"seed": True},
        {"negative": 1},
        {"model_overrides": []},
        {"model_overrides": {"diffusion_model": "../outside.safetensors"}},
        {"model_overrides": {"unknown": "test.safetensors"}},
        {"model": "C:/outside.safetensors"},
        {"priority": 101},
    ],
)
def test_invalid_generation_options_do_not_submit(generation, options):
    service, _store, _profiles, remote, _results = generation
    with pytest.raises(StoryboardGenerationError):
        service.submit("book", "page", options=options)
    assert remote.tasks == {}


def test_unwritable_bridge_and_page_escape_do_not_submit(generation):
    service, _store, _profiles, remote, _results = generation
    remote.writable = False
    with pytest.raises(StoryboardGenerationError, match="不可写"):
        service.submit("book", "page")
    with pytest.raises(ValueError, match="相对路径"):
        service.submit("../outside", "page")
    with pytest.raises(ValueError, match="相对路径"):
        service.submit("book", "../../outside")
    assert remote.tasks == {}


@pytest.mark.parametrize("failure", ["integrity", "hash", "escape", "run", "empty"])
def test_invalid_worker_returns_do_not_register(generation, failure):
    service, store, _profiles, remote, results = generation
    task_id = service.submit("book", "page")["task"]["task_id"]
    remote.complete(task_id)
    if failure == "integrity":
        remote.verified = False
    elif failure == "hash":
        remote.outputs[0]["sha256"] = "0" * 64
    elif failure == "escape":
        remote.outputs[0]["relative_path"] = "../../outside.png"
    elif failure == "run":
        remote.tasks[task_id]["run_id"] = "wrong-run"
    else:
        remote.outputs = []
    with pytest.raises(ValueError, match=r"校验|哈希|相对路径|不一致|尚未返回"):
        service.import_results("book", "page", task_id)
    assert not PageState(store.project, "page").production.get("renders")
    assert results.list_results() == []
    assert remote.receipts == []


def test_page_task_ownership_and_unregistered_selection(generation):
    service, _store, _profiles, _remote, _results = generation
    task_id = service.submit("book", "page")["task"]["task_id"]
    with pytest.raises(StoryboardGenerationError, match="不属于"):
        service.import_results("book", "other", task_id)
    with pytest.raises(StoryboardGenerationError, match="不存在"):
        service.import_results("book", "page", "task-missing")
    with pytest.raises(StoryboardGenerationError, match="尚未登记"):
        service.select_result("book", "page", "random-result")


def test_latest_task_can_be_restored_after_browser_refresh(generation):
    service, _store, _profiles, _remote, _results = generation
    assert service.last_task("book", "page") is None
    first = service.submit("book", "page")["task"]
    second = service.submit("book", "page")["task"]
    assert first["task_id"] != second["task_id"]
    assert service.last_task("book", "page") == {
        "node_id": "compute-5060ti",
        "task_id": second["task_id"],
    }


def test_page_http_recovers_task_and_refreshes_flat_review_results(generation):
    service, store, _profiles, remote, _results = generation
    task_id = service.submit("book", "page")["task"]["task_id"]
    remote.complete(task_id)
    app = FastAPI()
    app.include_router(create_storyboard_router(store, None, None, service))
    url = "/api/storyboard/projects/book/pages/page"
    with TestClient(app) as client:
        recovered = client.get(url).json()["last_task"]
        response = client.post(url + "/results/refresh", json=recovered)
        assert response.status_code == 200, response.text
        result = response.json()["results"][0]
        assert result["result_id"]
        assert result["thumbnail_url"].startswith("/comfy-results/")
        refreshed = client.get(url).json()
    assert refreshed["results"][0]["result_id"] == result["result_id"]


def test_minimal_model_overrides_are_forwarded(generation):
    service, _store, _profiles, remote, _results = generation
    task = service.submit(
        "book",
        "page",
        options={
            "model": "base",
            "model_overrides": {
                "diffusion_model": "moss.safetensors",
                "text_encoder": "clip.safetensors",
                "vae": "vae.safetensors",
            },
        },
    )["task"]
    package = json.loads(
        (remote.root / task["payload"]["generation_package"]).read_text(encoding="utf-8")
    )
    assert package["api_prompt"]["1"]["inputs"]["unet_name"] == "moss.safetensors"
    assert package["api_prompt"]["2"]["inputs"]["clip_name"] == "clip.safetensors"
    assert package["api_prompt"]["3"]["inputs"]["vae_name"] == "vae.safetensors"


def test_unicode_page_identifiers_have_worker_safe_workspace_ids(generation):
    service, store, _profiles, _remote, _results = generation
    raw = json.loads((store.project / "pages" / "page.json").read_text(encoding="utf-8"))
    raw["id"] = "第1页"
    (store.project / "pages" / "第1页.json").write_text(json.dumps(raw), encoding="utf-8")
    task = service.submit("book", "第1页")["task"]
    assert task["workspace_id"].startswith("storyboard-")
    assert "第" not in task["workspace_id"]


def test_character_lora_path_comes_from_core_policy(generation, monkeypatch):
    service, _store, _profiles, remote, _results = generation

    def fake_policy(_page, _characters):
        return {"character_id": "oc", "path": "characters/oc.safetensors", "strength": 0.75}

    monkeypatch.setattr("prompt_hub.storyboard_generation.select_lora", fake_policy)
    task = service.submit("book", "page")["task"]
    graph = json.loads(
        (remote.root / task["payload"]["generation_package"]).read_text(encoding="utf-8")
    )["api_prompt"]
    assert graph["lora"]["inputs"]["lora_name"] == "characters/oc.safetensors"
    assert graph["lora"]["inputs"]["strength_model"] == 0.75
    assert (
        len([node for node in graph.values() if node["class_type"].startswith("LoraLoader")]) == 1
    )


def test_v2_missing_profile_and_changed_source_fail_closed(generation):
    service, _store, profiles, _remote, _results = generation
    with pytest.raises(WorkflowProfileError, match="尚未导入"):
        service.submit("book", "page", options={"backend": "moss-soda-v2"})
    profiles.import_bytes(
        "moss-soda-v2", json.dumps(_v2_workflow()).encode(), label="MOSS", filename="moss.json"
    )
    source = profiles.root / "moss-soda-v2" / "source-workflow.json"
    source.write_text(json.dumps(_v2_workflow()) + "\n", encoding="utf-8")
    with pytest.raises(WorkflowProfileError, match="哈希"):
        service.submit("book", "page", options={"backend": "moss-soda-v2"})


def test_generic_workflow_compiler_requires_storyboard_compilation(generation):
    _service, _store, profiles, _remote, _results = generation
    profiles.import_bytes(
        "moss-soda-v2", json.dumps(_v2_workflow()).encode(), label="MOSS", filename="moss.json"
    )
    with pytest.raises(WorkflowProfileError, match="compile_moss_package"):
        profiles.compile_package("moss-soda-v2", run_id="test-run", positive="a regular prompt")


@pytest.mark.parametrize("payload", [{"project_id": "creative"}, {"use_source_prompt": True}])
def test_generic_workflow_http_rejects_moss_before_creative_compiler(generation, payload):
    _service, _store, profiles, _remote, _results = generation
    profiles.import_bytes(
        "moss-soda-v2", json.dumps(_v2_workflow()).encode(), label="MOSS", filename="moss.json"
    )
    app = FastAPI()
    app.include_router(create_workflow_router(None, profiles, None, None, None))
    with TestClient(app) as client:
        response = client.post("/api/workflow-profiles/moss-soda-v2/tasks", json=payload)
    assert response.status_code == 422
    assert "分镜页面" in response.json()["detail"]
