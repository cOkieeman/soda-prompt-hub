from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from soda_storyboard.bundle import export_bundle, load_bundle

from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.local_model import LocalModelError
from prompt_hub.model_connections import ModelConnectionStore
from prompt_hub.oc_manager import parse_oc_manager_json
from prompt_hub.storyboard import StoryboardStore
from prompt_hub.storyboard_ai import StoryboardAIService
from prompt_hub.storyboard_routes import create_storyboard_router


@pytest.fixture
def sb(settings):
    store = StoryboardStore(settings)
    store.initialize()
    database = PromptDatabase(settings.database_path)
    database.initialize()
    ai = StoryboardAIService(store, ModelConnectionStore(settings), database)
    editors = SimpleNamespace(
        start=lambda *_args: {"url": "http://127.0.0.1:8970/"},
        stop=lambda *_args: {"stopped": True},
    )
    generation = SimpleNamespace(
        submit=lambda *_args, **_kwargs: {"task_id": "fake"},
        import_results=lambda *_args, **_kwargs: {"results": []},
        select_result=lambda *_args: {"selected": "fake"},
        list_results=lambda *_args: [],
        last_task=lambda *_args: None,
    )
    app = FastAPI()
    app.include_router(create_storyboard_router(store, ai, editors, generation))
    with TestClient(app) as client:
        project = client.post("/api/storyboard/projects", json={"name": "Test"}).json()["id"]
        base = f"/api/storyboard/projects/{project}"
        assert (
            client.post(base + "/pages", json={"id": "first", "title": "First"}).status_code == 201
        )
        yield SimpleNamespace(
            store=store,
            ai=ai,
            client=client,
            database=database,
            project=project,
            base=base,
            url=base + "/pages/first",
        )


def _model(monkeypatch):
    monkeypatch.setattr(
        "prompt_hub.storyboard_ai.request_creative_json",
        lambda **_kwargs: {
            "panels": [
                {"description": "窗边有一盆花", "shot": "medium"},
                {"description": "花开了", "shot": "close_up"},
            ]
        },
    )


def _preview(sb):
    response = sb.client.post(
        sb.url + "/ai/preview",
        json={"story": "女孩发现花开了", "connection_id": "fake", "panel_count": 2},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _snapshot(sb):
    return {
        path.relative_to(sb.store.root).as_posix(): path.read_bytes()
        for path in sb.store.root.rglob("*")
        if path.is_file()
    }


def test_ai_preview_no_disk_writes_confirmation_and_layout_choice(sb, monkeypatch):
    _model(monkeypatch)
    before = _snapshot(sb)
    preview = _preview(sb)
    assert len(preview["candidates"]) >= 2
    assert _snapshot(sb) == before
    assert (
        sb.client.post(sb.url + "/ai/apply", json={"preview_id": preview["preview_id"]}).status_code
        == 409
    )
    assert _snapshot(sb) == before
    response = sb.client.post(
        sb.url + "/ai/apply",
        json={"preview_id": preview["preview_id"], "confirmed": True, "candidate_index": 1},
    )
    assert response.status_code == 200, response.text
    assert (
        sb.store.get_page(sb.project, "first")["page"]["panels"]
        == preview["candidates"][1]["page"]["panels"]
    )
    assert (
        sb.client.post(
            sb.url + "/ai/apply", json={"preview_id": preview["preview_id"], "confirmed": True}
        ).status_code
        == 409
    )


def test_ai_stale_or_nonempty_page_never_overwrites(sb, monkeypatch):
    _model(monkeypatch)
    preview = _preview(sb)
    current = sb.store.get_page(sb.project, "first")
    raw = {**current["page"], "description": "人工已填写"}
    assert (
        sb.client.put(
            sb.url, json={"page": raw, "expected_version": current["version"]}
        ).status_code
        == 200
    )
    before = _snapshot(sb)
    assert (
        sb.client.post(
            sb.url + "/ai/apply", json={"preview_id": preview["preview_id"], "confirmed": True}
        ).status_code
        == 409
    )
    assert _snapshot(sb) == before
    preview = _preview(sb)
    assert (
        sb.client.post(
            sb.url + "/ai/apply", json={"preview_id": preview["preview_id"], "confirmed": True}
        ).status_code
        == 409
    )
    assert sb.store.get_page(sb.project, "first")["page"]["description"] == "人工已填写"


def test_translation_preview_then_confirm(sb, monkeypatch):
    _model(monkeypatch)
    preview = _preview(sb)
    assert (
        sb.client.post(
            sb.url + "/ai/apply", json={"preview_id": preview["preview_id"], "confirmed": True}
        ).status_code
        == 200
    )
    todo = sb.client.get(sb.url + "/translations/todo").json()
    assert len(todo["panels"]) == 2
    translations = [
        {
            "panel_id": entry["panel_id"],
            "source_hash": entry["source_hash"],
            "text": "A flower pot on the windowsill.",
        }
        for entry in todo["panels"]
    ]
    monkeypatch.setattr(
        "prompt_hub.storyboard_ai.request_creative_json",
        lambda **_kwargs: {"translations": translations},
    )
    before = _snapshot(sb)
    response = sb.client.post(sb.url + "/translations/preview", json={"connection_id": "fake"})
    assert response.status_code == 200, response.text
    assert _snapshot(sb) == before
    response = sb.client.post(
        sb.url + "/translations/apply",
        json={"preview_id": response.json()["preview_id"], "confirmed": True},
    )
    assert response.status_code == 200, response.text
    assert len(response.json()["applied"]) == 2
    assert sb.client.get(sb.url + "/translations/todo").json()["panels"] == []
    assert (
        sb.client.post(
            sb.url + "/translations/apply", json={"translations": translations}
        ).status_code
        == 409
    )
    current = sb.store.get_page(sb.project, "first")
    assert (
        sb.client.post(
            sb.url + "/translations/apply",
            json={"translations": [], "confirmed": True, "expected_version": current["version"]},
        ).status_code
        == 200
    )


def test_pudding_http_import_validate_compile_export_consistency(sb, tmp_path):
    project = tmp_path / "pudding"
    shutil.copytree(Path(__file__).parent / "fixtures/storyboard_pudding", project)
    bundle = json.loads(
        Path(export_bundle(project / "pages/pudding.json")["path"]).read_text(encoding="utf-8")
    )
    expected_page, expected_cards, expected_project, _ = load_bundle(bundle)
    response = sb.client.post("/api/storyboard/import", json={"content": bundle})
    assert response.status_code == 201, response.text
    base = f"/api/storyboard/projects/{response.json()['id']}"
    assert sb.client.post(base + "/pages/pudding/validate").json()["errors"] == []
    assert sb.client.post(base + "/pages/pudding/compile").json()["moss"]["items"]
    response = sb.client.get(base + "/export")
    assert response.status_code == 200
    page, cards, settings, _ = load_bundle(response.json())
    assert page.to_dict() == expected_page.to_dict()
    assert {key: value.to_dict() for key, value in cards.items()} == {
        key: value.to_dict() for key, value in expected_cards.items()
    }
    assert all(settings[key] == value for key, value in expected_project.items())


def test_routes_project_pages_recycle_editor_and_fake_worker(sb):
    assert sb.client.get("/api/storyboard/projects").json()[0]["id"] == sb.project
    assert sb.client.get(sb.base).status_code == 200
    assert sb.client.get(sb.base + "/pages").json()[0]["id"] == "first"
    assert sb.client.get(sb.url).json()["last_task"] is None
    assert sb.client.get(sb.url + "/results").json() == []
    assert sb.client.get(sb.url + "/preview.png").headers["content-type"] == "image/png"
    assert sb.client.post(sb.url + "/editor/start").status_code == 200
    assert sb.client.post(sb.url + "/editor/stop").json()["stopped"]
    assert sb.client.post(sb.url + "/generate", json={}).json()["task_id"] == "fake"
    assert (
        sb.client.post(sb.url + "/results/refresh", json={"task_id": "fake"}).json()["results"]
        == []
    )
    assert (
        sb.client.post(sb.url + "/results/pick", json={"result_id": "fake"}).json()["selected"]
        == "fake"
    )
    page = {"format": "soda-storyboard-page-v1", "id": "second", "panels": []}
    assert sb.client.post(sb.base + "/import", json={"content": page}).status_code == 201
    assert sb.client.post(sb.base + "/import", json={"content": page}).status_code == 409
    assert sb.client.get(sb.base + "/export").status_code == 422
    assert sb.client.get(sb.base + "/export?page_id=second").status_code == 200
    assert sb.client.delete(sb.base + "/pages/second").status_code == 200
    assert sb.client.delete(sb.base).status_code == 200
    assert sb.client.get(sb.base).status_code == 404
    assert list((sb.store.root / "trash").iterdir())


@pytest.mark.parametrize(
    "content",
    [
        "../../private.json",
        {"id": "../escape"},
        {"id": "safe", "production": {"selected_render": "../../escape.png"}},
        {"id": "safe", "canvas_width": 999999},
    ],
)
def test_import_rejects_paths_and_oversize_without_disk_changes(sb, content):
    before = _snapshot(sb)
    assert sb.client.post("/api/storyboard/import", json={"content": content}).status_code == 422
    assert _snapshot(sb) == before


def test_oc_bilingual_card_preview_and_confirmation(sb, monkeypatch):
    bundle = parse_oc_manager_json(
        json.dumps(
            {"format": "oc-manager-single-character", "character": {"id": "luna", "name": "Luna"}}
        ).encode()
    )
    sb.database.import_oc_manager(bundle, source_file="fixture.json", import_hash="fixture")
    url = sb.base + "/characters"
    before = _snapshot(sb)
    response = sb.client.post(
        url + "/preview",
        json={
            "oc_id": "luna",
            "appearance_zh": "黑发白衬衫",
            "appearance_en": "black hair, white shirt",
            "lora": {"path": "luna.safetensors", "strength": 0.8},
        },
    )
    assert response.status_code == 200, response.text
    assert _snapshot(sb) == before
    preview = response.json()
    assert preview["character"]["appearance"]["en"] == "black hair, white shirt"
    assert (
        sb.client.post(url + "/apply", json={"preview_id": preview["preview_id"]}).status_code
        == 409
    )
    assert (
        sb.client.post(
            url + "/apply", json={"preview_id": preview["preview_id"], "confirmed": True}
        ).status_code
        == 200
    )
    assert len(sb.store.characters(sb.project)) == 1
    assert (
        sb.client.post(
            url + "/preview", json={"oc_id": "luna", "lora": {"path": "../bad.safetensors"}}
        ).status_code
        == 409
    )
    monkeypatch.setattr(
        "prompt_hub.storyboard_ai.request_creative_json",
        lambda **_kwargs: {
            "appearance_zh": "黑发白衬衫",
            "appearance_en": "black hair, white shirt",
            "outfit_zh": "白衬衫",
            "outfit_en": "white shirt",
        },
    )
    assert (
        sb.client.post(
            url + "/preview", json={"oc_id": "luna", "connection_id": "fake"}
        ).status_code
        == 200
    )


def test_invalid_model_output_and_preview_binding(sb, monkeypatch):
    monkeypatch.setattr(
        "prompt_hub.storyboard_ai.request_creative_json", lambda **_kwargs: {"panels": []}
    )
    assert (
        sb.client.post(
            sb.url + "/ai/preview",
            json={"story": "片段", "connection_id": "fake", "panel_count": 2},
        ).status_code
        == 409
    )
    _model(monkeypatch)
    preview = _preview(sb)
    assert (
        sb.client.post(
            sb.url + "/translations/apply",
            json={"preview_id": preview["preview_id"], "confirmed": True},
        ).status_code
        == 409
    )
    assert (
        sb.client.post(
            sb.url + "/ai/apply",
            json={"preview_id": preview["preview_id"], "confirmed": True, "candidate_index": 12},
        ).status_code
        == 409
    )
    sb.ai.pending[preview["preview_id"]]["created"] = 0
    assert (
        sb.client.post(
            sb.url + "/ai/apply", json={"preview_id": preview["preview_id"], "confirmed": True}
        ).status_code
        == 409
    )


def test_model_errors_and_app_lifespan(sb, settings, monkeypatch):
    def fail(**_kwargs):
        message = "offline fake"
        raise LocalModelError(message)

    monkeypatch.setattr("prompt_hub.storyboard_ai.request_creative_json", fail)
    assert (
        sb.client.post(
            sb.url + "/ai/preview", json={"story": "片段", "connection_id": "fake"}
        ).status_code
        == 502
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/storyboard/projects").status_code == 200


@pytest.mark.parametrize(
    "translations",
    [
        [{"text": "Missing identity"}],
        [{"panel_id": "unknown", "text": "Missing hash"}],
        [{"panel_id": [], "source_hash": "x", "text": "Invalid type"}],
    ],
)
def test_translation_malformed_identity_is_rejected_without_writes(sb, monkeypatch, translations):
    monkeypatch.setattr(
        "prompt_hub.storyboard_ai.request_creative_json",
        lambda **_kwargs: {"translations": translations},
    )
    before = _snapshot(sb)
    response = sb.client.post(sb.url + "/translations/preview", json={"connection_id": "fake"})
    assert response.status_code == 409
    assert _snapshot(sb) == before


def test_malformed_warnings_do_not_break_frontend_preview(sb, monkeypatch):
    monkeypatch.setattr(
        "prompt_hub.storyboard_ai.request_creative_json",
        lambda **_kwargs: {
            "panels": [{"description": "花"}, {"description": "花开"}],
            "warnings": "invalid",
        },
    )
    before = _snapshot(sb)
    response = sb.client.post(
        sb.url + "/ai/preview", json={"story": "花开", "connection_id": "fake", "panel_count": 2}
    )
    assert response.status_code == 409
    assert _snapshot(sb) == before


@pytest.mark.parametrize(
    "content",
    [
        [{"panel": 1, "description": "女孩站在窗边"}, {"panel": 2, "description": "花开了"}],
        "| 格 | 画面 |\n| --- | --- |\n| 1 | 女孩站在窗边 |\n| 2 | 花开了 |",
    ],
)
def test_external_storyboard_sheet_and_frame_array_import(sb, content):
    response = sb.client.post("/api/storyboard/import", json={"content": content})
    assert response.status_code == 201, response.text
    assert len(response.json()["page"]["panels"]) == 2


@pytest.mark.parametrize(
    "content",
    [
        {"summary": "invalid", "items": []},
        {
            "format": "soda-storyboard-bundle-v1",
            "page": {"id": "p"},
            "characters": {"c": {"id": "c", "clothing": 3}},
        },
    ],
)
def test_malformed_core_import_has_http_error_without_partial_project(sb, content):
    before = _snapshot(sb)
    response = sb.client.post("/api/storyboard/import", json={"content": content})
    assert response.status_code == 422
    assert _snapshot(sb) == before
