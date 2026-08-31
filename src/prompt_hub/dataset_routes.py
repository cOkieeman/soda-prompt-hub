from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from prompt_hub.dataset_export import (
    DatasetExportError,
    create_dataset_export,
    resolve_dataset_export,
    update_dataset_asset,
)
from prompt_hub.dataset_tagging import (
    MAX_BATCH_TAG_ASSETS,
    DatasetTaggingError,
    review_wd14_draft,
    store_wd14_result,
)
from prompt_hub.result_assets import (
    find_result_asset,
    result_asset_path,
    selected_result_assets,
)
from prompt_hub.wd14 import WD14Error, tag_image

if TYPE_CHECKING:
    from prompt_hub.config import Settings
    from prompt_hub.creative import CreativeStore


class DatasetAssetUpdate(BaseModel):
    selected: bool | None = None
    profile_id: Literal["anima", "krea2"] = "anima"
    caption_override: str | None = Field(default=None, max_length=12000)


class DatasetExportInput(BaseModel):
    profile_id: Literal["anima", "krea2"] = "anima"


class DatasetTagInput(BaseModel):
    general_threshold: float = Field(default=0.35, ge=0, le=1)
    character_threshold: float = Field(default=0.85, ge=0, le=1)
    limit: int = Field(default=80, ge=1, le=200)


class DatasetTagReviewInput(BaseModel):
    draft_tags: str = Field(default="", max_length=12000)
    confirm_anima: bool = False


def create_dataset_router(settings: Settings, creative_store: CreativeStore) -> APIRouter:
    router = APIRouter()

    @router.post("/api/creative/projects/{project_id}/dataset-export")
    def export_creative_dataset(
        project_id: str,
        payload: DatasetExportInput,
    ) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        try:
            export = create_dataset_export(
                settings,
                project=project,
                profile_id=payload.profile_id,
            )
        except DatasetExportError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        export.pop("path", None)
        export["download_url"] = f"/dataset-exports/{quote(str(export['filename']))}"
        return export

    @router.put("/api/creative/projects/{project_id}/results/{asset_id}/dataset")
    def update_creative_dataset_asset(
        project_id: str,
        asset_id: str,
        payload: DatasetAssetUpdate,
    ) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        try:
            generation, asset = update_dataset_asset(
                project,
                asset_id=asset_id,
                selected=payload.selected,
                profile_id=payload.profile_id,
                caption_override=payload.caption_override,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Result image not found") from error
        updated = creative_store.update_project(project_id, {"generation": generation})
        return {"asset": asset, "project": updated}

    @router.post("/api/creative/projects/{project_id}/results/{asset_id}/tag")
    def tag_creative_dataset_asset(
        project_id: str,
        asset_id: str,
        payload: DatasetTagInput,
    ) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        asset = find_result_asset(project, asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail="Result image not found")
        path = result_asset_path(settings, project_id, asset)
        try:
            result = tag_image(
                path,
                model_root=settings.wd14_model_root,
                general_threshold=payload.general_threshold,
                character_threshold=payload.character_threshold,
                limit=payload.limit,
                provider="auto",
            )
            generation, tagged_asset = store_wd14_result(
                project,
                asset_id=asset_id,
                result=result,
            )
        except WD14Error as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        updated = creative_store.update_project(project_id, {"generation": generation})
        return {"asset": tagged_asset, "project": updated}

    @router.post("/api/creative/projects/{project_id}/dataset-tag")
    def tag_selected_creative_dataset(
        project_id: str,
        payload: DatasetTagInput,
    ) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        assets = selected_result_assets(project)
        if not assets:
            raise HTTPException(status_code=422, detail="请先至少精选一张结果图")
        if len(assets) > MAX_BATCH_TAG_ASSETS:
            raise HTTPException(
                status_code=422,
                detail=f"同步批量打标一次最多处理 {MAX_BATCH_TAG_ASSETS} 张图片",
            )

        working = project
        results: list[dict[str, Any]] = []
        for asset in assets:
            asset_id = str(asset.get("asset_id", ""))
            try:
                path = result_asset_path(settings, project_id, asset)
                result = tag_image(
                    path,
                    model_root=settings.wd14_model_root,
                    general_threshold=payload.general_threshold,
                    character_threshold=payload.character_threshold,
                    limit=payload.limit,
                    provider="auto",
                )
                generation, _tagged_asset = store_wd14_result(
                    working,
                    asset_id=asset_id,
                    result=result,
                )
                working = {**working, "generation": generation}
                results.append({"asset_id": asset_id, "status": "tagged"})
            except (HTTPException, WD14Error) as error:
                detail = error.detail if isinstance(error, HTTPException) else str(error)
                results.append({"asset_id": asset_id, "status": "failed", "detail": detail})

        tagged_count = sum(item["status"] == "tagged" for item in results)
        updated = (
            creative_store.update_project(project_id, {"generation": working["generation"]})
            if tagged_count
            else project
        )
        return {
            "project": updated,
            "selected_count": len(assets),
            "tagged_count": tagged_count,
            "failed_count": len(assets) - tagged_count,
            "results": results,
        }

    @router.put("/api/creative/projects/{project_id}/results/{asset_id}/tag-review")
    def review_creative_dataset_tags(
        project_id: str,
        asset_id: str,
        payload: DatasetTagReviewInput,
    ) -> dict[str, Any]:
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        try:
            generation, asset = review_wd14_draft(
                project,
                asset_id=asset_id,
                draft_tags=payload.draft_tags,
                confirm_anima=payload.confirm_anima,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail="Result image not found") from error
        except DatasetTaggingError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        updated = creative_store.update_project(project_id, {"generation": generation})
        return {"asset": asset, "project": updated}

    @router.get(
        "/dataset-exports/{filename}",
        response_class=FileResponse,
        include_in_schema=False,
    )
    def dataset_export_file(filename: str) -> FileResponse:
        path = resolve_dataset_export(settings, filename)
        if path is None:
            raise HTTPException(status_code=404, detail="Dataset export not found")
        return FileResponse(path, media_type="application/zip", filename=filename)

    return router
