from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from PIL import Image, ImageOps

if TYPE_CHECKING:
    from prompt_hub.config import Settings

_KISEGA_SOURCE_ID = "kisegaeningyou"
_CLIO_SOURCE_ID = "clio-style-preview"
_THUMBNAIL_SIZE = (640, 640)


def build_kisega_thumbnails(settings: Settings) -> tuple[int, int]:
    source_root = settings.git_sources_root / "Kisegaeningyou"
    target_root = settings.thumbnails_root / _KISEGA_SOURCE_ID
    generated = 0
    current = 0
    for source in sorted(source_root.glob("images*/*.png")):
        relative = source.relative_to(source_root)
        target = (target_root / relative).with_suffix(".webp")
        if target.is_file() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
            current += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            thumbnail = ImageOps.exif_transpose(image).convert("RGB")
            thumbnail.thumbnail(_THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            thumbnail.save(target, "WEBP", quality=82, method=6)
        generated += 1
    return generated, current


def resolve_media_path(
    settings: Settings,
    source_id: str,
    variant: str,
    relative_path: str,
) -> Path | None:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        return None

    if source_id == _KISEGA_SOURCE_ID:
        if variant == "original":
            root = settings.git_sources_root / "Kisegaeningyou"
            requested = Path(*relative.parts)
            allowed_suffix = ".png"
        elif variant == "thumbnail":
            root = settings.thumbnails_root / _KISEGA_SOURCE_ID
            requested = Path(*relative.parts).with_suffix(".webp")
            allowed_suffix = ".webp"
        else:
            return None
    elif source_id == _CLIO_SOURCE_ID and variant in {"original", "thumbnail"}:
        root = settings.git_sources_root / "clio-style-preview"
        requested = Path(*relative.parts)
        allowed_suffix = ".jpg"
    else:
        return None

    resolved_root = root.resolve()
    candidate = (resolved_root / requested).resolve()
    if not candidate.is_relative_to(resolved_root):
        return None
    if candidate.suffix.casefold() != allowed_suffix or not candidate.is_file():
        return None
    return candidate
