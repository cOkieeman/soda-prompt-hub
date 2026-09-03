from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from prompt_hub.embedding_index import EmbeddingIndexError, EmbeddingIndexStore

if TYPE_CHECKING:
    from prompt_hub.dataset_workspace import DatasetWorkspaceStore


class EmbeddingImportItem(BaseModel):
    asset_id: str = Field(min_length=1, max_length=500)
    asset_type: str = Field(default="dataset_image", max_length=80)
    source_path: str = Field(default="", max_length=4096)
    source_sha256: str = Field(min_length=64, max_length=64)
    expected_sha256: str = Field(default="", max_length=64)
    vector: list[float] = Field(min_length=1, max_length=8192)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmbeddingImportInput(BaseModel):
    task_id: str = Field(default="", max_length=200)
    workspace_id: str = Field(default="", max_length=200)
    model_id: str = Field(min_length=1, max_length=300)
    model_revision: str = Field(min_length=1, max_length=300)
    dimension: int = Field(gt=0, le=8192)
    generated_by: str = Field(min_length=1, max_length=120)
    worker_id: str = Field(default="", max_length=160)
    items: list[EmbeddingImportItem] = Field(min_length=1, max_length=100000)


class EmbeddingQueryInput(BaseModel):
    vector: list[float] = Field(min_length=1, max_length=8192)
    asset_types: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=30, ge=1, le=200)


def create_embedding_router(
    store: EmbeddingIndexStore,
    workspace_store: DatasetWorkspaceStore,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/embedding-indexes")
    def list_embedding_indexes() -> list[dict[str, Any]]:
        return store.list_indexes()

    @router.post("/api/embedding-indexes/import", status_code=status.HTTP_201_CREATED)
    def import_embedding_batch(payload: EmbeddingImportInput) -> dict[str, Any]:
        try:
            expected = _expected_hashes(payload, workspace_store)
            result = store.import_batch(
                model_id=payload.model_id,
                model_revision=payload.model_revision,
                dimension=payload.dimension,
                generated_by=payload.generated_by,
                worker_id=payload.worker_id,
                items=(item.model_dump() for item in payload.items),
                expected_hashes=expected,
            )
        except EmbeddingIndexError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {**result, "task_id": payload.task_id, "workspace_id": payload.workspace_id}

    @router.post("/api/embedding-indexes/{index_id}/query")
    def query_embedding_index(
        index_id: str,
        payload: EmbeddingQueryInput,
    ) -> dict[str, Any]:
        try:
            return store.query(
                index_id,
                payload.vector,
                asset_types=payload.asset_types,
                limit=payload.limit,
            )
        except EmbeddingIndexError as error:
            code = 404 if "not found" in str(error).lower() else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    return router


def _expected_hashes(
    payload: EmbeddingImportInput,
    workspace_store: DatasetWorkspaceStore,
) -> dict[str, str]:
    if not payload.workspace_id:
        return {item.asset_id: item.expected_sha256 for item in payload.items}
    report = workspace_store.read_current_report(payload.workspace_id)
    if report is None:
        raise EmbeddingIndexError("Dataset scan report not found")
    records = {
        str(item.get("relative_path", "")): str(item.get("sha256", ""))
        for item in report.get("images", [])
        if isinstance(item, dict)
    }
    expected = {}
    for item in payload.items:
        known = records.get(item.source_path, "")
        if not known:
            raise EmbeddingIndexError(f"Dataset image not found: {item.source_path}")
        expected[item.asset_id] = known
    return expected
