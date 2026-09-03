from __future__ import annotations

import json
from pathlib import Path

import pytest

from prompt_hub.database import PromptDatabase
from prompt_hub.embedding_index import EmbeddingIndexStore
from prompt_hub.maintenance import BackupManager, MaintenanceError, verify_backup


def test_backup_verify_and_restore_to_new_directory(settings, tmp_path) -> None:
    database = PromptDatabase(settings.database_path)
    database.initialize()
    private_file = settings.library_root / "private" / "notes" / "soda.txt"
    private_file.parent.mkdir(parents=True, exist_ok=True)
    private_file.write_text("personal note", encoding="utf-8")
    remote_nodes = settings.remote_nodes_root / "nodes.json"
    remote_nodes.write_text(
        json.dumps({"format": "soda-remote-nodes-v1", "nodes": []}),
        encoding="utf-8",
    )
    embedding = EmbeddingIndexStore(settings.embedding_index_root)
    embedding.initialize()
    workflow_profile = settings.workflow_profiles_root / "anima-mansui" / "profile.json"
    workflow_profile.parent.mkdir(parents=True)
    workflow_profile.write_text('{"profile_id":"anima-mansui"}', encoding="utf-8")

    backup_path = tmp_path / "backups" / "snapshot-1"
    created = BackupManager(settings).create(backup_path)
    assert created["ok"] is True
    manifest = created["manifest"]
    assert manifest["format"] == "soda-prompt-hub-backup-v1"
    assert "sources/git (可从 Git 重建, 只记录 revision)" in manifest["excluded_roots"]
    assert (backup_path / "payload" / "private" / "notes" / "soda.txt").is_file()
    assert (backup_path / "payload" / "remote-nodes" / "nodes.json").is_file()
    assert (
        backup_path / "payload" / "workflow-profiles" / "anima-mansui" / "profile.json"
    ).is_file()

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
