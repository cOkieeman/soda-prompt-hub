from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from prompt_hub.web_capture import WebCaptureError, WebCaptureService

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner
    from prompt_hub.source_sync import SourceSyncService


class SourceSyncInput(BaseModel):
    source_ids: list[str] = Field(default_factory=list, max_length=100)


class WebCaptureInput(BaseModel):
    url: str = Field(min_length=8, max_length=4096)
    title: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=6000)
    safety: str = Field(default="sfw", max_length=40)
    license_name: str = Field(default="unknown", max_length=160)


def create_source_router(
    service: SourceSyncService,
    job_runner: BackgroundJobRunner,
    web_capture: WebCaptureService,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/sources/sync-status")
    def get_source_sync_status() -> list[dict[str, Any]]:
        return service.status()

    @router.post("/api/sources/sync", status_code=status.HTTP_202_ACCEPTED)
    def sync_sources(payload: SourceSyncInput) -> dict[str, Any]:
        job = job_runner.submit(
            "source_sync",
            {"source_ids": payload.source_ids},
            max_attempts=1,
        )
        return {"job": job}

    @router.get("/api/web-captures")
    def list_web_captures() -> list[dict[str, Any]]:
        return web_capture.list_captures()

    @router.post("/api/web-captures", status_code=status.HTTP_201_CREATED)
    def save_web_capture(payload: WebCaptureInput) -> dict[str, Any]:
        try:
            return web_capture.capture(**payload.model_dump())
        except WebCaptureError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/web-captures/{capture_id}/media", response_class=FileResponse)
    def read_web_capture_media(capture_id: str) -> FileResponse:
        try:
            path = web_capture.resolve_media(capture_id)
        except WebCaptureError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return FileResponse(path)

    return router
