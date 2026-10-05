from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from prompt_hub.comfy_results import MAX_COMFY_IMAGE_BYTES
from prompt_hub.creative import CreativeProjectConflictError
from prompt_hub.gallery import GalleryError
from prompt_hub.local_model import LocalModelError, analyze_result_image

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner
    from prompt_hub.config import Settings
    from prompt_hub.creative import CreativeStore
    from prompt_hub.gallery import GalleryStore
    from prompt_hub.model_connections import ModelConnectionStore

Purpose = Literal["style", "composition", "action", "lighting", "scene", "all"]
Kind = Literal["work", "reference"]


class GalleryRootInput(BaseModel):
    path: str = Field(min_length=1, max_length=2000)
    label: str = Field(default="", max_length=180)
    kind: Kind = "reference"
    recursive: bool = True


class GalleryAssetUpdate(BaseModel):
    kind: Kind | None = None
    title: str | None = Field(default=None, max_length=300)
    note: str | None = Field(default=None, max_length=6000)
    author: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=100)
    albums: list[str] | None = Field(default=None, max_length=100)
    favorite: bool | None = None
    project_id: str | None = Field(default=None, max_length=180)


class GalleryReferenceInput(BaseModel):
    purpose: Purpose = "all"


class GalleryAnalysisInput(GalleryReferenceInput):
    model: str = Field(min_length=1, max_length=300)


class GalleryAnalysisConfirmation(BaseModel):
    analysis: dict[str, Any]


def create_gallery_router(
    settings: Settings,
    store: GalleryStore,
    creative_store: CreativeStore,
    job_runner: BackgroundJobRunner,
    model_connections: ModelConnectionStore,
) -> APIRouter:
    router = APIRouter()
    # Gallery paths are owned by the injected store; Settings stays in the shared factory signature.
    if store.settings != settings:
        message = "GalleryStore settings must match router settings"
        raise ValueError(message)

    @router.get("/api/gallery/assets")
    def list_assets(
        *,
        kind: Literal["all", "work", "reference"] = "all",
        q: Annotated[str, Query(max_length=500)] = "",
        album: Annotated[str, Query(max_length=180)] = "",
        model: Annotated[str, Query(max_length=1000)] = "",
        lora: Annotated[str, Query(max_length=1000)] = "",
        favorite: bool = False,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=200)] = 48,
    ) -> dict[str, Any]:
        return store.list_assets(
            kind=kind,
            q=q,
            album=album,
            model=model,
            lora=lora,
            favorite=favorite,
            offset=offset,
            limit=limit,
        )

    @router.get("/api/gallery/facets")
    def list_facets() -> dict[str, list[str]]:
        return store.list_facets()

    @router.get("/api/gallery/assets/{asset_id}")
    def get_asset(asset_id: str) -> dict[str, Any]:
        return _require_asset(store, asset_id)

    @router.get("/api/gallery/roots")
    def list_roots() -> list[dict[str, Any]]:
        return store.list_roots()

    @router.post("/api/gallery/roots", status_code=status.HTTP_201_CREATED)
    def register_root(payload: GalleryRootInput) -> dict[str, Any]:
        try:
            return store.register_root(payload.model_dump())
        except GalleryError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/api/gallery/roots/{root_id}/scan", status_code=status.HTTP_202_ACCEPTED)
    def scan_root(root_id: str) -> dict[str, Any]:
        try:
            store.require_root(root_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Gallery root not found") from error
        return job_runner.submit("gallery_scan", {"root_id": root_id})

    @router.get("/api/gallery/albums")
    def list_albums() -> list[str]:
        return store.list_albums()

    @router.post("/api/gallery/import", status_code=status.HTTP_201_CREATED)
    async def import_image(
        request: Request,
        filename: Annotated[str, Query(min_length=1, max_length=180)] = "image.png",
        kind: Kind = "work",
    ) -> dict[str, Any]:
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_COMFY_IMAGE_BYTES:
                raise HTTPException(status_code=413, detail="图片超过 50 MiB 限制")
            raw.extend(chunk)
        try:
            return store.import_bytes(bytes(raw), filename=filename, kind=kind)
        except GalleryError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.put("/api/gallery/assets/{asset_id}")
    def update_asset(asset_id: str, payload: GalleryAssetUpdate) -> dict[str, Any]:
        _require_asset(store, asset_id)
        values = payload.model_dump(exclude_unset=True, exclude_none=True)
        project = (
            _require_project(creative_store, values["project_id"])
            if values.get("project_id")
            else None
        )
        try:
            updated = store.update_asset(asset_id, values)
            return store.link_project(asset_id, project) if project is not None else updated
        except GalleryError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.delete("/api/gallery/assets/{asset_id}")
    def delete_asset(asset_id: str) -> dict[str, Any]:
        try:
            return store.delete_asset(asset_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Gallery asset not found") from error
        except GalleryError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/gallery/assets/{asset_id}/media/{variant}", response_class=FileResponse)
    def media(asset_id: str, variant: Literal["original", "thumbnail"]) -> FileResponse:
        asset = _require_asset(store, asset_id)
        path = store.resolve_asset_path(asset_id, variant)
        if path is None:
            raise HTTPException(status_code=404, detail="Gallery image is offline or unavailable")
        content_type = asset["content_type"] if variant == "original" else "image/webp"
        return FileResponse(path, media_type=content_type)

    @router.post("/api/gallery/assets/{asset_id}/reference/{project_id}")
    def attach_reference(
        asset_id: str, project_id: str, payload: GalleryReferenceInput
    ) -> dict[str, Any]:
        asset = _require_asset(store, asset_id)
        project = _require_project(creative_store, project_id)
        reference = {
            "source_id": "local-gallery",
            "external_id": asset_id,
            "gallery_asset_id": asset_id,
            "purpose": payload.purpose,
            "slot": "composition" if payload.purpose == "all" else payload.purpose,
            "title": asset["title"],
            "thumbnail_url": asset["thumbnail_url"],
            "original_url": asset["original_url"],
            "source_sha256": asset["sha256"],
            "metadata": {"image_refs": [asset["original_url"]]},
        }
        references = list(project.get("references", []))
        known = next(
            (
                index
                for index, item in enumerate(references)
                if isinstance(item, dict)
                and item.get("gallery_asset_id") == asset_id
                and item.get("purpose") == payload.purpose
            ),
            None,
        )
        if known is not None:
            return project
        references.append(reference)
        try:
            return creative_store.update_project(
                project_id,
                {"references": references},
                expected_revision=project["revision"],
            )
        except CreativeProjectConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.post("/api/gallery/assets/{asset_id}/analyze")
    def analyze(asset_id: str, payload: GalleryAnalysisInput) -> dict[str, Any]:
        asset = _require_asset(store, asset_id)
        path = store.resolve_asset_path(asset_id)
        if path is None:
            raise HTTPException(status_code=404, detail="Gallery original image is offline")
        project = {
            "brief_zh": (
                f"分析这张参考图的 {payload.purpose}。描述可见动作关系、观察位置、空间层次、"
                "光源和画风特征。没有创作原意时不要虚构作者意图。"
                "不要根据外观猜测底模、LoRA 或权重。"
            ),
            "slots": {},
            "safety_mode": "sfw",
            "target_profile": "krea2",
        }
        try:
            analysis = analyze_result_image(
                image_path=path, project=project, model=payload.model, connections=model_connections
            )
        except LocalModelError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return {
            **analysis,
            "purpose": payload.purpose,
            "source_sha256": asset["sha256"],
            "model": payload.model,
            "confirmed": False,
        }

    @router.put("/api/gallery/assets/{asset_id}/analysis")
    def confirm_analysis(asset_id: str, payload: GalleryAnalysisConfirmation) -> dict[str, Any]:
        _require_asset(store, asset_id)
        try:
            return store.confirm_analysis(asset_id, payload.analysis)
        except GalleryError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return router


def _require_asset(store: GalleryStore, asset_id: str) -> dict[str, Any]:
    asset = store.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Gallery asset not found")
    return asset


def _require_project(store: CreativeStore, project_id: str) -> dict[str, Any]:
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Creative project not found")
    return project
