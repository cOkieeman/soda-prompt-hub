from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from prompt_hub.embedding_index import EmbeddingIndexError, EmbeddingIndexStore
from prompt_hub.local_visual import LocalVisualIndexService, VisualIndexError

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner


class VisualIndexBuildInput(BaseModel):
    asset_types: list[str] = Field(default_factory=list, max_length=20)
    max_items: int = Field(default=0, ge=0, le=10000)


class VisualSourceQueryInput(BaseModel):
    source_sha256: str = Field(min_length=64, max_length=64)
    asset_types: list[str] = Field(default_factory=list, max_length=20)
    safety: str = Field(default="", max_length=40)
    scope_id: str = Field(default="", max_length=200)
    limit: int = Field(default=30, ge=1, le=100)


def create_visual_router(
    service: LocalVisualIndexService,
    store: EmbeddingIndexStore,
    job_runner: BackgroundJobRunner,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/visual-index/status")
    def visual_index_status() -> dict[str, Any]:
        return service.status()

    @router.post("/api/visual-index/build", status_code=status.HTTP_202_ACCEPTED)
    def build_visual_index(payload: VisualIndexBuildInput) -> dict[str, Any]:
        if not service.encoder.status()["available"]:
            raise HTTPException(status_code=503, detail=service.encoder.status()["reason"])
        job = job_runner.submit("local_visual_index", payload.model_dump(), max_attempts=2)
        return {"job": job}

    @router.post("/api/visual-search/query")
    async def query_uploaded_image(
        request: Request,
        asset_types: str = "",
        safety: str = "",
        scope_id: str = "",
        limit: Annotated[int, Query(ge=1, le=100)] = 30,
    ) -> dict[str, Any]:
        try:
            return service.query_bytes(
                await request.body(),
                asset_types=_split_types(asset_types),
                safety=safety,
                scope_id=scope_id,
                limit=limit,
            )
        except VisualIndexError as error:
            code = 503 if not service.encoder.status()["available"] else 409
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.post("/api/visual-search/by-source")
    def query_existing_image(payload: VisualSourceQueryInput) -> dict[str, Any]:
        try:
            return service.query_source(
                payload.source_sha256,
                asset_types=set(payload.asset_types),
                safety=payload.safety,
                scope_id=payload.scope_id,
                limit=payload.limit,
            )
        except VisualIndexError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.get("/api/visual-index/{index_id}/clusters")
    def browse_visual_clusters(
        index_id: str,
        asset_types: str = "",
        limit: Annotated[int, Query(ge=1, le=1000)] = 240,
        threshold: Annotated[float, Query(ge=0.5, le=0.99)] = 0.84,
    ) -> dict[str, Any]:
        try:
            return store.clusters(
                index_id,
                asset_types=_split_types(asset_types) or None,
                limit=limit,
                threshold=threshold,
            )
        except EmbeddingIndexError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    return router


def _split_types(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}
