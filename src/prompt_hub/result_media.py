from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

if TYPE_CHECKING:
    from prompt_hub.config import Settings

MAX_RESULT_IMAGE_BYTES = 25 * 1024 * 1024
MAX_RESULT_IMAGE_PIXELS = 40_000_000
_THUMBNAIL_SIZE = (640, 640)
_SUPPORTED_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}


class ResultImageError(ValueError):
    pass


def store_result_image(
    settings: Settings,
    *,
    project_id: str,
    filename: str,
    raw: bytes,
    safety_mode: str,
) -> dict[str, object]:
    if not raw:
        raise ResultImageError("图片文件为空")
    if len(raw) > MAX_RESULT_IMAGE_BYTES:
        raise ResultImageError("结果图超过 25 MiB 限制")
    try:
        with Image.open(BytesIO(raw)) as opened:
            image_format = str(opened.format or "").upper()
            if image_format not in _SUPPORTED_FORMATS:
                raise ResultImageError("只支持 PNG、JPEG 或 WebP 图片")
            width, height = opened.size
            if width <= 0 or height <= 0 or width * height > MAX_RESULT_IMAGE_PIXELS:
                raise ResultImageError("结果图尺寸无效或超过 4000 万像素限制")
            opened.load()
            thumbnail = ImageOps.exif_transpose(opened).convert("RGB")
    except ResultImageError:
        raise
    except (Image.DecompressionBombError, OSError, UnidentifiedImageError) as error:
        raise ResultImageError("无法识别或读取这张图片") from error

    suffix, content_type = _SUPPORTED_FORMATS[image_format]
    asset_id = f"result-{uuid4().hex}"
    original_name = f"{asset_id}{suffix}"
    thumbnail_name = f"{asset_id}.webp"
    project_root = settings.result_images_root / project_id
    original_root = project_root / "original"
    thumbnail_root = project_root / "thumbnail"
    original_root.mkdir(parents=True, exist_ok=True)
    thumbnail_root.mkdir(parents=True, exist_ok=True)
    (original_root / original_name).write_bytes(raw)
    thumbnail.thumbnail(_THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
    thumbnail.save(thumbnail_root / thumbnail_name, "WEBP", quality=84, method=6)
    display_name = Path(filename).name.strip()[:180] or original_name
    return {
        "asset_id": asset_id,
        "filename": display_name,
        "original_name": original_name,
        "thumbnail_name": thumbnail_name,
        "content_type": content_type,
        "width": width,
        "height": height,
        "size_bytes": len(raw),
        "safety": safety_mode,
        "created_at": datetime.now(UTC).isoformat(),
        "original_url": f"/result-media/{project_id}/original/{asset_id}",
        "thumbnail_url": f"/result-media/{project_id}/thumbnail/{asset_id}",
    }


def resolve_result_image(
    settings: Settings,
    *,
    project_id: str,
    variant: str,
    stored_name: str,
) -> Path | None:
    if variant not in {"original", "thumbnail"}:
        return None
    if Path(project_id).name != project_id or Path(stored_name).name != stored_name:
        return None
    root = settings.result_images_root.resolve()
    variant_root = (root / project_id / variant).resolve()
    if not variant_root.is_relative_to(root):
        return None
    candidate = (variant_root / stored_name).resolve()
    if not candidate.is_relative_to(variant_root) or not candidate.is_file():
        return None
    allowed = {".png", ".jpg", ".webp"} if variant == "original" else {".webp"}
    return candidate if candidate.suffix.casefold() in allowed else None
