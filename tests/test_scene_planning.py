from __future__ import annotations

import json
from copy import deepcopy
from email.message import Message
from http.client import BadStatusLine, RemoteDisconnected
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub import local_model
from prompt_hub.creative import (
    SLOT_ORDER,
    CreativeStore,
    apply_iteration_suggestions,
    apply_result_review,
    compile_prompt,
    iteration_context,
    next_iteration_values,
    scene_input_fingerprint,
)
from prompt_hub.local_model import (
    MAX_CREATIVE_CONTEXT_BYTES,
    LocalModelError,
    _request_json,
    request_creative_json,
)
from prompt_hub.scene_planning import (
    STYLE_SYSTEM,
    ScenePlanError,
    ScenePlanStore,
    apply_scene_plan,
    apply_style_advice,
    build_style_evidence,
    generate_scene_plans,
    generate_scene_review,
    generate_style_advice,
    normalize_scene_plan,
    normalize_style_advice,
)
from prompt_hub.scene_routes import create_scene_router
from prompt_hub.workflow_profiles import RULES, WorkflowProfileError, WorkflowProfileStore


def raw_plan(event="护住灯火"):
    return {
        "title_zh": event,
        "event_zh": event,
        "moment_zh": "风吹过时手尚未合拢",
        "intent_zh": "保护微小希望",
        "camera_zh": "从门内斜看",
        "space_zh": "近门框中人物远雨路",
        "lighting_zh": "灯火照在手上",
        "clues_zh": ["衣摆湿透"],
        "warnings": [],
        "canvas": {
            "ratio": "3:4",
            "width": 960,
            "height": 1280,
            "reason_zh": "竖向门框与人物呼应",
            "alternatives": [
                {
                    "ratio": "3:2",
                    "width": 1344,
                    "height": 896,
                    "reason_zh": "横幅留出雨路,人物靠左",
                }
            ],
        },
        "slots": {
            "character": "a fox spirit",
            "outfit": "a wet robe",
            "action": "one hand shields the flame while her eyes follow it",
            "composition": "seen obliquely from inside a doorway",
            "scene": "a rain-soaked shrine path",
            "lighting": "warm light on her hand",
            "style": "flat ink painting",
        },
        "prompts": {
            "anima": "1girl, ink painting. One hand shields the flame while she watches it.",
            "krea2": "Seen from a doorway, a fox spirit shields a flame with one hand.",
        },
    }


def project_values():
    return {
        "brief_zh": "雨夜狐娘护灯",
        "target_profile": "krea2",
        "slots": {},
        "generation": {"width": 1024, "height": 1024, "seed": 7},
    }


def stored_plan(project):
    return {
        **normalize_scene_plan(raw_plan(), project=project),
        "source_fingerprint": scene_input_fingerprint(project),
    }


def catalog_lora(lora_id="lora-1", family="krea2", role=""):
    return {
        "lora_id": lora_id,
        "name": "Artist style",
        "model_family": family,
        "relative_path": f"styles/{lora_id}.safetensors",
        "metadata": {"role": role},
    }


def style_raw(lora_id="lora-1", weight=0.45):
    return {
        "suggestions": [
            {
                "title_zh": "轻量画风",
                "reason_zh": "尝试柔和上色",
                "loras": [
                    {
                        "lora_id": lora_id,
                        "role": "character",
                        "weight": weight,
                        "reason_zh": "待测试对场景光线的影响",
                    }
                ],
                "notes_zh": [],
                "unknowns_zh": [],
            }
        ],
        "warnings": [],
    }


def advice_for(project, *, family="krea2"):
    advice = normalize_style_advice(
        style_raw(), candidates=[catalog_lora(family=family)], family="krea2"
    )
    advice["source_fingerprint"] = scene_input_fingerprint(project)
    advice["workflow_profile_id"] = "krea2-ares-ocmanager"
    advice["workflow_sha256"] = "abc"
    return advice


def test_style_evidence_keeps_candidate_warnings_bounded_in_model_context(monkeypatch):
    candidates = [catalog_lora()]
    candidate_warning = "条件分支无法从保存记录确定, 列出的分支仅为候选。"
    asset = {
        "kind": "work",
        "availability": "online",
        "metadata": {
            "generation_evidence": {
                "status": "saved_workflow",
                "scope": "output_connected",
                "loras": [{"name": "lora-1", "strength_model": 0.7}],
                "warnings": [candidate_warning, *["未知节点" * 200 for _ in range(12)]],
            }
        },
    }
    outcomes = build_style_evidence([asset], candidates)
    request = Mock(return_value=style_raw())
    monkeypatch.setattr("prompt_hub.scene_planning.request_creative_json", request)
    generate_style_advice(
        project_values(),
        model="local",
        goal_zh="雨夜画风",
        candidates=candidates,
        recorded_outcomes=outcomes,
    )
    warnings = request.call_args.kwargs["context"]["recorded_outcomes"][0]["evidence_warnings"]
    assert warnings[0] == candidate_warning
    assert len(warnings) == 8
    assert all(len(item) <= 500 for item in warnings)
    assert request.call_args.kwargs["system_prompt"] == STYLE_SYSTEM
    assert "候选连接不能视为实际用过" in STYLE_SYSTEM
    assert "不能据此判断 LoRA 有效" in STYLE_SYSTEM


@pytest.mark.parametrize("warnings", [None, "bad warnings", {"bad": "mapping"}])
def test_style_evidence_ignores_malformed_warning_containers(warnings):
    asset = {
        "kind": "work",
        "availability": "online",
        "metadata": {
            "generation_evidence": {
                "status": "saved_api_prompt",
                "scope": "output_connected",
                "loras": [{"name": "lora-1"}],
                "warnings": warnings,
            }
        },
    }
    assert build_style_evidence([asset], [catalog_lora()])[0]["evidence_warnings"] == []


@pytest.mark.parametrize("weight", [10**400, float("nan"), float("inf"), True])
def test_style_evidence_invalid_weights_do_not_raise_or_reach_model(weight):
    asset = {
        "kind": "work",
        "availability": "online",
        "metadata": {
            "generation_evidence": {
                "status": "saved_workflow",
                "scope": "output_connected",
                "loras": [{"name": "lora-1", "strength_model": weight, "strength_clip": weight}],
            }
        },
    }
    record = build_style_evidence([asset], [catalog_lora()])[0]["lora_records"][0]
    assert record["strength_model"] is None
    assert record["strength_clip"] is None


def services(settings):
    creative = CreativeStore(settings.database_path)
    creative.initialize()
    store = ScenePlanStore(settings.database_path)
    store.initialize()
    remote = Mock()
    remote.get_lora.side_effect = catalog_lora
    remote.search_loras.return_value = [catalog_lora()]
    workflow = Mock()
    workflow.get_profile.return_value = {
        "profile_id": "krea2-ares-ocmanager",
        "model_family": "krea2",
        "source_sha256": "abc",
        "controls": {"additional_loras": True, "max_additional_loras": 4, "default_loras": []},
    }
    gallery = Mock()
    gallery.get_asset.return_value = None
    gallery.list_assets.return_value = {"items": []}
    gallery.resolve_asset_path.return_value = None
    app = FastAPI()
    app.include_router(
        create_scene_router(settings, store, creative, remote, workflow, gallery, Mock())
    )
    return SimpleNamespace(
        creative=creative,
        store=store,
        remote=remote,
        workflow=workflow,
        gallery=gallery,
        client=TestClient(app),
    )


def test_scene_preview_store_is_independent_and_does_not_apply(settings, monkeypatch):
    svc = services(settings)
    project = svc.creative.create_project(project_values())
    monkeypatch.setattr(
        "prompt_hub.scene_planning.request_creative_json",
        lambda **_: {"plans": [raw_plan(), raw_plan("等待归人"), raw_plan("留下告别")]},
    )
    response = svc.client.post(
        f"/api/creative/projects/{project['project_id']}/scene-plans", json={"model": "local"}
    )
    assert response.status_code == 200
    assert len(response.json()["plans"]) == 3
    assert svc.creative.get_project(project["project_id"]) == project
    plans = svc.store.list_plans(project["project_id"])
    assert len(plans) == 3
    assert plans[0]["source_fingerprint"] == scene_input_fingerprint(project)
    listing = svc.client.get(f"/api/creative/projects/{project['project_id']}/scene-plans").json()
    assert listing["selected_plan_id"] == ""
    assert not listing["plans"][0]["stale"]
    svc.store.initialize()
    assert len(svc.store.list_plans(project["project_id"])) == 3


def test_scene_adoption_preserves_locks_and_existing_slots_and_old_prompt(settings):
    svc = services(settings)
    project = svc.creative.create_project(
        {
            **project_values(),
            "slots": {"character": "my fox", "outfit": "a blue coat"},
            "slot_locks": {"character": True},
        }
    )
    raw = raw_plan()
    raw["slots"]["character"] = "my fox"
    raw["prompts"] = {key: "my fox. " + text for key, text in raw["prompts"].items()}
    plan = normalize_scene_plan(raw, project=project)
    svc.store.save_plans(project, [plan])
    response = svc.client.post(
        f"/api/creative/projects/{project['project_id']}/scene-plans/{plan['plan_id']}/apply",
        json={},
    )
    assert response.status_code == 200
    adopted = response.json()["project"]
    assert adopted["slots"]["outfit"] == "a blue coat"
    assert adopted["slots"]["character"] == "my fox"
    assert adopted["generation"]["width"] == 960
    assert not adopted["generation"]["scene_plan"]["prompt_usable"]
    assert compile_prompt(adopted)["positive"] != plan["prompts"]["krea2"]
    assert response.json()["warnings"]


def test_branch_can_replace_unlocked_slots_without_changing_parent(settings):
    svc = services(settings)
    project = svc.creative.create_project({**project_values(), "slots": {"outfit": "old clothes"}})
    plan = normalize_scene_plan(raw_plan(), project=project)
    svc.store.save_plans(project, [plan])
    url = f"/api/creative/projects/{project['project_id']}/scene-plans/{plan['plan_id']}/apply"
    assert svc.client.post(url, json={"replace_slots": True}).status_code == 409
    response = svc.client.post(url, json={"replace_slots": True, "branch": True})
    assert response.status_code == 200
    child = response.json()["project"]
    assert child["project_id"] != project["project_id"]
    assert child["slots"]["outfit"] == "a wet robe"
    assert child["lineage"]["parent_project_id"] == project["project_id"]
    assert svc.creative.get_project(project["project_id"]) == project
    compiled = compile_prompt(child)
    assert compiled["ready"]
    assert compiled["positive"] == plan["prompts"]["krea2"]
    assert not any("中文创作想法未自动拼入" in warning for warning in compiled["warnings"])


def test_scene_compile_preserves_relationships_and_rejects_stale_prompt():
    project = project_values()
    plan = stored_plan(project)
    values, _ = apply_scene_plan(project, plan)
    assert "One hand shields" in compile_prompt(values, "anima")["positive"]
    values["slots"]["action"] = "standing still"
    compiled = compile_prompt(values)
    assert not compiled["ready"]
    assert compiled["scene_plan_stale"]
    assert "standing still" in compiled["positive"]
    assert compiled["positive"] != plan["prompts"]["krea2"]
    with pytest.raises(ScenePlanError, match="过期"):
        apply_scene_plan(values, plan)


def test_scene_fingerprint_ignores_results_and_seed_but_tracks_controls():
    project = project_values()
    original = scene_input_fingerprint(project)
    project["generation"].update({"seed": 123, "result_assets": [{"asset_id": "new"}]})
    assert scene_input_fingerprint(project) == original
    project["generation"]["workflow_controls"] = {"krea2-ares-ocmanager": {"loras": []}}
    assert scene_input_fingerprint(project) != original


@pytest.mark.parametrize(
    "change",
    [
        {
            "canvas": {
                "ratio": "16:9",
                "width": 960,
                "height": 1280,
                "reason_zh": "x",
                "alternatives": [],
            }
        },
        {
            "canvas": {
                "ratio": "1:1",
                "width": True,
                "height": 1024,
                "reason_zh": "x",
                "alternatives": [],
            }
        },
        {
            "canvas": {
                "ratio": "1:1",
                "width": 4096,
                "height": 4096,
                "reason_zh": "x",
                "alternatives": [],
            }
        },
        {"prompts": {"anima": "中文", "krea2": "English"}},
        {"event_zh": []},
        {"clues_zh": "not-an-array"},
        {"slots": {"action": "holding"}},
    ],
)
def test_scene_model_output_has_strict_structure(change):
    value = {**raw_plan(), **change}
    with pytest.raises(ScenePlanError):
        normalize_scene_plan(value, project=project_values())


def test_locked_slot_cannot_be_rewritten_and_locked_empty_is_supported():
    project = {
        **project_values(),
        "slots": {"character": "my character"},
        "slot_locks": {"character": True},
    }
    with pytest.raises(ScenePlanError, match="锁定"):
        normalize_scene_plan(raw_plan(), project=project)
    project["slot_locks"] = {"style": True}
    raw = raw_plan()
    raw["slots"]["style"] = ""
    assert normalize_scene_plan(raw, project=project)["slots"]["style"] == ""


def test_scene_canvas_lock_is_enforced(monkeypatch):
    monkeypatch.setattr(
        "prompt_hub.scene_planning.request_creative_json",
        lambda **_: {"plans": [raw_plan(), raw_plan("等候")]},
    )
    with pytest.raises(ScenePlanError, match="锁定的画幅"):
        generate_scene_plans(project_values(), model="local", canvas_locked=True)
    with pytest.raises(ScenePlanError, match="整数"):
        generate_scene_plans(project_values(), model="local", width=1001)


def test_changed_project_during_model_request_does_not_store_suggestions(settings, monkeypatch):
    svc = services(settings)
    project = svc.creative.create_project(project_values())

    def concurrent_change(**_):
        svc.creative.update_project(project["project_id"], {"brief_zh": "晴天"})
        return {"plans": [raw_plan(), raw_plan("等候")]}

    monkeypatch.setattr("prompt_hub.scene_planning.request_creative_json", concurrent_change)
    response = svc.client.post(
        f"/api/creative/projects/{project['project_id']}/scene-plans", json={"model": "local"}
    )
    assert response.status_code == 409
    assert svc.store.list_plans(project["project_id"]) == []


def test_model_error_does_not_store_or_apply(settings, monkeypatch):
    svc = services(settings)
    project = svc.creative.create_project(project_values())
    monkeypatch.setattr(
        "prompt_hub.scene_planning.request_creative_json",
        Mock(side_effect=LocalModelError("offline")),
    )
    response = svc.client.post(
        f"/api/creative/projects/{project['project_id']}/scene-plans", json={"model": "local"}
    )
    assert response.status_code == 503
    assert svc.store.list_plans(project["project_id"]) == []
    assert svc.creative.get_project(project["project_id"]) == project


def test_style_cannot_invent_local_id_family_or_tested_weight():
    with pytest.raises(ScenePlanError, match="清单之外"):
        normalize_style_advice(style_raw("imaginary"), candidates=[catalog_lora()], family="krea2")
    with pytest.raises(ScenePlanError, match="不兼容"):
        normalize_style_advice(
            style_raw(), candidates=[catalog_lora(family="anima")], family="krea2"
        )
    advice = normalize_style_advice(
        style_raw(), candidates=[catalog_lora(family="unknown")], family="krea2"
    )
    lora = advice["suggestions"][0]["loras"][0]
    assert lora["role"] == "unknown"
    assert lora["compatibility"] == "unknown"
    assert "未经生成验证" in lora["weight_basis"]
    assert len(advice["suggestions"][0]["unknowns_zh"]) == 2


@pytest.mark.parametrize("weight", [True, "0.5", float("inf"), float("nan"), 3, -3])
def test_style_weights_reject_non_finite_or_unbounded_values(weight):
    with pytest.raises(ScenePlanError, match="权重"):
        normalize_style_advice(
            style_raw(weight=weight), candidates=[catalog_lora()], family="krea2"
        )


def test_style_apply_uses_native_controls_and_preserves_existing_choices(settings):
    svc = services(settings)
    project = svc.creative.create_project(project_values())
    advice = advice_for(project)
    values, warnings = apply_style_advice(
        project,
        advice,
        suggestion_id=advice["suggestions"][0]["suggestion_id"],
        profile_id="krea2-ares-ocmanager",
        remote_store=svc.remote,
        workflow_store=svc.workflow,
    )
    controls = values["generation"]["workflow_controls"]["krea2-ares-ocmanager"]
    assert controls["loras"] == [{"lora_id": "lora-1", "strength": 0.45, "clip_strength": 0.45}]
    assert values["generation"]["style_advice"]["weight_status"] == "untested"
    assert project["generation"] == {"width": 1024, "height": 1024, "seed": 7}
    assert svc.workflow.compile_package.call_args.kwargs["additional_loras"][0]["name"] == "lora-1"
    assert warnings


def test_default_lora_capacity_and_changed_family_block_adoption(settings):
    svc = services(settings)
    project = svc.creative.create_project(project_values())
    advice = advice_for(project)
    profile = svc.workflow.get_profile.return_value
    profile["controls"]["default_loras"] = [{"name": f"default-{i}"} for i in range(4)]
    values, warnings = apply_style_advice(
        project,
        advice,
        suggestion_id=advice["suggestions"][0]["suggestion_id"],
        profile_id="krea2-ares-ocmanager",
        remote_store=svc.remote,
        workflow_store=svc.workflow,
    )
    assert values["generation"]["workflow_controls"]
    assert any("默认 LoRA" in warning for warning in warnings)
    profile["controls"]["default_loras"] = []
    svc.remote.get_lora.side_effect = lambda _: catalog_lora(family="anima")
    with pytest.raises(ScenePlanError, match="不兼容"):
        apply_style_advice(
            project,
            advice,
            suggestion_id=advice["suggestions"][0]["suggestion_id"],
            profile_id="krea2-ares-ocmanager",
            remote_store=svc.remote,
            workflow_store=svc.workflow,
        )


def test_style_route_saves_preview_only_and_explicit_apply(settings, monkeypatch):
    svc = services(settings)
    project = svc.creative.create_project(project_values())
    monkeypatch.setattr("prompt_hub.scene_planning.request_creative_json", lambda **_: style_raw())
    base = f"/api/creative/projects/{project['project_id']}/style-advice"
    response = svc.client.post(
        base, json={"model": "local", "workflow_profile_id": "krea2-ares-ocmanager"}
    )
    assert response.status_code == 200
    assert svc.creative.get_project(project["project_id"]) == project
    advice = response.json()
    assert (
        svc.store.get_advice(project["project_id"], advice["advice_id"])["advice_id"]
        == advice["advice_id"]
    )
    response = svc.client.post(
        f"{base}/{advice['advice_id']}/apply",
        json={
            "workflow_profile_id": "krea2-ares-ocmanager",
            "suggestion_id": advice["suggestions"][0]["suggestion_id"],
        },
    )
    assert response.status_code == 200
    assert response.json()["project"]["generation"]["workflow_controls"]


def test_new_review_keeps_observations_separate_and_legacy_still_works():
    project = {**project_values(), "project_id": "project-parent"}
    observed = dict.fromkeys(SLOT_ORDER, "")
    suggested = dict.fromkeys(SLOT_ORDER, "")
    observed["action"] = "looking at viewer"
    suggested["action"] = "looking at the flame"
    review = {
        "observed_slots": observed,
        "suggested_slots": suggested,
        "scene_checks": [{"criterion": "视线", "status": "missing"}],
    }
    applied = apply_result_review(project, review, fill_empty_slots=True)
    assert applied["slots"]["action"] == "looking at the flame"
    child = next_iteration_values(project, {"asset_id": "asset-1"}, review)
    assert child["lineage"]["review"]["observed_slots"]["action"] == "looking at viewer"
    assert iteration_context(child, project)["changes"][2]["suggested"] == "looking at the flame"
    assert apply_iteration_suggestions(child)["slots"]["action"] == "looking at the flame"
    legacy = {"observed_slots": observed}
    assert (
        apply_result_review(project, legacy, fill_empty_slots=True)["slots"]["action"]
        == "looking at viewer"
    )
    empty_suggestion = {
        "observed_slots": observed,
        "suggested_slots": dict.fromkeys(SLOT_ORDER, ""),
    }
    assert (
        apply_result_review(project, empty_suggestion, fill_empty_slots=True)["slots"]["action"]
        == ""
    )


def test_scene_review_validates_status_and_returns_both_slot_sets(tmp_path, monkeypatch):
    values, _ = apply_scene_plan(project_values(), stored_plan(project_values()))
    image_path = tmp_path / "result.png"
    Image.new("RGB", (32, 32)).save(image_path)
    raw = {
        "summary_zh": "动作目标尚未表达",
        "observed_slots": dict.fromkeys(SLOT_ORDER, ""),
        "suggested_slots": dict.fromkeys(SLOT_ORDER, ""),
        "strengths": [],
        "issues": [],
        "improvements": [],
        "scene_checks": [
            {
                "criterion": "动作",
                "planned": "护火",
                "observed": "提灯",
                "status": "partial",
                "suggestion": "另一只手靠近火苗",
            }
        ],
    }
    raw["observed_slots"]["action"] = "holding a lantern"
    raw["suggested_slots"]["action"] = "one hand shielding the flame"
    monkeypatch.setattr(
        "prompt_hub.scene_planning.request_creative_json", lambda **_: deepcopy(raw)
    )
    result = generate_scene_review(values, image_path=image_path, model="local")
    assert result["observed_slots"]["action"] != result["suggested_slots"]["action"]
    raw["scene_checks"][0]["status"] = "excellent"
    with pytest.raises(ScenePlanError, match="状态"):
        generate_scene_review(values, image_path=image_path, model="local")


def test_generic_creative_model_rejects_truncated_output_and_uses_connection(monkeypatch):
    request = Mock(
        return_value={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
    )
    monkeypatch.setattr("prompt_hub.local_model._request_json", request)
    with pytest.raises(LocalModelError, match="截断"):
        request_creative_json(model="local", system_prompt="JSON", context={})
    request.return_value = {"choices": [{"message": {"content": '{"plans": []}'}}]}
    connection = SimpleNamespace(
        model_name="cloud", base_url="https://example.test/v1", api_key="secret"
    )
    connections = Mock()
    connections.resolve.return_value = connection
    result = request_creative_json(
        model="external-id", system_prompt="JSON", context={}, connections=connections
    )
    assert result == {"plans": []}
    assert request.call_args.args[0] == "https://example.test/v1/chat/completions"
    assert request.call_args.kwargs["api_key"] == "secret"
    assert request.call_args.kwargs["allow_redirects"] is False


def test_two_defaults_and_three_additional_loras_fit_existing_workflow_semantics(settings):
    svc = services(settings)
    profile = svc.workflow.get_profile.return_value
    profile["controls"]["default_loras"] = [{"name": "default-a"}, {"name": "default-b"}]
    project = svc.creative.create_project(
        {
            **project_values(),
            "generation": {
                "workflow_controls": {
                    "krea2-ares-ocmanager": {
                        "loras": [
                            {"lora_id": "existing-1", "strength": 0.3},
                            {"lora_id": "existing-2", "strength": 0.2},
                        ]
                    }
                }
            },
        }
    )
    advice = advice_for(project)
    values, warnings = apply_style_advice(
        project,
        advice,
        suggestion_id=advice["suggestions"][0]["suggestion_id"],
        profile_id="krea2-ares-ocmanager",
        remote_store=svc.remote,
        workflow_store=svc.workflow,
    )
    assert len(values["generation"]["workflow_controls"]["krea2-ares-ocmanager"]["loras"]) == 3
    assert any("5 个名称" in warning for warning in warnings)
    project["generation"]["workflow_controls"]["krea2-ares-ocmanager"]["loras"].extend(
        [
            {"lora_id": "existing-3", "strength": 0.2},
            {"lora_id": "existing-4", "strength": 0.2},
        ]
    )
    advice = advice_for(project)
    with pytest.raises(ScenePlanError, match="容量"):
        apply_style_advice(
            project,
            advice,
            suggestion_id=advice["suggestions"][0]["suggestion_id"],
            profile_id="krea2-ares-ocmanager",
            remote_store=svc.remote,
            workflow_store=svc.workflow,
        )


def test_gallery_reference_analysis_must_be_confirmed_current_and_online(settings, monkeypatch):
    svc = services(settings)
    project = svc.creative.create_project(project_values())
    captured = []

    def request(**kwargs):
        captured.append(kwargs["context"]["references"])
        return {"plans": [raw_plan(), raw_plan("等候")]}

    monkeypatch.setattr("prompt_hub.scene_planning.request_creative_json", request)
    svc.gallery.get_asset.return_value = {
        "asset_id": "gallery-1",
        "availability": "online",
        "analysis_stale": True,
        "analysis": {"confirmed": True, "summary_zh": "old"},
    }
    url = f"/api/creative/projects/{project['project_id']}/scene-plans"
    response = svc.client.post(url, json={"model": "local", "reference_asset_ids": ["gallery-1"]})
    assert response.status_code == 200
    assert captured[0][0]["analysis"] == {}
    assert any("尚未确认" in warning for warning in response.json()["warnings"])
    svc.gallery.get_asset.return_value["availability"] = "offline"
    assert (
        svc.client.post(
            url, json={"model": "local", "reference_asset_ids": ["gallery-1"]}
        ).status_code
        == 409
    )
    assert len(captured) == 1


def test_model_http_errors_do_not_echo_api_credentials(monkeypatch):
    key = "private-api-credential"
    error = HTTPError(
        "https://example.test/v1/chat/completions",
        401,
        "unauthorized",
        Message(),
        BytesIO(f'{{"error":{{"message":"Rejected {key}"}}}}'.encode()),
    )
    monkeypatch.setattr("prompt_hub.local_model.urlopen", Mock(side_effect=error))
    with pytest.raises(LocalModelError) as captured:
        _request_json("https://example.test/v1/chat/completions", api_key=key)
    assert key not in str(captured.value)
    assert "已隐藏凭据" in str(captured.value)


def test_style_adoption_compiles_actual_profile_without_writing_source_or_running(tmp_path):
    profile_id = "krea2-ares-ocmanager"
    workflow = {
        node_id: {"class_type": kind, "inputs": {}}
        for node_id, kind in RULES[profile_id].required_nodes.items()
    }
    workflow["142"]["inputs"] = {
        "model": ["123", 0],
        "clip": ["66", 0],
        "loras": {"__value__": [{"name": "lora-1", "active": True, "strength": 0.8}]},
    }
    workflow["132"]["inputs"] = {"samples": ["87", 0], "vae": ["65", 0]}
    workflow["87"]["inputs"] = {"model": ["142", 0], "sampler_name": "euler", "scheduler": "simple"}
    store = WorkflowProfileStore(tmp_path / "profiles")
    original = json.dumps(workflow).encode()
    profile = store.import_bytes(profile_id, original, label="test", filename="workflow.json")
    project = {**project_values(), "project_id": "project-1"}
    advice = advice_for(project)
    advice["workflow_sha256"] = profile["source_sha256"]
    remote = Mock()
    remote.get_lora.return_value = catalog_lora()
    values, warnings = apply_style_advice(
        project,
        advice,
        suggestion_id=advice["suggestions"][0]["suggestion_id"],
        profile_id=profile_id,
        remote_store=remote,
        workflow_store=store,
    )
    assert values["generation"]["workflow_controls"][profile_id]["loras"][0]["strength"] == 0.45
    assert any("同名选择会替换权重" in warning for warning in warnings)
    assert (store.root / profile_id / "source-workflow.json").read_bytes() == original
    assert not (store.root / profile_id / "runs").exists()
    workflow["142"]["inputs"]["loras"] = {"unsupported": []}
    store.import_bytes(
        profile_id,
        json.dumps(workflow).encode(),
        label="test",
        filename="workflow.json",
        replace=True,
    )
    advice["workflow_sha256"] = store.get_profile(profile_id)["source_sha256"]
    with pytest.raises(WorkflowProfileError, match="结构不受支持"):
        apply_style_advice(
            project,
            advice,
            suggestion_id=advice["suggestions"][0]["suggestion_id"],
            profile_id=profile_id,
            remote_store=remote,
            workflow_store=store,
        )


@pytest.mark.parametrize("relative_path", ["../../secret", "C:/secret.safetensors", "/etc/passwd"])
def test_style_adoption_rejects_catalog_path_escape(settings, relative_path):
    svc = services(settings)
    project = svc.creative.create_project(project_values())
    advice = advice_for(project)
    svc.remote.get_lora.side_effect = lambda _: {**catalog_lora(), "relative_path": relative_path}
    with pytest.raises(ScenePlanError, match="相对路径"):
        apply_style_advice(
            project,
            advice,
            suggestion_id=advice["suggestions"][0]["suggestion_id"],
            profile_id="krea2-ares-ocmanager",
            remote_store=svc.remote,
            workflow_store=svc.workflow,
        )
    svc.workflow.compile_package.assert_not_called()


def test_scene_adoption_rechecks_revision_inside_write_transaction(settings):
    svc = services(settings)
    project = svc.creative.create_project(project_values())
    adopted, _ = apply_scene_plan(project, stored_plan(project))
    svc.creative.update_project(project["project_id"], {"slots": {"action": "user edit"}})
    with pytest.raises(ValueError, match="确认期间"):
        svc.creative.update_project(
            project["project_id"], adopted, expected_revision=project["revision"]
        )
    assert svc.creative.get_project(project["project_id"])["slots"]["action"] == "user edit"


@pytest.mark.parametrize("error_type", [RemoteDisconnected, BadStatusLine, ConnectionResetError])
def test_model_disconnects_are_clear_redacted_errors(monkeypatch, error_type):
    key = "private-api-credential"
    monkeypatch.setattr(
        "prompt_hub.local_model.urlopen", Mock(side_effect=error_type(f"broken {key}"))
    )
    with pytest.raises(LocalModelError, match="无法连接") as captured:
        _request_json("https://example.test/v1/chat/completions", api_key=key)
    assert key not in str(captured.value)
    assert "已隐藏凭据" in str(captured.value)


def test_creative_context_byte_limit_blocks_request_without_exposing_paths(monkeypatch):
    request = Mock()
    monkeypatch.setattr("prompt_hub.local_model._request_json", request)
    with pytest.raises(LocalModelError, match="512 KiB") as captured:
        request_creative_json(
            model="local",
            system_prompt="JSON",
            context={
                "private_path": "/Users/private/gallery",
                "text": "x" * MAX_CREATIVE_CONTEXT_BYTES,
            },
        )
    request.assert_not_called()
    assert "/Users/private" not in str(captured.value)


def test_style_candidate_metadata_is_bounded_and_has_no_original_paths(monkeypatch):
    request = Mock(return_value=style_raw())
    monkeypatch.setattr("prompt_hub.scene_planning.request_creative_json", request)
    candidate = {
        **catalog_lora(),
        "relative_path": "/private/raw/lora.safetensors",
        "tags": ["t" * 300] * 300,
        "trigger_words": ["w" * 300] * 100,
    }
    generate_style_advice(project_values(), model="local", goal_zh="ink", candidates=[candidate])
    public = request.call_args.kwargs["context"]["candidates"][0]
    assert len(public["tags"]) == 16
    assert len(public["trigger_words"]) == 16
    assert max(map(len, public["tags"])) == 120
    assert "relative_path" not in public
    assert "/private/raw" not in json.dumps(public)


@pytest.mark.parametrize(
    "function_name",
    [
        "request_creative_json",
        "analyze_result_image",
        "draft_krea2_caption",
        "draft_anima_tags",
    ],
)
def test_native_vision_rejects_length_stop_even_with_valid_json(
    tmp_path, monkeypatch, function_name
):
    image = tmp_path / "image.png"
    Image.new("RGB", (32, 32)).save(image)
    monkeypatch.setattr(
        "prompt_hub.local_model._request_json",
        Mock(
            return_value={
                "output": [{"type": "message", "content": "{}"}],
                "stats": {"stop_reason": "maxPredictedTokensReached"},
            }
        ),
    )
    function = getattr(local_model, function_name)
    kwargs = {"image_path": image, "model": "local"}
    if function_name == "request_creative_json":
        kwargs.update(system_prompt="JSON", context={})
    elif function_name == "analyze_result_image":
        kwargs["project"] = project_values()
    with pytest.raises(LocalModelError, match="截断"):
        function(**kwargs)


def test_external_vision_rejects_length_with_nonempty_valid_json(tmp_path, monkeypatch):
    image = tmp_path / "image.png"
    Image.new("RGB", (32, 32)).save(image)
    connection = SimpleNamespace(
        model_name="vision", base_url="https://example.test/v1", api_key="key", supports_vision=True
    )
    connections = Mock()
    connections.resolve.return_value = connection
    monkeypatch.setattr(
        "prompt_hub.local_model._request_json",
        Mock(
            return_value={
                "choices": [{"finish_reason": "length", "message": {"content": "{}"}}],
            }
        ),
    )
    with pytest.raises(LocalModelError, match="截断"):
        request_creative_json(
            model="external",
            system_prompt="JSON",
            context={},
            image_path=image,
            connections=connections,
        )


def test_legacy_review_branch_keeps_slots_and_confirmed_scene_plan():
    project = {
        **project_values(),
        "project_id": "project-original",
        "slots": {"action": "old action", "style": "ink"},
        "generation": {
            "scene_plan": {"plan_id": "confirmed-plan"},
            "result_assets": [{"asset_id": "original-result"}],
        },
    }
    original = deepcopy(project)
    legacy = {"observed_slots": {"action": "observed new action"}}
    branch = next_iteration_values(project, {"asset_id": "original-result"}, legacy)
    assert branch["slots"]["action"] == "old action"
    assert branch["generation"]["scene_plan"] == {"plan_id": "confirmed-plan"}
    assert project == original


def test_new_review_branch_applies_only_nonempty_unlocked_suggestions():
    project = {
        **project_values(),
        "project_id": "project-original",
        "slots": {"action": "old action", "style": "ink", "character": "my fox"},
        "slot_locks": {"style": True},
        "generation": {"scene_plan": {"plan_id": "old-plan"}},
    }
    original = deepcopy(project)
    analysis = {
        "suggested_slots": {
            "action": "protecting the flame",
            "style": "watercolor",
            "character": "",
        },
        "observed_slots": {"action": "holding lantern"},
    }
    branch = next_iteration_values(project, {"asset_id": "original-result"}, analysis)
    assert branch["slots"]["action"] == "protecting the flame"
    assert branch["slots"]["style"] == "ink"
    assert branch["slots"]["character"] == "my fox"
    assert "scene_plan" not in branch["generation"]
    assert project == original
