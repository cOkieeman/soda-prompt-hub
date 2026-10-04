from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from prompt_hub.config import Settings


def local_source_mapping(settings: Settings) -> tuple[dict[str, Any], str]:
    """Read explicit local mappings without touching their external directories."""
    config = settings.library_root / "sources/local-sources.json"
    if not config.is_file():
        return {}, ""
    try:
        return _read_mapping(config), ""
    except (OSError, ValueError, TypeError):
        # A malformed mapping must never trigger a replacement Git download.
        return {}, "本地映射配置无效。已禁止自动拉取资料。"


def _read_mapping(config: Path) -> dict[str, Any]:
    raw = json.loads(config.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, dict) or raw.get("format") != "soda-local-sources-v1":
        message = "Unsupported local source configuration"
        raise ValueError(message)
    sources = raw.get("sources")
    if not isinstance(sources, dict):
        message = "Local sources must be an object"
        raise TypeError(message)
    return sources


def mapped_source_path(settings: Settings, source_id: str, default: Path) -> Path:
    mappings, _ = local_source_mapping(settings)
    details = mappings.get(source_id)
    if not isinstance(details, dict) or not isinstance(details.get("path"), str):
        return default
    path = Path(details["path"]).expanduser()
    return path if path.is_absolute() else default


def mapped_catalogue_path(settings: Settings, source_id: str) -> Path | None:
    mappings, _ = local_source_mapping(settings)
    details = mappings.get(source_id)
    if not isinstance(details, dict) or not isinstance(details.get("data_path"), str):
        return None
    candidate = Path(details["data_path"]).expanduser()
    return candidate if candidate.is_absolute() else None
