from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from prompt_hub.creative import compile_prompt
from prompt_hub.dataset_workspace import DatasetWorkspaceError
from prompt_hub.remote_nodes import RemoteNodeError
from prompt_hub.result_assets import result_asset_path, selected_result_assets

if TYPE_CHECKING:
    from prompt_hub.background_jobs import BackgroundJobRunner, BackgroundJobStore
    from prompt_hub.config import Settings
    from prompt_hub.creative import CreativeStore
    from prompt_hub.dataset_curation import DatasetCurationStore
    from prompt_hub.dataset_workspace import DatasetWorkspaceStore
    from prompt_hub.remote_nodes import RemoteNodeStore


LINEAGE_FILENAME = ".prompt-hub-lineage.json"
PROFILE_COUNT = 2


class ProjectJourneyError(ValueError):
    pass


class ProjectDatasetSyncInput(BaseModel):
    profile_id: Literal["anima", "krea2"] = "anima"


@dataclass(frozen=True, slots=True)
class ProjectJourneyServices:
    settings: Settings
    creative_store: CreativeStore
    workspace_store: DatasetWorkspaceStore
    curation_store: DatasetCurationStore
    job_store: BackgroundJobStore
    job_runner: BackgroundJobRunner
    remote_store: RemoteNodeStore


@dataclass(frozen=True, slots=True)
class ProjectSyncContext:
    settings: Settings
    project: Mapping[str, Any]
    project_id: str
    profile_id: Literal["anima", "krea2"]
    compiled: dict[str, dict[str, Any]]
    default_caption: str
    generation: Mapping[str, Any]
    source_root: Path


@dataclass(frozen=True, slots=True)
class JourneyFacts:
    project: Mapping[str, Any]
    filled_slots: int
    reference_count: int
    prompt_ready: int
    tasks: list[dict[str, Any]]
    assets: list[Mapping[str, Any]]
    selected: list[Mapping[str, Any]]
    latest_workspace: Mapping[str, Any] | None
    exports: list[dict[str, Any]]
    latest_export: Mapping[str, Any] | None


def create_project_journey_router(services: ProjectJourneyServices) -> APIRouter:
    router = APIRouter()

    @router.get("/api/creative/projects/{project_id}/journey")
    def get_project_journey(project_id: str) -> dict[str, Any]:
        project = services.creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        return build_project_journey(
            project,
            workspace_store=services.workspace_store,
            curation_store=services.curation_store,
            remote_store=services.remote_store,
        )

    @router.post(
        "/api/creative/projects/{project_id}/dataset-workspace",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def sync_project_dataset(
        project_id: str,
        payload: ProjectDatasetSyncInput,
    ) -> dict[str, Any]:
        project = services.creative_store.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Creative project not found")
        try:
            synced = sync_project_results(
                services.settings,
                project=project,
                profile_id=payload.profile_id,
            )
            workspace = services.workspace_store.register(
                synced["source_path"],
                name=f"{project.get('title', '绘图项目')} · 精选结果",
                origin=synced["origin"],
            )
            job = services.job_store.enqueue(
                "dataset_scan",
                {"workspace_id": workspace["workspace_id"]},
                max_attempts=2,
            )
            services.job_runner.wake()
        except (DatasetWorkspaceError, OSError, ProjectJourneyError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "workspace": workspace,
            "job": job,
            "synced": synced["synced"],
            "existing": synced["existing"],
            "profile_id": payload.profile_id,
            "review_changed": False,
        }

    return router


def sync_project_results(
    settings: Settings,
    *,
    project: Mapping[str, Any],
    profile_id: Literal["anima", "krea2"],
) -> dict[str, Any]:
    context = _project_sync_context(settings, project, profile_id)
    assets = selected_result_assets(dict(project))
    if not assets:
        message = "请先在结果图中至少手动精选一张图片"
        raise ProjectJourneyError(message)
    lineage_path = context.source_root / LINEAGE_FILENAME
    existing_lineage = _read_lineage(lineage_path)
    raw_items = existing_lineage.get("items", {})
    items = dict(raw_items) if isinstance(raw_items, Mapping) else {}
    results = [_sync_project_asset(context, asset) for asset in assets]
    for result in results:
        items[str(result["relative_image"])] = result["lineage"]
    origin = _project_origin(context, [str(result["asset_id"]) for result in results])
    _atomic_json(
        lineage_path,
        {
            "format": "soda-prompt-hub-project-dataset-lineage-v1",
            "origin": origin,
            "compiled_prompts": context.compiled,
            "items": items,
            "updated_at": _now(),
        },
    )
    return {
        "source_path": context.source_root,
        "origin": origin,
        "synced": sum(bool(result["created"]) for result in results),
        "existing": sum(not bool(result["created"]) for result in results),
    }


def _project_sync_context(
    settings: Settings,
    project: Mapping[str, Any],
    profile_id: Literal["anima", "krea2"],
) -> ProjectSyncContext:
    project_id = str(project.get("project_id", "")).strip()
    if not project_id or Path(project_id).name != project_id:
        message = "项目缺少有效的 project_id"
        raise ProjectJourneyError(message)
    compiled = {profile: compile_prompt(project, profile) for profile in ("anima", "krea2")}
    default_caption = str(compiled[profile_id].get("positive", "")).strip()
    if not default_caption:
        message = f"当前 {profile_id.upper()} Prompt 还没有可用内容"
        raise ProjectJourneyError(message)
    source_root = (settings.project_dataset_sources_root / project_id).resolve()
    if not source_root.is_relative_to(settings.project_dataset_sources_root.resolve()):
        message = "项目数据集目录无效"
        raise ProjectJourneyError(message)
    source_root.mkdir(parents=True, exist_ok=True)
    generation = project.get("generation", {})
    return ProjectSyncContext(
        settings=settings,
        project=project,
        project_id=project_id,
        profile_id=profile_id,
        compiled=compiled,
        default_caption=default_caption,
        generation=generation if isinstance(generation, Mapping) else {},
        source_root=source_root,
    )


def _sync_project_asset(
    context: ProjectSyncContext,
    asset: Mapping[str, Any],
) -> dict[str, Any]:
    asset_id = str(asset.get("asset_id", "")).strip()
    if not asset_id or Path(asset_id).name != asset_id:
        message = "结果图缺少有效 asset_id"
        raise ProjectJourneyError(message)
    source = result_asset_path(context.settings, context.project_id, dict(asset))
    relative_image = f"results/{asset_id}{source.suffix.casefold()}"
    target = context.source_root / relative_image
    target.parent.mkdir(parents=True, exist_ok=True)
    source_hash = _sha256(source)
    created = not target.is_file()
    if not created and _sha256(target) != source_hash:
        message = f"数据集工作区已有同名但内容不同的图片: {asset_id}"
        raise ProjectJourneyError(message)
    if created:
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        shutil.copy2(source, temporary)
        temporary.replace(target)

    captions = _mapping(asset.get("dataset_captions"))
    caption = str(captions.get(context.profile_id, "")).strip() or context.default_caption
    _atomic_text(target.with_suffix(".txt"), caption.rstrip() + "\n")
    return {
        "relative_image": relative_image,
        "asset_id": asset_id,
        "created": created,
        "lineage": _asset_lineage(context, asset, asset_id, source_hash),
    }


def _asset_lineage(
    context: ProjectSyncContext,
    asset: Mapping[str, Any],
    asset_id: str,
    source_hash: str,
) -> dict[str, Any]:
    comfy = _mapping(asset.get("comfy_metadata"))
    controls = _profile_controls(context.generation, context.profile_id)
    return {
        "project_id": context.project_id,
        "project_title": str(context.project.get("title", "")),
        "project_iteration": _positive_int(
            _mapping(context.project.get("lineage")).get("iteration"), 1
        ),
        "project_revision": _positive_int(context.project.get("revision"), 1),
        "asset_id": asset_id,
        "source_filename": str(asset.get("filename", "")),
        "source_result_url": f"/result-media/{context.project_id}/original/{asset_id}",
        "profile_id": context.profile_id,
        "prompt": context.compiled[context.profile_id],
        "workflow": {
            "controls": controls,
            "api_prompt": comfy.get("prompt"),
            "graph": comfy.get("workflow"),
        },
        "checkpoint": comfy.get("checkpoint") or _checkpoint_from_controls(controls),
        "loras": comfy.get("loras") or controls.get("loras", []),
        "seed": comfy.get("seed", context.generation.get("seed")),
        "width": comfy.get("width", asset.get("width")),
        "height": comfy.get("height", asset.get("height")),
        "steps": comfy.get("steps", context.generation.get("steps")),
        "cfg": comfy.get("cfg", context.generation.get("cfg")),
        "source_sha256": source_hash,
        "synced_at": _now(),
    }


def _project_origin(
    context: ProjectSyncContext,
    result_ids: list[str],
) -> dict[str, Any]:
    return {
        "kind": "creative_project",
        "project_id": context.project_id,
        "project_title": str(context.project.get("title", "")),
        "project_iteration": _positive_int(
            _mapping(context.project.get("lineage")).get("iteration"), 1
        ),
        "project_revision": _positive_int(context.project.get("revision"), 1),
        "result_asset_ids": result_ids,
        "profile_id": context.profile_id,
        "synced_at": _now(),
    }


def build_project_journey(
    project: Mapping[str, Any],
    *,
    workspace_store: DatasetWorkspaceStore,
    curation_store: DatasetCurationStore,
    remote_store: RemoteNodeStore,
) -> dict[str, Any]:
    project_id = str(project.get("project_id", ""))
    generation = _mapping(project.get("generation"))
    assets = [item for item in generation.get("result_assets", []) if isinstance(item, Mapping)]
    selected = [item for item in assets if item.get("dataset_selected") is True]
    references = [item for item in project.get("references", []) if isinstance(item, Mapping)]
    slots = _mapping(project.get("slots"))
    filled_slots = sum(bool(str(value).strip()) for value in slots.values())
    prompts = {profile: compile_prompt(project, profile) for profile in ("anima", "krea2")}
    prompt_ready = sum(bool(value.get("ready")) for value in prompts.values())
    workspaces = _project_workspaces(workspace_store, project_id)
    exports = _project_exports(curation_store, workspaces)
    tasks = _project_tasks(remote_store, project_id)
    latest_workspace = workspaces[0] if workspaces else None
    latest_export = max(exports, key=lambda item: str(item.get("created_at", "")), default=None)
    stages = _journey_stages(
        JourneyFacts(
            project=project,
            filled_slots=filled_slots,
            reference_count=len(references),
            prompt_ready=prompt_ready,
            tasks=tasks,
            assets=assets,
            selected=selected,
            latest_workspace=latest_workspace,
            exports=exports,
            latest_export=latest_export,
        )
    )
    return {
        "project_id": project_id,
        "updated_at": project.get("updated_at", ""),
        "stages": stages,
        "summary": {
            "result_count": len(assets),
            "selected_count": len(selected),
            "workspace_count": len(workspaces),
            "delivery_count": len(exports),
        },
        "linked_workspaces": workspaces,
        "latest_delivery": latest_export,
        "review_changed": False,
    }


def _journey_stages(facts: JourneyFacts) -> list[dict[str, Any]]:
    project = facts.project
    filled_slots = facts.filled_slots
    reference_count = facts.reference_count
    prompt_ready = facts.prompt_ready
    tasks = facts.tasks
    assets = facts.assets
    selected = facts.selected
    latest_workspace = facts.latest_workspace
    exports = facts.exports
    latest_export = facts.latest_export
    latest_task = tasks[0] if tasks else None
    dataset_count = int(
        _mapping(latest_workspace.get("summary") if latest_workspace else {}).get("image_count", 0)
    )
    workspace_id = str(latest_workspace.get("workspace_id", "")) if latest_workspace else ""
    workspace_origin = _mapping(latest_workspace.get("origin") if latest_workspace else {})
    synced_assets = {
        str(value) for value in workspace_origin.get("result_asset_ids", []) if str(value)
    }
    selected_assets = {str(item.get("asset_id", "")) for item in selected}
    needs_sync = bool(latest_workspace) and (
        not selected_assets.issubset(synced_assets)
        or _positive_int(workspace_origin.get("project_revision"), 1)
        < _positive_int(project.get("revision"), 1)
    )
    delivery_workspace_id = (
        str(latest_export.get("workspace_id", "")) if latest_export else workspace_id
    )
    specs = [
        {
            "stage_id": "inspiration",
            "label": "灵感与 OC",
            "count": filled_slots + reference_count,
            "ready": bool(project.get("brief_zh") or filled_slots),
            "status": (
                "已建立创作内容" if project.get("brief_zh") or filled_slots else "等待填写想法"
            ),
            "detail": f"{filled_slots}/7 槽位 · {reference_count} 个参考",
            "action": {"label": "继续编辑想法", "view": "creative", "target_id": ""},
        },
        {
            "stage_id": "prompts",
            "label": "Anima / Krea 2 提示词",
            "count": prompt_ready,
            "ready": prompt_ready == PROFILE_COUNT,
            "status": "Anima 与 Krea 2 均可用"
            if prompt_ready == PROFILE_COUNT
            else f"{prompt_ready}/{PROFILE_COUNT} 个版本可用",
            "detail": "两种格式分别整理",
            "action": {"label": "检查双版本输出", "view": "creative", "target_id": ""},
        },
        {
            "stage_id": "generation",
            "label": "5060 Ti 出图",
            "count": len(tasks),
            "ready": bool(tasks),
            "status": _task_status(latest_task),
            "detail": f"{len(tasks)} 个关联任务",
            "latest_at": str((latest_task or {}).get("updated_at", "")),
            "action": {"label": "设置并发送出图", "view": "creative", "target_id": ""},
        },
        {
            "stage_id": "results",
            "label": "结果图",
            "count": len(assets),
            "ready": bool(assets),
            "status": "已有回传或导入结果" if assets else "尚无结果图",
            "detail": f"{len(assets)} 张结果 · {len(selected)} 张精选",
            "action": {"label": "查看结果与手动精选", "view": "creative", "target_id": ""},
        },
        {
            "stage_id": "dataset",
            "label": "数据集工作区",
            "count": dataset_count,
            "ready": bool(latest_workspace),
            "status": "项目或精选内容有更新"
            if needs_sync
            else str(latest_workspace.get("status", ""))
            if latest_workspace
            else "尚未建立工作区",
            "detail": (
                f"{latest_workspace.get('name', '')} · 等待同步"
                if needs_sync
                else str(latest_workspace.get("name", ""))
                if latest_workspace
                else f"{len(selected)} 张可送入"
            ),
            "action": {
                "label": "更新并打开工作区"
                if needs_sync
                else "打开数据集工作区"
                if latest_workspace
                else "送入数据集工作区",
                "view": "creative" if needs_sync or not latest_workspace else "datasets",
                "target_id": "" if needs_sync else workspace_id,
            },
        },
        {
            "stage_id": "delivery",
            "label": "交付版本",
            "count": len(exports),
            "ready": bool(exports),
            "status": "已有交付版本" if latest_export else "尚未生成交付版本",
            "detail": str(latest_export.get("version_id", ""))
            if latest_export
            else "等待完成审核并生成版本",
            "latest_at": str((latest_export or {}).get("created_at", "")),
            "action": {
                "label": "查看交付版本",
                "view": "datasets",
                "target_id": delivery_workspace_id,
            },
        },
    ]
    return [_normalize_stage(spec) for spec in specs]


def _normalize_stage(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **spec,
        "state": "ready" if spec.get("ready") else "pending",
        "latest_at": str(spec.get("latest_at", "")),
    }


def _project_workspaces(
    workspace_store: DatasetWorkspaceStore,
    project_id: str,
) -> list[dict[str, Any]]:
    return [
        item
        for item in workspace_store.list_workspaces()
        if _mapping(item.get("origin")).get("project_id") == project_id
    ]


def _project_exports(
    curation_store: DatasetCurationStore,
    workspaces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {**item, "workspace_id": workspace["workspace_id"], "workspace_name": workspace["name"]}
        for workspace in workspaces
        for item in curation_store.list_exports(str(workspace["workspace_id"]))
    ]


def read_project_lineage(source_root: Path) -> dict[str, Any]:
    return _read_lineage(source_root / LINEAGE_FILENAME)


def _project_tasks(remote_store: RemoteNodeStore, project_id: str) -> list[dict[str, Any]]:
    try:
        return [
            task
            for task in remote_store.list_tasks("compute_5060ti", limit=1000)
            if task.get("project_id") == project_id and task.get("task_type") == "comfyui_generate"
        ]
    except RemoteNodeError:
        return []


def _task_status(task: Mapping[str, Any] | None) -> str:
    if task is None:
        return "尚未发送出图任务"
    labels = {
        "queued": "等待 Windows 领取",
        "running": "5060 Ti 正在生成",
        "returned": "结果已回传, 等待导入",
        "completed": "任务已完成",
        "failed": "任务失败",
        "canceled": "任务已取消",
        "recorded": "任务已记录",
    }
    return labels.get(str(task.get("status", "")), str(task.get("status", "未知状态")))


def _profile_controls(generation: Mapping[str, Any], profile_id: str) -> dict[str, Any]:
    controls = _mapping(generation.get("workflow_controls")).get(profile_id, {})
    return dict(controls) if isinstance(controls, Mapping) else {}


def _checkpoint_from_controls(controls: Mapping[str, Any]) -> str:
    models = _mapping(controls.get("models"))
    for key in ("checkpoint", "diffusion_model", "unet"):
        if models.get(key):
            return str(models[key])
    return ""


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _positive_int(value: object, fallback: int) -> int:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return fallback
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return fallback


def _read_lineage(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_text(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
