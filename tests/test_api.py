from __future__ import annotations

import json

from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import import_all


def test_api_health_stats_search_and_page(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    app = create_app(source_tree)

    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/api/stats").json()["entries"] > 5
        assert len(client.get("/api/sources").json()) == 4
        result = client.get("/api/search", params={"query": "gothic", "kind": "style"})
        assert result.status_code == 200
        assert result.json()["results"][0]["title"] == "Gothic Ink"
        assert result.json()["results"][0]["visuals"][0]["thumbnail_url"]
        clio_media = client.get(result.json()["results"][0]["visuals"][0]["thumbnail_url"])
        assert clio_media.status_code == 200
        kisega = client.get("/api/search", params={"query": "collared shirt", "kind": "tag"})
        thumbnail_url = kisega.json()["results"][0]["visuals"][0]["thumbnail_url"]
        assert client.get(thumbnail_url).headers["content-type"] == "image/webp"
        assert client.get(thumbnail_url.replace("thumbnail", "original")).status_code == 200
        assert client.get("/media/kisegaeningyou/original/../test.sqlite").status_code == 404
        suggestive = client.get(
            "/api/search",
            params={"query": "underboob", "kind": "tag", "safety": "suggestive"},
        ).json()["results"][0]
        assert suggestive["visuals"][0]["safety"] == "suggestive"
        mark_response = client.put(
            "/api/marks",
            json={
                "source_id": "clio-style-preview",
                "external_id": "style:0",
                "favorite": True,
                "rating": 5,
                "note": "Keep this <reference>",
            },
        )
        assert mark_response.status_code == 200
        assert mark_response.json()["user_rating"] == 5
        favorites = client.get("/api/search", params={"favorites_only": True}).json()
        assert favorites["count"] == 1
        assert favorites["results"][0]["user_note"] == "Keep this <reference>"
        assert client.get("/api/stats").json()["personal"]["favorites"] == 1
        assert (
            client.put(
                "/api/marks",
                json={"source_id": "missing", "external_id": "missing", "favorite": True},
            ).status_code
            == 404
        )
        assert (
            client.put(
                "/api/marks",
                json={"source_id": "clio-style-preview", "external_id": "style:0", "rating": 6},
            ).status_code
            == 422
        )
        page = client.get("/")
        assert page.status_code == 200
        assert "Soda Prompt Archive" in page.text
        assert "开始创作" in page.text
        assert "提示词库" in page.text
        assert "角色库" in page.text
        assert "资料管理" in page.text
        assert "今天想画" in page.text
        assert "ANIMA" in page.text
        assert "KREA 2" in page.text
        assert "高级筛选" in page.text
        assert "维多利亚军装" in page.text
        assert "Drawing Desk" in page.text
        assert "七个创作槽位" in page.text
        assert "从本地库智能取材" in page.text
        assert "智能取材候选" in page.text
        assert all(
            marker in page.text
            for marker in (
                "结果图复盘",
                "resultImageFile",
                "visionModel",
                "只写入实测备注",
                "由此创建下一版",
                "lineageNotice",
                "本轮迭代对照",
                "applyIterationSuggestions",
                "加入数据集",
                "datasetProfile",
                "WD14 · ANIMA 自动打标",
                "tagSelectedDataset",
                "data-wd14-tag",
                "导出精选数据集 ZIP",
            )
        )
        assert "导出 Anima + Krea 2 JSON" in page.text
        assert "data-creative-add" in page.text


def test_api_rebuild_index(source_tree, monkeypatch) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    app = create_app(source_tree)
    with TestClient(app) as client:
        response = client.post("/api/import")
        assert response.status_code == 200
        assert response.json()["stats"]["sources"] == 4


def test_api_imports_and_searches_oc_manager_json(settings) -> None:
    app = create_app(settings)
    export = {
        "format": "oc-manager-full-database",
        "characters": [
            {
                "id": "char-api",
                "name": "阿莉娅",
                "world": "镜海",
                "race": "人类",
                "story": "调查沉没图书馆",
                "prompts": [{"id": "p1", "label": "portrait", "text": "silver eyes"}],
            }
        ],
        "worlds": [{"id": "world-api", "name": "镜海", "system": "generic"}],
        "lore": {"镜海": {"locations": [{"id": "l1", "name": "沉没图书馆"}]}},
    }
    with TestClient(app) as client:
        response = client.post(
            "/api/oc-manager/import",
            params={"filename": "oc-backup.json"},
            content=json.dumps(export, ensure_ascii=False).encode(),
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 200
        assert response.json()["characters_imported"] == 1
        assert response.json()["stats"]["characters"] == 1
        archived = settings.oc_imports_root / response.json()["source_file"].split("/")[-1]
        assert archived.exists()

        search = client.get(
            "/api/oc-manager/characters",
            params={"query": "图书馆", "world": "镜海"},
        ).json()
        assert search["count"] == 1
        assert search["results"][0]["name"] == "阿莉娅"
        profile = client.get("/api/oc-manager/characters/char-api")
        assert profile.status_code == 200
        assert profile.json()["prompts"][0]["text"] == "silver eyes"
        assert client.get("/api/oc-manager/characters/missing").status_code == 404
        assert client.get("/api/oc-manager/worlds").json()[0]["character_count"] == 1
        lore = client.get("/api/oc-manager/lore", params={"query": "沉没"}).json()
        assert lore["count"] == 1
        assert client.get("/api/stats").json()["oc_manager"]["characters"] == 1

        invalid = client.post(
            "/api/oc-manager/import",
            params={"filename": "broken.json"},
            content=b"broken",
        )
        assert invalid.status_code == 422
