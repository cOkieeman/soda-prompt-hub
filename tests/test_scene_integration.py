from __future__ import annotations

import json
from copy import deepcopy
from http.client import RemoteDisconnected
from io import BytesIO
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from prompt_hub import scene_routes
from prompt_hub.api import create_app
from prompt_hub.creative import SLOT_ORDER
from prompt_hub.gallery import GalleryStore
from prompt_hub.remote_nodes import RemoteNodeStore
from prompt_hub.scene_planning import (
    REVIEW_SYSTEM,
    SCENE_SYSTEM,
    STYLE_SYSTEM,
    ScenePlanStore,
    build_style_evidence,
)
from prompt_hub.workflow_profiles import RULES, WorkflowProfileStore


def _plan(event):
    return {
        "title_zh": event,
        "event_zh": event,
        "moment_zh": "风吹过时手尚未合拢",
        "intent_zh": "保护希望",
        "camera_zh": "从门内斜看",
        "space_zh": "前门柱中人物远雨路",
        "lighting_zh": "灯火照手",
        "clues_zh": ["衣摆湿透"],
        "warnings": [],
        "canvas": {
            "ratio": "3:4",
            "width": 960,
            "height": 1280,
            "reason_zh": "纵向门框",
            "alternatives": [
                {"ratio": "3:2", "width": 1344, "height": 896, "reason_zh": "横幅展开道路"}
            ],
        },
        "slots": {
            "character": "a fox spirit",
            "outfit": "a wet robe",
            "action": "one hand shields a flame while her eyes follow it",
            "composition": "from inside a doorway",
            "scene": "a shrine path in rain",
            "lighting": "warm light on her hand",
            "style": "ink painting",
        },
        "prompts": {
            "anima": "1girl, ink painting. One hand shields a flame while she watches it.",
            "krea2": "A fox spirit shields a flame with one hand, seen from a doorway.",
        },
    }


def _style():
    return {
        "suggestions": [
            {
                "title_zh": "轻量画风",
                "reason_zh": "尝试柔和上色",
                "loras": [
                    {
                        "lora_id": "paint-lora",
                        "role": "style",
                        "weight": 0.45,
                        "reason_zh": "测试与雨夜环境光的关系",
                    }
                ],
                "notes_zh": [],
                "unknowns_zh": [],
            }
        ],
        "warnings": [],
    }


def _review():
    observed = dict.fromkeys(SLOT_ORDER, "")
    suggested = dict.fromkeys(SLOT_ORDER, "")
    observed["action"] = "holding a lantern"
    suggested["action"] = "one hand shields the flame"
    return {
        "summary_zh": "护灯动作尚未成立",
        "observed_slots": observed,
        "suggested_slots": suggested,
        "strengths": ["暖光明确"],
        "issues": ["手离火苗太远"],
        "improvements": ["明确护火手的位置"],
        "scene_checks": [
            {
                "criterion": "动作目标",
                "planned": "护火",
                "observed": "提灯",
                "status": "partial",
                "suggestion": "手靠近火苗",
            }
        ],
        "reconstructed_prompts": {},
        "safety_warning": "",
    }


@pytest.fixture
def model_calls(monkeypatch):
    calls = []

    def request(**kwargs):
        calls.append(kwargs)
        if kwargs["system_prompt"] == SCENE_SYSTEM:
            return {"plans": [_plan("护住灯火"), _plan("等待归人"), _plan("留下告别")]}
        if kwargs["system_prompt"] == STYLE_SYSTEM:
            return _style()
        assert kwargs["system_prompt"] == REVIEW_SYSTEM
        return _review()

    monkeypatch.setattr("prompt_hub.scene_planning.request_creative_json", request)
    return calls


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


def _project(client):
    response = client.post(
        "/api/creative/projects",
        json={
            "title": "雨夜护灯",
            "brief_zh": "狐娘在风雨中保护灯火",
            "target_profile": "krea2",
            "generation": {"width": 1024, "height": 1024, "seed": 42},
        },
    )
    assert response.status_code == 201
    return response.json()


def _scene(client, project):
    base = f"/api/creative/projects/{project['project_id']}/scene-plans"
    response = client.post(base, json={"model": "test"})
    assert response.status_code == 200
    return base, response.json()["plans"][0]


def _png(*, workflow=False):
    data = BytesIO()
    metadata = PngImagePlugin.PngInfo()
    if workflow:
        prompt = {
            "0": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "krea2.safetensors"},
            },
            "1": {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": "styles/paint.safetensors",
                    "strength_model": 0.6,
                    "strength_clip": 0.6,
                    "model": ["0", 0],
                    "clip": ["0", 1],
                },
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "fox spirit", "clip": ["1", 1]},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "bad anatomy", "clip": ["1", 1]},
            },
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024}},
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                    "seed": 42,
                    "steps": 8,
                },
            },
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["0", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
        }
        metadata.add_text("prompt", json.dumps(prompt))
    Image.new("RGB", (64, 64), "red" if workflow else "blue").save(data, "PNG", pnginfo=metadata)
    return data.getvalue()


def _install_local_catalog_and_workflow(settings):
    remote = RemoteNodeStore(settings.remote_nodes_root)
    remote.initialize()
    remote.import_lora_catalog(
        snapshot_id="style-snapshot",
        worker_id="test-worker",
        source_manager="test",
        items=[
            {
                "lora_id": "paint-lora",
                "name": "Paint",
                "relative_path": "styles/paint.safetensors",
                "model_family": "krea2",
                "metadata": {"role": "style"},
            }
        ],
    )
    profile_id = "krea2-ares-ocmanager"
    workflow = {
        node_id: {"class_type": kind, "inputs": {}}
        for node_id, kind in RULES[profile_id].required_nodes.items()
    }
    workflow["142"]["inputs"] = {"loras": {"__value__": []}, "model": ["123", 0], "clip": ["66", 0]}
    workflow["132"]["inputs"] = {"samples": ["87", 0], "vae": ["65", 0]}
    workflow["87"]["inputs"] = {"model": ["142", 0], "sampler_name": "euler", "scheduler": "simple"}
    raw = json.dumps(workflow).encode()
    store = WorkflowProfileStore(settings.workflow_profiles_root)
    store.import_bytes(profile_id, raw, label="Krea2 test", filename="workflow.json")
    return remote, store, raw


def _ui_apply_request(client, settings, project, kind):
    if kind in {"scene", "scene_branch"}:
        base, plan = _scene(client, project)
        branch = kind == "scene_branch"
        return (
            f"{base}/{plan['plan_id']}/apply",
            {
                "apply_resolution": True,
                "replace_slots": branch,
                "branch": branch,
                "expected_revision": project["revision"],
            },
            "apply_scene_plan",
        )
    _install_local_catalog_and_workflow(settings)
    base = f"/api/creative/projects/{project['project_id']}/style-advice"
    advice = client.post(
        base, json={"model": "test", "workflow_profile_id": "krea2-ares-ocmanager"}
    ).json()
    return (
        f"{base}/{advice['advice_id']}/apply",
        {
            "suggestion_id": advice["suggestions"][0]["suggestion_id"],
            "workflow_profile_id": "krea2-ares-ocmanager",
            "expected_revision": project["revision"],
        },
        "apply_style_advice",
    )


@pytest.mark.parametrize("kind", ["scene", "scene_branch", "style"])
def test_scene_and_style_apply_accept_exact_ui_revision_payload(
    client, settings, model_calls, monkeypatch, kind
):
    project = _project(client)
    url, payload, helper_name = _ui_apply_request(client, settings, project, kind)
    helper = Mock(wraps=getattr(scene_routes, helper_name))
    monkeypatch.setattr(scene_routes, helper_name, helper)
    response = client.post(url, json=payload)
    assert response.status_code == 200
    assert len(model_calls) == 1
    helper.assert_called_once()
    assert "expected_revision" not in helper.call_args.kwargs
    updated = response.json()["project"]
    if kind == "scene_branch":
        assert updated["project_id"] != project["project_id"]
        assert client.get(f"/api/creative/projects/{project['project_id']}").json() == project
    else:
        assert updated["revision"] == project["revision"] + 1
    if kind == "style":
        controls = updated["generation"]["workflow_controls"]["krea2-ares-ocmanager"]
        assert controls["loras"][0]["lora_id"] == "paint-lora"
    else:
        assert updated["generation"]["scene_plan"]["plan_id"]
        assert updated["generation"]["width"] == 960


@pytest.mark.parametrize("kind", ["scene", "scene_branch", "style"])
def test_scene_and_style_apply_reject_stale_ui_revision_before_helper(
    client, settings, model_calls, monkeypatch, kind
):
    project = _project(client)
    url, payload, helper_name = _ui_apply_request(client, settings, project, kind)
    current = client.put(
        f"/api/creative/projects/{project['project_id']}",
        json={"test_notes": "manual feedback written in another window"},
    ).json()
    helper = Mock(side_effect=AssertionError("Stale UI must not reach apply helpers"))
    monkeypatch.setattr(scene_routes, helper_name, helper)
    response = client.post(url, json=payload)
    assert response.status_code == 409
    assert len(model_calls) == 1
    helper.assert_not_called()
    assert client.get(f"/api/creative/projects/{project['project_id']}").json() == current
    assert len(client.get("/api/creative/projects").json()) == 1


def test_create_app_scene_generate_list_apply_compile_and_stale(client, model_calls):
    project = _project(client)
    base, plan = _scene(client, project)
    assert (
        client.get(f"/api/creative/projects/{project['project_id']}").json()["slots"]["action"]
        == ""
    )
    listing = client.get(base).json()
    assert len(listing["plans"]) == 3
    assert not listing["selected_plan_id"]
    response = client.post(f"{base}/{plan['plan_id']}/apply", json={})
    assert response.status_code == 200
    adopted = response.json()["project"]
    compiled = client.get(f"/api/creative/projects/{project['project_id']}/export").json()[
        "outputs"
    ]
    assert compiled["krea2"]["positive"] == plan["prompts"]["krea2"]
    assert compiled["anima"]["positive"] == plan["prompts"]["anima"]
    assert compiled["krea2"]["ready"]
    assert adopted["generation"]["width"] == 960
    listing = client.get(base).json()
    selected = next(item for item in listing["plans"] if item["plan_id"] == plan["plan_id"])
    assert not selected["stale"]
    client.put(f"/api/creative/projects/{project['project_id']}", json={"brief_zh": "改成晴天"})
    assert client.post(f"{base}/{plan['plan_id']}/apply", json={}).status_code == 409
    compiled = client.get(f"/api/creative/projects/{project['project_id']}/export").json()[
        "outputs"
    ]["krea2"]
    assert not compiled["ready"]
    assert compiled["scene_plan_stale"]
    assert model_calls[0]["system_prompt"] == SCENE_SYSTEM


def test_real_style_stores_apply_and_use_saved_workflow_feedback(client, settings, model_calls):
    remote, workflow_store, original = _install_local_catalog_and_workflow(settings)
    project = _project(client)
    work = client.post(
        "/api/gallery/import?kind=work&filename=my-result.png", content=_png(workflow=True)
    ).json()
    client.put(
        f"/api/gallery/assets/{work['asset_id']}",
        json={"note": "上色满意,动作略僵", "project_id": project["project_id"]},
    )
    base = f"/api/creative/projects/{project['project_id']}/style-advice"
    response = client.post(
        base, json={"model": "test", "workflow_profile_id": "krea2-ares-ocmanager"}
    )
    assert response.status_code == 200
    advice = response.json()
    evidence = model_calls[-1]["context"]["recorded_outcomes"]
    assert len(evidence) == 1
    assert evidence[0]["lora_records"][0]["lora_id"] == "paint-lora"
    assert evidence[0]["lora_records"][0]["strength_model"] == 0.6
    assert "上色满意" in evidence[0]["user_note"]
    assert "实际执行" in evidence[0]["evidence_limit"]
    assert "relative_path" not in json.dumps(evidence)
    assert advice["suggestions"][0]["evidence_zh"]
    assert "未经生成验证" in advice["suggestions"][0]["loras"][0]["weight_basis"]
    assert (
        not client.get(f"/api/creative/projects/{project['project_id']}")
        .json()["generation"]
        .get("workflow_controls")
    )
    response = client.post(
        f"{base}/{advice['advice_id']}/apply",
        json={
            "suggestion_id": advice["suggestions"][0]["suggestion_id"],
            "workflow_profile_id": "krea2-ares-ocmanager",
        },
    )
    assert response.status_code == 200
    controls = response.json()["project"]["generation"]["workflow_controls"]["krea2-ares-ocmanager"]
    assert controls["loras"] == [{"lora_id": "paint-lora", "strength": 0.45, "clip_strength": 0.45}]
    assert (
        workflow_store.root / "krea2-ares-ocmanager" / "source-workflow.json"
    ).read_bytes() == original
    assert not (workflow_store.root / "krea2-ares-ocmanager" / "runs").exists()
    assert not list(remote.task_records_root.glob("**/*.json"))


def test_scene_and_style_references_are_filtered_by_user_purpose(client, settings, model_calls):
    _install_local_catalog_and_workflow(settings)
    project = _project(client)
    asset = client.post(
        "/api/gallery/import?kind=reference&filename=teacher.png", content=_png()
    ).json()
    assert (
        client.post(
            f"/api/gallery/assets/{asset['asset_id']}/reference/{project['project_id']}",
            json={"purpose": "composition"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/api/gallery/assets/{asset['asset_id']}/analysis",
            json={
                "analysis": {
                    "summary_zh": "不要照搬的画风摘要",
                    "observed_slots": {
                        "composition": "doorway framing",
                        "style": "flat ukiyo-e",
                        "lighting": "neon lighting",
                    },
                }
            },
        ).status_code
        == 200
    )
    base = f"/api/creative/projects/{project['project_id']}"
    body = {"model": "test", "reference_asset_ids": [asset["asset_id"]]}
    assert client.post(f"{base}/scene-plans", json=body).status_code == 200
    reference = model_calls[-1]["context"]["references"][0]
    assert reference["purpose"] == "composition"
    assert reference["analysis"]["observed_slots"] == {"composition": "doorway framing"}
    assert "style" not in reference["analysis"]
    assert "summary_zh" not in reference["analysis"]
    assert (
        client.post(
            f"{base}/style-advice", json={**body, "workflow_profile_id": "krea2-ares-ocmanager"}
        ).status_code
        == 200
    )
    assert model_calls[-1]["context"]["references"][0]["analysis"] == reference["analysis"]
    assert model_calls[-1]["context"]["recorded_outcomes"] == []


def test_scene_review_confirmation_preserves_observation_and_suggestion_in_branch(
    client, model_calls
):
    project = _project(client)
    base, plan = _scene(client, project)
    assert client.post(f"{base}/{plan['plan_id']}/apply", json={}).status_code == 200
    asset = client.post(
        f"/api/creative/projects/{project['project_id']}/results?filename=output.png",
        content=_png(),
    ).json()["asset"]
    response = client.post(
        f"/api/creative/projects/{project['project_id']}/scene-review/{asset['asset_id']}",
        json={"model": "test"},
    )
    assert response.status_code == 200
    analysis = response.json()
    assert analysis["observed_slots"]["action"] == "holding a lantern"
    assert analysis["suggested_slots"]["action"] == "one hand shields the flame"
    client.put(
        f"/api/creative/projects/{project['project_id']}", json={"slot_locks": {"style": True}}
    )
    analysis["suggested_slots"]["style"] = "watercolor"
    project_before = client.get(f"/api/creative/projects/{project['project_id']}").json()
    assert not project_before["lineage"]
    branch = client.post(
        f"/api/creative/projects/{project['project_id']}/results/{asset['asset_id']}/branch",
        json={"analysis": analysis},
    ).json()
    assert (
        branch["lineage"]["review"]["observed_slots"]
        != branch["lineage"]["review"]["suggested_slots"]
    )
    assert branch["lineage"]["review"]["scene_checks"][0]["status"] == "partial"
    assert branch["slots"]["action"] == analysis["suggested_slots"]["action"]
    assert branch["slots"]["style"] == project_before["slots"]["style"]
    assert branch["slot_locks"]["style"]
    assert "scene_plan" not in branch["generation"]
    assert "result_assets" not in branch["generation"]
    compiled = client.get(f"/api/creative/projects/{branch['project_id']}/export").json()["outputs"]
    assert analysis["suggested_slots"]["action"] in compiled["krea2"]["positive"]
    assert compiled["krea2"]["positive"] != plan["prompts"]["krea2"]
    assert client.get(f"/api/creative/projects/{project['project_id']}").json() == project_before
    assert model_calls[-1]["system_prompt"] == REVIEW_SYSTEM


def test_style_evidence_never_guesses_from_reference_or_missing_metadata():
    candidates = [{"lora_id": "paint-lora", "relative_path": "styles/paint.safetensors"}]
    reference = {
        "kind": "reference",
        "availability": "online",
        "metadata": {
            "generation_evidence": {
                "status": "saved_workflow",
                "scope": "output_connected",
                "loras": [{"name": "paint"}],
            }
        },
    }
    plain = {"kind": "work", "availability": "online", "title": "paint-lora", "metadata": {}}
    assert build_style_evidence([reference, plain], candidates) == []
    own = {**deepcopy(reference), "kind": "work"}
    assert build_style_evidence([own], candidates)[0]["lora_records"][0]["lora_id"] == "paint-lora"
    ambiguous = [
        *candidates,
        {"lora_id": "other-paint", "relative_path": "other/paint.safetensors"},
    ]
    assert build_style_evidence([own], ambiguous) == []


@pytest.mark.parametrize("kind", ["scene", "style"])
def test_relevant_reference_changed_during_generation_is_rejected_without_saving(
    client,
    settings,
    monkeypatch,
    kind,
):
    if kind == "style":
        _install_local_catalog_and_workflow(settings)
    project = _project(client)
    asset = client.post(
        "/api/gallery/import?kind=reference&filename=reference.png", content=_png()
    ).json()
    gallery = GalleryStore(settings)
    gallery.confirm_analysis(asset["asset_id"], {"observed_slots": {"composition": "old doorway"}})
    client.post(
        f"/api/gallery/assets/{asset['asset_id']}/reference/{project['project_id']}",
        json={"purpose": "composition"},
    )

    def update_during_request(**_):
        gallery.confirm_analysis(
            asset["asset_id"], {"observed_slots": {"composition": "new landscape"}}
        )
        return {"plans": [_plan("护灯"), _plan("等候")]} if kind == "scene" else _style()

    monkeypatch.setattr("prompt_hub.scene_planning.request_creative_json", update_during_request)
    endpoint = "scene-plans" if kind == "scene" else "style-advice"
    body = {"model": "test", "reference_asset_ids": [asset["asset_id"]]}
    if kind == "style":
        body["workflow_profile_id"] = "krea2-ares-ocmanager"
    response = client.post(f"/api/creative/projects/{project['project_id']}/{endpoint}", json=body)
    assert response.status_code == 409
    store = ScenePlanStore(settings.database_path)
    assert store.list_plans(project["project_id"]) == []
    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM creative_style_advice").fetchone()[0] == 0


def test_reference_snapshot_apply_rejects_related_change_but_ignores_other_data(
    client,
    settings,
    model_calls,
):
    project = _project(client)
    asset = client.post(
        "/api/gallery/import?kind=reference&filename=related.png", content=_png()
    ).json()
    other = client.post(
        "/api/gallery/import?kind=reference&filename=other.png", content=_png(workflow=True)
    ).json()
    gallery = GalleryStore(settings)
    gallery.confirm_analysis(
        asset["asset_id"], {"observed_slots": {"composition": "doorway", "style": "ink"}}
    )
    client.post(
        f"/api/gallery/assets/{asset['asset_id']}/reference/{project['project_id']}",
        json={"purpose": "composition"},
    )
    base = f"/api/creative/projects/{project['project_id']}/scene-plans"
    response = client.post(base, json={"model": "test", "reference_asset_ids": [asset["asset_id"]]})
    assert response.status_code == 200
    plan = response.json()["plans"][0]
    gallery.confirm_analysis(other["asset_id"], {"observed_slots": {"style": "oil"}})
    gallery.confirm_analysis(
        asset["asset_id"], {"observed_slots": {"composition": "doorway", "style": "NEW oil"}}
    )
    assert (
        client.post(
            f"{base}/{plan['plan_id']}/apply", json={"branch": True, "replace_slots": True}
        ).status_code
        == 200
    )
    gallery.confirm_analysis(
        asset["asset_id"], {"observed_slots": {"composition": "NEW close-up", "style": "oil"}}
    )
    assert (
        client.post(
            f"{base}/{plan['plan_id']}/apply", json={"branch": True, "replace_slots": True}
        ).status_code
        == 409
    )
    assert model_calls[-1]["context"]["references"][0]["analysis"]["observed_slots"] == {
        "composition": "doorway"
    }


def test_style_snapshot_rejects_reference_changes_at_apply(client, settings, model_calls):
    _install_local_catalog_and_workflow(settings)
    project = _project(client)
    asset = client.post(
        "/api/gallery/import?kind=reference&filename=ref.png", content=_png()
    ).json()
    base = f"/api/creative/projects/{project['project_id']}/style-advice"
    response = client.post(
        base,
        json={
            "model": "test",
            "reference_asset_ids": [asset["asset_id"]],
            "workflow_profile_id": "krea2-ares-ocmanager",
        },
    )
    assert response.status_code == 200
    advice = response.json()
    GalleryStore(settings).update_asset(asset["asset_id"], {"note": "new preference"})
    response = client.post(
        f"{base}/{advice['advice_id']}/apply",
        json={
            "suggestion_id": advice["suggestions"][0]["suggestion_id"],
            "workflow_profile_id": "krea2-ares-ocmanager",
        },
    )
    assert response.status_code == 409
    assert model_calls[-1]["context"]["references"][0]["note"] == ""


@pytest.mark.parametrize("endpoint", ["scene-plans", "style-advice"])
def test_network_disconnect_is_503_without_saved_preview(client, settings, monkeypatch, endpoint):
    if endpoint == "style-advice":
        _install_local_catalog_and_workflow(settings)
    project = _project(client)
    monkeypatch.setattr(
        "prompt_hub.local_model.urlopen", Mock(side_effect=RemoteDisconnected("connection closed"))
    )
    body = {"model": "local-test"}
    if endpoint == "style-advice":
        body["workflow_profile_id"] = "krea2-ares-ocmanager"
    response = client.post(f"/api/creative/projects/{project['project_id']}/{endpoint}", json=body)
    assert response.status_code == 503
    assert "无法连接LM Studio" in response.json()["detail"]
    with ScenePlanStore(settings.database_path).connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM creative_scene_plans").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM creative_style_advice").fetchone()[0] == 0
