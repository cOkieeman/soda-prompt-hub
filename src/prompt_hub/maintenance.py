from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4

if TYPE_CHECKING:
    from prompt_hub.config import Settings

BACKUP_FORMAT = "soda-prompt-hub-backup-v1"
MANIFEST_NAME = "manifest.json"
MIN_FREE_GIB = 5
HTTP_OK = 200
PERSONAL_ROOTS = (
    "private",
    "sources/imports",
    "sources/web",
    "sources/api",
    "test-results",
    "datasets/workspaces",
    "lora-projects",
    "exports",
    "remote-nodes",
    "workflow-profiles",
)
EXCLUDED_ROOTS = (
    "sources/git (可从 Git 重建, 只记录 revision)",
    "thumbnails (可重建)",
    "normalized (可重建)",
    "models (独立管理的大模型权重)",
)


class MaintenanceError(ValueError):
    pass


class BackupManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create(self, destination: Path | None = None) -> dict[str, Any]:
        target = destination or self._default_destination()
        target = target.expanduser().resolve()
        if target.exists():
            raise MaintenanceError("备份目标已存在，请使用新的目录")
        target.parent.mkdir(parents=True, exist_ok=True)
        required_bytes = _selected_size(self.settings.library_root)
        free_bytes = shutil.disk_usage(target.parent).free
        if free_bytes < required_bytes + 256 * 1024 * 1024:
            raise MaintenanceError("备份目标磁盘剩余空间不足")

        temporary = target.parent / f".{target.name}.tmp-{uuid4().hex[:8]}"
        payload = temporary / "payload"
        try:
            payload.mkdir(parents=True, exist_ok=False)
            sqlite_reports = self._snapshot_databases(payload)
            for relative in PERSONAL_ROOTS:
                source = self.settings.library_root / relative
                if source.exists():
                    _copy_tree(source, payload / relative)
            files = _file_manifest(payload)
            manifest = {
                "format": BACKUP_FORMAT,
                "created_at": _now(),
                "source_library_root": str(self.settings.library_root.resolve()),
                "included_roots": ["database", "indexes/embeddings", *PERSONAL_ROOTS],
                "excluded_roots": list(EXCLUDED_ROOTS),
                "sqlite": sqlite_reports,
                "git_sources": _git_source_revisions(self.settings.git_sources_root),
                "files": files,
                "file_count": len(files),
                "total_bytes": sum(item["bytes"] for item in files),
            }
            _write_json(temporary / MANIFEST_NAME, manifest)
            verification = verify_backup(temporary)
            if not verification["ok"]:
                raise MaintenanceError("备份自检失败")
            temporary.rename(target)
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
        return {"backup_path": str(target), **verification}

    def restore_to_new_directory(self, backup_path: Path, destination: Path) -> dict[str, Any]:
        source = backup_path.expanduser().resolve()
        target = destination.expanduser().resolve()
        verification = verify_backup(source)
        if not verification["ok"]:
            raise MaintenanceError("备份校验失败，拒绝恢复")
        if target.exists() and any(target.iterdir()):
            raise MaintenanceError("恢复目标必须是不存在或为空的新目录")
        target.mkdir(parents=True, exist_ok=True)
        _copy_tree(source / "payload", target)
        restored_files = _file_manifest(target)
        expected = {item["path"]: item["sha256"] for item in verification["manifest"]["files"]}
        actual = {item["path"]: item["sha256"] for item in restored_files}
        if actual != expected:
            raise MaintenanceError("恢复后的文件哈希与备份不一致")
        sqlite_reports = _verify_sqlite_payload(target)
        if any(item["integrity"] != "ok" for item in sqlite_reports):
            raise MaintenanceError("恢复后的 SQLite 完整性检查失败")
        return {
            "ok": True,
            "backup_path": str(source),
            "restored_path": str(target),
            "file_count": len(restored_files),
            "sqlite": sqlite_reports,
        }

    def _default_destination(self) -> Path:
        token = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        return self.settings.library_root.parent / "backups" / "prompt-hub" / token

    def _snapshot_databases(self, payload: Path) -> list[dict[str, Any]]:
        sources = (
            (self.settings.database_path, payload / "database" / "prompt-library.sqlite"),
            (
                self.settings.embedding_index_root / "embeddings.sqlite",
                payload / "indexes" / "embeddings" / "embeddings.sqlite",
            ),
        )
        reports = []
        for source, target in sources:
            if not source.is_file():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with (
                sqlite3.connect(source) as source_connection,
                sqlite3.connect(target) as target_connection,
            ):
                source_connection.backup(target_connection)
            integrity = _sqlite_integrity(target, immutable=True)
            if integrity != "ok":
                raise MaintenanceError(f"SQLite 快照完整性失败: {source.name}")
            reports.append(
                {
                    "path": target.relative_to(payload).as_posix(),
                    "integrity": integrity,
                }
            )
        return reports


def verify_backup(backup_path: Path) -> dict[str, Any]:
    root = backup_path.expanduser().resolve()
    manifest_path = root / MANIFEST_NAME
    payload = root / "payload"
    if not manifest_path.is_file() or not payload.is_dir():
        raise MaintenanceError("不是有效的 Prompt Hub 备份目录")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != BACKUP_FORMAT or not isinstance(manifest.get("files"), list):
        raise MaintenanceError("备份 manifest 格式不兼容")
    expected = {str(item["path"]): str(item["sha256"]) for item in manifest["files"]}
    actual_items = _file_manifest(payload)
    actual = {item["path"]: item["sha256"] for item in actual_items}
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    mismatched = sorted(
        path for path in expected.keys() & actual.keys() if expected[path] != actual[path]
    )
    sqlite_reports = _verify_sqlite_payload(payload)
    sqlite_ok = all(item["integrity"] == "ok" for item in sqlite_reports)
    return {
        "ok": not missing and not unexpected and not mismatched and sqlite_ok,
        "manifest": manifest,
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
        "sqlite": sqlite_reports,
    }


def doctor(settings: Settings, *, service_url: str = "http://127.0.0.1:8765") -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(_path_check("library_root", settings.library_root, writable=True))
    checks.append(_path_check("database_parent", settings.database_path.parent, writable=True))
    if settings.database_path.is_file():
        integrity = _sqlite_integrity(settings.database_path)
        checks.append({"name": "database_integrity", "ok": integrity == "ok", "detail": integrity})
    else:
        checks.append({"name": "database_integrity", "ok": False, "detail": "missing"})
    embedding_path = settings.embedding_index_root / "embeddings.sqlite"
    if embedding_path.is_file():
        integrity = _sqlite_integrity(embedding_path)
        checks.append({"name": "embedding_integrity", "ok": integrity == "ok", "detail": integrity})
    else:
        checks.append({"name": "embedding_integrity", "ok": True, "detail": "not created yet"})
    free_gib = shutil.disk_usage(settings.library_root).free / (1024**3)
    checks.append(
        {"name": "disk_free", "ok": free_gib >= MIN_FREE_GIB, "detail": f"{free_gib:.1f} GiB"}
    )
    checks.append(
        {
            "name": "wd14_model",
            "ok": (settings.wd14_model_root / "model.onnx").is_file(),
            "detail": str(settings.wd14_model_root),
        }
    )
    checks.append(_service_check(service_url))
    return {"ok": all(item["ok"] for item in checks), "checked_at": _now(), "checks": checks}


def _copy_tree(source: Path, destination: Path) -> None:
    if source.is_symlink():
        return
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _file_manifest(root: Path) -> list[dict[str, Any]]:
    paths = sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink())
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in paths
    ]


def _selected_size(library_root: Path) -> int:
    selected = [library_root / relative for relative in PERSONAL_ROOTS]
    selected.extend(
        (
            library_root / "database" / "prompt-library.sqlite",
            library_root / "indexes" / "embeddings" / "embeddings.sqlite",
        )
    )
    total = 0
    for root in selected:
        if root.is_file():
            total += root.stat().st_size
        elif root.is_dir():
            total += sum(
                path.stat().st_size
                for path in root.rglob("*")
                if path.is_file() and not path.is_symlink()
            )
    return total


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_integrity(path: Path, *, immutable: bool = False) -> str:
    try:
        immutable_flag = "&immutable=1" if immutable else ""
        with sqlite3.connect(
            f"file:{path}?mode=ro{immutable_flag}",
            uri=True,
        ) as connection:
            row = connection.execute("PRAGMA integrity_check").fetchone()
        return str(row[0]) if row else "no result"
    except sqlite3.Error as error:
        return str(error)


def _verify_sqlite_payload(payload: Path) -> list[dict[str, str]]:
    reports = []
    for relative in ("database/prompt-library.sqlite", "indexes/embeddings/embeddings.sqlite"):
        path = payload / relative
        if path.is_file():
            reports.append({"path": relative, "integrity": _sqlite_integrity(path, immutable=True)})
    return reports


def _git_source_revisions(git_root: Path) -> list[dict[str, str]]:
    revisions = []
    if not git_root.is_dir():
        return revisions
    for repository in sorted(path for path in git_root.iterdir() if path.is_dir()):
        result = subprocess.run(  # noqa: S603
            ["/usr/bin/git", "-C", str(repository), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        revisions.append(
            {
                "name": repository.name,
                "revision": result.stdout.strip() if result.returncode == 0 else "unavailable",
            }
        )
    return revisions


def _path_check(name: str, path: Path, *, writable: bool) -> dict[str, Any]:
    exists = path.is_dir()
    can_write = exists and (not writable or os.access(path, os.W_OK))
    return {"name": name, "ok": exists and can_write, "detail": str(path)}


def _service_check(service_url: str) -> dict[str, Any]:
    try:
        with urlopen(f"{service_url.rstrip('/')}/api/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        ok = response.status == HTTP_OK and payload.get("status") == "ok"
    except (OSError, URLError, ValueError, json.JSONDecodeError) as error:
        return {"name": "service", "ok": False, "detail": str(error)}
    else:
        return {"name": "service", "ok": ok, "detail": service_url}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
