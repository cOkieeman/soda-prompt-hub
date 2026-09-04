from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NoReturn
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from prompt_hub.comfy_results import ComfyResultError, ComfyResultStore
from prompt_hub.comfy_routes import attach_comfy_result
from prompt_hub.creative import compile_prompt
from prompt_hub.remote_nodes import RemoteNodeError
from prompt_hub.workflow_profiles import MAX_SEED, WorkflowProfileError, WorkflowProfileStore

if TYPE_CHECKING:
    from prompt_hub.config import Settings
    from prompt_hub.creative import CreativeStore
    from prompt_hub.remote_nodes import RemoteNodeStore


class WorkflowProfileRunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(default="compute-5060ti", min_length=1, max_length=160)
    project_id: str = Field(default="", max_length=160)
    use_source_prompt: bool = False
    low_cost: bool = True
    width: int | None = Field(default=None, ge=256, le=4096)
    height: int | None = Field(default=None, ge=256, le=4096)
    steps: int | None = Field(default=None, ge=1, le=200)
    cfg: float | None = Field(default=None, ge=0, le=30)
    seed: int | None = Field(default=None, ge=-1, le=MAX_SEED)
    priority: int = Field(default=50, ge=-100, le=100)


class WorkflowResultImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(default="compute-5060ti", min_length=1, max_length=160)


def create_workflow_router(
    settings: Settings,
    store: WorkflowProfileStore,
    creative_store: CreativeStore,
    comfy_store: ComfyResultStore,
    remote_store: RemoteNodeStore,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/workflow-profiles")
    def list_workflow_profiles() -> list[dict[str, Any]]:
        return store.list_profiles()

    @router.get("/api/workflow-profiles/{profile_id}")
    def get_workflow_profile(profile_id: str) -> dict[str, Any]:
        try:
            return store.get_profile(profile_id)
        except WorkflowProfileError as error:
            _raise_workflow_http(error)

    @router.post(
        "/api/workflow-profiles/{profile_id}/import",
        status_code=status.HTTP_201_CREATED,
    )
    async def import_workflow_profile(
        profile_id: str,
        request: Request,
        label: Annotated[str, Query(min_length=1, max_length=160)],
        filename: Annotated[str, Query(min_length=1, max_length=180)] = "workflow-api.json",
        replace: bool = False,
    ) -> dict[str, Any]:
        try:
            return store.import_bytes(
                profile_id,
                await request.body(),
                label=label,
                filename=filename,
                replace=replace,
            )
        except WorkflowProfileError as error:
            _raise_workflow_http(error)

    @router.post(
        "/api/workflow-profiles/{profile_id}/tasks",
        status_code=status.HTTP_201_CREATED,
    )
    def run_workflow_profile(
        profile_id: str,
        payload: WorkflowProfileRunInput,
    ) -> dict[str, Any]:
        try:
            profile = store.get_profile(profile_id)
            project, compiled, generation = _project_values(
                creative_store,
                payload.project_id,
                str(profile["model_family"]),
                use_source_prompt=payload.use_source_prompt,
            )
            run_id = _new_run_id()
            dimensions = _dimensions(payload, generation)
            controls = _resolve_workflow_controls(
                remote_store,
                generation,
                profile_id=profile_id,
                model_family=str(profile["model_family"]),
            )
            package = store.compile_package(
                profile_id,
                run_id=run_id,
                positive=str(compiled["positive"]) if compiled else None,
                negative=str(compiled["negative"]) if compiled else None,
                seed=_run_int(payload.seed, generation, "seed"),
                width=dimensions[0],
                height=dimensions[1],
                steps=_run_int(payload.steps, generation, "steps"),
                cfg=_run_float(payload.cfg, generation, "cfg"),
                model_overrides=controls["model_overrides"],
                additional_loras=controls["additional_loras"],
                sampler=controls["sampler"],
                scheduler=controls["scheduler"],
                low_cost=payload.low_cost,
            )
            local_path = store.save_run_package(profile_id, run_id, package)
            raw = local_path.read_bytes()
            remote_relative = f"packages/generated/{profile_id}/{run_id}.json"
            diagnostic = remote_store.diagnostics(payload.node_id)
            if not diagnostic.get("bridge_writable"):
                raise WorkflowProfileError("Windows 交付桥当前不可写")
            remote_path = Path(str(diagnostic["bridge_root"])) / remote_relative
            _write_bytes(remote_path, raw)
            digest = hashlib.sha256(raw).hexdigest()
            task = remote_store.submit_task(
                payload.node_id,
                {
                    "task_type": "comfyui_generate",
                    "payload": {
                        "generation_package": remote_relative,
                        "workflow_id": package["workflow_id"],
                        "output_profile": profile_id,
                    },
                    "manifest": [
                        {
                            "relative_path": remote_relative,
                            "sha256": digest,
                            "size_bytes": len(raw),
                        }
                    ],
                    "project_id": str(project.get("project_id", "")) if project else "",
                    "workspace_id": f"workflow-profile-{profile_id}",
                    "run_id": run_id,
                    "priority": payload.priority,
                },
            )
        except (RemoteNodeError, WorkflowProfileError) as error:
            _raise_workflow_http(error)
        return {
            "task": task,
            "profile": profile,
            "run_id": run_id,
            "local_package": str(local_path),
            "remote_package": remote_relative,
            "sha256": digest,
            "node_count": len(package["api_prompt"]),
            "low_cost": payload.low_cost,
        }

    @router.post("/api/workflow-tasks/{task_id}/import-results")
    def import_workflow_results(
        task_id: str,
        payload: WorkflowResultImportInput,
    ) -> dict[str, Any]:
        try:
            task_detail = remote_store.get_task(payload.node_id, task_id)
            local_task = task_detail.get("local_task", {})
            if local_task.get("task_type") != "comfyui_generate":
                raise WorkflowProfileError("只有 ComfyUI 生成任务可以导入图片")
            integrity = remote_store.verify_returned_task(payload.node_id, task_id)
            if not integrity.get("verified"):
                errors = "; ".join(str(item) for item in integrity.get("errors", []))
                raise WorkflowProfileError(f"回传完整性校验失败: {errors}")
            project_id = str(local_task.get("project_id", ""))
            imported = []
            duplicates = 0
            for output in integrity.get("outputs", []):
                if output.get("kind") != "image":
                    continue
                relative = str(output.get("relative_path", ""))
                image_path = _verified_remote_path(remote_store, payload.node_id, relative)
                outcome = comfy_store.import_bytes(
                    image_path.read_bytes(),
                    filename=image_path.name,
                    source_path=relative,
                )
                duplicates += int(outcome["duplicate"])
                result = outcome["result"]
                if project_id:
                    attached = attach_comfy_result(
                        settings,
                        comfy_store,
                        creative_store,
                        result_id=str(result["result_id"]),
                        project_id=project_id,
                        selected=False,
                    )
                    result = attached["result"]
                imported.append(result)
        except (ComfyResultError, RemoteNodeError, WorkflowProfileError) as error:
            _raise_workflow_http(error)
        return {
            "task_id": task_id,
            "project_id": project_id,
            "image_count": len(imported),
            "duplicates": duplicates,
            "results": imported,
            "associated": bool(project_id),
        }

    return router


def _project_values(
    creative_store: CreativeStore,
    project_id: str,
    model_family: str,
    *,
    use_source_prompt: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, Mapping[str, Any]]:
    if not project_id:
        if not use_source_prompt:
            raise WorkflowProfileError("请选择创作项目，或明确使用 workflow 原始 Prompt")
        return None, None, {}
    project = creative_store.get_project(project_id)
    if project is None:
        raise WorkflowProfileError("创作项目不存在")
    compiled = compile_prompt(project, model_family)
    if not compiled["ready"]:
        warnings = "；".join(str(item) for item in compiled["warnings"])
        raise WorkflowProfileError(f"当前 {model_family} Prompt 尚未就绪：{warnings}")
    raw_generation = project.get("generation", {})
    generation = raw_generation if isinstance(raw_generation, Mapping) else {}
    return project, compiled, generation


def _dimensions(
    payload: WorkflowProfileRunInput,
    generation: Mapping[str, Any],
) -> tuple[int | None, int | None]:
    width = _run_int(payload.width, generation, "width")
    height = _run_int(payload.height, generation, "height")
    if payload.low_cost:
        width = int(width or 512)
        height = int(height or 768)
    return int(width) if width is not None else None, int(height) if height is not None else None


def _resolve_workflow_controls(
    remote_store: RemoteNodeStore,
    generation: Mapping[str, Any],
    *,
    profile_id: str,
    model_family: str,
) -> dict[str, Any]:
    all_controls = generation.get("workflow_controls", {})
    if not isinstance(all_controls, Mapping):
        raise WorkflowProfileError("项目中的 workflow_controls 必须是对象")
    selected = all_controls.get(profile_id, {})
    if selected in (None, {}):
        return {
            "model_overrides": {},
            "additional_loras": [],
            "sampler": None,
            "scheduler": None,
        }
    if not isinstance(selected, Mapping):
        raise WorkflowProfileError("当前 Workflow Profile 控制参数必须是对象")
    model_overrides = {}
    raw_models = selected.get("models", {})
    if not isinstance(raw_models, Mapping):
        raise WorkflowProfileError("Workflow 模型选择必须是对象")
    for asset_type, asset_id in raw_models.items():
        if not str(asset_id).strip():
            continue
        model = remote_store.get_model(str(asset_id))
        if model.get("asset_type") != asset_type:
            raise WorkflowProfileError(f"{asset_type} 选择与模型资产类型不匹配")
        _validate_model_family(str(model.get("model_family", "")), model_family, str(asset_type))
        model_overrides[str(asset_type)] = str(model["relative_path"])
    raw_loras = selected.get("loras", [])
    if not isinstance(raw_loras, list):
        raise WorkflowProfileError("Workflow LoRA 选择必须是列表")
    additional_loras = []
    seen_loras = set()
    for value in raw_loras:
        if not isinstance(value, Mapping):
            raise WorkflowProfileError("Workflow LoRA 条目必须是对象")
        lora_id = str(value.get("lora_id", "")).strip()
        if not lora_id or lora_id in seen_loras:
            raise WorkflowProfileError("Workflow LoRA ID 为空或重复")
        lora = remote_store.get_lora(lora_id)
        _validate_model_family(str(lora.get("model_family", "")), model_family, "LoRA")
        additional_loras.append(
            {
                "name": Path(str(lora["relative_path"])).stem,
                "strength": value.get("strength", 1),
                "clip_strength": value.get("clip_strength", value.get("strength", 1)),
            }
        )
        seen_loras.add(lora_id)
    sampler = str(selected.get("sampler", "")).strip() or None
    scheduler = str(selected.get("scheduler", "")).strip() or None
    return {
        "model_overrides": model_overrides,
        "additional_loras": additional_loras,
        "sampler": sampler,
        "scheduler": scheduler,
    }


def _validate_model_family(actual: str, expected: str, label: str) -> None:
    normalized = actual.strip().casefold()
    if normalized not in {"", "unknown", expected.casefold()}:
        raise WorkflowProfileError(
            f"{label} 模型族为 {actual}，与当前 {expected} Workflow Profile 不兼容"
        )


def _run_int(
    explicit: int | None,
    generation: Mapping[str, Any],
    key: str,
) -> int | None:
    value: Any = explicit if explicit is not None else generation.get(key)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise WorkflowProfileError(f"项目中的 {key} 不是有效数字") from error


def _run_float(
    explicit: float | None,
    generation: Mapping[str, Any],
    key: str,
) -> float | None:
    value: Any = explicit if explicit is not None else generation.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise WorkflowProfileError(f"项目中的 {key} 不是有效数字") from error


def _write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)


def _verified_remote_path(
    remote_store: RemoteNodeStore,
    node_id: str,
    relative: str,
) -> Path:
    diagnostic = remote_store.diagnostics(node_id)
    root_value = str(diagnostic.get("bridge_root", ""))
    if not root_value:
        raise WorkflowProfileError("Windows 交付桥路径不可用")
    root = Path(root_value).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise WorkflowProfileError("已校验的回传图片路径不可用")
    return path


def _new_run_id() -> str:
    token = datetime.now(UTC).strftime("%Y%m%dt%H%M%Sz")
    return f"run-{token}-{uuid4().hex[:8]}"


def _raise_workflow_http(error: Exception) -> NoReturn:
    message = str(error)
    code = 404 if "不存在" in message or "尚未导入" in message else 422
    raise HTTPException(status_code=code, detail=message) from error
