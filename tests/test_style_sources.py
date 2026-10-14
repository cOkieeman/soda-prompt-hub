from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import import_report
from prompt_hub.media import resolve_media_path


@pytest.fixture
def style_sources(settings, monkeypatch):
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    krea = settings.git_sources_root / "Krea2-Style-Explorer"
    (krea / "app").mkdir(parents=True)
    (krea / "images" / "1").mkdir(parents=True)
    (krea / "app" / "data.js").write_text(
        "const galleryData = "
        + json.dumps(
            [
                {"id": "abc123", "folder": "1", "prompt": "cyanotype, blue ink, paper grain"},
                {"id": "def456", "folder": "2", "prompt": "soft watercolor, delicate washes"},
            ],
        )
        + ";\n",
        encoding="utf-8",
    )
    Image.new("RGB", (48, 64), "blue").save(krea / "images" / "1" / "abc123.webp")
    neons = settings.git_sources_root / "ComfyUI-NeonsStyleExplorer" / "styles"
    neons.mkdir(parents=True)
    rows = [
        {
            "id": f"anime.{axis}",
            "name": f"Anime {axis}",
            "family": "Anime & Manga",
            "axis": axis,
            "nl": f"{axis}, cel colouring, anime style image,",
            "negative": "photo, muddy colour",
            "tags": ["cel_shading"],
            "tags_negative": ["photorealistic"],
            "aliases": ["flat cel"],
        }
        for axis in ("style", "format", "finish")
    ]
    (neons / "01_anime_manga.json").write_text(
        json.dumps({"schema": 1, "family": "Anime & Manga", "styles": rows}),
        encoding="utf-8",
    )
    (neons / "10_other.json").write_text(
        json.dumps({"schema": 1, "family": "Extra", "styles": rows}),
        encoding="utf-8",
    )
    return settings


def test_style_sources_search_previews_and_favorites_survive_reorder(style_sources):
    database = PromptDatabase(style_sources.database_path)
    report = import_report(style_sources, database)
    assert report["sources"] == {"krea2-style-explorer": 2, "neons-style-explorer": 3}
    assert report["failed"] == []
    with TestClient(create_app(style_sources)) as client:
        result = client.get(
            "/api/search",
            params={"query": "cyanotype", "model_family": "krea2", "has_visual": True},
        ).json()["results"][0]
        assert result["content"] == "cyanotype, blue ink, paper grain"
        assert result["safety"] == "unrated"
        assert "/blob/deadbeef/app/data.js" in result["source_url"]
        for key in ("thumbnail_url", "original_url"):
            preview = client.get(result["visuals"][0][key])
            assert preview.status_code == 200
            assert preview.headers["content-type"] == "image/webp"
        assert (
            client.get(
                "/api/search",
                params={"query": "cyanotype", "safety": "sfw"},
            ).json()["total"]
            == 0
        )
        missing = client.get("/api/search", params={"query": "watercolor"}).json()["results"][0]
        assert missing["visuals"] == []
        assert (
            client.put(
                "/api/marks",
                json={
                    "source_id": result["source_id"],
                    "external_id": result["external_id"],
                    "favorite": True,
                    "note": "Keep blue grain",
                },
            ).status_code
            == 200
        )
        path = style_sources.git_sources_root / "Krea2-Style-Explorer" / "app" / "data.js"
        rows = json.loads(
            path.read_text(encoding="utf-8").split("=", 1)[1].strip().removesuffix(";")
        )
        path.write_text("const galleryData = " + json.dumps(rows[::-1]) + ";", encoding="utf-8")
        assert client.post("/api/import").json()["failed"] == []
        favorite = client.get("/api/search", params={"favorites_only": True}).json()["results"]
        assert len(favorite) == 1
        assert favorite[0]["external_id"] == "style:abc123"
        assert favorite[0]["user_note"] == "Keep blue grain"


def test_neons_preserves_axes_tags_and_negative_without_claiming_model_support(style_sources):
    database = PromptDatabase(style_sources.database_path)
    import_report(style_sources, database)
    rows = database.search("", source_id="neons-style-explorer")
    assert len(rows) == 3
    by_axis = {row["metadata"]["axis"]: row for row in rows}
    assert by_axis["style"]["kind"] == "style"
    assert by_axis["format"]["kind"] == "modifier"
    assert by_axis["format"]["category"] == "composition/Anime & Manga"
    assert by_axis["finish"]["kind"] == "modifier"
    for row in rows:
        assert row["model_family"] == ""
        assert row["negative_content"] == "photo, muddy colour"
        assert row["metadata"]["tags"] == ["cel_shading"]
        assert row["metadata"]["tags_negative"] == ["photorealistic"]
        assert row["metadata"]["aliases"] == ["flat cel"]
        assert row["metadata"]["image_paths"] == []
        assert row["metadata"]["compatibility"] == "untested"


@pytest.mark.parametrize(
    "replacement",
    [
        "const galleryData = []; alert('must not execute');",
        "const galleryData = [null];",
        'const galleryData = [{"id":"../escape","folder":"1","prompt":"blue"}];',
        'const galleryData = [{"id":"abc123","folder":"../1","prompt":"blue"}];',
        'const galleryData = [{"id":"abc123","folder":"1","prompt":null}];',
        "const galleryData = [];",
        "const galleryData = "
        + json.dumps(
            [{"id": "abc123", "folder": "1", "prompt": "blue"}] * 2,
        )
        + ";",
    ],
)
def test_invalid_krea_update_preserves_index_and_other_sources(style_sources, replacement):
    database = PromptDatabase(style_sources.database_path)
    import_report(style_sources, database)
    path = style_sources.git_sources_root / "Krea2-Style-Explorer" / "app" / "data.js"
    path.write_text(replacement, encoding="utf-8")
    report = import_report(style_sources, database)
    assert report["failed"][0]["source_id"] == "krea2-style-explorer"
    assert report["sources"]["neons-style-explorer"] == 3
    assert len(database.search("", source_id="krea2-style-explorer")) == 2


@pytest.mark.parametrize("fault", ["schema", "styles", "axis", "duplicate", "missing"])
def test_invalid_neons_update_preserves_index(style_sources, fault):
    database = PromptDatabase(style_sources.database_path)
    import_report(style_sources, database)
    path = (
        style_sources.git_sources_root
        / "ComfyUI-NeonsStyleExplorer"
        / "styles"
        / "01_anime_manga.json"
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    if fault == "schema":
        data["schema"] = 2
    elif fault == "styles":
        data["styles"] = [None]
    elif fault == "axis":
        data["styles"][0]["axis"] = "unknown"
    elif fault == "duplicate":
        data["styles"].append(data["styles"][0])
    if fault == "missing":
        path.unlink()
    else:
        path.write_text(json.dumps(data), encoding="utf-8")
    report = import_report(style_sources, database)
    assert report["failed"][0]["source_id"] == "neons-style-explorer"
    assert report["sources"]["krea2-style-explorer"] == 2
    assert len(database.search("", source_id="neons-style-explorer")) == 3


def test_krea_media_rejects_escape_and_non_images(style_sources, tmp_path):
    source_id = "krea2-style-explorer"
    for path in ("../secret.webp", "/secret.webp", "app/data.js", "images/1/missing.webp"):
        assert resolve_media_path(style_sources, source_id, "original", path) is None
    assert resolve_media_path(style_sources, source_id, "unknown", "images/1/abc123.webp") is None
    outside = tmp_path / "outside.webp"
    Image.new("RGB", (16, 16), "red").save(outside)
    preview = (
        style_sources.git_sources_root / "Krea2-Style-Explorer" / "images" / "1" / "abc123.webp"
    )
    preview.unlink()
    preview.symlink_to(outside)
    assert resolve_media_path(style_sources, source_id, "original", "images/1/abc123.webp") is None
    database = PromptDatabase(style_sources.database_path)
    import_report(style_sources, database)
    assert database.search("cyanotype")[0]["metadata"]["image_paths"] == []
