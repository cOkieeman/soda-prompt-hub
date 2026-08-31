from __future__ import annotations

import json

from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.database import EntryInput, PromptDatabase
from prompt_hub.importers import import_all
from prompt_hub.local_model import expand_sourcing_queries
from prompt_hub.sourcing import build_slot_queries, source_candidates


def test_build_slot_queries_maps_zh_and_respects_locks() -> None:
    queries = build_slot_queries(
        "银发调查员穿维多利亚军装,在黄昏图书馆读信,电影感特写",
        slots={"lighting": "rim light"},
        locks={"character": True},
    )
    assert queries["character"] == []
    assert "military uniform" in queries["outfit"]
    assert "reading" in queries["action"]
    assert "close-up" in queries["composition"]
    assert "library" in queries["scene"]
    assert "golden hour" in queries["lighting"]
    assert "cinematic" in queries["style"]


def test_source_candidates_returns_real_ranked_and_safety_filtered_cards(
    source_tree,
    monkeypatch,
) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)

    result = source_candidates(
        database,
        brief="哥特风格的黑色连衣裙",
        safety_mode="sfw",
        slots={},
        locks={},
        query_hints={"outfit": ["collared shirt"]},
        limit_per_slot=6,
    )
    outfit = result["slots"]["outfit"]["candidates"]
    style = result["slots"]["style"]["candidates"]
    assert result["candidate_count"] >= 3
    assert any("dress" in item["content"] for item in outfit)
    assert any(item["category"] == "outfit-reference" for item in outfit)
    assert any(item["title"] == "Gothic Ink" for item in style)
    assert all(item["safety"] == "sfw" for item in outfit + style)
    assert all(item["recommended_slot"] in {"outfit", "style"} for item in outfit + style)


def test_source_candidates_skip_locked_slot(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    result = source_candidates(
        database,
        brief="gothic ink",
        safety_mode="explicit-adult",
        locks={"style": True},
    )
    assert result["slots"]["style"] == {"locked": True, "queries": [], "candidates": []}


def test_source_candidates_prefers_exact_action_and_hair_context(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    with database.connect() as connection:
        database.upsert_source(
            source_id="sourcing-test",
            name="Sourcing test cards",
            source_type="test",
            url="",
            local_path="tests",
            commit_hash="fixture",
            license_name="test-only",
            notes="Dedicated ranking fixtures",
            connection=connection,
        )
        database.replace_source_entries(
            "sourcing-test",
            [
                EntryInput(
                    "sourcing-test",
                    "hair",
                    "wildcard",
                    "silver hair",
                    "silver hair",
                    category="hair",
                ),
                EntryInput(
                    "sourcing-test",
                    "reading",
                    "wildcard",
                    "reading",
                    "reading",
                    category="action",
                ),
                EntryInput(
                    "sourcing-test",
                    "mind-reading",
                    "wildcard",
                    "a mind-reading device creates controversy",
                    "a mind-reading device creates controversy",
                    category="action",
                ),
            ],
            connection=connection,
        )
        connection.commit()
    result = source_candidates(
        database,
        brief="银发角色正在读信",
        safety_mode="sfw",
        query_hints={"character": ["silver hair"], "action": ["reading"]},
        limit_per_slot=10,
    )
    character = result["slots"]["character"]["candidates"]
    action = result["slots"]["action"]["candidates"]
    assert all(
        "hair" in f"{item['title']} {item['content']} {item['category']}" for item in character
    )
    assert action[0]["content"] == "reading"


def test_sourcing_api_attaches_visuals(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    with TestClient(create_app(source_tree)) as client:
        response = client.post(
            "/api/creative/source",
            json={
                "brief": "哥特连衣裙",
                "safety_mode": "sfw",
                "query_hints": {"outfit": ["collared shirt"]},
            },
        )
        assert response.status_code == 200
        data = response.json()
        candidates = data["slots"]["outfit"]["candidates"]
        visual_candidate = next(item for item in candidates if item["visuals"])
        assert visual_candidate["visuals"][0]["thumbnail_url"].startswith("/media/")
        assert visual_candidate["visuals"][0]["safety"] == "sfw"


def test_expand_sourcing_queries_returns_short_lists_and_locks(monkeypatch) -> None:
    def fake_request(_url, **_kwargs):
        content = json.dumps(
            {
                "character": ["silver hair", "adult investigator"],
                "outfit": "victorian military uniform",
                "action": ["opening a letter"],
                "composition": ["medium shot"],
                "scene": ["old library"],
                "lighting": ["golden hour", "rim light"],
                "style": ["cinematic", "gothic illustration", "ink", "vintage", "extra"],
            }
        )
        return {"choices": [{"message": {"content": content}}]}

    monkeypatch.setattr("prompt_hub.local_model._request_json", fake_request)
    result = expand_sourcing_queries(
        brief="黄昏图书馆调查员",
        slots={},
        locks={"character": True},
        model="local-model",
    )
    assert result["queries"]["character"] == []
    assert result["queries"]["outfit"] == ["victorian military uniform"]
    assert len(result["queries"]["style"]) == 4


def test_sourcing_expand_api(settings, monkeypatch) -> None:
    monkeypatch.setattr(
        "prompt_hub.api.expand_sourcing_queries",
        lambda **_kwargs: {"model": "local", "queries": {"scene": ["library"]}},
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/creative/source/expand",
            json={"brief": "图书馆", "model": "local", "slot_locks": {}},
        )
        assert response.status_code == 200
        assert response.json()["queries"]["scene"] == ["library"]
