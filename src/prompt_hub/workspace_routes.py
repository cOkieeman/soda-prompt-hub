from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, Never
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from prompt_hub.config import DEFAULT_TAGGER_MODEL_ID
from prompt_hub.dataset_workspace import (
    ARCHIVE_JOB_TYPE,
    MAX_ARCHIVE_UPLOAD_BYTES,
    DatasetWorkspaceError,
    DatasetWorkspaceStore,
)
from prompt_hub.local_model import caption_mode_contract
from prompt_hub.remote_nodes import RemoteNodeError, RemoteNodeStore

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner, BackgroundJobStore
    from prompt_hub.dataset_curation import DatasetCurationStore


class DatasetWorkspaceImport(BaseModel):
    source_path: str = Field(min_length=1, max_length=4096)
    name: str = Field(default="", max_length=160)
    # 来源出处。交接进来的工作区若不记这个。
    # 事后无从分辨它是从哪个筛选项目、哪一版分析交出来的。
    # 跟手动挑的文件夹长得一模一样。
    origin: dict[str, Any] | None = Field(default=None)
    source_origin: str = Field(default="user_directory", max_length=64)


class DatasetReviewItem(BaseModel):
    relative_path: str = Field(min_length=1, max_length=4096)
    status: Literal["pending", "approved", "excluded", "needs_review"] = "pending"
    selected: bool = False
    note: str = Field(default="", max_length=2000)


class DatasetReviewUpdate(BaseModel):
    items: list[DatasetReviewItem] = Field(min_length=1, max_length=1000)


class DatasetWD14QueueInput(BaseModel):
    scope: Literal["untagged", "failed", "selected", "filtered", "all"] = "untagged"
    paths: list[str] = Field(default_factory=list, max_length=100000)
    tagger: Literal["wd14", "model"] = "wd14"
    tagger_model_id: Literal["wd-swinv2-tagger-v3", "idolsankaku-swinv2-tagger-v1"] = (
        DEFAULT_TAGGER_MODEL_ID
    )
    model: str = Field(default="", max_length=400)
    provider: Literal["auto", "coreml", "cpu"] = "auto"
    overwrite: bool = False
    mode: Literal["general", "portrait", "outfit", "style"] = "general"
    trigger: str = Field(default="", max_length=120)
    media_tags: bool = True
    options: dict[str, bool] = Field(default_factory=dict)
    max_tokens: int = Field(default=300, ge=1, le=1200)


class DatasetKrea2VLMQueueInput(BaseModel):
    scope: Literal["selected", "missing", "failed", "all"] = "missing"
    paths: list[str] = Field(default_factory=list, max_length=100000)
    model: str = Field(min_length=1, max_length=400)
    mode: Literal["general", "portrait", "outfit", "style"] = "general"
    trigger: str = Field(default="", max_length=120)
    media_tags: bool = True
    options: dict[str, bool] = Field(default_factory=dict)
    max_tokens: int = Field(default=300, ge=1, le=1200)


class DatasetKrea2DraftInput(BaseModel):
    relative_path: str = Field(min_length=1, max_length=4096)
    draft: str = Field(default="", max_length=12000)
    confirm: bool = False


class DatasetCaptionConfirmInput(BaseModel):
    profile_id: Literal["anima", "krea2"]
    paths: list[str] = Field(min_length=1, max_length=100000)


class DatasetKrea2LocaleQueueInput(BaseModel):
    scope: Literal["selected", "missing", "all"] = "selected"
    paths: list[str] = Field(default_factory=list, max_length=100000)
    overwrite: bool = False


class DatasetKrea2DraftBatchInput(BaseModel):
    paths: list[str] = Field(min_length=1, max_length=100000)
    overwrite_reviewed: bool = False


class DatasetKrea2VLMResultItem(BaseModel):
    relative_path: str = Field(min_length=1, max_length=4096)
    source_sha256: str = Field(min_length=64, max_length=64)
    caption_draft: str = Field(default="", max_length=12000)
    observations: dict[str, Any] = Field(default_factory=dict)
    safety_warning: str = Field(default="", max_length=2000)
    error: str = Field(default="", max_length=2000)


class DatasetKrea2VLMImportInput(BaseModel):
    task_id: str = Field(min_length=1, max_length=200)
    worker_id: str = Field(min_length=1, max_length=160)
    model: str = Field(min_length=1, max_length=400)
    items: list[DatasetKrea2VLMResultItem] = Field(min_length=1, max_length=100000)


class DatasetCaptionInput(BaseModel):
    relative_path: str = Field(min_length=1, max_length=4096)
    profile_id: Literal["anima", "krea2"]
    caption: str = Field(default="", max_length=12000)
    caption_status: Literal["draft", "reviewed"] = "reviewed"
    mode: Literal["general", "portrait", "outfit", "style"] = "general"
    trigger: str = Field(default="", max_length=120)
    media_tags: bool = True
    options: dict[str, bool] = Field(default_factory=dict)
    max_tokens: int = Field(default=300, ge=1, le=1200)


class DatasetSourceCaptionInput(BaseModel):
    profile_id: Literal["anima", "krea2"]
    paths: list[str] = Field(default_factory=list, max_length=100000)
    overwrite_existing: bool = False
    caption_status: Literal["draft", "reviewed"] = "draft"
    mode: Literal["general", "portrait", "outfit", "style"] = "general"
    trigger: str = Field(default="", max_length=120)
    media_tags: bool = True
    options: dict[str, bool] = Field(default_factory=dict)
    max_tokens: int = Field(default=300, ge=1, le=1200)


class DatasetBulkTagsInput(BaseModel):
    profile_id: Literal["anima", "krea2"] = "anima"
    paths: list[str] = Field(min_length=1, max_length=100000)
    add: list[str] = Field(default_factory=list, max_length=500)
    prepend: list[str] = Field(default_factory=list, max_length=50)
    remove: list[str] = Field(default_factory=list, max_length=500)
    replace: dict[str, str] = Field(default_factory=dict)
    sort: bool = False
    mode: Literal["general", "portrait", "outfit", "style"] = "general"
    trigger: str = Field(default="", max_length=120)
    media_tags: bool = True
    options: dict[str, bool] = Field(default_factory=dict)
    max_tokens: int = Field(default=300, ge=1, le=1200)


class DatasetConflictRule(BaseModel):
    rule_id: str = Field(default="", max_length=120)
    tags: list[str] = Field(min_length=2, max_length=20)


class DatasetConflictRulesInput(BaseModel):
    rules: list[DatasetConflictRule] = Field(max_length=200)


class DatasetWorkspaceExportInput(BaseModel):
    profile_id: Literal["anima", "krea2"]
    paths: list[str] = Field(min_length=1, max_length=100000)


class DatasetWorkspaceCopyInput(BaseModel):
    node_id: str = Field(default="compute_5060ti", min_length=1, max_length=160)


def create_workspace_router(
    workspace_store: DatasetWorkspaceStore,
    curation_store: DatasetCurationStore,
    job_store: BackgroundJobStore,
    job_runner: BackgroundJobRunner,
    remote_store: RemoteNodeStore,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/dataset-workspaces")
    def list_dataset_workspaces() -> list[dict[str, Any]]:
        return workspace_store.list_workspaces()

    @router.get("/api/dataset-workspaces/caption-modes")
    def get_dataset_workspace_caption_modes() -> dict[str, Any]:
        return caption_mode_contract()

    @router.get("/api/dataset-workspaces/browse")
    def browse_dataset_directories(
        path: Annotated[str, Query(max_length=4096)] = "",
    ) -> dict[str, Any]:
        try:
            return workspace_store.browse_directory(path or None)
        except DatasetWorkspaceError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.post(
        "/api/dataset-workspaces/import",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def import_dataset_workspace(payload: DatasetWorkspaceImport) -> dict[str, Any]:
        try:
            workspace = workspace_store.register(
                payload.source_path,
                name=payload.name,
                origin=payload.origin,
                source_origin=payload.source_origin,
            )
        except DatasetWorkspaceError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        job = job_runner.submit(
            "dataset_scan",
            {"workspace_id": workspace["workspace_id"]},
            max_attempts=2,
        )
        return {"workspace": workspace, "job": job}

    @router.post(
        "/api/dataset-workspaces/import-zip",
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def import_dataset_archive(
        request: Request,
        filename: Annotated[str, Query(min_length=1, max_length=180)] = "",
        name: Annotated[str, Query(max_length=160)] = "",
    ) -> dict[str, Any]:
        archive_name = Path(filename).name
        if not archive_name.lower().endswith(".zip"):
            raise HTTPException(status_code=422, detail="只支持 .zip 压缩包")
        staging_root = workspace_store.settings.imported_archives_root / ".staging"
        staging_root.mkdir(parents=True, exist_ok=True)
        archive_id = f"zip-{uuid4().hex[:12]}"
        staged = staging_root / f"{archive_id}.zip"
        received = 0
        try:
            with staged.open("wb") as sink:
                async for chunk in request.stream():
                    received += len(chunk)
                    if received > MAX_ARCHIVE_UPLOAD_BYTES:
                        limit_gib = MAX_ARCHIVE_UPLOAD_BYTES / (1024**3)
                        raise DatasetWorkspaceError(f"压缩包超过上传上限（{limit_gib:.0f} GiB）")
                    sink.write(chunk)
        except DatasetWorkspaceError as error:
            staged.unlink(missing_ok=True)
            raise HTTPException(status_code=413, detail=str(error)) from error
        except Exception:
            staged.unlink(missing_ok=True)
            raise
        if received == 0:
            staged.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail="上传内容为空")
        job = job_runner.submit(
            ARCHIVE_JOB_TYPE,
            {
                "archive_path": str(staged),
                "archive_id": archive_id,
                "filename": archive_name,
                "name": name.strip(),
            },
        )
        return {"job": job, "archive_id": archive_id, "filename": archive_name}

    @router.get("/api/dataset-workspaces/{workspace_id}")
    def get_dataset_workspace(workspace_id: str) -> dict[str, Any]:
        workspace = workspace_store.get(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Dataset workspace not found")
        return workspace

    @router.get("/api/dataset-workspaces/{workspace_id}/report")
    def get_dataset_workspace_report(workspace_id: str) -> dict[str, Any]:
        if workspace_store.get(workspace_id) is None:
            raise HTTPException(status_code=404, detail="Dataset workspace not found")
        report = workspace_store.read_current_report(workspace_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Dataset scan report not found")
        review_state = workspace_store.read_review_state(workspace_id)
        for image in report.get("images", []):
            if not isinstance(image, dict):
                continue
            thumbnail = str(image.get("thumbnail", ""))
            if thumbnail:
                image["thumbnail_url"] = (
                    f"/dataset-workspaces/{workspace_id}/thumbnails/{thumbnail.rsplit('/', 1)[-1]}"
                )
            relative_path = str(image.get("relative_path", ""))
            image["original_url"] = (
                f"/dataset-workspaces/{workspace_id}/original"
                f"?relative_path={quote(relative_path, safe='')}"
            )
            image["review"] = review_state.get(
                relative_path,
                {"status": "pending", "selected": False, "note": ""},
            )
        return curation_store.decorate_report(workspace_id, report)

    @router.put("/api/dataset-workspaces/{workspace_id}/review")
    def update_dataset_workspace_review(
        workspace_id: str,
        payload: DatasetReviewUpdate,
    ) -> dict[str, Any]:
        try:
            state = workspace_store.update_review_state(
                workspace_id,
                (item.model_dump() for item in payload.items),
            )
        except DatasetWorkspaceError as error:
            status_code = 404 if "not found" in str(error).lower() else 422
            raise HTTPException(status_code=status_code, detail=str(error)) from error
        return {"workspace_id": workspace_id, "updated": len(payload.items), "items": state}

    @router.post(
        "/api/dataset-workspaces/{workspace_id}/wd14",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def queue_dataset_workspace_wd14(
        workspace_id: str,
        payload: DatasetWD14QueueInput,
    ) -> dict[str, Any]:
        if workspace_store.get(workspace_id) is None:
            raise HTTPException(status_code=404, detail="Dataset workspace not found")
        if payload.tagger == "model" and not payload.model.strip():
            raise HTTPException(status_code=422, detail="使用模型打标时必须选择打标模型")
        job = job_runner.submit(
            "dataset_wd14",
            {"workspace_id": workspace_id, **payload.model_dump()},
            # 只在「一张都没成功」时才算失败。那几乎总是决定性的原因——
            # 送错模型、服务没开、来源不见了。重跑整批只是把成本加倍。
            # 扫描可以重试。它便宜。这两个每张都要呼叫一次模型。
            max_attempts=1,
        )
        return {"workspace_id": workspace_id, "job": job}

    @router.post(
        "/api/dataset-workspaces/{workspace_id}/krea2-vlm",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def queue_dataset_workspace_krea2_vlm(
        workspace_id: str,
        payload: DatasetKrea2VLMQueueInput,
    ) -> dict[str, Any]:
        if workspace_store.get(workspace_id) is None:
            raise HTTPException(status_code=404, detail="Dataset workspace not found")
        job = job_runner.submit(
            "dataset_krea2_vlm",
            {"workspace_id": workspace_id, **payload.model_dump()},
            # 只在「一张都没成功」时才算失败。那几乎总是决定性的原因——
            # 送错模型、服务没开、来源不见了。重跑整批只是把成本加倍。
            # 扫描可以重试。它便宜。这两个每张都要呼叫一次模型。
            max_attempts=1,
        )
        return {"workspace_id": workspace_id, "job": job}

    @router.put("/api/dataset-workspaces/{workspace_id}/krea2-draft")
    def update_dataset_workspace_krea2_draft(
        workspace_id: str,
        payload: DatasetKrea2DraftInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.update_krea2_draft(
                workspace_id,
                payload.relative_path,
                draft=payload.draft,
                confirm=payload.confirm,
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post("/api/dataset-workspaces/{workspace_id}/captions/confirm")
    def confirm_dataset_workspace_captions(
        workspace_id: str,
        payload: DatasetCaptionConfirmInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.confirm_captions(
                workspace_id,
                payload.paths,
                profile_id=payload.profile_id,
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post(
        "/api/dataset-workspaces/{workspace_id}/krea2-locale",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def queue_dataset_workspace_krea2_locale(
        workspace_id: str,
        payload: DatasetKrea2LocaleQueueInput,
    ) -> dict[str, Any]:
        if workspace_store.get(workspace_id) is None:
            raise HTTPException(status_code=404, detail="Dataset workspace not found")
        job = job_runner.submit(
            "dataset_krea2_locale",
            {"workspace_id": workspace_id, **payload.model_dump()},
            # 和打标、草稿一样每张都要呼叫一次模型。整批失败几乎总是同一个原因。
            max_attempts=1,
        )
        return {"workspace_id": workspace_id, "job": job}

    @router.post("/api/dataset-workspaces/{workspace_id}/krea2-drafts/confirm")
    def confirm_dataset_workspace_krea2_drafts(
        workspace_id: str,
        payload: DatasetKrea2DraftBatchInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.confirm_krea2_drafts(
                workspace_id,
                payload.paths,
                overwrite_reviewed=payload.overwrite_reviewed,
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post(
        "/api/dataset-workspaces/{workspace_id}/krea2-vlm/import",
        status_code=status.HTTP_201_CREATED,
    )
    def import_dataset_workspace_krea2_vlm(
        workspace_id: str,
        payload: DatasetKrea2VLMImportInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.import_krea2_vlm_results(
                workspace_id,
                model=payload.model,
                worker_id=payload.worker_id,
                task_id=payload.task_id,
                items=(item.model_dump() for item in payload.items),
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.get("/api/dataset-workspaces/{workspace_id}/analytics")
    def get_dataset_workspace_analytics(workspace_id: str) -> dict[str, Any]:
        try:
            return curation_store.analytics(workspace_id)
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    def _update_dataset_workspace_caption(
        workspace_id: str,
        payload: DatasetCaptionInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.update_caption(
                workspace_id,
                payload.relative_path,
                profile_id=payload.profile_id,
                caption=payload.caption,
                status=payload.caption_status,
                caption_settings=payload.model_dump(
                    include={"mode", "trigger", "media_tags", "options", "max_tokens"}
                ),
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post("/api/dataset-workspaces/{workspace_id}/caption")
    def post_dataset_workspace_caption(
        workspace_id: str,
        payload: DatasetCaptionInput,
    ) -> dict[str, Any]:
        return _update_dataset_workspace_caption(workspace_id, payload)

    @router.put("/api/dataset-workspaces/{workspace_id}/caption")
    def put_dataset_workspace_caption(
        workspace_id: str,
        payload: DatasetCaptionInput,
    ) -> dict[str, Any]:
        return _update_dataset_workspace_caption(workspace_id, payload)

    @router.post("/api/dataset-workspaces/{workspace_id}/source-captions/preview")
    def preview_dataset_workspace_source_captions(
        workspace_id: str,
        payload: DatasetSourceCaptionInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.source_caption_preview(
                workspace_id,
                profile_id=payload.profile_id,
                paths=payload.paths,
                overwrite_existing=payload.overwrite_existing,
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post("/api/dataset-workspaces/{workspace_id}/source-captions/apply")
    def apply_dataset_workspace_source_captions(
        workspace_id: str,
        payload: DatasetSourceCaptionInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.apply_source_captions(
                workspace_id,
                profile_id=payload.profile_id,
                paths=payload.paths,
                overwrite_existing=payload.overwrite_existing,
                status=payload.caption_status,
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post("/api/dataset-workspaces/{workspace_id}/bulk-tags/preview")
    def preview_dataset_workspace_bulk_tags(
        workspace_id: str,
        payload: DatasetBulkTagsInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.bulk_preview(
                workspace_id,
                payload.paths,
                payload.model_dump(exclude={"paths"}),
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post("/api/dataset-workspaces/{workspace_id}/bulk-tags/apply")
    def apply_dataset_workspace_bulk_tags(
        workspace_id: str,
        payload: DatasetBulkTagsInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.apply_bulk_edit(
                workspace_id,
                payload.paths,
                payload.model_dump(exclude={"paths"}),
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.get("/api/dataset-workspaces/{workspace_id}/snapshots")
    def list_dataset_workspace_snapshots(workspace_id: str) -> list[dict[str, Any]]:
        try:
            return curation_store.list_snapshots(workspace_id)
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post("/api/dataset-workspaces/{workspace_id}/snapshots/{snapshot_id}/rollback")
    def rollback_dataset_workspace_snapshot(
        workspace_id: str,
        snapshot_id: str,
    ) -> dict[str, Any]:
        try:
            return curation_store.rollback_snapshot(workspace_id, snapshot_id)
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.get("/api/dataset-workspaces/{workspace_id}/conflict-rules")
    def get_dataset_workspace_conflict_rules(workspace_id: str) -> list[dict[str, Any]]:
        try:
            return curation_store.read_conflict_rules(workspace_id)
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.put("/api/dataset-workspaces/{workspace_id}/conflict-rules")
    def update_dataset_workspace_conflict_rules(
        workspace_id: str,
        payload: DatasetConflictRulesInput,
    ) -> list[dict[str, Any]]:
        try:
            return curation_store.update_conflict_rules(
                workspace_id,
                (rule.model_dump() for rule in payload.rules),
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post("/api/dataset-workspaces/{workspace_id}/export", status_code=201)
    def export_dataset_workspace_version(
        workspace_id: str,
        payload: DatasetWorkspaceExportInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.export_version(
                workspace_id,
                profile_id=payload.profile_id,
                paths=payload.paths,
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post("/api/dataset-workspaces/{workspace_id}/preflight")
    def preflight_dataset_workspace_export(
        workspace_id: str,
        payload: DatasetWorkspaceExportInput,
    ) -> dict[str, Any]:
        try:
            return curation_store.preflight_export(
                workspace_id,
                profile_id=payload.profile_id,
                paths=payload.paths,
            )
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.get("/api/dataset-workspaces/{workspace_id}/exports")
    def list_dataset_workspace_exports(workspace_id: str) -> list[dict[str, Any]]:
        try:
            return curation_store.list_exports(workspace_id)
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)

    @router.post(
        "/api/dataset-workspaces/{workspace_id}/exports/{version_id}/copy",
        status_code=status.HTTP_201_CREATED,
    )
    def copy_dataset_workspace_export(
        workspace_id: str,
        version_id: str,
        payload: DatasetWorkspaceCopyInput,
        response: Response,
    ) -> dict[str, Any]:
        try:
            result = curation_store.copy_export_to_share(
                workspace_id,
                version_id,
                node_id=payload.node_id,
                bridge_root=_required_delivery_root(remote_store, payload.node_id),
            )
        except (DatasetWorkspaceError, RemoteNodeError) as error:
            _raise_workspace_http(error)
        if result["status"] == "already_present":
            response.status_code = status.HTTP_200_OK
        return result

    @router.post("/api/dataset-workspaces/{workspace_id}/exports/{version_id}/reveal")
    def reveal_dataset_workspace_export(workspace_id: str, version_id: str) -> dict[str, Any]:
        try:
            path = curation_store.resolve_export_directory(workspace_id, version_id)
        except DatasetWorkspaceError as error:
            _raise_workspace_http(error)
        if path is None:
            raise HTTPException(status_code=404, detail="Dataset export version not found")
        _reveal_in_finder(path)
        return {"workspace_id": workspace_id, "version_id": version_id, "revealed": True}

    @router.get(
        "/dataset-workspaces/{workspace_id}/exports/{filename}",
        response_class=FileResponse,
        include_in_schema=False,
    )
    def download_dataset_workspace_export(workspace_id: str, filename: str) -> FileResponse:
        path = curation_store.resolve_export(workspace_id, filename)
        if path is None:
            raise HTTPException(status_code=404, detail="Dataset export not found")
        return FileResponse(path, media_type="application/zip", filename=path.name)

    @router.get(
        "/dataset-workspaces/{workspace_id}/thumbnails/{filename}",
        response_class=FileResponse,
        include_in_schema=False,
    )
    def get_dataset_workspace_thumbnail(workspace_id: str, filename: str) -> FileResponse:
        path = workspace_store.resolve_thumbnail(workspace_id, filename)
        if path is None:
            raise HTTPException(status_code=404, detail="Dataset thumbnail not found")
        return FileResponse(path, media_type="image/webp")

    @router.get(
        "/dataset-workspaces/{workspace_id}/original",
        response_class=FileResponse,
        include_in_schema=False,
    )
    def get_dataset_workspace_original(
        workspace_id: str,
        relative_path: Annotated[str, Query(min_length=1, max_length=4096)],
    ) -> FileResponse:
        path = workspace_store.resolve_source_image(workspace_id, relative_path)
        if path is None:
            raise HTTPException(status_code=404, detail="Dataset image not found")
        return FileResponse(path)

    @router.post(
        "/api/dataset-workspaces/{workspace_id}/rescan",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def rescan_dataset_workspace(workspace_id: str) -> dict[str, Any]:
        workspace = workspace_store.get(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Dataset workspace not found")
        job = job_runner.submit(
            "dataset_scan",
            {"workspace_id": workspace_id},
            max_attempts=2,
        )
        return {"workspace": workspace, "job": job}

    @router.delete("/api/dataset-workspaces/{workspace_id}")
    def remove_dataset_workspace(workspace_id: str) -> dict[str, Any]:
        workspace = workspace_store.remove(workspace_id)
        if workspace is None:
            raise HTTPException(status_code=404, detail="Dataset workspace not found")
        zip_archive = str(workspace.get("source_origin", "")) == "zip_archive"
        return {
            "removed": True,
            "workspace_id": workspace_id,
            "source_path": workspace["source_path"],
            "source_origin": workspace.get("source_origin", "user_directory"),
            "source_untouched": not zip_archive,
            "archive_copy_removed": zip_archive,
        }

    @router.get("/api/jobs")
    def list_background_jobs(
        job_status: Literal["queued", "running", "completed", "failed", "canceled"] | None = (None),
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[dict[str, Any]]:
        return job_store.list_jobs(status=job_status or "", limit=limit)

    @router.get("/api/jobs/{job_id}")
    def get_background_job(job_id: str) -> dict[str, Any]:
        job = job_store.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Background job not found")
        return job

    @router.post("/api/jobs/{job_id}/cancel")
    def cancel_background_job(job_id: str) -> dict[str, Any]:
        job = job_store.request_cancel(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Background job not found")
        return job

    @router.post("/api/jobs/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
    def retry_background_job(job_id: str) -> dict[str, Any]:
        previous = job_store.get(job_id)
        if previous is None:
            raise HTTPException(status_code=404, detail="Background job not found")
        if previous["status"] not in {"failed", "canceled"}:
            raise HTTPException(status_code=409, detail="Only failed or canceled jobs can retry")
        job = job_store.retry(job_id)
        job_runner.wake()
        if job is None:  # pragma: no cover - guarded by get above
            raise HTTPException(status_code=404, detail="Background job not found")
        return job

    return router


def _reveal_in_finder(path: Path) -> None:
    result = subprocess.run(  # noqa: S603 - executable and arguments are fixed by the app.
        ["/usr/bin/open", "-R", str(path)],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise HTTPException(status_code=503, detail="无法打开 Finder, 请稍后重试")


def _required_delivery_root(remote_store: RemoteNodeStore, node_id: str) -> Path:
    diagnostic = remote_store.diagnostics(node_id)
    if not diagnostic.get("bridge_prepared") or not diagnostic.get("bridge_writable"):
        message = "Windows 设备共享目录离线或不可写, 请先在 Finder 挂载"
        raise RemoteNodeError(message)
    return Path(str(diagnostic["bridge_root"]))


def _raise_workspace_http(error: DatasetWorkspaceError | RemoteNodeError) -> Never:
    status_code = 404 if "not found" in str(error).lower() else 422
    raise HTTPException(status_code=status_code, detail=str(error)) from error
