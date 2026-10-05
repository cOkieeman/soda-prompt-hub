from __future__ import annotations

import json
import shutil
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import discover_sources, import_report
from prompt_hub.media import resolve_media_path
from prompt_hub.source_sync import SourceSyncService


def mapping(settings, path):
    config = settings.library_root / "sources/local-sources.json"
    config.write_text(
        json.dumps(
            {
                "format": "soda-local-sources-v1",
                "sources": {"anima-style-explorer": {"path": str(path)}},
            }
        ),
        encoding="utf-8",
    )


def test_external_archive_without_git_is_indexed_and_never_updated(settings, tmp_path, monkeypatch):
    root = tmp_path / "large local library"
    (root / "app").mkdir(parents=True)
    (root / "images/1").mkdir(parents=True)
    data = root / "app/data.js"
    data.write_text(
        'const galleryData = [{"id":1,"name":"artist (name)","p":1}];', encoding="utf-8"
    )
    image = root / "images/1/1.webp"
    Image.new("RGB", (8, 8), "red").save(image)
    mapping(settings, root)
    git = Mock(side_effect=AssertionError("Local mappings must not invoke Git"))
    monkeypatch.setattr("prompt_hub.source_sync._git", git)
    monkeypatch.setattr("prompt_hub.importers._git_commit", git)
    database = PromptDatabase(settings.database_path)
    spec = next(s for s in discover_sources(settings) if s.source_id == "anima-style-explorer")
    service = SourceSyncService(settings, database, sources=[spec])
    before = data.read_bytes(), image.read_bytes()
    assert service.status()[0]["status"] == "local"
    assert service.clone(spec.source_id)["status"] == "skipped_local"
    assert service.job({"clone_missing": True}, Mock())["entry_counts"] == {spec.source_id: 1}
    assert not git.called
    row = database.search("artist")[0]
    assert row["external_id"] == "style:1"
    assert row["source_url"] == spec.url
    assert database.list_sources()[0]["source_type"] == "local"
    assert resolve_media_path(settings, spec.source_id, "thumbnail", "images/1/1.webp") == image
    assert before == (data.read_bytes(), image.read_bytes())


def test_disconnected_local_mapping_never_clones(settings, tmp_path, monkeypatch):
    mapping(settings, tmp_path / "not-mounted")
    git = Mock(side_effect=AssertionError("Do not clone a missing local mapping"))
    monkeypatch.setattr("prompt_hub.source_sync._git", git)
    spec = next(s for s in discover_sources(settings) if s.source_id == "anima-style-explorer")
    service = SourceSyncService(settings, PromptDatabase(settings.database_path), sources=[spec])
    assert service.job({"clone_missing": True}, Mock())["missing"] == 1
    assert service.clone(spec.source_id)["status"] == "skipped_local"
    assert not git.called


@pytest.mark.parametrize("raw", ["{broken", "[]", '{"format":"unknown","sources":{}}'])
def test_invalid_mapping_disables_download_without_breaking_api(settings, raw, monkeypatch):
    (settings.library_root / "sources/local-sources.json").write_text(raw, encoding="utf-8")
    git = Mock(side_effect=AssertionError("Malformed mapping must not trigger downloads"))
    monkeypatch.setattr("prompt_hub.source_sync._git", git)
    sources = discover_sources(settings)
    assert all(s.local_only and s.local_error for s in sources)
    service = SourceSyncService(settings, PromptDatabase(settings.database_path), reindexer=dict)
    assert service.job({"clone_missing": True}, Mock())["failed"] == 9
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/sources/sync-status").status_code == 200
        assert client.post("/api/import").status_code == 200
    assert not git.called


def test_animadex_external_catalogue_mapping_does_not_modify_upstream(source_tree, tmp_path):
    source = source_tree.git_sources_root / "AnimaDex"
    external = tmp_path / "external-data"
    shutil.copytree(source / "samples", external)
    (external / "import").mkdir()
    for name in ("characters.csv", "artists.csv"):
        shutil.move(str(external / name), external / "import" / name)
    for name in ("characters", "artists", "copyrights"):
        if (external / "images" / name).is_dir():
            shutil.move(str(external / "images" / name), external / name)
    (source_tree.library_root / "sources/local-sources.json").write_text(
        json.dumps(
            {
                "format": "soda-local-sources-v1",
                "sources": {"animadex": {"path": str(source), "data_path": str(external)}},
            }
        ),
        encoding="utf-8",
    )
    database = PromptDatabase(source_tree.database_path)
    import_report(source_tree, database)
    rows = database.search("", source_id="animadex")
    assert len(rows) == 3
    row = next(r for r in rows if r["kind"] == "character_reference")
    assert row["metadata"]["image_paths"][0].startswith("catalogue/")
    assert resolve_media_path(
        source_tree, "animadex", "thumbnail", row["metadata"]["image_paths"][0]
    ).is_file()
    assert not (source / "config.toml").exists()
    shutil.rmtree(external / "import")
    report = import_report(source_tree, database)
    assert (
        next(r for r in report["failed"] if r["source_id"] == "animadex")["status"] == "load_error"
    )
    assert len(database.search("", source_id="animadex")) == 3
