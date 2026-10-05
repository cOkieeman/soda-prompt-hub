from __future__ import annotations

import json
import os
import sqlite3
from contextlib import ExitStack, contextmanager, suppress
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from PIL import Image, ImageOps

from prompt_hub.comfy_results import (
    INVALID_METADATA_NUMBER_WARNING,
    MAX_COMFY_IMAGE_BYTES,
    ComfyResultError,
    inspect_comfy_image,
)
from prompt_hub.generation_evidence import EXTRACTOR_VERSION, inspect_generation_evidence
from prompt_hub.schema_migrations import record_schema_migration

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

    from prompt_hub.background_jobs import JobContext
    from prompt_hub.config import Settings

GALLERY_KINDS = {"work", "reference"}
REFERENCE_PURPOSES = {"style", "composition", "action", "lighting", "scene", "all"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_ANALYSIS_BYTES = 100_000
GALLERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS gallery_roots (
    root_id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('work', 'reference')),
    recursive INTEGER NOT NULL DEFAULT 1,
    last_scan_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gallery_assets (
    asset_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('work', 'reference')),
    title TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    albums_json TEXT NOT NULL DEFAULT '[]',
    favorite INTEGER NOT NULL DEFAULT 0,
    project_id TEXT NOT NULL DEFAULT '',
    image_json TEXT NOT NULL,
    analysis_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS gallery_assets_kind_updated
ON gallery_assets(kind, updated_at DESC);
CREATE TABLE IF NOT EXISTS gallery_origins (
    root_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    asset_id TEXT NOT NULL REFERENCES gallery_assets(asset_id),
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    seen_scan TEXT NOT NULL DEFAULT '',
    missing INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (root_id, relative_path)
);
CREATE INDEX IF NOT EXISTS gallery_origins_asset ON gallery_origins(asset_id);
CREATE TABLE IF NOT EXISTS gallery_exclusions (
    sha256 TEXT PRIMARY KEY,
    removed_at TEXT NOT NULL
);
"""


class GalleryError(ValueError):
    pass


class GalleryStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = settings.database_path
        self.library_root = settings.library_root.expanduser().resolve()
        self.root = self.library_root / "gallery"
        self.original_root = self.root / "original"
        self.thumbnail_root = self.root / "thumbnail"
        self._evidence_lock = RLock()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self._validate_storage()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.original_root.mkdir(parents=True, exist_ok=True)
        self.thumbnail_root.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(GALLERY_SCHEMA)
            record_schema_migration(connection, "gallery", 1, "Local mapped gallery and provenance")
            record_schema_migration(
                connection, "gallery", 2, "Gallery index deletion and scan exclusions"
            )
            connection.commit()

    def register_root(self, values: Mapping[str, Any]) -> dict[str, Any]:
        kind = _valid_kind(str(values.get("kind", "reference")))
        raw_path = Path(str(values.get("path", ""))).expanduser()
        if not raw_path.is_absolute():
            message = "请选择可访问的绝对目录路径"
            raise GalleryError(message)
        path = raw_path.resolve()
        if not path.is_dir():
            message = "画廊目录不存在或无法读取"
            raise GalleryError(message)
        if path == Path(path.anchor) or path == Path.home().resolve():
            message = "请勿登记系统根目录或整个个人主目录"
            raise GalleryError(message)
        own_root = self.root.resolve()
        if path.is_relative_to(own_root) or own_root.is_relative_to(path):
            message = "画廊来源目录不能包含 Hub 的画廊派生目录"
            raise GalleryError(message)
        with self.connect() as connection:
            known = connection.execute(
                "SELECT * FROM gallery_roots WHERE path = ?", (str(path),)
            ).fetchone()
            if known is not None:
                return _root_from_row(known)
            root_id = f"gallery-root-{uuid4().hex}"
            connection.execute(
                "INSERT INTO gallery_roots (root_id, path, label, kind, recursive, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    root_id,
                    str(path),
                    str(values.get("label", "")).strip()[:180] or path.name,
                    kind,
                    int(bool(values.get("recursive", True))),
                    _now(),
                ),
            )
            connection.commit()
        return self.require_root(root_id)

    def list_roots(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM gallery_roots ORDER BY created_at").fetchall()
        return [_root_from_row(row) for row in rows]

    def require_root(self, root_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM gallery_roots WHERE root_id = ?", (root_id,)
            ).fetchone()
        if row is None:
            raise KeyError(root_id)
        return _root_from_row(row)

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        self._refresh_generation_evidence(asset_id)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
        return self._decorate(row) if row is not None else None

    def require_asset(self, asset_id: str) -> dict[str, Any]:
        asset = self.get_asset(asset_id)
        if asset is None:
            raise KeyError(asset_id)
        return asset

    def list_assets(
        self,
        *,
        kind: str = "all",
        q: str = "",
        album: str = "",
        model: str = "",
        lora: str = "",
        favorite: bool = False,
        offset: int = 0,
        limit: int = 48,
    ) -> dict[str, Any]:
        self._refresh_generation_evidence()
        conditions = ["1 = 1"]
        values: list[Any] = []
        if kind != "all":
            conditions.append("kind = ?")
            values.append(_valid_kind(kind))
        if q.strip():
            conditions.append(
                "(title LIKE ? ESCAPE '\\' OR note LIKE ? ESCAPE '\\' "
                "OR author LIKE ? ESCAPE '\\' OR tags_json LIKE ? ESCAPE '\\')"
            )
            escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            values.extend([f"%{escaped}%"] * 4)
        if album:
            conditions.append("EXISTS (SELECT 1 FROM json_each(albums_json) WHERE value = ?)")
            values.append(album)
        if favorite:
            conditions.append("favorite = 1")
        if model:
            conditions.append(
                "(EXISTS (SELECT 1 FROM json_each(image_json, "
                "'$.metadata.generation_evidence.final_generation.models') "
                "WHERE json_extract(value, '$.name') = ? "
                "AND json_extract(value, '$.kind') IN ('checkpoint', 'diffusion_model')) "
                "OR (json_extract(image_json, '$.metadata.source') = 'parameters' "
                "AND json_extract(image_json, '$.metadata.checkpoint') = ?))"
            )
            values.extend([model, model])
        if lora:
            conditions.append(
                "EXISTS (SELECT 1 FROM json_each(image_json, "
                "'$.metadata.generation_evidence.final_generation.loras') "
                "WHERE json_extract(value, '$.name') = ?)"
            )
            values.append(lora)
        clause = " AND ".join(conditions)
        offset, limit = max(0, offset), min(200, max(1, limit))
        with self.connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM gallery_assets WHERE {clause}", values
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM gallery_assets WHERE {clause} "
                "ORDER BY updated_at DESC, rowid DESC LIMIT ? OFFSET ?",
                [*values, limit, offset],
            ).fetchall()
        return {
            "items": [self._decorate(row, include_raw=False) for row in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    def list_albums(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT DISTINCT value FROM gallery_assets, json_each(albums_json) ORDER BY value"
            ).fetchall()
        return [str(row[0]) for row in rows]

    def list_facets(self) -> dict[str, list[str]]:
        """Return names recorded in files, never inferred from image appearance."""
        self._refresh_generation_evidence()
        with self.connect() as connection:
            models = connection.execute(
                "SELECT DISTINCT json_extract(m.value, '$.name') AS name "
                "FROM gallery_assets, json_each(image_json, "
                "'$.metadata.generation_evidence.final_generation.models') m WHERE "
                "json_extract(m.value, '$.kind') IN ('checkpoint', 'diffusion_model') "
                "UNION SELECT json_extract(image_json, '$.metadata.checkpoint') AS name "
                "FROM gallery_assets WHERE json_extract(image_json, '$.metadata.source') = "
                "'parameters' ORDER BY name"
            ).fetchall()
            loras = connection.execute(
                "SELECT DISTINCT json_extract(m.value, '$.name') AS name "
                "FROM gallery_assets, json_each(image_json, "
                "'$.metadata.generation_evidence.final_generation.loras') m ORDER BY name"
            ).fetchall()
        return {
            "models": [str(row[0]) for row in models if isinstance(row[0], str) and row[0]],
            "loras": [str(row[0]) for row in loras if isinstance(row[0], str) and row[0]],
        }

    def delete_asset(self, asset_id: str) -> dict[str, Any]:
        """Delete the Hub index entry, never the owned or mapped image files."""
        self._validate_storage()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT sha256 FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
            if row is None:
                raise KeyError(asset_id)
            connection.execute(
                "INSERT OR REPLACE INTO gallery_exclusions (sha256, removed_at) VALUES (?, ?)",
                (row["sha256"], _now()),
            )
            connection.execute("DELETE FROM gallery_origins WHERE asset_id = ?", (asset_id,))
            connection.execute("DELETE FROM gallery_assets WHERE asset_id = ?", (asset_id,))
            connection.commit()
        return {"asset_id": asset_id, "deleted": True, "source_files_deleted": False}

    def _refresh_generation_evidence(self, asset_id: str = "") -> None:
        """Upgrade cached summaries without touching originals or personal records."""
        condition = (
            "CAST(COALESCE(json_extract(image_json, "
            "'$.metadata.generation_evidence.extractor_version'), 0) AS INTEGER) < ?"
        )
        values: list[Any] = [EXTRACTOR_VERSION]
        if asset_id:
            condition += " AND asset_id = ?"
            values.append(asset_id)
        with self._evidence_lock:
            while True:
                with self.connect() as connection:
                    rows = connection.execute(
                        "SELECT asset_id, image_json FROM gallery_assets "
                        f"WHERE {condition} LIMIT 100",
                        values,
                    ).fetchall()
                if not rows:
                    return
                self._validate_storage()
                updates = []
                for row in rows:
                    image = json.loads(row["image_json"])
                    metadata = image.setdefault("metadata", {})
                    old = metadata.get("generation_evidence", {})
                    evidence = inspect_generation_evidence(
                        metadata.get("prompt"),
                        metadata.get("workflow"),
                        parameters=metadata.get("parameters", ""),
                        saved_metadata=metadata.get("saved_resource_metadata"),
                    )
                    # The raw cached graph has already been normalized to null; retain its warning.
                    if INVALID_METADATA_NUMBER_WARNING in old.get("warnings", []):
                        evidence["warnings"].append(INVALID_METADATA_NUMBER_WARNING)
                    metadata["generation_evidence"] = evidence
                    updates.append((_dump(image), row["asset_id"], row["image_json"]))
                with self.connect() as connection:
                    # Avoid overwriting a concurrent import or project snapshot attachment.
                    connection.executemany(
                        "UPDATE gallery_assets SET image_json = ? "
                        "WHERE asset_id = ? AND image_json = ?",
                        updates,
                    )
                    connection.commit()

    def update_asset(self, asset_id: str, values: Mapping[str, Any]) -> dict[str, Any]:
        current = self.require_asset(asset_id)
        merged = {**current, **values}
        kind = _valid_kind(str(merged["kind"]))
        tags = _clean_strings(merged.get("tags", []))
        albums = _clean_strings(merged.get("albums", []))
        with self.connect() as connection:
            connection.execute(
                "UPDATE gallery_assets SET kind = ?, title = ?, note = ?, author = ?, "
                "source_url = ?, tags_json = ?, albums_json = ?, favorite = ?, project_id = ?, "
                "updated_at = ? WHERE asset_id = ?",
                (
                    kind,
                    str(merged.get("title", ""))[:300],
                    str(merged.get("note", ""))[:6000],
                    str(merged.get("author", ""))[:300],
                    str(merged.get("source_url", ""))[:2000],
                    _dump(tags),
                    _dump(albums),
                    int(bool(merged.get("favorite", False))),
                    str(merged.get("project_id", ""))[:180],
                    _now(),
                    asset_id,
                ),
            )
            connection.commit()
        return self.require_asset(asset_id)

    def confirm_analysis(self, asset_id: str, analysis: Mapping[str, Any]) -> dict[str, Any]:
        asset = self.require_asset(asset_id)
        if analysis.get("source_sha256", asset["sha256"]) != asset["sha256"]:
            message = "分析对应的图片已改变，请重新分析"
            raise GalleryError(message)
        if asset["availability"] != "online":
            message = "原图已离线或发生变化，不能确认旧分析"
            raise GalleryError(message)
        data = dict(analysis)
        encoded = _dump(data)
        if len(encoded.encode("utf-8")) > MAX_ANALYSIS_BYTES:
            message = "分析内容过长"
            raise GalleryError(message)
        # Confirmation stores a separate interpretation, never generation facts or manual fields.
        data["confirmed"] = True
        data["confirmed_at"] = _now()
        data["source_sha256"] = asset["sha256"]
        with self.connect() as connection:
            connection.execute(
                "UPDATE gallery_assets SET analysis_json = ?, updated_at = ? WHERE asset_id = ?",
                (_dump(data), _now(), asset_id),
            )
            connection.commit()
        return self.require_asset(asset_id)

    def import_bytes(self, raw: bytes, *, filename: str, kind: str = "work") -> dict[str, Any]:
        kind = _valid_kind(kind)
        inspected = _inspect(raw, filename)
        digest = inspected["sha256"]
        original_name = f"{digest}{inspected.pop('suffix')}"
        original = self.original_root / original_name
        self._validate_storage_path(original)
        if not original.is_file():
            self._write_owned_bytes(original, raw)
        asset_id, _ = self._save_image(inspected, filename=filename, kind=kind, raw=raw)
        stat = original.stat()
        self._record_origin(
            root_id="",
            relative=original_name,
            asset_id=asset_id,
            size=stat.st_size,
            mtime=stat.st_mtime_ns,
            scan="upload",
        )
        return self.require_asset(asset_id)

    def scan_root(self, root_id: str, *, context: JobContext | None = None) -> dict[str, Any]:
        root = self.require_root(root_id)
        source = Path(root["path"])
        if not _safe_root(source):
            message = "画廊目录离线或已被替换，请恢复原目录后重试"
            raise GalleryError(message)
        scan = uuid4().hex
        report: dict[str, Any] = {
            "root_id": root_id,
            "scanned": 0,
            "imported": 0,
            "duplicates": 0,
            "unchanged": 0,
            "excluded": 0,
            "failed": [],
            "source_mode": "read-only-mapping",
        }
        for path in _iter_images(source, recursive=root["recursive"], context=context):
            _checkpoint(context, report["scanned"], 0, "正在增量索引画廊，原图保持原位")
            report["scanned"] += 1
            relative = path.relative_to(source).as_posix()
            try:
                self._scan_image(root, path, relative, scan, report)
            except (GalleryError, OSError) as error:
                report["failed"].append({"path": relative, "error": str(error)})
        _checkpoint(context, report["scanned"], report["scanned"], "正在完成画廊索引")
        with self.connect() as connection:
            connection.execute(
                "UPDATE gallery_origins SET missing = 1 WHERE root_id = ? AND seen_scan != ?",
                (root_id, scan),
            )
            connection.execute(
                "UPDATE gallery_roots SET last_scan_at = ? WHERE root_id = ?", (_now(), root_id)
            )
            connection.commit()
        return report

    def _scan_image(
        self,
        root: Mapping[str, Any],
        path: Path,
        relative: str,
        scan: str,
        report: dict[str, Any],
    ) -> None:
        source = Path(root["path"])
        candidate = _safe_child(source, relative)
        if candidate is None:
            message = "图片路径越界或不可读取"
            raise GalleryError(message)
        stat = candidate.stat()
        with self.connect() as connection:
            known = connection.execute(
                "SELECT * FROM gallery_origins WHERE root_id = ? AND relative_path = ?",
                (root["root_id"], relative),
            ).fetchone()
        if known is not None and (known["size_bytes"], known["mtime_ns"]) == (
            stat.st_size,
            stat.st_mtime_ns,
        ):
            asset = self.require_asset(known["asset_id"])
            evidence = asset.get("metadata", {}).get("generation_evidence", {})
            current_summary = all(key in evidence for key in ("models", "prompts", "sampling"))
            if (
                current_summary
                and self.resolve_asset_path(asset["asset_id"], "thumbnail") is not None
            ):
                self._record_origin(
                    root_id=root["root_id"],
                    relative=relative,
                    asset_id=known["asset_id"],
                    size=stat.st_size,
                    mtime=stat.st_mtime_ns,
                    scan=scan,
                )
                report["unchanged"] += 1
                return
        if stat.st_size > MAX_COMFY_IMAGE_BYTES:
            message = "图片超过 50 MiB 限制"
            raise GalleryError(message)
        raw = candidate.read_bytes()
        after = candidate.stat()
        if (stat.st_size, stat.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            message = "图片正在写入，请稍后重新扫描"
            raise GalleryError(message)
        inspected = _inspect(raw, path.name)
        with self.connect() as connection:
            excluded = connection.execute(
                "SELECT 1 FROM gallery_exclusions WHERE sha256 = ?", (inspected["sha256"],)
            ).fetchone()
        if excluded is not None:
            report["excluded"] += 1
            return
        inspected.pop("suffix")
        asset_id, created = self._save_image(
            inspected, filename=path.name, kind=root["kind"], raw=raw, respect_exclusions=True
        )
        if not asset_id:
            report["excluded"] += 1
            return
        self._record_origin(
            root_id=root["root_id"],
            relative=relative,
            asset_id=asset_id,
            size=after.st_size,
            mtime=after.st_mtime_ns,
            scan=scan,
        )
        report["imported" if created else "duplicates"] += 1

    def _save_image(
        self,
        inspected: dict[str, Any],
        *,
        filename: str,
        kind: str,
        raw: bytes,
        respect_exclusions: bool = False,
    ) -> tuple[str, bool]:
        digest = inspected["sha256"]
        thumbnail = self.thumbnail_root / f"{digest}.webp"
        self._validate_storage_path(thumbnail)
        if not thumbnail.is_file():
            with Image.open(BytesIO(raw)) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                image.thumbnail((640, 640), Image.Resampling.LANCZOS)
                output = BytesIO()
                image.save(output, "WEBP", quality=84, method=4)
                self._write_owned_bytes(thumbnail, output.getvalue())
        image_data = {
            **inspected,
            "filename": Path(filename).name[:180],
            "thumbnail_name": thumbnail.name,
        }
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if respect_exclusions:
                # Recheck under the write lock: deletion may happen during image inspection.
                if connection.execute(
                    "SELECT 1 FROM gallery_exclusions WHERE sha256 = ?", (digest,)
                ).fetchone():
                    return "", False
            else:
                # Only an explicit upload cancels a prior scan exclusion, atomically with import.
                connection.execute("DELETE FROM gallery_exclusions WHERE sha256 = ?", (digest,))
            known = connection.execute(
                "SELECT asset_id, image_json FROM gallery_assets WHERE sha256 = ?", (digest,)
            ).fetchone()
            if known is not None:
                existing_image = json.loads(known["image_json"])
                # Re-inspection upgrades summaries without touching notes, snapshots or identity.
                existing_image.update(inspected)
                connection.execute(
                    "UPDATE gallery_assets SET image_json = ? WHERE asset_id = ?",
                    (_dump(existing_image), known["asset_id"]),
                )
                connection.commit()
                return str(known["asset_id"]), False
            asset_id = f"gallery-{uuid4().hex}"
            now = _now()
            connection.execute(
                "INSERT INTO gallery_assets "
                "(asset_id, sha256, kind, title, image_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (asset_id, digest, kind, Path(filename).stem[:300], _dump(image_data), now, now),
            )
            connection.commit()
        return asset_id, True

    def _record_origin(
        self, *, root_id: str, relative: str, asset_id: str, size: int, mtime: int, scan: str
    ) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not connection.execute(
                "SELECT 1 FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone():
                return
            connection.execute(
                "INSERT INTO gallery_origins "
                "(root_id, relative_path, asset_id, size_bytes, mtime_ns, seen_scan) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (root_id, relative_path) "
                "DO UPDATE SET asset_id = excluded.asset_id, size_bytes = excluded.size_bytes, "
                "mtime_ns = excluded.mtime_ns, seen_scan = excluded.seen_scan, missing = 0",
                (root_id, relative, asset_id, size, mtime, scan),
            )
            connection.commit()

    def _validate_storage(self) -> None:
        owned = (self.library_root, self.root, self.original_root, self.thumbnail_root)
        try:
            configured = self.settings.library_root.expanduser().resolve()
            valid = configured == self.library_root and all(
                path.resolve() == path
                and not path.is_symlink()
                and (not path.exists() or path.is_dir())
                for path in owned
            )
        except (OSError, RuntimeError) as error:
            raise GalleryError(str(error)) from error
        if not valid:
            message = "画廊派生目录已被替换或指向库外，已停止写入"
            raise GalleryError(message)

    def _validate_storage_path(self, path: Path) -> None:
        self._validate_storage()
        if (
            path.parent not in {self.original_root, self.thumbnail_root}
            or path.is_symlink()
            or path.resolve() != path
        ):
            message = "画廊派生文件路径越界或已被替换，已停止写入"
            raise GalleryError(message)

    @contextmanager
    def _owned_directory(self, parent: Path) -> Iterator[int | None]:
        # POSIX pins each owned directory without following replaced directory symlinks.
        if os.open not in os.supports_dir_fd or not hasattr(os, "O_DIRECTORY"):
            yield None
            return
        flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
        with ExitStack() as stack:
            descriptor = os.open(self.library_root, flags)
            stack.callback(os.close, descriptor)
            for name in ("gallery", parent.name):
                descriptor = os.open(name, flags, dir_fd=descriptor)
                stack.callback(os.close, descriptor)
            yield descriptor

    def _write_owned_bytes(self, path: Path, raw: bytes) -> None:
        self._validate_storage_path(path)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        self._validate_storage_path(temporary)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            with self._owned_directory(path.parent) as directory:
                created = False
                try:
                    descriptor = os.open(
                        temporary.name if directory is not None else temporary,
                        flags,
                        0o600,
                        dir_fd=directory,
                    )
                    created = True
                    with os.fdopen(descriptor, "wb") as stream:
                        stream.write(raw)
                    self._validate_storage_path(path)
                    self._validate_storage_path(temporary)
                    if directory is not None:
                        opened = os.fstat(directory)
                        current = path.parent.stat()
                        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                            message = "画廊派生目录在写入期间发生变化，已停止写入"
                            raise GalleryError(message)
                        os.replace(
                            temporary.name, path.name, src_dir_fd=directory, dst_dir_fd=directory
                        )
                    else:
                        temporary.replace(path)
                finally:
                    if created and directory is not None:
                        with suppress(FileNotFoundError):
                            os.unlink(temporary.name, dir_fd=directory)
                    elif created:
                        # Never clean up through a directory that was swapped to a symlink.
                        self._validate_storage_path(temporary)
                        temporary.unlink(missing_ok=True)
        except OSError as error:
            raise GalleryError(str(error)) from error

    def resolve_asset_path(self, asset_id: str, variant: str = "original") -> Path | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
            origins = connection.execute(
                "SELECT o.*, r.path AS root_path FROM gallery_origins o "
                "LEFT JOIN gallery_roots r ON r.root_id = o.root_id "
                "WHERE o.asset_id = ? AND o.missing = 0 ORDER BY o.root_id",
                (asset_id,),
            ).fetchall()
        if row is None:
            return None
        if variant == "thumbnail":
            name = json.loads(row["image_json"])["thumbnail_name"]
            return _safe_child(self.thumbnail_root, name)
        if variant != "original":
            return None
        for origin in origins:
            root = Path(origin["root_path"]) if origin["root_id"] else self.original_root
            candidate = _safe_child(root, origin["relative_path"])
            if candidate is None:
                continue
            try:
                stat = candidate.stat()
            except OSError:
                continue
            if (stat.st_size, stat.st_mtime_ns) == (origin["size_bytes"], origin["mtime_ns"]):
                return candidate
        return None

    def read_asset(self, asset_id: str) -> dict[str, Any]:
        return self.require_asset(asset_id)

    def iter_assets(self) -> Iterator[dict[str, Any]]:
        offset = 0
        while True:
            page = self.list_assets(offset=offset, limit=200)
            yield from page["items"]
            offset += len(page["items"])
            if offset >= page["total"] or not page["items"]:
                return

    def link_project(self, asset_id: str, project: Mapping[str, Any]) -> dict[str, Any]:
        asset = self.require_asset(asset_id)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT image_json FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
            image = json.loads(row["image_json"])
            image["project_snapshot"] = {
                "project_id": project["project_id"],
                "revision": project.get("revision", 1),
                "title": project.get("title", ""),
                "target_profile": project.get("target_profile", ""),
                "generation": project.get("generation", {}),
                "slots": project.get("slots", {}),
                "test_notes": project.get("test_notes", ""),
                "linked_at": _now(),
                "source_sha256": asset["sha256"],
            }
            connection.execute(
                "UPDATE gallery_assets SET project_id = ?, image_json = ?, updated_at = ? "
                "WHERE asset_id = ?",
                (project["project_id"], _dump(image), _now(), asset_id),
            )
            connection.commit()
        return self.require_asset(asset_id)

    def _decorate(self, row: sqlite3.Row, *, include_raw: bool = True) -> dict[str, Any]:
        image = json.loads(row["image_json"])
        if not include_raw:
            metadata = image.get("metadata", {})
            image["metadata"] = {
                key: value
                for key, value in metadata.items()
                if key not in {"prompt", "workflow", "parameters"}
            }
            snapshot = image.get("project_snapshot")
            if isinstance(snapshot, dict):
                image["project_snapshot"] = {
                    key: value for key, value in snapshot.items() if key != "generation"
                }
        asset_id = row["asset_id"]
        with self.connect() as connection:
            origins = connection.execute(
                "SELECT o.root_id, o.relative_path, o.missing, r.path, r.label "
                "FROM gallery_origins o LEFT JOIN gallery_roots r ON r.root_id = o.root_id "
                "WHERE o.asset_id = ? ORDER BY o.root_id, o.relative_path",
                (asset_id,),
            ).fetchall()
        availability = "online" if self.resolve_asset_path(asset_id) else "offline"
        analysis = json.loads(row["analysis_json"])
        stale = bool(analysis) and (
            availability == "offline" or analysis.get("source_sha256") != row["sha256"]
        )
        return {
            **image,
            "safety": image.get("safety", "unrated"),
            **{
                key: row[key]
                for key in (
                    "asset_id",
                    "sha256",
                    "kind",
                    "title",
                    "note",
                    "author",
                    "source_url",
                    "project_id",
                    "created_at",
                    "updated_at",
                )
            },
            "favorite": bool(row["favorite"]),
            "tags": json.loads(row["tags_json"]),
            "albums": json.loads(row["albums_json"]),
            "analysis": {**analysis, "stale": stale} if analysis else {},
            "analysis_stale": stale,
            "availability": availability,
            "origins": [
                {
                    "root_id": origin["root_id"],
                    "source_kind": "directory_mapping" if origin["root_id"] else "manual_upload",
                    "source_root": origin["path"] or "",
                    "relative_path": origin["relative_path"],
                    "label": origin["label"] or "手动上传",
                    "missing": bool(origin["missing"]),
                }
                for origin in origins
            ],
            "original_url": f"/api/gallery/assets/{asset_id}/media/original",
            "thumbnail_url": f"/api/gallery/assets/{asset_id}/media/thumbnail",
        }


def _inspect(raw: bytes, filename: str) -> dict[str, Any]:
    try:
        inspected = inspect_comfy_image(raw, filename=filename)
    except ComfyResultError as error:
        raise GalleryError(str(error)) from error
    metadata = inspected["metadata"]
    metadata["recognition_scope"] = (
        "api_prompt_nodes"
        if isinstance(metadata.get("prompt"), dict)
        else "gui_workflow_preserved"
        if metadata.get("workflow")
        else "parameters"
        if metadata.get("parameters")
        else "none"
    )
    metadata["recognition_note"] = (
        "生成摘要来自图片保存的 API prompt、已支持的 GUI 节点或 parameters；原始记录保留。"
        "不保证完整识别自定义节点、条件执行与运行时替换；没有记录时不猜测底模或 LoRA。"
    )
    return inspected


def _root_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["recursive"] = bool(data["recursive"])
    data["availability"] = "online" if _safe_root(Path(data["path"])) else "offline"
    return data


def _safe_root(root: Path) -> bool:
    try:
        return root.is_absolute() and root.resolve() == root and root.is_dir()
    except (OSError, RuntimeError):
        return False


def _safe_child(root: Path, relative: str) -> Path | None:
    try:
        if not _safe_root(root) or Path(relative).is_absolute() or ".." in Path(relative).parts:
            return None
        candidate = (root / relative).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return candidate
    except (OSError, RuntimeError):
        return None
    return None


def _iter_images(source: Path, *, recursive: bool, context: JobContext | None) -> Iterator[Path]:
    def on_error(error: OSError) -> None:
        raise GalleryError(str(error)) from error

    for directory, dirs, filenames in os.walk(source, followlinks=False, onerror=on_error):
        _checkpoint(context, 0, 0, "正在读取画廊目录")
        dirs[:] = sorted(name for name in dirs if not (Path(directory) / name).is_symlink())
        for name in sorted(filenames):
            _checkpoint(context, 0, 0, "正在读取画廊目录")
            path = Path(directory) / name
            if path.suffix.casefold() in IMAGE_SUFFIXES:
                yield path
        if not recursive:
            break


def _checkpoint(context: JobContext | None, current: int, total: int, message: str) -> None:
    if context is not None:
        context.raise_if_cancelled()
        context.update(current, total, message)


def _valid_kind(kind: str) -> str:
    if kind not in GALLERY_KINDS:
        message = "图片分类必须为 work 或 reference"
        raise GalleryError(message)
    return kind


def _clean_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        message = "标签和图集必须为列表"
        raise GalleryError(message)
    return list(dict.fromkeys(str(item).strip()[:180] for item in value if str(item).strip()))[:100]


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def _now() -> str:
    return datetime.now(UTC).isoformat()
