from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
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


class DatasetWorkspaceError(ValueError):
    pass


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
        return _load_json(path)

    def list_workspaces(self) -> list[dict[str, Any]]:
        workspaces = []
        if not self.root.is_dir():
            return workspaces
        for path in self.root.glob("dataset-*/workspace.json"):
            try:
                workspaces.append(_load_json(path))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return sorted(workspaces, key=lambda item: str(item.get("updated_at", "")), reverse=True)

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
        return workspace

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
        home = Path.home().resolve()
        library_root = self.settings.library_root.expanduser().resolve()
        workspaces_root = self.root.expanduser().resolve()
        if source in {Path("/").resolve(), home, library_root, workspaces_root}:
            raise DatasetWorkspaceError("请不要把系统根目录、个人主目录或资料库根目录作为数据集")
        if workspaces_root.is_relative_to(source):
            raise DatasetWorkspaceError("数据集目录不能包含 Prompt Hub 工作区")
        return source

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
