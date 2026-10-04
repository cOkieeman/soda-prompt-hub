from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import discover_sources, import_report
from prompt_hub.media import resolve_media_path
from prompt_hub.source_sync import SourceSyncService
from prompt_hub.style_explorers import discover_style_explorers, load_style_entries


@pytest.fixture
def style_library(settings, monkeypatch):
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "a" * 40)
    root = settings.git_sources_root / "Krea2-Style-Explorer"
    (root / "app").mkdir(parents=True)
    (root / "images/1").mkdir(parents=True)
    (root / "app/data.js").write_text(
        '\ufeffconst galleryData = [{"id":"abc123", "folder":"1", "prompt":"painted garden"}];',
        encoding="utf-8",
    )
    Image.new("RGB", (32, 32), "green").save(root / "images/1/abc123.webp")
    return root


@pytest.mark.usefixtures("style_library")
def test_git_gallery_indexes_without_backup_config_and_keeps_content_and_preview(settings):
    database = PromptDatabase(settings.database_path)
    report = import_report(settings, database)
    assert report["sources"] == {"krea2-style-explorer": 1}
    entry = database.search("painted garden", source_id="krea2-style-explorer")[0]
    assert entry["content"] == "painted garden"
    assert entry["model_family"] == "krea2"
    assert entry["safety"] == "unrated"
    assert entry["metadata"]["image_paths"] == ["images/1/abc123.webp"]
    assert database.list_sources()[0]["source_type"] == "git"
    assert not (settings.library_root / "sources/style-explorers.json").exists()


def test_external_media_is_confined_to_registered_images(settings, style_library):
    source = "krea2-style-explorer"
    assert resolve_media_path(settings, source, "thumbnail", "images/1/abc123.webp") == (
        style_library / "images/1/abc123.webp"
    )
    assert resolve_media_path(settings, source, "original", "../private/secret.webp") is None
    assert resolve_media_path(settings, source, "original", "app/data.js") is None
    assert resolve_media_path(settings, "unknown", "thumbnail", "images/1/abc123.webp") is None


@pytest.mark.parametrize(
    "source_id", ["krea2-style-explorer", "anima-style-explorer", "illustrious-style-explorer"]
)
def test_builtin_galleries_clone_their_github_urls(settings, source_id, monkeypatch):
    spec = next(s for s in discover_sources(settings) if s.source_id == source_id)
    calls = []

    def fake_git(path, *args, **_kwargs):
        calls.append((path, args))
        if args[0] == "clone":
            spec.path.mkdir()
            (spec.path / ".git").mkdir()
        return {
            "rev-parse": "a" * 40 if args[-1] == "HEAD" else "origin/main",
            "branch": "main",
        }.get(args[0], "")

    monkeypatch.setattr("prompt_hub.source_sync._git", fake_git)
    service = SourceSyncService(
        settings, PromptDatabase(settings.database_path), sources=[spec], reindexer=dict
    )
    assert service.status()[0]["status"] == "missing"
    assert service.job({"clone_missing": True}, Mock())["cloned"] == 1
    assert calls[0] == (settings.git_sources_root, ("clone", "--", spec.url, str(spec.path)))
    assert spec.url.startswith("https://github.com/ThetaCursed/")
    assert service.job({}, Mock())["unchanged"] == 1
    assert (spec.path, ("fetch", "--prune", "origin")) in calls
    assert (spec.path, ("merge", "--ff-only", "origin/main")) in calls


def test_import_rejects_executable_javascript_without_overwriting_entries(settings, style_library):
    database = PromptDatabase(settings.database_path)
    import_report(settings, database)
    (style_library / "app/data.js").write_text('fetch("https://example.com");', encoding="utf-8")
    report = import_report(settings, database)
    assert report["failed"][0]["status"] == "load_error"
    assert database.search("painted garden", source_id="krea2-style-explorer")


def test_artist_catalogue_keeps_canonical_tags_and_reports_missing_previews(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app/data.js").write_text(
        'const galleryData = [{"id":123, "p":1, "name":"artist (name)", "post_count":9}];',
        encoding="utf-8",
    )
    entry = load_style_entries(
        "anima-style-explorer", tmp_path, "https://github.com/test", "b" * 40
    )[0]
    assert entry.content == "artist (name)"
    assert entry.model_family == "anima"
    assert entry.metadata["image_refs"] == []


def test_configuration_rejects_relative_paths(settings):
    (settings.library_root / "sources/style-explorers.json").write_text(
        json.dumps(
            {
                "format": "soda-style-explorers-v1",
                "libraries": {
                    "anima-style-explorer": {"path": "relative", "revision": "a" * 40},
                },
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="absolute path"):
        discover_style_explorers(settings)


@pytest.mark.usefixtures("style_library")
def test_gallery_api_search_media_and_favorite_round_trip(settings):
    database = PromptDatabase(settings.database_path)
    import_report(settings, database)
    with TestClient(create_app(settings)) as client:
        result = client.get(
            "/api/search", params={"source_id": "krea2-style-explorer", "has_visual": True}
        ).json()
        entry = result["results"][0]
        response = client.get(entry["visuals"][0]["thumbnail_url"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/webp"
        statuses = client.get("/api/sources/sync-status").json()
        assert len(statuses) == 8
        assert all(item["status"] != "read_only" for item in statuses)
        mark = {
            "source_id": entry["source_id"],
            "external_id": entry["external_id"],
            "favorite": True,
        }
        assert client.put("/api/marks", json=mark).status_code == 200
        favorites = client.get(
            "/api/search", params={"source_id": entry["source_id"], "favorites_only": True}
        ).json()
        assert favorites["count"] == 1
        assert favorites["results"][0]["favorite"] is True


def test_historical_preview_matches_name_not_reused_id(settings, tmp_path):
    current = settings.git_sources_root / "Anima-Style-Explorer"
    backup = tmp_path / "backup"
    for root in (current, backup):
        (root / "app").mkdir(parents=True)
    (current / "app/data.js").write_text(
        'const galleryData = [{"id":1,"p":1,"name":"new artist"},'
        '{"id":2,"p":1,"name":"old artist"}];',
        encoding="utf-8",
    )
    (backup / "app/data.js").write_text(
        'const galleryData = [{"id":1,"p":1,"name":"old artist"}];', encoding="utf-8"
    )
    (backup / "images/1").mkdir(parents=True)
    image = backup / "images/1/1.webp"
    Image.new("RGB", (32, 32), "green").save(image)
    (settings.library_root / "sources/style-explorers.json").write_text(
        json.dumps(
            {
                "format": "soda-style-explorers-v1",
                "libraries": {"anima-style-explorer": {"path": str(backup), "revision": "b" * 40}},
            }
        ),
        encoding="utf-8",
    )
    entries = load_style_entries(
        "anima-style-explorer",
        current,
        "https://github.com/test",
        "a" * 40,
        backup=(backup, "b" * 40),
    )
    assert entries[0].metadata["image_refs"] == []
    assert entries[1].metadata["image_paths"] == ["snapshot/images/1/1.webp"]
    assert entries[1].metadata["preview_revision"] == "b" * 40
    assert (
        resolve_media_path(
            settings, "anima-style-explorer", "thumbnail", "snapshot/images/1/1.webp"
        )
        == image
    )
    assert (
        resolve_media_path(settings, "anima-style-explorer", "thumbnail", "snapshot/../app/data.js")
        is None
    )
    assert image.is_file()

    (current / "images/1").mkdir(parents=True)
    Image.new("RGB", (32, 32), "blue").save(current / "images/1/2.webp")
    entries = load_style_entries(
        "anima-style-explorer",
        current,
        "https://github.com/test",
        "a" * 40,
        backup=(backup, "b" * 40),
    )
    assert entries[1].metadata["image_paths"] == ["images/1/2.webp"]
    assert entries[1].metadata["preview_origin"] == "git"
