from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

MAX_BATCH_TAG_ASSETS = 24


class DatasetTaggingError(ValueError):
    pass


def store_wd14_result(
    project: dict[str, Any],
    *,
    asset_id: str,
    result: dict[str, object],
) -> tuple[dict[str, Any], dict[str, Any]]:
    tagging = {
        "model": str(result.get("model", "SmilingWolf/wd-swinv2-tagger-v3")),
        "provider": str(result.get("provider", "")),
        "tagged_at": datetime.now(UTC).isoformat(),
        "general_threshold": result.get("general_threshold", 0.35),
        "character_threshold": result.get("character_threshold", 0.85),
        "rating": _scored_tag(result.get("rating")),
        "general": _scored_tags(result.get("general")),
        "characters": _scored_tags(result.get("characters")),
        "draft_tags": normalize_tag_draft(str(result.get("tag_string", ""))),
        "elapsed_seconds": result.get("elapsed_seconds"),
    }
    return _update_asset(project, asset_id=asset_id, values={"wd14_tagging": tagging})


def review_wd14_draft(
    project: dict[str, Any],
    *,
    asset_id: str,
    draft_tags: str,
    confirm_anima: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generation, asset = _asset_copy(project, asset_id)
    raw_tagging = asset.get("wd14_tagging")
    if not isinstance(raw_tagging, dict):
        raise DatasetTaggingError("请先对这张图片运行 WD14 自动打标")
    clean_draft = normalize_tag_draft(draft_tags)
    if confirm_anima and not clean_draft:
        raise DatasetTaggingError("确认 Anima caption 前请至少保留一个标签")

    tagging = dict(raw_tagging)
    tagging["draft_tags"] = clean_draft
    tagging["reviewed_at"] = datetime.now(UTC).isoformat()
    if confirm_anima:
        tagging["confirmed_at"] = tagging["reviewed_at"]
        raw_captions = asset.get("dataset_captions", {})
        captions = dict(raw_captions) if isinstance(raw_captions, dict) else {}
        captions["anima"] = clean_draft
        asset["dataset_captions"] = captions
    asset["wd14_tagging"] = tagging
    return _replace_asset(generation, asset_id=asset_id, asset=asset)


def normalize_tag_draft(value: str) -> str:
    tags: list[str] = []
    seen: set[str] = set()
    for raw_tag in value.replace("\n", ",").split(","):
        tag = raw_tag.strip()
        normalized = tag.casefold()
        if not tag or normalized in seen:
            continue
        seen.add(normalized)
        tags.append(tag)
    return ", ".join(tags)


def _update_asset(
    project: dict[str, Any],
    *,
    asset_id: str,
    values: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    generation, asset = _asset_copy(project, asset_id)
    asset.update(values)
    return _replace_asset(generation, asset_id=asset_id, asset=asset)


def _asset_copy(
    project: dict[str, Any],
    asset_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    generation = dict(project.get("generation", {}))
    raw_assets = generation.get("result_assets", [])
    for raw_asset in raw_assets if isinstance(raw_assets, list) else []:
        if isinstance(raw_asset, dict) and str(raw_asset.get("asset_id", "")) == asset_id:
            return generation, dict(raw_asset)
    raise LookupError(asset_id)


def _replace_asset(
    generation: dict[str, Any],
    *,
    asset_id: str,
    asset: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_assets = generation.get("result_assets", [])
    assets = [dict(item) if isinstance(item, dict) else item for item in raw_assets]
    for index, current in enumerate(assets):
        if isinstance(current, dict) and str(current.get("asset_id", "")) == asset_id:
            assets[index] = asset
            generation["result_assets"] = assets
            return generation, asset
    raise LookupError(asset_id)


def _scored_tag(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    tag = str(value.get("tag", "")).strip()
    if not tag:
        return None
    return {"tag": tag, "score": float(value.get("score", 0))}


def _scored_tags(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [tag for item in value if (tag := _scored_tag(item)) is not None]
