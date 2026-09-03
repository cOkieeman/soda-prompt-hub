from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from prompt_hub.embedding_index import EmbeddingIndexError

if TYPE_CHECKING:
    from prompt_hub.hybrid_search import HybridSearchService


class HybridTextSearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    vector: list[float] | None = Field(default=None, min_length=1, max_length=8192)
    index_id: str = Field(default="", max_length=200)
    safety: str = Field(default="", max_length=40)
    limit: int = Field(default=20, ge=1, le=100)


class SimilarSourceInput(BaseModel):
    source_sha256: str = Field(min_length=64, max_length=64)
    index_id: str = Field(default="", max_length=200)
    limit: int = Field(default=30, ge=1, le=100)


def create_search_router(service: HybridSearchService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/hybrid-search")
    def hybrid_search(payload: HybridTextSearchInput) -> dict[str, Any]:
        try:
            return service.search_text(
                payload.query,
                vector=payload.vector,
                index_id=payload.index_id,
                safety=payload.safety,
                limit=payload.limit,
            )
        except EmbeddingIndexError as error:
            code = 404 if "not found" in str(error).lower() else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.post("/api/hybrid-search/by-source")
    def similar_by_source(payload: SimilarSourceInput) -> dict[str, Any]:
        try:
            return service.search_by_source(
                payload.source_sha256,
                index_id=payload.index_id,
                limit=payload.limit,
            )
        except EmbeddingIndexError as error:
            code = 404 if "尚未进入" in str(error) or "not found" in str(error).lower() else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.get("/api/hybrid-search/source-status")
    def source_embedding_status(
        source_sha256: Annotated[str, Query(min_length=64, max_length=64)],
    ) -> dict[str, Any]:
        try:
            return service.embedding_store.source_status(source_sha256)
        except EmbeddingIndexError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return router
