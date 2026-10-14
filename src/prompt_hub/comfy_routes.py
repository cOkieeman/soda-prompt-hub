from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal, NoReturn
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from prompt_hub.comfy_results import ComfyResultError, ComfyResultStore
from prompt_hub.creative import CreativeProjectConflictError, next_iteration_values
from prompt_hub.result_media import ResultImageError, store_result_image

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner, BackgroundJobStore
    from prompt_hub.config import Settings
    from prompt_hub.creative import CreativeStore


class ComfyDirectoryInput(BaseModel):
    source_path: str = Field(min_length=1, max_length=2000)
    remember: bool = True


class ComfySettingsInput(BaseModel):
    default_directory: str = Field(default="", max_length=2000)


class ComfyResultUpdate(BaseModel):
    disposition: Literal["unreviewed", "candidate", "failed_test", "reference"] | None = None
    note: str | None = Field(default=None, max_length=3000)


class ComfyAttachInput(BaseModel):
    expected_revision: int | None = Field(default=None, ge=1)


def create_comfy_router(
    settings: Settings,
    store: ComfyResultStore,
    creative_store: CreativeStore,
    job_store: BackgroundJobStore,
    job_runner: BackgroundJobRunner,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/comfy-results/scan-jobs/latest")
    def latest_scan_job() -> dict[str, Any] | None:
        jobs = job_store.list_jobs(job_type="comfy_scan", limit=1)
        return jobs[0] if jobs else None

    @router.post("/api/comfy-results/scan-jobs", status_code=status.HTTP_202_ACCEPTED)
    def start_scan_job(payload: ComfyDirectoryInput) -> dict[str, Any]:
        try:
            if payload.remember:
                store.update_settings({"default_directory": payload.source_path})
        except ComfyResultError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        values = payload.model_dump()
        values["import_batch_id"] = f"scan-{uuid4().hex}"
        return job_runner.submit("comfy_scan", values, exclusive=True)

    @router.get("/api/comfy-results/settings")
    def get_comfy_settings() -> dict[str, str]:
        return store.get_settings()

    @router.put("/api/comfy-results/settings")
    def update_comfy_settings(payload: ComfySettingsInput) -> dict[str, str]:
        try:
            return store.update_settings(payload.model_dump())
        except ComfyResultError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/api/comfy-results")
    def list_comfy_results(
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[dict[str, Any]]:
        return store.list_results(limit=limit)

    @router.get("/api/comfy-results/{result_id}")
    def get_comfy_result(result_id: str) -> dict[str, Any]:
        return _require_result(store, result_id)

    @router.post("/api/comfy-results/import", status_code=status.HTTP_201_CREATED)
    async def import_comfy_result(
        request: Request,
        filename: Annotated[str, Query(min_length=1, max_length=180)] = "result.png",
    ) -> dict[str, Any]:
        try:
            return store.import_bytes(await request.body(), filename=filename)
        except ComfyResultError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post("/api/comfy-results/import-directory")
    def import_comfy_directory(payload: ComfyDirectoryInput) -> dict[str, Any]:
        try:
            return store.import_directory(payload.source_path)
        except ComfyResultError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.put("/api/comfy-results/{result_id}")
    def update_comfy_result(
        result_id: str,
        payload: ComfyResultUpdate,
    ) -> dict[str, Any]:
        try:
            return store.update(result_id, payload.model_dump(exclude_unset=True))
        except ComfyResultError as error:
            _raise_comfy_http(error)

    @router.delete("/api/comfy-results/{result_id}")
    def remove_comfy_result(result_id: str) -> dict[str, Any]:
        try:
            return store.remove(result_id)
        except ComfyResultError as error:
            _raise_comfy_http(error)

    @router.post("/api/comfy-results/{result_id}/attach/{project_id}")
    def attach_comfy_result_route(
        result_id: str, project_id: str, payload: ComfyAttachInput | None = None
    ) -> dict[str, Any]:
        return attach_comfy_result(
            settings,
            store,
            creative_store,
            result_id=result_id,
            project_id=project_id,
            selected=False,
            expected_revision=payload.expected_revision if payload else None,
        )

    @router.post("/api/comfy-results/{result_id}/candidate/{project_id}")
    def select_comfy_candidate_route(
        result_id: str, project_id: str, payload: ComfyAttachInput | None = None
    ) -> dict[str, Any]:
        return attach_comfy_result(
            settings,
            store,
            creative_store,
            result_id=result_id,
            project_id=project_id,
            selected=True,
            expected_revision=payload.expected_revision if payload else None,
        )

    @router.post(
        "/api/comfy-results/{result_id}/branch/{project_id}",
        status_code=status.HTTP_201_CREATED,
    )
    def branch_comfy_result(result_id: str, project_id: str) -> dict[str, Any]:
        result = _require_result(store, result_id)
        project = creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        metadata = result.get("metadata", {})
        prompts = metadata.get("text_prompts", []) if isinstance(metadata, dict) else []
        positive = str(prompts[0]) if prompts else ""
        analysis = {
            "model": "ComfyUI metadata",
            "summary_zh": "由 ComfyUI 回流结果建立下一版，保留原始生成参数。",
            "reconstructed_prompts": {
                "anima_positive": positive,
                "anima_negative": "",
                "krea2_positive": positive,
                "krea2_avoid": "",
            },
        }
        asset = {"asset_id": result_id, "filename": result["filename"]}
        values = next_iteration_values(project, asset, analysis)
        lineage = dict(values["lineage"])
        lineage.update(
            {
                "created_from": "comfyui-result-import",
                "comfy_import_id": result_id,
                "comfy_metadata": metadata,
            }
        )
        values["lineage"] = lineage
        child = creative_store.create_project(values)
        store.update(
            result_id,
            {
                "disposition": "reference",
                "association": {"kind": "creative-project-branch", "id": child["project_id"]},
            },
        )
        return child

    @router.get(
        "/comfy-results/{result_id}/{variant}",
        response_class=FileResponse,
        include_in_schema=False,
    )
    def get_comfy_media(result_id: str, variant: Literal["original", "thumbnail"]) -> FileResponse:
        result = _require_result(store, result_id)
        path = store.resolve_media(result_id, variant)
        if path is None:
            raise HTTPException(status_code=404, detail="ComfyUI result file not found")
        media_type = str(result["content_type"]) if variant == "original" else "image/webp"
        return FileResponse(path, media_type=media_type)

    return router


def attach_comfy_result(
    settings: Settings,
    store: ComfyResultStore,
    creative_store: CreativeStore,
    *,
    result_id: str,
    project_id: str,
    selected: bool,
    expected_revision: int | None = None,
) -> dict[str, Any]:
    result = _require_result(store, result_id)
    project = creative_store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Creative project not found")
    if expected_revision is not None and project["revision"] != expected_revision:
        raise HTTPException(status_code=409, detail="项目已改变，请重新读取后再关联结果图")
    generation = dict(project.get("generation", {}))
    raw_assets = generation.get("result_assets", [])
    assets = list(raw_assets) if isinstance(raw_assets, list) else []
    asset = next(
        (
            item
            for item in assets
            if isinstance(item, dict) and item.get("comfy_import_id") == result_id
        ),
        None,
    )
    if asset is None:
        try:
            asset = store_result_image(
                settings,
                project_id=project_id,
                filename=str(result["filename"]),
                raw=store.read_original(result_id),
                safety_mode=str(project["safety_mode"]),
            )
        except (ComfyResultError, ResultImageError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        asset.update(
            {
                "comfy_import_id": result_id,
                "comfy_metadata": result["metadata"],
                "generation_source": "comfyui",
                "dataset_selected": selected,
            }
        )
        assets.append(asset)
    elif selected:
        asset["dataset_selected"] = True
    generation["result_assets"] = assets
    try:
        updated = creative_store.update_project(
            project_id,
            {"generation": generation},
            expected_revision=int(project["revision"]),
        )
    except CreativeProjectConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    disposition = "candidate" if selected else "reference"
    linked = store.update(
        result_id,
        {
            "disposition": disposition,
            "association": {"kind": "creative-project", "id": project_id},
        },
    )
    return {"asset": asset, "project": updated, "result": linked}


def _require_result(store: ComfyResultStore, result_id: str) -> dict[str, Any]:
    result = store.get(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="ComfyUI result not found")
    return result


def _raise_comfy_http(error: ComfyResultError) -> NoReturn:
    code = 404 if "not found" in str(error).lower() else 422
    raise HTTPException(status_code=code, detail=str(error)) from error
