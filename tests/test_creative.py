from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.creative import (
    CREATIVE_SCHEMA,
    CreativeStore,
    apply_iteration_suggestions,
    compile_prompt,
    export_project,
    iteration_context,
    next_iteration_values,
)
from prompt_hub.local_model import LocalModelError, organize_slots


def sample_project() -> dict:
    return {
        "title": "黄昏图书馆",
        "brief_zh": "一位调查员在黄昏的旧图书馆寻找线索",
        "safety_mode": "adult",
        "target_profile": "anima",
        "slots": {
            "character": "1girl, silver eyes",
            "outfit": "victorian military uniform, leather gloves",
            "action": "holding an old letter",
            "composition": "medium shot, low angle",
            "scene": "old library, floating dust",
            "lighting": "golden hour, rim light",
            "style": "gothic ink illustration",
        },
        "slot_locks": {"character": True},
        "references": [{"source_id": "clio", "title": "Gothic Ink", "slot": "style"}],
        "generation": {"steps": 28, "seed": 42},
        "test_notes": "先测试半身构图",
    }


def test_creative_store_project_recipe_and_export(settings) -> None:
    store = CreativeStore(settings.database_path)
    store.initialize()
    created = store.create_project(sample_project())

    assert created["project_id"].startswith("project-")
    assert created["slots"]["character"] == "1girl, silver eyes"
    assert created["slot_locks"]["character"] is True
    assert store.list_projects()[0]["title"] == "黄昏图书馆"

    updated = store.update_project(
        created["project_id"],
        {"title": "黄昏档案", "slots": {**created["slots"], "action": "reading"}},
    )
    assert updated["revision"] == 2
    assert updated["slots"]["action"] == "reading"

    recipe = store.save_recipe(created["project_id"], "第一版", favorite=True)
    assert recipe["favorite"] is True
    assert recipe["snapshot"]["outputs"]["anima"]["positive"].startswith("masterpiece")
    assert store.get_recipe(recipe["recipe_id"])["name"] == "第一版"
    assert store.list_recipes()[0]["project_id"] == created["project_id"]

    exported = export_project(updated)
    assert exported["format"] == "soda-prompt-hub-creative-v1"
    assert exported["outputs"]["krea2"]["profile_id"] == "krea2"
    assert store.get_project("missing") is None
    assert store.get_recipe("missing") is None
    with pytest.raises(KeyError):
        store.update_project("missing", {})
    with pytest.raises(KeyError):
        store.save_recipe("missing", "nope")


def test_creative_store_migrates_legacy_projects_with_lineage(settings) -> None:
    legacy_schema = CREATIVE_SCHEMA.replace(
        "    lineage_json TEXT NOT NULL DEFAULT '{}',\n",
        "",
    )
    with sqlite3.connect(settings.database_path) as connection:
        connection.executescript(legacy_schema)
    store = CreativeStore(settings.database_path)
    store.initialize()
    with store.connect() as connection:
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(creative_projects)").fetchall()
        }
    assert "lineage_json" in columns
    assert store.create_project(sample_project())["lineage"] == {}


def test_next_iteration_values_builds_v2_and_v3_without_old_results() -> None:
    parent = {
        **sample_project(),
        "project_id": "project-root",
        "generation": {
            "steps": 28,
            "seed": 42,
            "result_images": ["old.png"],
            "result_assets": [{"asset_id": "old"}],
        },
    }
    asset = {"asset_id": "result-v1", "filename": "v1.png"}
    analysis = {
        "model": "vision-model",
        "summary_zh": "构图清晰",
        "observed_slots": {"character": "changed", "lighting": "strong rim light"},
        "improvements": ["加强轮廓光"],
        "reconstructed_prompts": {"anima_positive": "rim light"},
    }
    v2 = next_iteration_values(parent, asset, analysis)
    assert v2["title"] == "黄昏图书馆 · V2"
    assert v2["lineage"]["root_project_id"] == "project-root"
    assert v2["lineage"]["review"]["observed_slots"]["lighting"] == "strong rim light"
    assert v2["generation"] == {"steps": 28, "seed": 42, "result_images": []}

    v3 = next_iteration_values(
        {**v2, "project_id": "project-v2"},
        {"asset_id": "result-v2", "filename": "v2.png"},
        analysis,
    )
    assert v3["title"] == "黄昏图书馆 · V3"
    assert v3["lineage"]["iteration"] == 3
    assert v3["lineage"]["root_project_id"] == "project-root"
    assert v3["lineage"]["parent_project_id"] == "project-v2"


def test_iteration_context_and_suggestions_protect_existing_and_locked_slots() -> None:
    parent = sample_project()
    project = {
        **sample_project(),
        "slots": {**sample_project()["slots"], "lighting": ""},
        "lineage": {
            "iteration": 2,
            "parent_iteration": 1,
            "parent_project_id": "project-v1",
            "review": {
                "observed_slots": {
                    "character": "changed character",
                    "outfit": "changed outfit",
                    "lighting": "warm rim light",
                }
            },
        },
    }
    context = iteration_context(project, parent)
    lighting = next(item for item in context["changes"] if item["slot"] == "lighting")
    assert context["parent_available"] is True
    assert context["applicable_slots"] == ["lighting"]
    assert lighting["status"] == "removed"
    assert lighting["applicable"] is True

    applied = apply_iteration_suggestions(project)
    assert applied["slots"]["character"] == parent["slots"]["character"]
    assert applied["slots"]["outfit"] == parent["slots"]["outfit"]
    assert applied["slots"]["lighting"] == "warm rim light"
    assert applied["applied_slots"] == ["lighting"]
    assert "[迭代建议已应用] lighting" in applied["test_notes"]

    missing_parent = iteration_context(project, None)
    assert missing_parent["parent_available"] is False
    assert all(item["status"] == "unknown" for item in missing_parent["changes"])


def test_profiles_keep_adult_intent_and_warn_about_format() -> None:
    project = sample_project()
    anima = compile_prompt(project, "anima")
    assert "victorian military uniform" in anima["positive"]
    assert "nude" not in anima["negative"]

    project["safety_mode"] = "sfw"
    project["slots"]["character"] = "银发女性"
    sfw = compile_prompt(project, "anima")
    assert "nsfw" in sfw["negative"]
    assert any("Booru" in warning for warning in sfw["warnings"])

    project["safety_mode"] = "suggestive"
    project["slots"]["style"] = ", ".join(f"tag-{index}" for index in range(12))
    krea = compile_prompt(project, "krea2")
    assert "创作意图" in krea["positive"]
    assert "明确性行为" in krea["negative"]
    assert any("标签堆叠" in warning for warning in krea["warnings"])

    with pytest.raises(ValueError, match="Unknown creative profile"):
        compile_prompt(project, "missing")


def test_empty_profile_has_actionable_warnings() -> None:
    result = compile_prompt({"slots": {}}, "krea2")
    assert len(result["warnings"]) == 2
    assert result["positive"] == ""


def test_creative_api_flow(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "prompt_hub.api.list_local_models",
        lambda: [{"id": "gemma-4-12b-it-heretic", "name": "Gemma Heretic", "loaded": True}],
    )
    app = create_app(settings)
    with TestClient(app) as client:
        created_response = client.post("/api/creative/projects", json=sample_project())
        assert created_response.status_code == 201
        created = created_response.json()
        project_id = created["project_id"]

        assert client.get("/api/creative/projects").json()[0]["project_id"] == project_id
        assert client.get(f"/api/creative/projects/{project_id}").status_code == 200
        assert client.get("/api/creative/projects/missing").status_code == 404

        update = client.put(
            f"/api/creative/projects/{project_id}",
            json={"brief_zh": "更新后的想法", "target_profile": "krea2"},
        )
        assert update.status_code == 200
        assert update.json()["target_profile"] == "krea2"
        assert client.put("/api/creative/projects/missing", json={"title": "x"}).status_code == 404

        compiled = client.post(
            "/api/creative/compile",
            json={**sample_project(), "profile_id": "krea2"},
        )
        assert compiled.status_code == 200
        assert compiled.json()["profile_id"] == "krea2"

        recipe = client.post(
            "/api/creative/recipes",
            json={"project_id": project_id, "name": "可用版本", "favorite": True},
        )
        assert recipe.status_code == 201
        assert client.get("/api/creative/recipes").json()[0]["name"] == "可用版本"
        assert (
            client.post(
                "/api/creative/recipes",
                json={"project_id": "missing", "name": "x"},
            ).status_code
            == 404
        )

        exported = client.get(f"/api/creative/projects/{project_id}/export")
        assert exported.status_code == 200
        assert set(exported.json()["outputs"]) == {"anima", "krea2"}
        assert client.get("/api/creative/projects/missing/export").status_code == 404
        assert client.get("/api/local-models").json()["models"][0]["id"].startswith("gemma")


def test_local_assist_preserves_locked_slots(monkeypatch) -> None:
    def fake_request(_url, **_kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": "```json\n"
                        + json.dumps(
                            {
                                "character": "changed",
                                "outfit": "black coat",
                                "action": "walking",
                            }
                        )
                        + "\n```"
                    }
                }
            ]
        }

    monkeypatch.setattr("prompt_hub.local_model._request_json", fake_request)
    result = organize_slots(
        brief="黄昏的调查员",
        slots={"character": "silver-haired investigator"},
        locks={"character": True},
        model="local-model",
        target_profile="anima",
    )
    assert result["suggested_slots"]["character"] == "silver-haired investigator"
    assert result["suggested_slots"]["outfit"] == "black coat"
    assert result["locked_slots"] == ["character"]


def test_local_models_unavailable_is_graceful(settings, monkeypatch) -> None:
    def unavailable():
        message = "offline"
        raise LocalModelError(message)

    monkeypatch.setattr("prompt_hub.api.list_local_models", unavailable)
    monkeypatch.setattr(
        "prompt_hub.api.organize_slots",
        lambda **_kwargs: (_ for _ in ()).throw(LocalModelError("not loaded")),
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/local-models").json()["available"] is False
        response = client.post(
            "/api/creative/assist",
            json={"brief": "test", "model": "missing", "target_profile": "anima"},
        )
        assert response.status_code == 503
