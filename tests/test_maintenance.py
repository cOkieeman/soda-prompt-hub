from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from prompt_hub.creative import CreativeStore
from prompt_hub.database import PromptDatabase
from prompt_hub.embedding_index import EmbeddingIndexStore
from prompt_hub.maintenance import BackupManager, MaintenanceError, verify_backup


def _seed_backup_roots(settings) -> dict[str, str]:
    PromptDatabase(settings.database_path).initialize()
    private_file = settings.library_root / "private" / "notes" / "soda.txt"
    private_file.parent.mkdir(parents=True, exist_ok=True)
    private_file.write_text("personal note", encoding="utf-8")
    remote_nodes = settings.remote_nodes_root / "nodes.json"
    remote_nodes.write_text(
        json.dumps({"format": "soda-remote-nodes-v1", "nodes": []}),
        encoding="utf-8",
    )
    remote_catalog = settings.remote_nodes_root / "lora-catalog" / "catalog.json"
    remote_catalog.parent.mkdir(parents=True)
    remote_catalog.write_text('{"count":1}', encoding="utf-8")
    remote_preview = settings.remote_nodes_root / "lora-previews" / "cache" / "000.png"
    remote_preview.parent.mkdir(parents=True)
    remote_preview.write_bytes(b"rebuildable-preview")
    embedding = EmbeddingIndexStore(settings.embedding_index_root)
    embedding.initialize()
    workflow_profile = settings.workflow_profiles_root / "anima-mansui" / "profile.json"
    workflow_profile.parent.mkdir(parents=True)
    workflow_profile.write_text('{"profile_id":"anima-mansui"}', encoding="utf-8")
    project = CreativeStore(settings.database_path)
    project.initialize()
    project.create_project({"title": "备份验收项目", "brief_zh": "黄昏图书馆"})
    expected_roots = {
        "test-results/prompt-hub/result.json": "result",
        "datasets/workspaces/dataset-test/workspace.json": "workspace",
        "datasets/project-sources/project-test/.prompt-hub-lineage.json": "lineage",
        "exports/datasets/version-test/manifest.json": "export",
        "lora-projects/lora-test/project.json": "lora",
    }
    for relative_path, content in expected_roots.items():
        path = settings.library_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return expected_roots


def test_backup_verify_and_restore_to_new_directory(settings, tmp_path) -> None:
    expected_roots = _seed_backup_roots(settings)

    backup_path = tmp_path / "backups" / "snapshot-1"
    created = BackupManager(settings).create(backup_path)
    assert created["ok"] is True
    manifest = created["manifest"]
    assert manifest["format"] == "soda-prompt-hub-backup-v1"
    assert "sources/git (可从 Git 重建, 只记录 revision)" in manifest["excluded_roots"]
    assert (backup_path / "payload" / "private" / "notes" / "soda.txt").is_file()
    assert (backup_path / "payload" / "remote-nodes" / "nodes.json").is_file()
    assert (backup_path / "payload" / "remote-nodes" / "lora-catalog" / "catalog.json").is_file()
    assert not (backup_path / "payload" / "remote-nodes" / "lora-previews").exists()
    assert (
        backup_path / "payload" / "workflow-profiles" / "anima-mansui" / "profile.json"
    ).is_file()
    for relative_path in expected_roots:
        assert (backup_path / "payload" / relative_path).is_file()

    verified = verify_backup(backup_path)
    assert verified["ok"] is True
    assert all(item["integrity"] == "ok" for item in verified["sqlite"])

    restored = tmp_path / "restored-library"
    outcome = BackupManager(settings).restore_to_new_directory(backup_path, restored)
    assert outcome["ok"] is True
    assert (restored / "private" / "notes" / "soda.txt").read_text() == "personal note"
    assert (restored / "remote-nodes" / "nodes.json").is_file()
    assert (restored / "database" / "prompt-library.sqlite").is_file()
    assert (restored / "indexes" / "embeddings" / "embeddings.sqlite").is_file()
    assert (restored / "workflow-profiles" / "anima-mansui" / "profile.json").is_file()
    for relative_path, content in expected_roots.items():
        assert (restored / relative_path).read_text(encoding="utf-8") == content
    restored_projects = CreativeStore(restored / "database" / "prompt-library.sqlite")
    assert restored_projects.list_projects()[0]["title"] == "备份验收项目"


def test_backup_rejects_tampering_and_nonempty_restore_target(settings, tmp_path) -> None:
    PromptDatabase(settings.database_path).initialize()
    backup_path = tmp_path / "backups" / "snapshot-2"
    BackupManager(settings).create(backup_path)
    manifest = json.loads((backup_path / "manifest.json").read_text(encoding="utf-8"))
    first = Path(manifest["files"][0]["path"])
    (backup_path / "payload" / first).write_bytes(b"tampered")
    assert verify_backup(backup_path)["ok"] is False
    with pytest.raises(MaintenanceError, match="校验失败"):
        BackupManager(settings).restore_to_new_directory(
            backup_path,
            tmp_path / "restored",
        )

    clean_backup = tmp_path / "backups" / "snapshot-3"
    BackupManager(settings).create(clean_backup)
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(MaintenanceError, match="为空"):
        BackupManager(settings).restore_to_new_directory(clean_backup, nonempty)


def test_backup_rejects_low_disk_without_leaving_partial_directory(
    settings,
    tmp_path,
    monkeypatch,
) -> None:
    PromptDatabase(settings.database_path).initialize()
    destination = tmp_path / "backups" / "no-space"
    monkeypatch.setattr(
        "prompt_hub.maintenance.shutil.disk_usage",
        lambda _path: SimpleNamespace(free=0),
    )

    with pytest.raises(MaintenanceError, match="磁盘剩余空间不足"):
        BackupManager(settings).create(destination)

    assert not destination.exists()
    assert not list(destination.parent.glob(f".{destination.name}.tmp-*"))
