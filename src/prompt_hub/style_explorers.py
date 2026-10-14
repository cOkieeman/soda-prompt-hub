from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from prompt_hub.database import EntryInput
from prompt_hub.local_sources import mapped_source_path

if TYPE_CHECKING:
    from prompt_hub.config import Settings


@dataclass(frozen=True, slots=True)
class StyleExplorer:
    source_id: str
    name: str
    repository: str
    model_family: str
    path: Path
    notes: str
    backup_path: Path | None = None
    backup_revision: str = ""


_CATALOGUES = {
    "krea2-style-explorer": ("Krea2 Style Explorer", "Krea2-Style-Explorer", "krea2"),
    "anima-style-explorer": ("Anima Style Explorer", "Anima-Style-Explorer", "anima"),
    "illustrious-style-explorer": (
        "Illustrious / NoobAI Style Explorer",
        "Illustrious-NoobAI-Style-Explorer",
        "illustrious-noobai",
    ),
}


def _configured_backups(config: Path) -> dict[str, Any]:
    raw = json.loads(config.read_text(encoding="utf-8-sig")) if config.is_file() else {}
    if not isinstance(raw, dict) or (raw and raw.get("format") != "soda-style-explorers-v1"):
        message = "Unsupported style explorer configuration"
        raise ValueError(message)
    libraries = raw.get("libraries", {})
    if not isinstance(libraries, dict):
        message = "Invalid style explorer libraries"
        raise TypeError(message)
    return libraries


def _validated_backup(details: dict[str, Any]) -> tuple[Path, str]:
    candidate = Path(details["path"]).expanduser()
    revision = details["revision"]
    if (
        not candidate.is_absolute()
        or not isinstance(revision, str)
        or not re.fullmatch(r"[0-9a-f]{40}", revision)
    ):
        message = "Invalid historical preview path or Git revision"
        raise ValueError(message)
    return candidate, revision


def discover_style_explorers(settings: Settings) -> list[StyleExplorer]:
    config = settings.library_root / "sources" / "style-explorers.json"
    config_error = ""
    try:
        libraries = _configured_backups(config)
    except (OSError, ValueError, TypeError):
        libraries = {}
        config_error = " 历史预览配置无效。已忽略配置。当前 GitHub 资料仍可正常导入。"
    sources = []
    for source_id, (name, repository, model_family) in _CATALOGUES.items():
        details = libraries.get(source_id, {})
        backup = None
        revision = ""
        notes = "通过 GitHub 拉取和更新。画风效果需使用对应模型实测。" + config_error
        if details:
            try:
                backup, revision = _validated_backup(details)
            except (KeyError, TypeError, ValueError):
                revision = ""
                notes += " 此来源历史预览配置无效。已忽略配置。"
        if backup is not None:
            notes += " 缺失预览可使用备份中同名画风的历史图片。不代表最新版效果。"
        sources.append(
            StyleExplorer(
                source_id,
                name,
                repository,
                model_family,
                mapped_source_path(settings, source_id, settings.git_sources_root / repository),
                notes,
                backup,
                revision,
            )
        )
    return sources


def style_media_root(settings: Settings, source_id: str, *, snapshot: bool = False) -> Path | None:
    source = next(
        (source for source in discover_style_explorers(settings) if source.source_id == source_id),
        None,
    )
    return (source.backup_path if snapshot else source.path) if source is not None else None


def _gallery_items(root: Path) -> list[dict[str, Any]]:
    text = (root / "app" / "data.js").read_text(encoding="utf-8-sig")
    match = re.fullmatch(r"\s*const\s+galleryData\s*=\s*(\[.*\])\s*;?\s*", text, re.DOTALL)
    if match is None:
        message = "Unsupported style explorer data.js format"
        raise ValueError(message)
    items = json.loads(match[1])
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        message = "Style explorer entries must be objects"
        raise TypeError(message)
    return items


def _style_identity(item: dict[str, Any]) -> tuple[str, str]:
    value = item.get("id")
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        message = "Invalid style identifier"
        raise TypeError(message)
    external_id = str(value)
    content = item.get("prompt", item.get("name"))
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]+", external_id)
        or not isinstance(content, str)
        or not content.strip()
    ):
        message = "Invalid style identifier or prompt"
        raise ValueError(message)
    return external_id, content.strip()


def _item_image(item: dict[str, Any]) -> str | None:
    external_id, _ = _style_identity(item)
    partition = item.get("folder", item.get("p"))
    if partition is None:
        return None
    if (
        isinstance(partition, bool)
        or not isinstance(partition, (str, int))
        or not re.fullmatch(r"[0-9]+", str(partition))
    ):
        message = "Invalid preview partition"
        raise ValueError(message)
    return PurePosixPath("images", str(partition), external_id + ".webp").as_posix()


def _available_images(root: Path, items: list[dict[str, Any]]) -> set[str]:
    # Enumerate each partition once: one SMB directory listing instead of tens
    # of thousands of per-image network stat/resolve requests.
    partitions = {str(item.get("folder", item.get("p"))) for item in items if _item_image(item)}
    images: set[str] = set()
    resolved_root = root.resolve()
    for partition in partitions:
        directory = root / "images" / partition
        if not directory.resolve().is_relative_to(resolved_root) or not directory.is_dir():
            continue
        with os.scandir(directory) as files:
            for entry in files:
                if entry.name.endswith(".webp") and not entry.is_symlink() and entry.is_file():
                    images.add(f"images/{partition}/{entry.name}")
    return images


def load_style_entries(
    source_id: str,
    root: Path,
    source_url: str,
    revision: str,
    *,
    backup: tuple[Path, str] | None = None,
) -> list[EntryInput]:
    model_family = _CATALOGUES[source_id][2]
    backup_path, backup_revision = backup or (None, "")
    items = _gallery_items(root)
    current_images = _available_images(root, items)
    backup_images = {}
    if backup_path is not None and any(_item_image(item) not in current_images for item in items):
        try:
            backup_items = _gallery_items(backup_path)
            available_backup = _available_images(backup_path, backup_items)
            for item in backup_items:
                _, content = _style_identity(item)
                relative = _item_image(item)
                if relative is not None and relative in available_backup:
                    backup_images[content] = relative
        except (OSError, ValueError, TypeError, KeyError):
            logging.getLogger(__name__).warning(
                "Ignoring unusable historical previews for %s", source_id
            )
    entries = []
    seen: set[str] = set()
    for item in items:
        external_id, content = _style_identity(item)
        if external_id in seen:
            message = f"Duplicate style identifier: {external_id}"
            raise ValueError(message)
        seen.add(external_id)
        relative = _item_image(item)
        preview_exists = relative in current_images
        preview_revision = revision
        if not preview_exists and content in backup_images:
            relative = "snapshot/" + backup_images[content]
            preview_exists = True
            preview_revision = backup_revision
        entries.append(
            EntryInput(
                source_id=source_id,
                external_id=f"style:{external_id}",
                kind="style",
                title=content
                if model_family != "krea2"
                else content.split(",", maxsplit=1)[0].strip(),
                content=content,
                category="prompt-based" if model_family == "krea2" else "artist-based",
                model_family=model_family,
                safety="unrated",
                source_path="app/data.js",
                source_url=source_url
                if revision.startswith("local:")
                else f"{source_url}/blob/{revision}/app/data.js",
                metadata={
                    "image_paths": [relative] if preview_exists else [],
                    "image_refs": [{"path": relative, "safety": "unrated"}]
                    if preview_exists
                    else [],
                    "upstream": item,
                    "preview_origin": "historical-backup"
                    if relative and relative.startswith("snapshot/")
                    else "git",
                    "preview_revision": preview_revision if preview_exists else "",
                },
            )
        )
    return entries
