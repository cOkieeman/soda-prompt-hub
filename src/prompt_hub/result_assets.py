from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from prompt_hub.result_media import resolve_result_image

if TYPE_CHECKING:
    from pathlib import Path

    from prompt_hub.config import Settings


def find_result_asset(project: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    generation = project.get("generation", {})
    if not isinstance(generation, dict):
        return None
    assets = generation.get("result_assets", [])
    if not isinstance(assets, list):
        return None
    return next(
        (
            asset
            for asset in assets
            if isinstance(asset, dict) and str(asset.get("asset_id", "")) == asset_id
        ),
        None,
    )


def selected_result_assets(project: dict[str, Any]) -> list[dict[str, Any]]:
    generation = project.get("generation", {})
    assets = generation.get("result_assets", []) if isinstance(generation, dict) else []
    return [
        asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("dataset_selected") is True
    ]


def result_asset_path(
    settings: Settings,
    project_id: str,
    asset: dict[str, Any],
) -> Path:
    path = resolve_result_image(
        settings,
        project_id=project_id,
        variant="original",
        stored_name=str(asset.get("original_name", "")),
    )
    if path is None:
        raise HTTPException(status_code=404, detail="Result image file not found")
    return path
