from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from soda_storyboard.lora import select_lora
from soda_storyboard.production.api import pick_render
from soda_storyboard.production.graphs import minimal_graph
from soda_storyboard.production.imaging import open_rgb
from soda_storyboard.production.state import PageState, digest

from prompt_hub.storyboard_safety import local_path, validate_paths
from prompt_hub.workflow_profiles import MAX_SEED, PACKAGE_FORMAT

if TYPE_CHECKING:
    from prompt_hub.comfy_results import ComfyResultStore
    from prompt_hub.remote_nodes import RemoteNodeStore
    from prompt_hub.storyboard import StoryboardStore
    from prompt_hub.workflow_profiles import WorkflowProfileStore

RUN_FORMAT = "soda-storyboard-generation-v1"
_MODEL_KEYS = {"diffusion_model": "sft", "text_encoder": "clip", "vae": "vae"}


class StoryboardGenerationError(ValueError):
    pass


class StoryboardGenerationService:
    """Connect core-authored MOSS graphs to Hub's existing Worker and review store."""

    def __init__(
        self,
        store: StoryboardStore,
        workflows: WorkflowProfileStore,
        remote: RemoteNodeStore,
        results: ComfyResultStore,
    ) -> None:
        self.store = store
        self.workflows = workflows
        self.remote = remote
        self.results = results

    def submit(
        self,
        project_id: str,
        page_id: str,
        *,
        node_id: str = "compute-5060ti",
        options: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        values = _options(options or {})
        with self.store.project_lock(project_id):
            root = self.store.project_path(project_id)
            compiled = self.store.compile_page(project_id, page_id)
            state = PageState(root, page_id)
            run_id = f"sb-{uuid4().hex}"
            config = _model_config(state.config, values["model_overrides"])
            selected_lora = select_lora(state.page, state.characters)
            if selected_lora:
                selected_lora["path"] = _model_name(str(selected_lora["path"]))
            selected_model = values["model_overrides"].get("diffusion_model") or values["model"]
            prompt = json.dumps(compiled["moss"], ensure_ascii=False, allow_nan=False)
            graph_options: dict[str, Any] = {
                "config": config,
                "model": selected_model,
                "preset": values["preset"],
                "seed": values["seed"],
                "width": compiled["width"],
                "height": compiled["height"],
                "lora": selected_lora,
            }
            if values["backend"] == "minimal":
                graph = minimal_graph(
                    prompt,
                    **graph_options,
                    prefix=f"PromptHub/storyboard/{run_id}",
                )
                graph["6"]["inputs"]["text"] = values["negative"]
                package = {
                    "format": PACKAGE_FORMAT,
                    "workflow_id": f"moss-minimal-{run_id}",
                    "profile_id": "moss-minimal",
                    "model_family": "moss",
                    "api_prompt": graph,
                }
            else:
                package = self.workflows.compile_moss_package(
                    run_id=run_id,
                    prompt=prompt,
                    negative=values["negative"],
                    **graph_options,
                )
            relative = f"packages/generated/storyboard/{run_id}.json"
            raw = _json_bytes(package)
            diagnostic = self.remote.diagnostics(node_id)
            if not diagnostic.get("bridge_writable"):
                raise StoryboardGenerationError("Windows 交付桥当前不可写")
            bridge = _bridge_root(diagnostic)
            package_path = local_path(bridge, relative)
            _write_bytes(package_path, raw)
            package_digest = hashlib.sha256(raw).hexdigest()
            run = {
                "format": RUN_FORMAT,
                "run_id": run_id,
                "project_id": project_id,
                "page_id": page_id,
                "node_id": node_id,
                "task_id": "",
                "workflow_id": package["workflow_id"],
                "backend": values["backend"],
                "preset": values["preset"],
                "seed": values["seed"],
                "json_hash": digest(compiled["moss"]),
                "package_sha256": package_digest,
                "model": selected_model or config.get("model", "sft"),
                "model_file": config.get(
                    selected_model or str(config.get("model", "sft")), selected_model
                ),
                "clip_file": config.get("clip"),
                "vae_file": config.get("vae"),
                "lora": selected_lora,
                "created_at": _now(),
            }
            run_path = local_path(self.store.root, f"generation-runs/{run_id}.json")
            _write_bytes(run_path, _json_bytes(run))
            task = self.remote.submit_task(
                node_id,
                {
                    "task_type": "comfyui_generate",
                    "payload": {
                        "generation_package": relative,
                        "workflow_id": package["workflow_id"],
                        "output_profile": package["profile_id"],
                    },
                    "manifest": [
                        {
                            "relative_path": relative,
                            "sha256": package_digest,
                            "size_bytes": len(raw),
                        }
                    ],
                    "workspace_id": "storyboard-"
                    + hashlib.sha256(f"{project_id}/{page_id}".encode()).hexdigest()[:32],
                    "run_id": run_id,
                    "priority": values["priority"],
                },
            )
            run["task_id"] = str(task["task_id"])
            _write_bytes(run_path, _json_bytes(run))
        return {
            "task": task,
            "run_id": run_id,
            "backend": values["backend"],
            "remote_package": relative,
            "sha256": package_digest,
            "node_count": len(package["api_prompt"]),
        }

    def import_results(
        self,
        project_id: str,
        page_id: str,
        task_id: str,
        *,
        node_id: str = "compute-5060ti",
    ) -> dict[str, Any]:
        with self.store.project_lock(project_id):
            root = self.store.project_path(project_id)
            run = self._find_run(project_id, page_id, task_id, node_id)
            task = self.remote.get_task(node_id, task_id).get("local_task", {})
            if (
                task.get("task_type") != "comfyui_generate"
                or task.get("run_id") != run["run_id"]
                or task.get("payload", {}).get("workflow_id") != run["workflow_id"]
            ):
                raise StoryboardGenerationError("任务与分镜页生成记录不一致")
            integrity = self.remote.verify_returned_task(node_id, task_id)
            if not integrity.get("verified"):
                raise StoryboardGenerationError("回传完整性校验失败，请先检查 Worker 任务")
            images = [item for item in integrity.get("outputs", []) if item.get("kind") == "image"]
            if not images:
                raise StoryboardGenerationError("Worker 尚未返回图片")
            bridge = _bridge_root(self.remote.diagnostics(node_id))
            imported = []
            for output in images:
                relative = str(output.get("relative_path", ""))
                path = local_path(bridge, relative)
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != output.get("sha256") or len(
                    raw
                ) != output.get("size_bytes"):
                    raise StoryboardGenerationError("回传图片读取时哈希或大小已变化")
                outcome = self.results.import_bytes(
                    raw,
                    filename=path.name,
                    origin={
                        "source_kind": "worker_return",
                        "source_root": str(path.parent),
                        "source_path": relative,
                        "import_batch_id": task_id,
                    },
                )
                result_id = str(outcome["result"]["result_id"])
                record = self._register_result(root, page_id, result_id, run)
                result = self.results.update(
                    result_id,
                    {"association": _association(project_id, page_id)},
                )
                imported.append(
                    {
                        **result,
                        "result": result,
                        "render": record,
                        "duplicate": outcome["duplicate"],
                    }
                )
            receipt = self.remote.mark_task_received(
                node_id, task_id, receipt_kind="comfyui_images"
            )
        return {
            "task_id": task_id,
            "project_id": project_id,
            "page_id": page_id,
            "image_count": len(imported),
            "results": imported,
            "received_at": receipt["received_at"],
        }

    def select_result(self, project_id: str, page_id: str, result_id: str) -> dict[str, Any]:
        with self.store.project_lock(project_id):
            root = self.store.project_path(project_id)
            state = PageState(root, page_id)
            record = next(
                (
                    item
                    for item in state.production.get("renders", [])
                    if item.get("meta", {}).get("hub_result_id") == result_id
                ),
                None,
            )
            if record is None or self.results.get(result_id) is None:
                raise StoryboardGenerationError("结果尚未登记到此分镜页")
            _check_paths(state.raw, root)
            local_path(root, str(record["path"]))
            selected = pick_render(root, page_id, record["path"])
            result = self.results.update(
                result_id,
                {"disposition": "candidate", "association": _association(project_id, page_id)},
            )
        return {"render": selected, "result": result}

    def list_results(self, project_id: str, page_id: str) -> list[dict[str, Any]]:
        with self.store.project_lock(project_id):
            root = self.store.project_path(project_id)
            state = PageState(root, page_id)
            records = []
            for render in state.production.get("renders", []):
                result_id = str(render.get("meta", {}).get("hub_result_id", ""))
                result = self.results.get(result_id) if result_id else None
                if result is not None:
                    records.append(
                        {
                            **result,
                            "render": render,
                            "selected": state.production.get("selected_render") == render["path"],
                        }
                    )
            return records

    def last_task(self, project_id: str, page_id: str) -> dict[str, str] | None:
        with self.store.project_lock(project_id):
            PageState(self.store.project_path(project_id), page_id)
            matches = [
                run
                for run in self._runs()
                if run.get("project_id") == project_id
                and run.get("page_id") == page_id
                and run.get("task_id")
            ]
            if not matches:
                return None
            latest = max(matches, key=lambda run: str(run.get("created_at", "")))
            return {key: str(latest[key]) for key in ("node_id", "task_id")}

    def _find_run(
        self, project_id: str, page_id: str, task_id: str, node_id: str
    ) -> dict[str, Any]:
        for run in self._runs():
            if run.get("task_id") == task_id:
                if (run.get("project_id"), run.get("page_id"), run.get("node_id")) != (
                    project_id,
                    page_id,
                    node_id,
                ):
                    raise StoryboardGenerationError("任务不属于此分镜页或 Worker")
                return run
        raise StoryboardGenerationError("分镜生成记录不存在")

    def _runs(self) -> list[dict[str, Any]]:
        directory = local_path(self.store.root, "generation-runs")
        runs = []
        for path in sorted(directory.glob("*.json")):
            checked = local_path(self.store.root, f"generation-runs/{path.name}")
            run = json.loads(checked.read_text(encoding="utf-8"))
            if isinstance(run, dict) and run.get("format") == RUN_FORMAT:
                runs.append(run)
        return runs

    def _register_result(
        self, root: Path, page_id: str, result_id: str, run: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Compatibility seam until core exposes register_render for external workers."""
        state = PageState(root, page_id)
        existing = next(
            (
                item
                for item in state.production.get("renders", [])
                if item.get("meta", {}).get("hub_result_id") == result_id
            ),
            None,
        )
        if existing is not None:
            return existing
        result = self.results.get(result_id)
        if result is None:
            raise StoryboardGenerationError("ComfyUI 结果不存在")
        path = local_path(root, f"pages/{page_id}/renders/hub-{uuid4().hex}.png")
        _write_bytes(path, self.results.read_original(result_id))
        open_rgb(path, (state.page.canvas_width, state.page.canvas_height)).save(path, format="PNG")
        record = {
            "path": path.relative_to(root).as_posix(),
            "seed": run["seed"],
            "meta": {
                "preset": run["preset"],
                "model": run["model"],
                "model_file": run.get("model_file"),
                "clip_file": run.get("clip_file"),
                "vae_file": run.get("vae_file"),
                "lora": run.get("lora"),
                "json_hash": run["json_hash"],
                "backend": run["backend"],
                "created_at": _now(),
                "hub_result_id": result_id,
                "hub_task_id": run["task_id"],
                "hub_run_id": run["run_id"],
            },
        }
        state.production.setdefault("renders", []).append(record)
        _check_paths(state.raw, root)
        state.save()
        return record


def _association(project_id: str, page_id: str) -> dict[str, str]:
    return {"kind": "storyboard-page", "id": f"{project_id}/{page_id}"}


def _check_paths(raw: dict[str, Any], root: Path) -> None:
    if errors := validate_paths(raw, root):
        raise StoryboardGenerationError("; ".join(errors))


def _model_config(source: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    config = {
        key: _model_name(str(source[key]))
        for key in ("model", "sft", "base", "clip", "vae")
        if key in source
    }
    for asset_type, name in overrides.items():
        if asset_type not in _MODEL_KEYS:
            raise StoryboardGenerationError("不支持的 MOSS 模型类型")
        config[_MODEL_KEYS[asset_type]] = _model_name(str(name))
    if "diffusion_model" in overrides:
        config["model"] = "sft"
    return config


def _model_name(value: str) -> str:
    path = PureWindowsPath(value)
    if (
        not value.strip()
        or len(value) > 4096
        or path.drive
        or path.root
        or ".." in path.parts
        or any(character in value for character in "\x00\r\n:")
    ):
        raise StoryboardGenerationError("模型名称必须是 ComfyUI 模型目录内的相对名称")
    return value


def _options(source: Mapping[str, Any]) -> dict[str, Any]:
    values = {
        "backend": "minimal",
        "preset": "draft",
        "seed": None,
        "negative": "",
        "model": None,
        "model_overrides": {},
        "priority": 50,
        **source,
    }
    if values["backend"] not in {"minimal", "moss-soda-v2"}:
        raise StoryboardGenerationError("出图后端必须是 minimal 或 moss-soda-v2")
    if values.get("workflow_profile_id") not in {None, "", "moss-soda-v2"}:
        raise StoryboardGenerationError("分镜工作流规则必须是 moss-soda-v2")
    if values["preset"] not in {"draft", "final"}:
        raise StoryboardGenerationError("出图预设必须是 draft 或 final")
    seed = values["seed"]
    if seed is None:
        values["seed"] = secrets.randbelow(MAX_SEED + 1)
    elif isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
        raise StoryboardGenerationError("种子超出安全整数范围")
    negative = values["negative"]
    if not isinstance(negative, str) or len(negative) > 20_000:
        raise StoryboardGenerationError("负面提示词不能超过 20000 字符")
    if not isinstance(values["model_overrides"], Mapping):
        raise StoryboardGenerationError("模型覆盖必须是对象")
    if values["model"] is not None:
        values["model"] = _model_name(str(values["model"]))
    priority = values["priority"]
    if isinstance(priority, bool) or not isinstance(priority, int) or not -100 <= priority <= 100:
        raise StoryboardGenerationError("任务优先级必须在 -100 到 100 之间")
    return values


def _bridge_root(diagnostic: Mapping[str, Any]) -> Path:
    value = str(diagnostic.get("bridge_root", ""))
    if not value:
        raise StoryboardGenerationError("Windows 交付桥路径不可用")
    return Path(value).resolve()


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def _write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(raw)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")
