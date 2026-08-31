from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from prompt_hub.creative import PROFILE_IDS, compile_prompt
from prompt_hub.result_media import resolve_result_image

if TYPE_CHECKING:
    from prompt_hub.config import Settings

MAX_DATASET_ASSETS = 500
MAX_DATASET_BYTES = 4 * 1024 * 1024 * 1024
PreparedAsset = tuple[dict[str, Any], Path, str, str, str]


class DatasetExportError(ValueError):
    pass


def update_dataset_asset(
    project: dict[str, Any],
    *,
    asset_id: str,
    selected: bool | None,
    profile_id: str,
    caption_override: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if profile_id not in PROFILE_IDS:
        raise DatasetExportError("不支持的数据集 Profile")
    generation = dict(project.get("generation", {}))
    raw_assets = generation.get("result_assets", [])
    assets = [dict(asset) if isinstance(asset, dict) else asset for asset in raw_assets]
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict) or str(asset.get("asset_id", "")) != asset_id:
            continue
        if selected is not None:
            asset["dataset_selected"] = selected
        if caption_override is not None:
            raw_captions = asset.get("dataset_captions", {})
            captions = dict(raw_captions) if isinstance(raw_captions, dict) else {}
            clean_caption = caption_override.strip()
            if clean_caption:
                captions[profile_id] = clean_caption
            else:
                captions.pop(profile_id, None)
            asset["dataset_captions"] = captions
        assets[index] = asset
        generation["result_assets"] = assets
        return generation, asset
    raise LookupError(asset_id)


def create_dataset_export(
    settings: Settings,
    *,
    project: dict[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    if profile_id not in PROFILE_IDS:
        raise DatasetExportError("不支持的数据集 Profile")
    project_id = str(project.get("project_id", "")).strip()
    if not project_id:
        raise DatasetExportError("项目缺少 project_id")
    compiled = compile_prompt(project, profile_id)
    default_caption = str(compiled.get("positive", "")).strip()
    if not default_caption:
        raise DatasetExportError("当前 Profile 没有可用的 positive prompt")
    selected = _selected_assets(project)
    prepared, total_bytes = _prepare_assets(
        settings,
        project_id=project_id,
        assets=selected,
        profile_id=profile_id,
        default_caption=default_caption,
    )

    exported_at = datetime.now(UTC)
    manifest = {
        "format": "soda-prompt-hub-dataset-v1",
        "exported_at": exported_at.isoformat(),
        "project": {
            "project_id": project_id,
            "title": project.get("title", ""),
            "iteration": project.get("lineage", {}).get("iteration", 1),
            "revision": project.get("revision", 1),
            "safety_mode": project.get("safety_mode", "sfw"),
        },
        "profile": compiled,
        "item_count": len(prepared),
        "total_source_bytes": total_bytes,
        "items": _manifest_items(prepared, profile_id, project),
    }

    settings.dataset_exports_root.mkdir(parents=True, exist_ok=True)
    title = _safe_name(str(project.get("title", "")), fallback="prompt-hub-dataset")
    timestamp = exported_at.strftime("%Y%m%d-%H%M%S")
    filename = f"{title}-{profile_id}-{timestamp}-{uuid4().hex[:8]}.zip"
    output_path = settings.dataset_exports_root / filename
    _write_archive(output_path, prepared, manifest)

    return {
        "filename": filename,
        "path": output_path,
        "profile_id": profile_id,
        "item_count": len(prepared),
        "size_bytes": output_path.stat().st_size,
        "manifest": manifest,
    }


def resolve_dataset_export(settings: Settings, filename: str) -> Path | None:
    if Path(filename).name != filename or Path(filename).suffix.casefold() != ".zip":
        return None
    root = settings.dataset_exports_root.resolve()
    candidate = (root / filename).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        return None
    return candidate


def _selected_assets(project: dict[str, Any]) -> list[dict[str, Any]]:
    generation = project.get("generation", {})
    raw_assets = generation.get("result_assets", []) if isinstance(generation, dict) else []
    selected = [
        asset
        for asset in raw_assets
        if isinstance(asset, dict) and asset.get("dataset_selected") is True
    ]
    if not selected:
        raise DatasetExportError("请先在结果图中至少精选一张图片")
    if len(selected) > MAX_DATASET_ASSETS:
        raise DatasetExportError(f"单次最多导出 {MAX_DATASET_ASSETS} 张图片")
    return selected


def _prepare_assets(
    settings: Settings,
    *,
    project_id: str,
    assets: list[dict[str, Any]],
    profile_id: str,
    default_caption: str,
) -> tuple[list[PreparedAsset], int]:
    prepared = []
    total_bytes = 0
    for index, asset in enumerate(assets, start=1):
        path = resolve_result_image(
            settings,
            project_id=project_id,
            variant="original",
            stored_name=str(asset.get("original_name", "")),
        )
        if path is None:
            name = str(asset.get("filename", asset.get("asset_id", "未知图片")))
            raise DatasetExportError(f"精选图片文件不存在: {name}")
        total_bytes += path.stat().st_size
        if total_bytes > MAX_DATASET_BYTES:
            raise DatasetExportError("单次导出原图总大小不能超过 4 GiB")
        asset_id = str(asset.get("asset_id", "result"))
        stem = f"{index:04d}_{_safe_name(asset_id, fallback='result')}"
        raw_captions = asset.get("dataset_captions", {})
        captions = raw_captions if isinstance(raw_captions, dict) else {}
        override = str(captions.get(profile_id, "")).strip()
        prepared.append(
            (
                asset,
                path,
                f"dataset/{stem}{path.suffix.casefold()}",
                f"dataset/{stem}.txt",
                override or default_caption,
            )
        )
    return prepared, total_bytes


def _manifest_items(
    prepared: list[PreparedAsset],
    profile_id: str,
    project: dict[str, Any],
) -> list[dict[str, Any]]:
    items = []
    for asset, _path, image_name, caption_name, _caption in prepared:
        raw_captions = asset.get("dataset_captions", {})
        captions = raw_captions if isinstance(raw_captions, dict) else {}
        items.append(
            {
                "asset_id": asset.get("asset_id", ""),
                "source_filename": asset.get("filename", ""),
                "image": image_name,
                "caption": caption_name,
                "caption_source": (
                    "override" if str(captions.get(profile_id, "")).strip() else "profile"
                ),
                "width": asset.get("width"),
                "height": asset.get("height"),
                "safety": asset.get("safety", project.get("safety_mode", "sfw")),
            }
        )
    return items


def _write_archive(
    output_path: Path,
    prepared: list[PreparedAsset],
    manifest: dict[str, Any],
) -> None:
    temporary_path = output_path.with_suffix(".zip.tmp")
    try:
        with ZipFile(temporary_path, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            for _asset, image_path, image_name, caption_name, caption in prepared:
                archive.write(image_path, image_name)
                archive.writestr(caption_name, caption.rstrip() + "\n")
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            )
        temporary_path.replace(output_path)
    except OSError as error:
        temporary_path.unlink(missing_ok=True)
        raise DatasetExportError("无法写入本地数据集导出目录") from error


def _safe_name(value: str, *, fallback: str) -> str:
    compact = re.sub(r"[^\w.-]+", "-", value.strip(), flags=re.UNICODE).strip("-._")
    return compact[:80] or fallback
