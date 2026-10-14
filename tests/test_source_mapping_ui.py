from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import discover_sources
from prompt_hub.local_sources import local_source_mapping
from prompt_hub.source_sync import SourceSyncService


def test_mapping_preserves_other_sources_and_never_changes_external_files(settings, tmp_path):
    external = tmp_path / "画风库" / "Clio"
    external.mkdir(parents=True)
    (external / "gallery").mkdir()
    (external / "gallery/manifest.json").write_text('{"sections":{}}')
    catalogue = external / "styles.json"
    catalogue.write_text('[{"name":"A","prompt":"ink drawing"}]')
    config = settings.library_root / "sources/local-sources.json"
    config.write_text(
        json.dumps(
            {
                "format": "soda-local-sources-v1",
                "sources": {"anima-style-explorer": {"path": "/existing"}},
            }
        )
    )
    before = {p.name: p.read_bytes() for p in external.rglob("*") if p.is_file()}
    service = SourceSyncService(settings, PromptDatabase(settings.database_path))
    service.map_local_source("clio-style-preview", external)
    mappings, error = local_source_mapping(settings)
    assert not error
    assert mappings["anima-style-explorer"]["path"] == "/existing"
    assert mappings["clio-style-preview"]["path"] == str(external)
    assert before == {p.name: p.read_bytes() for p in external.rglob("*") if p.is_file()}
    row = next(item for item in service.status() if item["source_id"] == "clio-style-preview")
    assert row["status"] == "local"
    assert row["local_only"] is True


@pytest.mark.parametrize(
    "case", ["unknown", "relative", "missing", "wrong-library", "invalid-config"]
)
def test_invalid_mapping_does_not_overwrite_existing_configuration(settings, tmp_path, case):
    external = tmp_path / "external"
    external.mkdir()
    (external / "gallery").mkdir()
    (external / "gallery/manifest.json").write_text('{"sections":{}}')
    (external / "styles.json").write_text("[]")
    config = settings.library_root / "sources/local-sources.json"
    config.write_text(
        "broken" if case == "invalid-config" else '{"format":"soda-local-sources-v1","sources":{}}'
    )
    before = config.read_bytes()
    source_id = "unknown" if case == "unknown" else "clio-style-preview"
    path = (
        Path("relative")
        if case == "relative"
        else tmp_path / "missing"
        if case == "missing"
        else external
    )
    if case == "wrong-library":
        (external / "styles.json").unlink()
    service = SourceSyncService(settings, PromptDatabase(settings.database_path))
    with pytest.raises(ValueError, match=r"资料源|绝对目录|数据文件|映射配置"):
        service.map_local_source(source_id, path)
    assert config.read_bytes() == before


def test_mapping_endpoint_saves_only_config_and_requires_explicit_reindex(source_tree, tmp_path):
    external = tmp_path / "Clio"
    external.mkdir()
    (external / "gallery").mkdir()
    (external / "gallery/manifest.json").write_text('{"sections":{}}')
    (external / "styles.json").write_text('[{"name":"New","prompt":"new drawing"}]')
    with TestClient(create_app(source_tree)) as client:
        before = client.get("/api/sources").json()
        response = client.put(
            "/api/sources/clio-style-preview/local-mapping", json={"path": str(external)}
        )
        assert response.status_code == 200
        assert response.json()["saved"] is True
        assert client.get("/api/sources").json() == before
        rows = client.get("/api/sources/sync-status").json()
        assert (
            next(item for item in rows if item["source_id"] == "clio-style-preview")["local_only"]
            is True
        )
        assert (
            client.put(
                "/api/sources/unknown/local-mapping", json={"path": str(external)}
            ).status_code
            == 422
        )


def test_source_modes_keep_both_directories_and_existing_index(source_tree, tmp_path):
    managed = next(
        spec.path
        for spec in discover_sources(source_tree)
        if spec.source_id == "clio-style-preview"
    )
    external = tmp_path / "external-clio"
    external.mkdir()
    (external / "gallery").mkdir()
    (external / "gallery/manifest.json").write_text('{"sections":{"krea2":{"images":[]}}}')
    (external / "styles.json").write_text("[]")
    before = {p.relative_to(external): p.read_bytes() for p in external.rglob("*") if p.is_file()}
    with TestClient(create_app(source_tree)) as client:
        indexed = client.get("/api/sources").json()
        assert (
            client.put(
                "/api/sources/clio-style-preview/local-mapping", json={"path": str(external)}
            ).status_code
            == 200
        )
        assert (
            client.put(
                "/api/sources/clio-style-preview/source-mode", json={"mode": "remote"}
            ).status_code
            == 200
        )
        remote = next(
            spec for spec in discover_sources(source_tree) if spec.source_id == "clio-style-preview"
        )
        assert remote.path == managed
        assert not remote.local_only
        rows = client.get("/api/sources/sync-status").json()
        row = next(item for item in rows if item["source_id"] == "clio-style-preview")
        assert row["mapping_path"] == str(external)
        assert row["source_mode"] == "remote"
        assert client.get("/api/sources").json() == indexed
        assert (
            client.put(
                "/api/sources/clio-style-preview/local-mapping", json={"path": row["mapping_path"]}
            ).status_code
            == 200
        )
        local = next(
            spec for spec in discover_sources(source_tree) if spec.source_id == "clio-style-preview"
        )
        assert local.path == external
        assert local.local_only
        assert (
            client.put("/api/sources/unknown/source-mode", json={"mode": "remote"}).status_code
            == 422
        )
        assert (
            client.put(
                "/api/sources/clio-style-preview/source-mode", json={"mode": "invalid"}
            ).status_code
            == 422
        )
    assert before == {
        p.relative_to(external): p.read_bytes() for p in external.rglob("*") if p.is_file()
    }
    mappings, error = local_source_mapping(source_tree)
    assert not error
    assert mappings["clio-style-preview"]["path"] == str(external)
    assert mappings["clio-style-preview"]["mode"] == "local"
