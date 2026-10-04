from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from prompt_hub.database import EntryInput

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


def discover_style_explorers(settings: Settings) -> list[StyleExplorer]:
    config = settings.library_root / "sources" / "style-explorers.json"
    raw: dict[str, Any] = (
        json.loads(config.read_text(encoding="utf-8-sig"))
        if config.is_file()
        else {"format": "soda-style-explorers-v1", "libraries": {}}
    )
    if raw.get("format") != "soda-style-explorers-v1":
        message = "Unsupported style explorer configuration"
        raise ValueError(message)
    sources = []
    for source_id, (name, repository, model_family) in _CATALOGUES.items():
        details = raw.get("libraries", {}).get(source_id, {})
        backup = Path(details["path"]).expanduser() if details else None
        revision = str(details.get("revision", ""))
        if backup is not None and (
            not backup.is_absolute() or not re.fullmatch(r"[0-9a-f]{40}", revision)
        ):
            message = "Style explorer requires an absolute path and a full Git revision"
            raise ValueError(message)
        notes = "通过 GitHub 拉取和更新。画风效果需使用对应模型实测。"
        if backup is not None:
            notes += " 缺失预览可使用备份中同名画风的历史图片。不代表最新版效果。"
        sources.append(
            StyleExplorer(
                source_id,
                name,
                repository,
                model_family,
                settings.git_sources_root / repository,
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
    return json.loads(match[1])


def _item_image(item: dict[str, Any]) -> str | None:
    external_id = str(item["id"])
    partition = str(item.get("folder", item.get("p", "")))
    if not re.fullmatch(r"[\w-]+", external_id) or not partition.isdecimal():
        return None
    return PurePosixPath("images", partition, external_id + ".webp").as_posix()


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
    backup_images = {}
    if backup_path is not None and (backup_path / "app/data.js").is_file():
        for item in _gallery_items(backup_path):
            content = str(item.get("prompt") or item.get("name") or "").strip()
            relative = _item_image(item)
            if content and relative and (backup_path / relative).is_file():
                backup_images[content] = relative
    entries = []
    for item in _gallery_items(root):
        external_id = str(item["id"])
        content = str(item.get("prompt") or item.get("name") or "").strip()
        relative = _item_image(item)
        if not content or relative is None:
            continue
        preview_exists = (root / relative).is_file()
        preview_revision = revision
        if not preview_exists and content in backup_images:
            relative = "snapshot/" + backup_images[content]
            preview_exists = True
            preview_revision = backup_revision
        entries.append(
            EntryInput(
                source_id=source_id,
                external_id=external_id,
                kind="style",
                title=content if model_family != "krea2" else content[:100],
                content=content,
                category="prompt-based" if model_family == "krea2" else "artist-based",
                model_family=model_family,
                safety="unrated",
                source_path="app/data.js",
                source_url=f"{source_url}/blob/{revision}/app/data.js",
                metadata={
                    "image_paths": [relative] if preview_exists else [],
                    "image_refs": [{"path": relative, "safety": "unrated"}]
                    if preview_exists
                    else [],
                    "upstream": item,
                    "preview_origin": "historical-backup"
                    if relative.startswith("snapshot/")
                    else "git",
                    "preview_revision": preview_revision if preview_exists else "",
                },
            )
        )
    return entries
