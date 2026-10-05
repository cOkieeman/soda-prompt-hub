from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import unicodedata
import zipfile
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from prompt_hub.background_jobs import (
    JobCancelledError,
    JobContext,
    JobInterruptedError,
)

if TYPE_CHECKING:
    from prompt_hub.config import Settings

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
NEAR_DUPLICATE_DISTANCE = 5
MAX_CAPTION_CHARS = 12000
THUMBNAIL_DIGEST_CHARS = 20
REVIEW_STATUSES = {"pending", "approved", "excluded", "needs_review"}

BROWSE_IMAGE_COUNT_LIMIT = 500
BROWSE_MAX_SUBDIRS = 400
BROWSE_HOME_SHORTCUTS = (("Desktop", "桌面"), ("Pictures", "图片"), ("Downloads", "下载"))
# Linux localizes the directory names above. xdg-user-dirs records the real locations in
# ~/.config/user-dirs.dirs, so 桌面 / ダウンロード / … resolve as well. This stays a separate
# mapping so BROWSE_HOME_SHORTCUTS keeps the shape other callers already expect.
BROWSE_XDG_HOME_KEYS = {
    "Desktop": "XDG_DESKTOP_DIR",
    "Pictures": "XDG_PICTURES_DIR",
    "Downloads": "XDG_DOWNLOAD_DIR",
}
# macOS mounts removable volumes under /Volumes; Linux uses these bases.
BROWSE_VOLUME_BASES = (Path("/Volumes"), Path("/media"), Path("/run/media"), Path("/mnt"))

ARCHIVE_JOB_TYPE = "dataset_archive_import"
ARCHIVE_ALLOWED_SUFFIXES = IMAGE_SUFFIXES | {".txt", ".json"}
ARCHIVE_MAX_ENTRIES = 20_000
ARCHIVE_MAX_SINGLE_ENTRY_BYTES = 4 * 1024**3
ARCHIVE_MAX_TOTAL_BYTES = 16 * 1024**3
ARCHIVE_MAX_COMPRESSION_RATIO = 1000
ARCHIVE_RATIO_MIN_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_UPLOAD_BYTES = 1024**3
_ARCHIVE_NAME_CONTROL_MAX = 31
_ARCHIVE_NAME_DELETE_CODE = 127


class DatasetWorkspaceError(ValueError):
    pass


WORKSPACE_MISSING_MESSAGE = "数据集工作区不存在"


def _source_is_available(source_path: str) -> bool:
    if not source_path:
        return False
    try:
        return Path(source_path).expanduser().is_dir()
    except (OSError, ValueError):
        return False


def _with_source_availability(workspace: dict[str, Any]) -> dict[str, Any]:
    """标注来源是否还在。

    只加在读出来的副本上。不写回 manifest——目录可能只是暂时没挂载。
    把「不在」固化进档案会让重新挂载后仍显示失效。
    """
    workspace["source_available"] = _source_is_available(str(workspace.get("source_path", "")))
    return workspace


class DatasetWorkspaceStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.dataset_workspaces_root
        self._write_lock = Lock()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def register(
        self,
        source_path: Path | str,
        *,
        name: str = "",
        origin: Mapping[str, Any] | None = None,
        source_origin: str = "user_directory",
    ) -> dict[str, Any]:
        source = self._validate_source(source_path)
        existing = self.find_by_source(source)
        if existing is not None:
            if origin is not None:
                return self._update_workspace(existing["workspace_id"], origin=dict(origin))
            return existing
        workspace_id = f"dataset-{uuid4().hex}"
        now = _now()
        workspace = {
            "workspace_id": workspace_id,
            "name": name.strip() or source.name,
            "source_path": str(source),
            "source_mode": "read-only",
            "source_origin": source_origin,
            "status": "registered",
            "current_report": "",
            "summary": {},
            "error": "",
            "origin": dict(origin) if origin is not None else {},
            "created_at": now,
            "updated_at": now,
        }
        directory = self._workspace_directory(workspace_id)
        (directory / "scans").mkdir(parents=True, exist_ok=False)
        (directory / "thumbnails").mkdir()
        self._write_manifest(workspace)
        return workspace

    def get(self, workspace_id: str) -> dict[str, Any] | None:
        path = self._manifest_path(workspace_id)
        if path is None or not path.is_file():
            return None
        return _with_source_availability(_load_json(path))

    def list_workspaces(self) -> list[dict[str, Any]]:
        workspaces = []
        if not self.root.is_dir():
            return workspaces
        for path in self.root.glob("dataset-*/workspace.json"):
            try:
                workspaces.append(_with_source_availability(_load_json(path)))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return sorted(workspaces, key=lambda item: str(item.get("updated_at", "")), reverse=True)

    def require_source(self, workspace_id: str) -> Path:
        """确认来源目录还在。不在就立刻报清楚。

        来源被移走或删掉之后。逐张解析会一张一张地回「图片不存在」。
        52 张就是 52 条各自独立的错误——真正的原因是整个目录不见了。
        这个诊断在逐张那一层被拆散了。所以在队列开始前先问一次。
        """
        workspace = self.get(workspace_id)
        if workspace is None:
            raise DatasetWorkspaceError(WORKSPACE_MISSING_MESSAGE)
        source = str(workspace.get("source_path", ""))
        if not _source_is_available(source):
            raise DatasetWorkspaceError(
                f"数据集来源目录已经不在：{source}。"
                "它可能被移动或删除了。请重新导入，或把目录放回原处。"
            )
        return Path(source)

    def find_by_source(self, source_path: Path) -> dict[str, Any] | None:
        source = str(source_path.resolve())
        return next(
            (item for item in self.list_workspaces() if str(item.get("source_path", "")) == source),
            None,
        )

    def scan_job(self, payload: Mapping[str, Any], context: JobContext) -> dict[str, Any]:
        workspace_id = str(payload.get("workspace_id", ""))
        if not workspace_id:
            raise DatasetWorkspaceError("Dataset scan job is missing workspace_id")
        try:
            return self.scan(workspace_id, context)
        except JobCancelledError:
            self._update_workspace(workspace_id, status="canceled", error="")
            raise
        except JobInterruptedError:
            self._update_workspace(workspace_id, status="queued", error="")
            raise
        except Exception as error:
            self._update_workspace(workspace_id, status="failed", error=str(error)[:1000])
            raise

    def scan(self, workspace_id: str, context: JobContext) -> dict[str, Any]:
        workspace = self.get(workspace_id)
        if workspace is None:
            raise DatasetWorkspaceError("Dataset workspace not found")
        source = self._validate_source(str(workspace["source_path"]))
        self._update_workspace(workspace_id, status="scanning", error="")

        image_paths, caption_paths = _collect_source_files(source)
        context.update(0, len(image_paths), "正在检查数据集文件")
        caption_map = {_caption_key(source, path): path for path in caption_paths}
        image_keys = {_image_key(source, path) for path in image_paths}
        thumbnails_root = self._workspace_directory(workspace_id) / "thumbnails"
        records: list[dict[str, Any]] = []
        for index, image_path in enumerate(image_paths, start=1):
            context.update(index - 1, len(image_paths), f"正在检查 {image_path.name}")
            key = _image_key(source, image_path)
            caption_path = caption_map.get(key)
            records.append(
                _inspect_image(
                    source,
                    image_path,
                    caption_path=caption_path,
                    thumbnails_root=thumbnails_root,
                )
            )
            context.update(index, len(image_paths), f"已检查 {index}/{len(image_paths)}")

        orphan_captions = [
            path.relative_to(source).as_posix()
            for path in caption_paths
            if _caption_key(source, path) not in image_keys
        ]
        exact_duplicates = _exact_duplicate_groups(records)
        near_duplicates = _near_duplicate_groups(records)
        valid_count = sum(item["valid"] for item in records)
        paired_count = sum(item["caption_status"] == "paired" for item in records)
        summary = {
            "image_count": len(records),
            "valid_image_count": valid_count,
            "invalid_image_count": len(records) - valid_count,
            "paired_caption_count": paired_count,
            "missing_caption_count": len(records) - paired_count,
            "orphan_caption_count": len(orphan_captions),
            "exact_duplicate_groups": len(exact_duplicates),
            "near_duplicate_groups": len(near_duplicates),
        }
        report = {
            "format": "soda-prompt-hub-dataset-scan-v1",
            "workspace_id": workspace_id,
            "source_path": str(source),
            "source_mode": "read-only",
            "scanned_at": _now(),
            "summary": summary,
            "images": records,
            "orphan_captions": orphan_captions,
            "exact_duplicates": exact_duplicates,
            "near_duplicates": near_duplicates,
            "perceptual_hash": "phash-64",
            "near_duplicate_distance": NEAR_DUPLICATE_DISTANCE,
        }
        report_name = f"scan-{_timestamp_token()}-{uuid4().hex[:8]}.json"
        report_path = self._workspace_directory(workspace_id) / "scans" / report_name
        _atomic_json_write(report_path, report)
        self._update_workspace(
            workspace_id,
            status="ready",
            current_report=f"scans/{report_name}",
            summary=summary,
            error="",
        )
        return {"workspace_id": workspace_id, "report": f"scans/{report_name}", **summary}

    def read_current_report(self, workspace_id: str) -> dict[str, Any] | None:
        workspace = self.get(workspace_id)
        if workspace is None:
            return None
        relative = str(workspace.get("current_report", ""))
        if not relative:
            return None
        path = (self._workspace_directory(workspace_id) / relative).resolve()
        if not path.is_relative_to(self._workspace_directory(workspace_id).resolve()):
            return None
        return _load_json(path) if path.is_file() else None

    def read_review_state(self, workspace_id: str) -> dict[str, dict[str, Any]]:
        if self.get(workspace_id) is None:
            raise DatasetWorkspaceError("Dataset workspace not found")
        path = self._workspace_directory(workspace_id) / "review.json"
        if not path.is_file():
            return {}
        payload = _load_json(path)
        items = payload.get("items", {})
        return items if isinstance(items, dict) else {}

    def update_review_state(
        self,
        workspace_id: str,
        updates: Iterable[Mapping[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        report = self.read_current_report(workspace_id)
        if report is None:
            raise DatasetWorkspaceError("Dataset scan report not found")
        known = {
            str(item.get("relative_path", "")): str(item.get("sha256", ""))
            for item in report.get("images", [])
            if isinstance(item, dict)
        }
        state = self.read_review_state(workspace_id)
        now = _now()
        for update in updates:
            relative_path = str(update.get("relative_path", ""))
            if relative_path not in known:
                message = f"Dataset image not found: {relative_path}"
                raise DatasetWorkspaceError(message)
            review_status = str(update.get("status", "pending"))
            if review_status not in REVIEW_STATUSES:
                raise DatasetWorkspaceError("Invalid dataset review status")
            state[relative_path] = {
                "status": review_status,
                "selected": bool(update.get("selected", False)),
                "note": str(update.get("note", ""))[:2000],
                "sha256": known[relative_path],
                "updated_at": now,
            }
        _atomic_json_write(
            self._workspace_directory(workspace_id) / "review.json",
            {"format": "soda-prompt-hub-dataset-review-v1", "items": state},
        )
        return state

    def resolve_source_image(self, workspace_id: str, relative_path: str) -> Path | None:
        workspace = self.get(workspace_id)
        if workspace is None:
            return None
        report = self.read_current_report(workspace_id)
        known = {
            str(item.get("relative_path", ""))
            for item in (report or {}).get("images", [])
            if isinstance(item, dict) and item.get("valid") is True
        }
        if relative_path not in known:
            return None
        try:
            source = self._validate_source(str(workspace["source_path"]))
            path = (source / relative_path).resolve(strict=True)
        except (DatasetWorkspaceError, OSError, RuntimeError):
            return None
        return path if path.is_relative_to(source) and path.is_file() else None

    def remove(self, workspace_id: str) -> dict[str, Any] | None:
        workspace = self.get(workspace_id)
        if workspace is None:
            return None
        directory = self._workspace_directory(workspace_id)
        with self._write_lock:
            shutil.rmtree(directory)
        self._remove_imported_archive_copy(workspace)
        return workspace

    def _remove_imported_archive_copy(self, workspace: Mapping[str, Any]) -> bool:
        if str(workspace.get("source_origin", "")) != "zip_archive":
            return False
        try:
            source = Path(str(workspace.get("source_path", ""))).expanduser().resolve()
        except (OSError, RuntimeError):
            return False
        archives_root = self.settings.imported_archives_root.expanduser().resolve()
        if not source.is_relative_to(archives_root) or not source.is_dir():
            return False
        shutil.rmtree(source)
        return True

    def resolve_thumbnail(self, workspace_id: str, filename: str) -> Path | None:
        if Path(filename).name != filename or not filename.endswith(".webp"):
            return None
        stem = Path(filename).stem
        if len(stem) != THUMBNAIL_DIGEST_CHARS or any(
            character not in "0123456789abcdef" for character in stem
        ):
            return None
        try:
            root = (self._workspace_directory(workspace_id) / "thumbnails").resolve()
        except DatasetWorkspaceError:
            return None
        path = (root / filename).resolve()
        return path if path.is_relative_to(root) and path.is_file() else None

    def _validate_source(self, source_path: Path | str) -> Path:
        try:
            source = Path(source_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise DatasetWorkspaceError("数据集目录不存在或无法读取") from error
        if not source.is_dir():
            raise DatasetWorkspaceError("数据集来源必须是文件夹")
        rejection = self.source_rejection(source)
        if rejection:
            raise DatasetWorkspaceError(rejection)
        return source

    def source_rejection(self, source: Path) -> str | None:
        home = Path.home().resolve()
        library_root = self.settings.library_root.expanduser().resolve()
        workspaces_root = self.root.expanduser().resolve()
        if source in {Path("/").resolve(), home, library_root, workspaces_root}:
            return "请不要把系统根目录、个人主目录或资料库根目录作为数据集"
        if workspaces_root.is_relative_to(source):
            return "数据集目录不能包含 Prompt Hub 工作区"
        return None

    def browse_directory(self, path: Path | str | None = None) -> dict[str, Any]:
        roots = browse_roots()
        if path is None or not str(path).strip():
            return self._browse_roots_response(roots)
        try:
            current = Path(str(path)).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise DatasetWorkspaceError("目录不存在或无法读取") from error
        scope = next((root for root in roots if current.is_relative_to(root)), None)
        if scope is None:
            raise DatasetWorkspaceError("目录浏览范围仅限于个人主目录和已挂载的外接卷")
        if not current.is_dir():
            raise DatasetWorkspaceError("只能浏览文件夹")
        return self._browse_response(current, scope, roots)

    def _browse_roots_response(self, roots: list[Path]) -> dict[str, Any]:
        imported = {str(item.get("source_path", "")) for item in self.list_workspaces()}
        entries = [self._browse_entry(root, imported) for root in roots]
        return {
            "path": "",
            "parent": None,
            "crumbs": [],
            "quick": self._browse_quick_entries(roots),
            "selectable": False,
            "reason": "",
            "imported": False,
            "image_count": 0,
            "image_count_capped": False,
            "entries": entries,
            "skipped": [],
            "truncated": False,
        }

    def _browse_response(self, current: Path, scope: Path, roots: list[Path]) -> dict[str, Any]:
        imported = {str(item.get("source_path", "")) for item in self.list_workspaces()}
        entries, skipped, truncated = self._list_subdirectories(current, imported)
        crumbs = []
        node = current
        while node != scope:
            crumbs.append({"name": node.name, "path": str(node)})
            node = node.parent
        crumbs.append({"name": _browse_root_label(scope, roots), "path": str(scope)})
        crumbs.reverse()
        try:
            count, capped = _count_directory_images(current, BROWSE_IMAGE_COUNT_LIMIT)
        except (OSError, PermissionError):
            count, capped = 0, False
        rejection = self.source_rejection(current)
        return {
            "path": str(current),
            "parent": None if current == scope else str(current.parent),
            "crumbs": crumbs,
            "quick": self._browse_quick_entries(roots),
            "selectable": rejection is None,
            "reason": rejection or "",
            "imported": str(current) in imported,
            "image_count": count,
            "image_count_capped": capped,
            "entries": entries,
            "skipped": skipped,
            "truncated": truncated,
        }

    def _browse_quick_entries(self, roots: list[Path]) -> list[dict[str, Any]]:
        home = roots[0] if roots else Path.home().resolve()
        quick = [{"label": "主目录", "path": str(home), "available": home.is_dir()}]
        for candidate, label in home_shortcuts(home):
            if not any(candidate.is_relative_to(root) for root in roots):
                continue
            quick.append({"label": label, "path": str(candidate), "available": True})
        quick.extend(
            {"label": volume.name, "path": str(volume), "available": volume.is_dir()}
            for volume in roots[1:]
        )
        return quick

    def _browse_entry(self, directory: Path, imported: set[str]) -> dict[str, Any]:
        try:
            count, capped = _count_directory_images(directory, BROWSE_IMAGE_COUNT_LIMIT)
        except (OSError, PermissionError):
            count, capped = 0, False
        rejection = self.source_rejection(directory)
        return {
            "name": directory.name,
            "path": str(directory),
            "selectable": rejection is None,
            "reason": rejection or "",
            "imported": str(directory) in imported,
            "image_count": count,
            "image_count_capped": capped,
        }

    def _list_subdirectories(
        self,
        current: Path,
        imported: set[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, str]], bool]:
        try:
            with os.scandir(current) as iterator:
                children = sorted(iterator, key=lambda item: item.name.lower())
        except OSError as error:
            raise DatasetWorkspaceError("无法读取该目录") from error
        entries: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        truncated = False
        for child in children:
            if len(entries) >= BROWSE_MAX_SUBDIRS:
                truncated = True
                break
            try:
                if child.is_symlink():
                    skipped.append({"name": child.name, "reason": "符号链接目录未列出"})
                    continue
                if not child.is_dir():
                    continue
            except OSError:
                skipped.append({"name": child.name, "reason": "无权限读取"})
                continue
            directory = Path(child.path)
            try:
                count, capped = _count_directory_images(directory, BROWSE_IMAGE_COUNT_LIMIT)
            except (OSError, PermissionError):
                skipped.append({"name": child.name, "reason": "无权限读取"})
                continue
            rejection = self.source_rejection(directory)
            entries.append(
                {
                    "name": child.name,
                    "path": str(directory),
                    "selectable": rejection is None,
                    "reason": rejection or "",
                    "imported": str(directory) in imported,
                    "image_count": count,
                    "image_count_capped": capped,
                }
            )
        return entries, skipped, truncated

    def import_archive_job(self, payload: Mapping[str, Any], context: JobContext) -> dict[str, Any]:
        archive_path = Path(str(payload.get("archive_path", "")))
        archive_id = str(payload.get("archive_id", "")).strip()
        filename = str(payload.get("filename", "dataset.zip")).strip() or "dataset.zip"
        name = str(payload.get("name", "")).strip()
        if not archive_id or Path(archive_id).name != archive_id:
            raise DatasetWorkspaceError("无效的压缩包任务参数")
        target_root = self.settings.imported_archives_root / archive_id
        if not archive_path.is_file():
            existing = self.find_by_source(target_root) if target_root.is_dir() else None
            if existing is None:
                raise DatasetWorkspaceError("上传的压缩包已不存在，请重新上传")
            return {
                "workspace": existing,
                "source_origin": "zip_archive",
                "archive_name": filename,
                "extracted_files": 0,
                "total_bytes": 0,
                "skipped": [],
                "manifest": None,
                "resumed": True,
            }
        report = extract_dataset_archive(archive_path, target_root, context)
        archive_path.unlink(missing_ok=True)
        workspace = self.register(
            target_root,
            name=name or Path(filename).stem,
            source_origin="zip_archive",
        )
        return {
            "workspace": workspace,
            "source_origin": "zip_archive",
            "archive_name": filename,
            "extracted_files": len(report["files"]),
            "total_bytes": report["total_bytes"],
            "skipped": report["skipped"],
            "manifest": report["manifest"],
        }

    def _workspace_directory(self, workspace_id: str) -> Path:
        if not workspace_id.startswith("dataset-") or not workspace_id[8:].isalnum():
            raise DatasetWorkspaceError("Invalid dataset workspace id")
        path = (self.root / workspace_id).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise DatasetWorkspaceError("Invalid dataset workspace path")
        return path

    def _manifest_path(self, workspace_id: str) -> Path | None:
        try:
            return self._workspace_directory(workspace_id) / "workspace.json"
        except DatasetWorkspaceError:
            return None

    def _update_workspace(self, workspace_id: str, **values: Any) -> dict[str, Any]:
        workspace = self.get(workspace_id)
        if workspace is None:
            raise DatasetWorkspaceError("Dataset workspace not found")
        updated = {**workspace, **values, "updated_at": _now()}
        self._write_manifest(updated)
        return updated

    def _write_manifest(self, workspace: Mapping[str, Any]) -> None:
        workspace_id = str(workspace["workspace_id"])
        with self._write_lock:
            _atomic_json_write(
                self._workspace_directory(workspace_id) / "workspace.json",
                workspace,
            )


def _collect_source_files(source: Path) -> tuple[list[Path], list[Path]]:
    images: list[Path] = []
    captions: list[Path] = []
    for directory, names, filenames in os.walk(source, followlinks=False):
        names[:] = sorted(name for name in names if not (Path(directory) / name).is_symlink())
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if path.is_symlink():
                continue
            suffix = path.suffix.lower()
            if suffix in IMAGE_SUFFIXES:
                images.append(path)
            elif suffix == ".txt":
                captions.append(path)
    return sorted(images), sorted(captions)


def browse_roots() -> list[Path]:
    roots = [Path.home().resolve()]
    for volume in _volume_roots():
        if volume not in roots:
            roots.append(volume)
    return roots


def _volume_roots() -> list[Path]:
    """Mounted volumes the directory browser may reach.

    macOS keeps removable disks in /Volumes; Linux puts them in /media/<user>,
    /run/media/<user> (udisks) or /mnt. Without this, a Linux user could not browse a
    dataset that lives on a second disk.
    """
    found: list[Path] = []
    for base in _volume_bases():
        for entry in _directory_entries(base):
            if entry not in found:
                found.append(entry)
    return found


def _volume_bases() -> list[Path]:
    """Concrete per-user mount bases; the literal /media is not where udisks mounts."""
    home_name = Path.home().name
    return [
        base / home_name if str(base).startswith(("/media", "/run/media")) else base
        for base in BROWSE_VOLUME_BASES
    ]


def _directory_entries(base: Path) -> list[Path]:
    """Direct subdirectories of ``base``, skipping symlinks (and never failing hard)."""
    try:
        if not base.is_dir():
            return []
    except OSError:
        return []
    found: list[Path] = []
    try:
        with os.scandir(base) as entries:
            for entry in sorted(entries, key=lambda item: item.name.lower()):
                try:
                    if entry.is_symlink() or not entry.is_dir():
                        continue
                    found.append(Path(entry.path).resolve())
                except OSError:
                    continue
    except OSError:
        return []
    return found


def home_shortcuts(home: Path) -> list[tuple[Path, str]]:
    """Quick-jump entries inside ``home``, following XDG user-dirs when available."""
    configured = _xdg_user_dirs(home)
    shortcuts: list[tuple[Path, str]] = []
    for name, label in BROWSE_HOME_SHORTCUTS:
        key = BROWSE_XDG_HOME_KEYS.get(name, "")
        candidate = configured.get(key) or (home / name)
        if candidate == home:
            continue
        try:
            if not candidate.is_dir():
                continue
        except OSError:
            continue
        if any(candidate == existing for existing, _ in shortcuts):
            continue
        shortcuts.append((candidate, label))
    return shortcuts


def _xdg_user_dirs(home: Path) -> dict[str, Path]:
    """Read ``user-dirs.dirs`` (written by xdg-user-dirs) if it exists."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or (home / ".config"))
    try:
        text = (config_home / "user-dirs.dirs").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    values: dict[str, Path] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw_value = line.partition("=")
        value = raw_value.strip().strip('"')
        if not value:
            continue
        expanded = value.replace("$HOME", str(home))
        candidate = Path(expanded).expanduser()
        values[key.strip()] = candidate.resolve() if candidate.is_absolute() else home / candidate
    return values


def _browse_root_label(scope: Path, roots: list[Path]) -> str:
    if roots and scope == roots[0]:
        return "主目录"
    return scope.name


def _count_directory_images(path: Path, limit: int) -> tuple[int, bool]:
    count = 0
    with os.scandir(path) as entries:
        for entry in entries:
            try:
                if entry.is_symlink() or not entry.is_file():
                    continue
            except OSError:
                continue
            if Path(entry.name).suffix.lower() in IMAGE_SUFFIXES:
                count += 1
                if count >= limit:
                    return count, True
    return count, False


def extract_dataset_archive(
    archive_path: Path,
    target_root: Path,
    context: JobContext,
) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(archive_path)
    except (zipfile.BadZipFile, OSError) as error:
        raise DatasetWorkspaceError("文件不是有效的 zip 压缩包") from error
    try:
        infos = archive.infolist()
    except (zipfile.BadZipFile, OSError) as error:
        archive.close()
        raise DatasetWorkspaceError("无法读取压缩包目录") from error
    try:
        return _extract_archive_entries(archive, infos, target_root, context)
    finally:
        archive.close()


def _extract_archive_entries(
    archive: zipfile.ZipFile,
    infos: list[zipfile.ZipInfo],
    target_root: Path,
    context: JobContext,
) -> dict[str, Any]:
    if len(infos) > ARCHIVE_MAX_ENTRIES:
        raise DatasetWorkspaceError(
            f"压缩包条目过多（{len(infos)} 个，上限 {ARCHIVE_MAX_ENTRIES}），已拒绝导入"
        )
    target_root.mkdir(parents=True, exist_ok=True)
    resolved_root = target_root.resolve()
    files: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    seen_names: set[str] = set()
    total_bytes = 0
    for number, info in enumerate(infos, start=1):
        context.raise_if_cancelled()
        name = info.filename
        context.update(number - 1, len(infos), f"正在解压 {name}")
        if info.is_dir() or not PurePosixPath(name).name:
            continue
        if _archive_entry_is_symlink(info):
            raise DatasetWorkspaceError(f"压缩包含符号链接条目，已拒绝导入：{name}")
        unsafe = _archive_name_violation(name)
        if unsafe:
            raise DatasetWorkspaceError(f"压缩包含不安全路径（{unsafe}），已拒绝导入：{name}")
        suffix = Path(name).suffix.lower()
        if suffix not in ARCHIVE_ALLOWED_SUFFIXES:
            skipped.append({"name": name, "reason": f"不支持的文件类型：{suffix or '无后缀'}"})
            context.update(number, len(infos), f"已跳过 {name}")
            continue
        normalized = unicodedata.normalize("NFC", name)
        if normalized in seen_names:
            raise DatasetWorkspaceError(f"压缩包含 Unicode 归一化后重名的条目，已拒绝导入：{name}")
        seen_names.add(normalized)
        destination = (target_root / name).resolve()
        if not destination.is_relative_to(resolved_root):
            raise DatasetWorkspaceError(f"压缩包含越界路径，已拒绝导入：{name}")
        if info.file_size > ARCHIVE_MAX_SINGLE_ENTRY_BYTES:
            raise DatasetWorkspaceError(f"压缩包条目过大，已拒绝导入：{name}")
        if (
            info.file_size > ARCHIVE_RATIO_MIN_BYTES
            and info.compress_size > 0
            and info.file_size / info.compress_size > ARCHIVE_MAX_COMPRESSION_RATIO
        ):
            raise DatasetWorkspaceError(f"压缩比异常，疑似压缩炸弹，已拒绝导入：{name}")
        total_bytes += info.file_size
        if total_bytes > ARCHIVE_MAX_TOTAL_BYTES:
            raise DatasetWorkspaceError("压缩包解压后总大小超过上限，已拒绝导入")
        if destination.is_file() and destination.stat().st_size == info.file_size:
            files.append({"name": name, "bytes": info.file_size})
            context.update(number, len(infos), f"已存在，跳过 {name}")
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with archive.open(info) as source, destination.open("wb") as sink:
                written = 0
                while chunk := source.read(1024 * 1024):
                    sink.write(chunk)
                    written += len(chunk)
                    if written > info.file_size:
                        message = f"条目解压后大小与目录记录不一致：{name}"
                        raise DatasetWorkspaceError(message)
        except (OSError, zipfile.BadZipFile, RuntimeError) as error:
            raise DatasetWorkspaceError(f"解压失败：{name}：{error}") from error
        files.append({"name": name, "bytes": info.file_size})
        context.update(number, len(infos), f"已解压 {number}/{len(infos)}")
    manifest = _read_archive_manifest(target_root, files)
    return {
        "files": files,
        "total_bytes": total_bytes,
        "skipped": skipped,
        "manifest": manifest,
    }


def _archive_entry_is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def _archive_name_violation(name: str) -> str | None:
    if "\x00" in name:
        return "含 NUL 字节"
    if any(
        ord(character) <= _ARCHIVE_NAME_CONTROL_MAX or ord(character) == _ARCHIVE_NAME_DELETE_CODE
        for character in name
    ):
        return "含控制字符"
    parts = PurePosixPath(name).parts
    if ".." in parts:
        return "包含 .. 路径段"
    if name.startswith("/") or (parts and parts[0] == "/"):
        return "绝对路径"
    return None


def _read_archive_manifest(
    target_root: Path,
    files: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = [
        item["name"] for item in files if Path(item["name"]).name.lower().endswith("_manifest.json")
    ]
    if not candidates:
        return None
    for relative in sorted(candidates):
        try:
            value = json.loads((target_root / relative).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(value, dict):
            continue
        source = value.get("source")
        export_type = value.get("export_type")
        if not isinstance(source, str) or not source.strip():
            continue
        if not isinstance(export_type, str) or not export_type.strip():
            continue
        suggested = ""
        lowered = export_type.lower()
        if "natural" in lowered:
            suggested = "krea2"
        elif "tag" in lowered or "booru" in lowered:
            suggested = "anima"
        return {
            "filename": Path(relative).name,
            "source": source.strip(),
            "export_type": export_type.strip(),
            "suggested_profile": suggested,
        }
    return None


def _inspect_image(
    source: Path,
    image_path: Path,
    *,
    caption_path: Path | None,
    thumbnails_root: Path,
) -> dict[str, Any]:
    relative = image_path.relative_to(source).as_posix()
    digest = _sha256(image_path)
    record: dict[str, Any] = {
        "relative_path": relative,
        "filename": image_path.name,
        "bytes": image_path.stat().st_size,
        "sha256": digest,
        "phash": "",
        "width": 0,
        "height": 0,
        "format": "",
        "valid": False,
        "error": "",
        "caption_status": "missing",
        "caption_path": "",
        "caption": "",
        "thumbnail": "",
    }
    if caption_path is not None:
        record["caption_status"] = "paired"
        record["caption_path"] = caption_path.relative_to(source).as_posix()
        record["caption"] = caption_path.read_text(encoding="utf-8", errors="replace")[
            :MAX_CAPTION_CHARS
        ]
    try:
        with Image.open(image_path) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
            record["width"], record["height"] = image.size
            record["format"] = str(opened.format or image_path.suffix.lstrip(".")).upper()
            record["phash"] = _phash(image)
            thumbnail_name = f"{digest[:20]}.webp"
            thumbnail_path = thumbnails_root / thumbnail_name
            if not thumbnail_path.exists():
                thumbnail = image.convert("RGB")
                thumbnail.thumbnail((512, 512), Image.Resampling.LANCZOS)
                thumbnail.save(thumbnail_path, "WEBP", quality=82, method=4)
            record["thumbnail"] = f"thumbnails/{thumbnail_name}"
            record["valid"] = True
    except (OSError, ValueError, UnidentifiedImageError) as error:
        record["error"] = str(error)[:500]
    return record


def _exact_duplicate_groups(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for record in records:
        grouped[str(record["sha256"])].append(str(record["relative_path"]))
    return [
        {"sha256": digest, "files": sorted(files)}
        for digest, files in sorted(grouped.items())
        if len(files) > 1
    ]


def _near_duplicate_groups(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    hash_files: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        value = str(record.get("phash", ""))
        if value:
            hash_files[int(value, 16)].append(record)
    tree: _BKTree | None = None
    groups: list[dict[str, Any]] = []
    for value in sorted(hash_files):
        same_hash_by_sha: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for record in hash_files[value]:
            same_hash_by_sha[str(record["sha256"])].append(record)
        digest_groups = list(same_hash_by_sha.values())
        for index, left in enumerate(digest_groups):
            groups.extend(
                {
                    "distance": 0,
                    "left_phash": f"{value:016x}",
                    "right_phash": f"{value:016x}",
                    "left_files": sorted(str(item["relative_path"]) for item in left),
                    "right_files": sorted(str(item["relative_path"]) for item in right),
                }
                for right in digest_groups[index + 1 :]
            )
        matches = tree.search(value, NEAR_DUPLICATE_DISTANCE) if tree is not None else []
        for other, distance in matches:
            left = hash_files[other]
            right = hash_files[value]
            groups.append(
                {
                    "distance": distance,
                    "left_phash": f"{other:016x}",
                    "right_phash": f"{value:016x}",
                    "left_files": sorted(str(item["relative_path"]) for item in left),
                    "right_files": sorted(str(item["relative_path"]) for item in right),
                }
            )
        if tree is None:
            tree = _BKTree(value)
        else:
            tree.add(value)
    return groups


class _BKTree:
    def __init__(self, value: int) -> None:
        self.value = value
        self.children: dict[int, _BKTree] = {}

    def add(self, value: int) -> None:
        node = self
        while True:
            distance = _hamming(node.value, value)
            child = node.children.get(distance)
            if child is None:
                node.children[distance] = _BKTree(value)
                return
            node = child

    def search(self, value: int, limit: int) -> list[tuple[int, int]]:
        distance = _hamming(self.value, value)
        matches = [(self.value, distance)] if distance <= limit else []
        for edge, child in self.children.items():
            if distance - limit <= edge <= distance + limit:
                matches.extend(child.search(value, limit))
        return matches


def _phash(image: Image.Image) -> str:
    size = 32
    low_frequency_size = 8
    grayscale = image.convert("L").resize((size, size), Image.Resampling.LANCZOS)
    pixels = np.asarray(grayscale, dtype=np.float64)
    positions = np.arange(size, dtype=np.float64)
    frequencies = np.arange(low_frequency_size, dtype=np.float64)[:, np.newaxis]
    basis = np.cos(np.pi * (2 * positions + 1) * frequencies / (2 * size))
    basis[0] *= np.sqrt(1 / size)
    basis[1:] *= np.sqrt(2 / size)
    low_frequency = basis @ pixels @ basis.T
    median = float(np.median(low_frequency[1:, :]))
    bits = low_frequency > median
    value = 0
    for bit in bits.flat:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _image_key(source: Path, path: Path) -> str:
    return path.relative_to(source).with_suffix("").as_posix().casefold()


def _caption_key(source: Path, path: Path) -> str:
    return path.relative_to(source).with_suffix("").as_posix().casefold()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError("JSON object expected")
    return dict(loaded)


def _atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timestamp_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
