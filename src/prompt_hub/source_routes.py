from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner
    from prompt_hub.source_sync import SourceSyncService


class SourceSyncInput(BaseModel):
    source_ids: list[str] = Field(default_factory=list, max_length=100)


def create_source_router(
    service: SourceSyncService,
    job_runner: BackgroundJobRunner,
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

    return router
