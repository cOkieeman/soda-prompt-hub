from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from prompt_hub.remote_nodes import RemoteNodeError, RemoteNodeStore


class RemoteNodeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(default="", max_length=160)
    role: Literal["compute_5060ti"]
    host: str = Field(default="", max_length=255)
    smb_mount: str = Field(default="", max_length=4096)
    enabled: bool = False
    capabilities: list[str] = Field(default_factory=list, max_length=50)
    notes: str = Field(default="", max_length=1000)


class LoraCatalogItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lora_id: str = Field(min_length=1, max_length=160)
    name: str = Field(default="", max_length=300)
    relative_path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(default="", max_length=64)
    size_bytes: int = Field(default=0, ge=0)
    base_model: str = Field(default="", max_length=300)
    model_family: str = Field(default="", max_length=160)
    trigger_words: list[str] = Field(default_factory=list, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=300)
    preview_relative_path: str = Field(default="", max_length=4096)
    preview_relative_paths: list[str] = Field(default_factory=list, max_length=100)
    notes: str = Field(default="", max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RemoteTaskManifestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relative_path: str = Field(min_length=1, max_length=4096)
    sha256: str = Field(min_length=64, max_length=64)
    size_bytes: int = Field(default=0, ge=0)


class RemoteTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any]
    manifest: list[RemoteTaskManifestItem] = Field(max_length=100000)
    project_id: str = Field(default="", max_length=160)
    workspace_id: str = Field(default="", max_length=160)
    run_id: str = Field(default="", max_length=160)
    priority: int = Field(default=0, ge=-100, le=100)


class LoraCatalogImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str = Field(min_length=1, max_length=160)
    worker_id: str = Field(min_length=1, max_length=160)
    source_manager: str = Field(default="ComfyUI LoRA Manager", max_length=200)
    items: list[LoraCatalogItemInput] = Field(min_length=1, max_length=100000)


def create_remote_router(store: RemoteNodeStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/remote-nodes")
    def list_remote_nodes() -> list[dict[str, Any]]:
        return store.list_nodes()

    @router.put("/api/remote-nodes/{node_id}")
    def save_remote_node(node_id: str, payload: RemoteNodeInput) -> dict[str, Any]:
        try:
            return store.save_node(node_id, payload.model_dump())
        except RemoteNodeError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/remote-nodes/{node_id}/diagnostics")
    def diagnose_remote_node(node_id: str) -> dict[str, Any]:
        try:
            return store.diagnostics(node_id)
        except RemoteNodeError as error:
            code = 404 if "尚未登记" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.post("/api/remote-nodes/{node_id}/prepare", status_code=status.HTTP_201_CREATED)
    def prepare_remote_node_bridge(node_id: str) -> dict[str, Any]:
        try:
            return store.prepare_bridge(node_id)
        except RemoteNodeError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/remote-nodes/{node_id}/tasks")
    def list_remote_tasks(
        node_id: str,
        limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    ) -> list[dict[str, Any]]:
        try:
            return store.list_tasks(node_id, limit=limit)
        except RemoteNodeError as error:
            code = 404 if "尚未登记" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.post(
        "/api/remote-nodes/{node_id}/tasks",
        status_code=status.HTTP_201_CREATED,
    )
    def submit_remote_task(node_id: str, payload: RemoteTaskInput) -> dict[str, Any]:
        try:
            values = payload.model_dump()
            return store.submit_task(node_id, values)
        except RemoteNodeError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/remote-nodes/{node_id}/tasks/{task_id}")
    def get_remote_task(node_id: str, task_id: str) -> dict[str, Any]:
        try:
            return store.get_task(node_id, task_id)
        except RemoteNodeError as error:
            code = 404 if "不存在" in str(error) or "尚未登记" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.post(
        "/api/remote-nodes/{node_id}/tasks/{task_id}/retry",
        status_code=status.HTTP_201_CREATED,
    )
    def retry_remote_task(node_id: str, task_id: str) -> dict[str, Any]:
        try:
            return store.retry_task(node_id, task_id)
        except RemoteNodeError as error:
            code = 404 if "不存在" in str(error) or "尚未登记" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.get("/api/remote-nodes/{node_id}/tasks/{task_id}/integrity")
    def verify_remote_task(node_id: str, task_id: str) -> dict[str, Any]:
        try:
            return store.verify_returned_task(node_id, task_id)
        except RemoteNodeError as error:
            code = 404 if "不存在" in str(error) or "尚未" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.post("/api/remote-nodes/{node_id}/tasks/{task_id}/cancel")
    def cancel_remote_task(node_id: str, task_id: str) -> dict[str, Any]:
        try:
            return store.cancel_task(node_id, task_id)
        except RemoteNodeError as error:
            code = 404 if "不存在" in str(error) or "尚未" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.post(
        "/api/remote-nodes/{node_id}/lora-catalog/sync",
        status_code=status.HTTP_201_CREATED,
    )
    def sync_windows_lora_catalog(node_id: str) -> dict[str, Any]:
        try:
            return store.submit_lora_catalog_snapshot(node_id)
        except RemoteNodeError as error:
            code = 404 if "尚未登记" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.post(
        "/api/remote-nodes/{node_id}/tasks/{task_id}/import-lora-catalog",
        status_code=status.HTTP_201_CREATED,
    )
    def import_returned_windows_lora_catalog(node_id: str, task_id: str) -> dict[str, Any]:
        try:
            return store.import_returned_lora_catalog(node_id, task_id)
        except RemoteNodeError as error:
            code = 404 if "不存在" in str(error) or "尚未" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.get("/api/windows-loras/status")
    def windows_lora_status() -> dict[str, Any]:
        return store.lora_catalog_status()

    @router.get("/api/windows-loras")
    def search_windows_loras(
        query: str = "",
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> dict[str, Any]:
        results = store.search_loras(query, limit=limit)
        return {"query": query, "count": len(results), "results": results}

    @router.get(
        "/api/windows-loras/previews/{snapshot_id}/{lora_id}/{filename}",
        response_class=FileResponse,
        include_in_schema=False,
    )
    def get_windows_lora_preview(
        snapshot_id: str,
        lora_id: str,
        filename: str,
    ) -> FileResponse:
        try:
            path, media_type = store.resolve_lora_preview(snapshot_id, lora_id, filename)
        except RemoteNodeError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(path, media_type=media_type)

    @router.post(
        "/api/remote-nodes/{node_id}/model-catalog/sync",
        status_code=status.HTTP_201_CREATED,
    )
    def sync_windows_model_catalog(node_id: str) -> dict[str, Any]:
        try:
            return store.submit_model_catalog_snapshot(node_id)
        except RemoteNodeError as error:
            code = 404 if "尚未登记" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.post(
        "/api/remote-nodes/{node_id}/tasks/{task_id}/import-model-catalog",
        status_code=status.HTTP_201_CREATED,
    )
    def import_returned_windows_model_catalog(node_id: str, task_id: str) -> dict[str, Any]:
        try:
            return store.import_returned_model_catalog(node_id, task_id)
        except RemoteNodeError as error:
            code = 404 if "不存在" in str(error) or "尚未" in str(error) else 422
            raise HTTPException(status_code=code, detail=str(error)) from error

    @router.get("/api/windows-models/status")
    def windows_model_status() -> dict[str, Any]:
        return store.model_catalog_status()

    @router.get(
        "/api/windows-models/previews/{snapshot_id}/{asset_id}/{filename}",
        response_class=FileResponse,
        include_in_schema=False,
    )
    def get_windows_model_preview(
        snapshot_id: str,
        asset_id: str,
        filename: str,
    ) -> FileResponse:
        try:
            path, media_type = store.resolve_model_preview(snapshot_id, asset_id, filename)
        except RemoteNodeError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(path, media_type=media_type)

    @router.get("/api/windows-models")
    def search_windows_models(
        query: str = "",
        asset_type: str = "",
        model_family: str = "",
        limit: Annotated[int, Query(ge=1, le=2000)] = 200,
    ) -> dict[str, Any]:
        try:
            results = store.search_models(
                query,
                asset_type=asset_type,
                model_family=model_family,
                limit=limit,
            )
        except RemoteNodeError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "query": query,
            "asset_type": asset_type,
            "model_family": model_family,
            "count": len(results),
            "results": results,
        }

    @router.post("/api/windows-loras/import", status_code=status.HTTP_201_CREATED)
    def import_windows_loras(payload: LoraCatalogImportInput) -> dict[str, Any]:
        try:
            return store.import_lora_catalog(
                snapshot_id=payload.snapshot_id,
                worker_id=payload.worker_id,
                source_manager=payload.source_manager,
                items=[item.model_dump() for item in payload.items],
            )
        except RemoteNodeError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    return router
