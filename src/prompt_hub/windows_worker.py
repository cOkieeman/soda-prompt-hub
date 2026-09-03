from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Self
from uuid import uuid4

COMPUTE_PROTOCOL_VERSION = "soda-compute-bridge-v2"
TASK_FORMAT = "soda-compute-task-v1"
RESULT_FORMAT = "soda-compute-result-v1"
PACKAGE_FORMAT = "soda-comfyui-package-v1"
TARGET_ROLE = "compute_5060ti"
SAFE_TASK_TYPES = {"comfyui_generate", "lora_catalog_snapshot"}
FINAL_DIRECTORIES = ("inbox", "completed", "failed")
LORA_MODEL_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".pth"}
LORA_PREVIEW_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")
LORA_PREVIEW_SIDECAR_STEMS = ("civitai_bak",)
MAX_LORA_METADATA_BYTES = 2 * 1024 * 1024
MAX_LORA_PREVIEW_BYTES = 32 * 1024 * 1024
MAX_LORA_PREVIEW_COUNT = 1024
MAX_LORA_PREVIEW_TOTAL_BYTES = 2 * 1024 * 1024 * 1024


class WorkerError(RuntimeError):
    pass


class TaskCanceledError(WorkerError):
    pass


@dataclass(frozen=True, slots=True)
class LoraRootConfig:
    root_id: str
    path: Path


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    bridge_root: Path
    comfyui_url: str
    worker_id: str
    role: str = TARGET_ROLE
    poll_interval_seconds: float = 2.0
    history_poll_seconds: float = 1.0
    task_timeout_seconds: float = 900.0
    http_timeout_seconds: float = 30.0
    lora_roots: tuple[LoraRootConfig, ...] = ()

    @classmethod
    def load(cls, path: Path) -> WorkerConfig:
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkerError(f"无法读取 worker 配置：{error}") from error
        if not isinstance(raw, dict):
            raise WorkerError("worker 配置必须是 JSON 对象")
        root_value = str(raw.get("bridge_root", "")).strip()
        worker_id = str(raw.get("worker_id", "")).strip()
        role = str(raw.get("role", TARGET_ROLE)).strip()
        comfyui_url = str(raw.get("comfyui_url", "")).strip().rstrip("/")
        if not root_value or not Path(root_value).is_absolute():
            raise WorkerError("bridge_root 必须是 Windows 绝对路径")
        if not worker_id or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for char in worker_id
        ):
            raise WorkerError("worker_id 只能包含字母、数字、点、下划线和连字符")
        if role != TARGET_ROLE:
            raise WorkerError(f"role 必须是 {TARGET_ROLE}")
        parsed = urllib.parse.urlsplit(comfyui_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise WorkerError("comfyui_url 必须指向本机 HTTP 地址")
        lora_roots = _parse_lora_roots(raw.get("lora_roots", []))
        return cls(
            bridge_root=Path(root_value),
            comfyui_url=comfyui_url,
            worker_id=worker_id,
            role=role,
            poll_interval_seconds=_positive_float(raw, "poll_interval_seconds", 2.0),
            history_poll_seconds=_positive_float(raw, "history_poll_seconds", 1.0),
            task_timeout_seconds=_positive_float(raw, "task_timeout_seconds", 900.0),
            http_timeout_seconds=_positive_float(raw, "http_timeout_seconds", 30.0),
            lora_roots=lora_roots,
        )


class WorkerLock(AbstractContextManager["WorkerLock"]):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: BinaryIO | None = None

    def __enter__(self) -> Self:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            handle.close()
            raise WorkerError("已有另一个 worker 正在运行") from error
        self.handle = handle
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback_value: object) -> None:
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None


class ComfyUIClient:
    def __init__(self, base_url: str, *, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def system_stats(self) -> dict[str, Any]:
        return self._json_request("GET", "/system_stats")

    def lora_names(self) -> list[str]:
        result = self._json_request("GET", "/object_info/LoraLoader")
        try:
            values = result["LoraLoader"]["input"]["required"]["lora_name"][0]
        except (KeyError, IndexError, TypeError) as error:
            raise WorkerError("ComfyUI LoraLoader 返回结构无效") from error
        if not isinstance(values, list):
            raise WorkerError("ComfyUI LoraLoader 没有返回 LoRA 名称列表")
        return [str(value).replace("\\", "/") for value in values if str(value).strip()]

    def queue_prompt(self, api_prompt: dict[str, Any], *, client_id: str) -> str:
        result = self._json_request(
            "POST",
            "/prompt",
            {"prompt": api_prompt, "client_id": client_id},
        )
        node_errors = result.get("node_errors", {})
        if isinstance(node_errors, dict) and node_errors:
            raise WorkerError(f"ComfyUI workflow 校验失败：{_short_json(node_errors)}")
        prompt_id = str(result.get("prompt_id", "")).strip()
        if not prompt_id:
            raise WorkerError("ComfyUI 未返回 prompt_id")
        return prompt_id

    def history(self, prompt_id: str) -> dict[str, Any] | None:
        result = self._json_request("GET", f"/history/{urllib.parse.quote(prompt_id)}")
        record = result.get(prompt_id)
        return record if isinstance(record, dict) else None

    def download_output(self, image: dict[str, Any]) -> bytes:
        query = urllib.parse.urlencode(
            {
                "filename": str(image.get("filename", "")),
                "subfolder": str(image.get("subfolder", "")),
                "type": str(image.get("type", "output")),
            }
        )
        return self._request("GET", f"/view?{query}")

    def interrupt(self) -> None:
        self._json_request("POST", "/interrupt", {})

    def _json_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw = self._request(method, path, payload)
        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WorkerError(f"ComfyUI 返回了无效 JSON：{error}") from error
        if not isinstance(result, dict):
            raise WorkerError("ComfyUI 返回值不是 JSON 对象")
        return result

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> bytes:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise WorkerError(f"无法访问 ComfyUI：{error}") from error


class WindowsWorker:
    def __init__(self, config: WorkerConfig) -> None:
        self.config = config
        self.client = ComfyUIClient(config.comfyui_url, timeout=config.http_timeout_seconds)

    def initialize(self) -> None:
        self.config.bridge_root.mkdir(parents=True, exist_ok=True)
        for name in ("outbox", "inbox", "processing", "completed", "failed"):
            (self.config.bridge_root / name).mkdir(exist_ok=True)

    def self_test(self) -> dict[str, Any]:
        self.initialize()
        probe = self.config.bridge_root / "processing" / ".worker-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        stats = self.client.system_stats()
        lora_roots = [_lora_root_status(root) for root in self.config.lora_roots]
        result = {
            "format": "soda-worker-status-v1",
            "status": "ready",
            "worker_id": self.config.worker_id,
            "hostname": socket.gethostname(),
            "python": sys.version.split()[0],
            "protocol_version": COMPUTE_PROTOCOL_VERSION,
            "role": self.config.role,
            "comfyui_url": self.config.comfyui_url,
            "comfyui_reachable": True,
            "capabilities": sorted(SAFE_TASK_TYPES),
            "lora_roots": lora_roots,
            "checked_at": _now(),
            "system_stats": stats,
        }
        _write_json(self.config.bridge_root / "worker-status.json", result)
        return result

    def run_forever(self) -> None:
        self.initialize()
        self.recover_processing()
        print(f"[{_now()}] worker 已启动；等待任务。按 Ctrl+C 停止。", flush=True)
        while True:
            worked = self.run_once()
            if not worked:
                time.sleep(self.config.poll_interval_seconds)

    def run_once(self) -> bool:
        self.initialize()
        claimed = self._claim_next()
        if claimed is None:
            return False
        self._process_claimed(claimed)
        return True

    def _claim_next(self) -> Path | None:
        outbox = self.config.bridge_root / "outbox"
        processing = self.config.bridge_root / "processing"
        candidates: list[tuple[int, str, Path]] = []
        for path in outbox.glob("*.json"):
            try:
                raw = _read_json(path)
                priority = int(raw.get("priority", 0))
                created_at = str(raw.get("created_at", ""))
            except (WorkerError, TypeError, ValueError):
                priority, created_at = 0, ""
            candidates.append((-priority, created_at, path))
        for _, _, source in sorted(candidates):
            target = processing / source.name
            try:
                os.replace(source, target)
            except FileNotFoundError:
                continue
            except OSError:
                continue
            return target
        return None

    def recover_processing(self) -> None:
        processing = self.config.bridge_root / "processing"
        for path in sorted(processing.glob("*.json")):
            if path.name.endswith(".state.json"):
                continue
            task_id = path.stem
            if any(
                (self.config.bridge_root / name / f"{task_id}.json").is_file()
                for name in FINAL_DIRECTORIES
            ):
                path.unlink(missing_ok=True)
                self._state_path(task_id).unlink(missing_ok=True)
                continue
            print(f"[{_now()}] 恢复未完成任务 {task_id}", flush=True)
            self._process_claimed(path)

    def _process_claimed(self, task_path: Path) -> None:
        started_at = _now()
        task_id = task_path.stem
        task_type = "unknown"
        source_hashes: list[dict[str, Any]] = []
        try:
            task = self._validate_task(task_path)
            task_id = str(task["task_id"])
            task_type = str(task["task_type"])
            source_hashes = self._verify_manifest(task)
            outputs, details = self._run_task(task)
            result = self._result_envelope(
                task,
                status="completed",
                started_at=started_at,
                source_hashes=source_hashes,
                outputs=outputs,
                details=details,
            )
            _write_json(self.config.bridge_root / "inbox" / f"{task_id}.json", result)
            print(f"[{_now()}] 完成任务 {task_id}，回传 {len(outputs)} 个文件", flush=True)
        except TaskCanceledError as error:
            self._write_failure(
                task_id,
                task_type,
                started_at,
                source_hashes,
                "canceled",
                error,
            )
        except Exception as error:
            self._write_failure(
                task_id,
                task_type,
                started_at,
                source_hashes,
                "failed",
                error,
            )
        finally:
            task_path.unlink(missing_ok=True)
            self._state_path(task_id).unlink(missing_ok=True)

    def _validate_task(self, path: Path) -> dict[str, Any]:
        task = _read_json(path)
        task_id = str(task.get("task_id", ""))
        if task_id != path.stem or not _safe_identifier(task_id):
            raise WorkerError("task_id 与文件名不一致或格式无效")
        if task.get("format") != TASK_FORMAT:
            raise WorkerError("任务格式不受支持")
        if task.get("protocol_version") != COMPUTE_PROTOCOL_VERSION:
            raise WorkerError("任务协议版本不匹配")
        if task.get("target_role") != self.config.role:
            raise WorkerError("任务目标角色与 worker 不匹配")
        task_type = str(task.get("task_type", ""))
        if task_type not in SAFE_TASK_TYPES:
            raise WorkerError(f"当前 worker 不支持任务类型：{task_type}")
        if not isinstance(task.get("payload"), dict) or not isinstance(task.get("manifest"), list):
            raise WorkerError("任务 payload 或 manifest 无效")
        return task

    def _verify_manifest(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        verified = []
        for raw in task["manifest"]:
            if not isinstance(raw, dict):
                raise WorkerError("manifest 条目必须是对象")
            relative = _safe_relative_path(str(raw.get("relative_path", "")))
            path = _inside_root(self.config.bridge_root, relative)
            if not path.is_file():
                raise WorkerError(f"manifest 文件不存在：{relative}")
            expected_hash = str(raw.get("sha256", "")).strip().lower()
            actual_hash = _sha256(path)
            if expected_hash != actual_hash:
                raise WorkerError(f"manifest SHA-256 不匹配：{relative}")
            expected_size = int(raw.get("size_bytes", 0) or 0)
            actual_size = path.stat().st_size
            if expected_size and expected_size != actual_size:
                raise WorkerError(f"manifest 文件大小不匹配：{relative}")
            verified.append(
                {"relative_path": relative, "sha256": actual_hash, "size_bytes": actual_size}
            )
        return verified

    def _run_task(self, task: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if task["task_type"] == "comfyui_generate":
            return self._run_comfyui(task)
        if task["task_type"] == "lora_catalog_snapshot":
            return self._run_lora_catalog_snapshot(task)
        raise WorkerError(f"当前 worker 不支持任务类型：{task['task_type']}")

    def _run_lora_catalog_snapshot(
        self,
        task: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = task["payload"]
        requested = payload.get("lora_roots")
        if not isinstance(requested, list) or not requested:
            raise WorkerError("lora_roots 必须是非空 root_id 列表")
        configured = {root.root_id: root for root in self.config.lora_roots}
        roots = []
        for value in requested:
            root_id = str(value).strip()
            if not _safe_identifier(root_id) or root_id not in configured:
                raise WorkerError(f"LoRA 根目录未在 Worker 配置中登记：{root_id}")
            root = configured[root_id]
            if not root.path.is_dir():
                raise WorkerError(f"LoRA 根目录不存在：{root_id}")
            roots.append(root)

        visible_names = {value.casefold() for value in self.client.lora_names()}
        items = []
        for root in roots:
            items.extend(_scan_lora_root(root, visible_names))
        if not items:
            raise WorkerError("配置的 LoRA 根目录中没有可用模型")
        items.sort(key=lambda item: (str(item["relative_path"]).casefold(), item["lora_id"]))
        snapshot_id = _lora_snapshot_id(items)
        output_root = self.config.bridge_root / "inbox" / str(task["task_id"])
        preview_outputs, preview_summary = _copy_lora_previews(
            items,
            {root.root_id: root.path for root in roots},
            self.config.bridge_root,
            output_root,
        )
        catalog = {
            "format": "soda-windows-lora-catalog-v1",
            "snapshot_id": snapshot_id,
            "worker_id": self.config.worker_id,
            "source_manager": str(payload.get("source_manager", "ComfyUI LoRA Manager"))[:200],
            "created_at": _now(),
            "items": items,
        }
        output_path = output_root / "lora-catalog.json"
        _write_json(output_path, catalog)
        output = _output_record(self.config.bridge_root, output_path, "lora_catalog")
        return [output, *preview_outputs], {
            "snapshot_id": snapshot_id,
            "item_count": len(items),
            **preview_summary,
            "lora_roots": [root.root_id for root in roots],
            "comfyui_visible_count": sum(
                item["metadata"].get("comfyui_visible") is True for item in items
            ),
            "weights_read": False,
        }

    def _run_comfyui(self, task: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = task["payload"]
        package_relative = _safe_relative_path(str(payload.get("generation_package", "")))
        manifested = {
            str(item.get("relative_path", ""))
            for item in task["manifest"]
            if isinstance(item, dict)
        }
        if package_relative not in manifested:
            raise WorkerError("generation_package 必须出现在已校验的 manifest 中")
        package_path = _inside_root(self.config.bridge_root, package_relative)
        package = _read_json(package_path)
        if package.get("format") != PACKAGE_FORMAT:
            raise WorkerError(f"生成包 format 必须是 {PACKAGE_FORMAT}")
        workflow_id = str(payload.get("workflow_id", ""))
        if not workflow_id or package.get("workflow_id") != workflow_id:
            raise WorkerError("任务与生成包的 workflow_id 不一致")
        api_prompt = package.get("api_prompt")
        if not isinstance(api_prompt, dict) or not api_prompt:
            raise WorkerError("生成包缺少非空 api_prompt；请从 ComfyUI 导出 API Format workflow")

        task_id = str(task["task_id"])
        state_path = self._state_path(task_id)
        state = _read_json(state_path) if state_path.is_file() else {}
        prompt_id = str(state.get("prompt_id", ""))
        if not prompt_id:
            prompt_id = self.client.queue_prompt(api_prompt, client_id=self.config.worker_id)
            _write_json(
                state_path,
                {
                    "format": "soda-worker-task-state-v1",
                    "task_id": task_id,
                    "prompt_id": prompt_id,
                    "submitted_at": _now(),
                },
            )
        history = self._wait_for_history(task_id, prompt_id)
        output_root = self.config.bridge_root / "inbox" / task_id
        output_root.mkdir(parents=True, exist_ok=True)
        outputs = self._collect_outputs(history, output_root)
        if not outputs:
            raise WorkerError("ComfyUI 已完成，但 history 中没有可回传图片")
        workflow_path = output_root / "workflow-api.json"
        _write_json(workflow_path, api_prompt)
        outputs.append(_output_record(self.config.bridge_root, workflow_path, "workflow"))
        log_path = output_root / "run-log.json"
        log = {
            "task_id": task_id,
            "prompt_id": prompt_id,
            "workflow_id": workflow_id,
            "output_profile": str(payload.get("output_profile", "")),
            "history_status": history.get("status", {}),
            "downloaded_images": sum(item["kind"] == "image" for item in outputs),
        }
        _write_json(log_path, log)
        outputs.append(_output_record(self.config.bridge_root, log_path, "run_log"))
        return outputs, {"prompt_id": prompt_id, "workflow_id": workflow_id}

    def _wait_for_history(self, task_id: str, prompt_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.config.task_timeout_seconds
        while time.monotonic() < deadline:
            if self._cancel_path(task_id).is_file():
                try:
                    self.client.interrupt()
                finally:
                    self._cancel_path(task_id).unlink(missing_ok=True)
                raise TaskCanceledError("任务已由取消标记停止")
            history = self.client.history(prompt_id)
            if history is not None:
                status = history.get("status", {})
                if isinstance(status, dict) and status.get("status_str") == "error":
                    raise WorkerError(f"ComfyUI 执行失败：{_short_json(status)}")
                return history
            time.sleep(self.config.history_poll_seconds)
        with suppress(WorkerError):
            self.client.interrupt()
        raise WorkerError(f"ComfyUI 任务超过 {self.config.task_timeout_seconds:g} 秒")

    def _collect_outputs(
        self,
        history: dict[str, Any],
        output_root: Path,
    ) -> list[dict[str, Any]]:
        raw_outputs = history.get("outputs", {})
        if not isinstance(raw_outputs, dict):
            return []
        records = []
        index = 0
        for node_id, node_output in raw_outputs.items():
            if not isinstance(node_output, dict):
                continue
            images = node_output.get("images", [])
            for image in images if isinstance(images, list) else []:
                if not isinstance(image, dict) or not str(image.get("filename", "")).strip():
                    continue
                index += 1
                original_name = Path(str(image["filename"])).name
                safe_name = _safe_output_name(original_name, index)
                target = output_root / safe_name
                target.write_bytes(self.client.download_output(image))
                record = _output_record(self.config.bridge_root, target, "image")
                record.update(
                    {
                        "node_id": str(node_id),
                        "comfyui_filename": original_name,
                        "comfyui_subfolder": str(image.get("subfolder", "")),
                        "comfyui_type": str(image.get("type", "output")),
                    }
                )
                records.append(record)
        return records

    def _result_envelope(
        self,
        task: dict[str, Any],
        *,
        status: str,
        started_at: str,
        source_hashes: list[dict[str, Any]],
        outputs: list[dict[str, Any]],
        details: dict[str, Any],
    ) -> dict[str, Any]:
        result = {
            "format": RESULT_FORMAT,
            "protocol_version": COMPUTE_PROTOCOL_VERSION,
            "task_id": task["task_id"],
            "task_type": task["task_type"],
            "worker_id": self.config.worker_id,
            "status": status,
            "started_at": started_at,
            "finished_at": _now(),
            "source_hashes": source_hashes,
            "outputs": outputs,
            "details": details,
        }
        for key in ("project_id", "workspace_id", "run_id", "attempt", "retry_of"):
            if key in task:
                result[key] = task[key]
        return result

    def _write_failure(
        self,
        task_id: str,
        task_type: str,
        started_at: str,
        source_hashes: list[dict[str, Any]],
        status: str,
        error: Exception,
    ) -> None:
        safe_task_id = task_id if _safe_identifier(task_id) else f"invalid-{uuid4().hex[:12]}"
        detail_root = self.config.bridge_root / "failed" / safe_task_id
        detail_root.mkdir(parents=True, exist_ok=True)
        log_path = detail_root / "worker-error.txt"
        trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        log_path.write_text(trace, encoding="utf-8")
        output = _output_record(self.config.bridge_root, log_path, "run_log")
        result = {
            "format": RESULT_FORMAT,
            "protocol_version": COMPUTE_PROTOCOL_VERSION,
            "task_id": safe_task_id,
            "task_type": task_type,
            "worker_id": self.config.worker_id,
            "status": status,
            "started_at": started_at,
            "finished_at": _now(),
            "source_hashes": source_hashes,
            "outputs": [output],
            "error": str(error)[:2000],
        }
        _write_json(self.config.bridge_root / "failed" / f"{safe_task_id}.json", result)
        print(f"[{_now()}] 任务 {safe_task_id} {status}：{error}", flush=True)

    def _state_path(self, task_id: str) -> Path:
        return self.config.bridge_root / "processing" / f"{task_id}.state.json"

    def _cancel_path(self, task_id: str) -> Path:
        return self.config.bridge_root / "processing" / f"{task_id}.cancel"


def _parse_lora_roots(value: object) -> tuple[LoraRootConfig, ...]:
    if value in (None, []):
        return ()
    if not isinstance(value, list):
        raise WorkerError("lora_roots 配置必须是列表")
    roots = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            raise WorkerError("lora_roots 配置条目必须是对象")
        root_id = str(item.get("root_id", "")).strip()
        path = Path(str(item.get("path", "")).strip())
        if not _safe_identifier(root_id) or root_id in seen:
            raise WorkerError(f"LoRA root_id 无效或重复：{root_id}")
        if not path.is_absolute():
            raise WorkerError(f"LoRA 根目录必须是绝对路径：{root_id}")
        roots.append(LoraRootConfig(root_id=root_id, path=path))
        seen.add(root_id)
    return tuple(roots)


def _lora_root_status(root: LoraRootConfig) -> dict[str, Any]:
    exists = root.path.is_dir()
    count = 0
    if exists:
        count = sum(
            path.is_file() and path.suffix.casefold() in LORA_MODEL_SUFFIXES
            for path in root.path.rglob("*")
        )
    return {
        "root_id": root.root_id,
        "path": str(root.path),
        "exists": exists,
        "model_count": count,
    }


def _scan_lora_root(
    root: LoraRootConfig,
    visible_names: set[str],
) -> list[dict[str, Any]]:
    items = []
    for path in root.path.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in LORA_MODEL_SUFFIXES:
            continue
        relative = path.relative_to(root.path).as_posix()
        metadata = _read_lora_metadata(path.with_suffix(".metadata.json"))
        civitai = metadata.get("civitai")
        civitai = civitai if isinstance(civitai, dict) else {}
        civitai_model = civitai.get("model")
        civitai_model = civitai_model if isinstance(civitai_model, dict) else {}
        previews = _find_lora_previews(root.path, path, metadata)
        trigger_words = _metadata_strings(
            metadata,
            "trigger_words",
            "triggerWords",
            "trained_words",
            "trainedWords",
        )
        if not trigger_words:
            trigger_words = _metadata_strings(civitai, "trainedWords", "triggerWords")
        tags = _unique_strings(
            _metadata_strings(metadata, "tags", "tag_list", "tagList")
            + _metadata_strings(civitai_model, "tags")
        )
        base_model = _metadata_text(metadata, "base_model", "baseModel", "base_model_name") or (
            _metadata_text(civitai, "baseModel", "base_model")
        )
        family = _model_family(relative, base_model)
        item_metadata = _public_lora_metadata(metadata)
        item_metadata.update(
            {
                "root_id": root.root_id,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                "comfyui_visible": relative.casefold() in visible_names,
                "metadata_sidecar": path.with_suffix(".metadata.json").is_file(),
            }
        )
        items.append(
            {
                "lora_id": _lora_id(root.root_id, relative),
                "name": _metadata_text(metadata, "name", "model_name", "modelName") or path.stem,
                "relative_path": relative,
                "sha256": _metadata_sha256(metadata),
                "size_bytes": path.stat().st_size,
                "base_model": base_model,
                "model_family": family,
                "trigger_words": trigger_words,
                "tags": tags,
                "preview_relative_path": previews[0] if previews else "",
                "preview_relative_paths": previews,
                "notes": _metadata_text(metadata, "notes")[:2000],
                "metadata": item_metadata,
            }
        )
    return items


def _read_lora_metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        if path.stat().st_size > MAX_LORA_METADATA_BYTES:
            return {"metadata_error": "sidecar_too_large"}
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"metadata_error": "sidecar_unreadable"}
    return value if isinstance(value, dict) else {"metadata_error": "sidecar_not_object"}


def _find_lora_previews(root: Path, model: Path, metadata: dict[str, Any]) -> list[str]:
    discovered: list[Path] = []
    preview_value = _metadata_text(metadata, "preview_url", "previewUrl", "preview")
    if preview_value:
        candidate = Path(preview_value)
        if not candidate.is_absolute():
            candidate = model.parent / candidate
        with suppress(OSError, ValueError):
            resolved = candidate.resolve()
            if resolved.is_file() and resolved.is_relative_to(root.resolve()):
                discovered.append(resolved)
    model_stem = model.stem.casefold()
    accepted_stems = {model_stem}
    accepted_stems.update(f"{model_stem}.{sidecar}" for sidecar in LORA_PREVIEW_SIDECAR_STEMS)
    candidates = [
        path
        for path in model.parent.iterdir()
        if path.is_file()
        and path.suffix.casefold() in LORA_PREVIEW_SUFFIXES
        and path.stem.casefold() in accepted_stems
    ]
    preferred = sorted(
        (path.resolve() for path in candidates if path.is_file()),
        key=lambda path: (
            "civitai_bak" in path.name.casefold(),
            len(path.name),
            path.name.casefold(),
        ),
    )
    discovered.extend(preferred)
    unique = []
    root_resolved = root.resolve()
    for path in discovered:
        with suppress(OSError, ValueError):
            relative = path.relative_to(root_resolved).as_posix()
            if relative not in unique:
                unique.append(relative)
    return unique


def _copy_lora_previews(
    items: list[dict[str, Any]],
    roots: dict[str, Path],
    bridge_root: Path,
    output_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    total_bytes = 0
    skipped = 0
    skipped_reasons: Counter[str] = Counter()
    for item in items:
        copied_sources = []
        root_id = str(item.get("metadata", {}).get("root_id", ""))
        root = roots.get(root_id)
        if root is None:
            continue
        for source_relative in item.get("preview_relative_paths", []):
            if len(outputs) >= MAX_LORA_PREVIEW_COUNT:
                skipped += 1
                skipped_reasons["count_limit"] += 1
                continue
            try:
                clean_relative = _safe_relative_path(str(source_relative))
                source = _inside_root(root, clean_relative)
                suffix = source.suffix.casefold()
                size = source.stat().st_size
            except (OSError, WorkerError):
                skipped += 1
                skipped_reasons["source_unavailable"] += 1
                continue
            if suffix not in LORA_PREVIEW_SUFFIXES:
                skipped += 1
                skipped_reasons["unsupported_format"] += 1
                continue
            if size <= 0:
                skipped += 1
                skipped_reasons["empty_file"] += 1
                continue
            if size > MAX_LORA_PREVIEW_BYTES:
                skipped += 1
                skipped_reasons["file_too_large"] += 1
                continue
            try:
                detected_suffix = _lora_preview_suffix(source)
            except OSError:
                skipped += 1
                skipped_reasons["source_unavailable"] += 1
                continue
            if not detected_suffix:
                skipped += 1
                skipped_reasons["invalid_image_header"] += 1
                continue
            if total_bytes + size > MAX_LORA_PREVIEW_TOTAL_BYTES:
                skipped += 1
                skipped_reasons["total_size_limit"] += 1
                continue
            index = len(copied_sources)
            target = (
                output_root
                / "lora-previews"
                / str(item["lora_id"])
                / f"{index:03d}{detected_suffix}"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
            try:
                shutil.copyfile(source, temporary)
                os.replace(temporary, target)
            finally:
                with suppress(OSError):
                    temporary.unlink()
            record = _output_record(bridge_root, target, "lora_preview")
            record.update(
                {
                    "lora_id": item["lora_id"],
                    "preview_index": index,
                    "source_relative_path": clean_relative,
                }
            )
            outputs.append(record)
            copied_sources.append(clean_relative)
            total_bytes += size
        item["preview_relative_paths"] = copied_sources
        item["preview_relative_path"] = copied_sources[0] if copied_sources else ""
    return outputs, {
        "preview_count": len(outputs),
        "preview_total_bytes": total_bytes,
        "preview_skipped_count": skipped,
        "preview_skipped_reasons": dict(sorted(skipped_reasons.items())),
    }


def _lora_preview_suffix(path: Path) -> str:
    with path.open("rb") as handle:
        header = handle.read(16)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpeg"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    if header[:6] in {b"GIF87a", b"GIF89a"}:
        return ".gif"
    return ""


def _metadata_text(metadata: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()[:1000]
    return ""


def _metadata_strings(metadata: dict[str, Any], *keys: str) -> list[str]:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str):
            return [part.strip()[:300] for part in value.split(",") if part.strip()][:300]
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict):
                    text = _metadata_text(item, "word", "name", "tag")
                else:
                    text = str(item).strip()[:300]
                if text and text not in result:
                    result.append(text)
                if len(result) >= 300:
                    break
            return result
    return []


def _unique_strings(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result[:300]


def _metadata_sha256(metadata: dict[str, Any]) -> str:
    value = _metadata_text(metadata, "sha256").casefold()
    if len(value) == 64 and all(char in "0123456789abcdef" for char in value):
        return value
    return ""


def _public_lora_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "modelId",
        "modelVersionId",
        "civitai_model_id",
        "civitai_version_id",
        "metadata_source",
        "preview_nsfw_level",
        "description",
        "version_name",
    )
    result = {}
    for key in allowed:
        value = metadata.get(key)
        if isinstance(value, (str, int, float, bool)):
            result[key] = str(value)[:2000] if isinstance(value, str) else value
    if error := _metadata_text(metadata, "metadata_error"):
        result["metadata_error"] = error
    civitai = metadata.get("civitai")
    if isinstance(civitai, dict):
        for source_key, target_key in (
            ("modelId", "civitai_model_id"),
            ("id", "civitai_version_id"),
            ("name", "civitai_version_name"),
        ):
            value = civitai.get(source_key)
            if isinstance(value, (str, int, float)):
                result[target_key] = str(value)[:1000] if isinstance(value, str) else value
    return result


def _model_family(relative: str, base_model: str) -> str:
    text = f"{relative} {base_model}".casefold()
    if "anima" in text:
        return "anima"
    if "krea" in text:
        return "krea2"
    if "illustrious" in text or "noob" in text:
        return "illustrious"
    if "flux" in text:
        return "flux"
    if "sdxl" in text or "pony" in text:
        return "sdxl"
    return "unknown"


def _lora_id(root_id: str, relative: str) -> str:
    value = f"{root_id}:{relative.casefold()}".encode()
    return f"lora-{hashlib.sha256(value).hexdigest()[:24]}"


def _lora_snapshot_id(items: list[dict[str, Any]]) -> str:
    facts = [
        {
            "lora_id": item["lora_id"],
            "relative_path": item["relative_path"],
            "size_bytes": item["size_bytes"],
            "modified_at": item["metadata"].get("modified_at", ""),
        }
        for item in items
    ]
    digest = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"catalog-{stamp}-{digest}"


def _positive_float(raw: dict[str, Any], key: str, default: float) -> float:
    try:
        value = float(raw.get(key, default))
    except (TypeError, ValueError) as error:
        raise WorkerError(f"{key} 必须是数字") from error
    if value <= 0:
        raise WorkerError(f"{key} 必须大于 0")
    return value


def _safe_identifier(value: str) -> bool:
    return (
        bool(value)
        and len(value) <= 160
        and all(
            char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for char in value
        )
    )


def _safe_relative_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or ":" in normalized
        or any(part in {"", "."} for part in path.parts)
    ):
        raise WorkerError(f"相对路径无效：{value}")
    return path.as_posix()


def _inside_root(root: Path, relative: str) -> Path:
    root_resolved = root.resolve()
    candidate = (root_resolved / Path(*PurePosixPath(relative).parts)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as error:
        raise WorkerError(f"路径越过 bridge_root：{relative}") from error
    return candidate


def _safe_output_name(name: str, index: int) -> str:
    stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in Path(name).stem)
    suffix = "".join(char for char in Path(name).suffix if char.isalnum() or char == ".")[:12]
    return f"{index:03d}-{stem[:120] or 'output'}{suffix}"


def _output_record(root: Path, path: Path, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "relative_path": path.resolve().relative_to(root.resolve()).as_posix(),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkerError(f"无法读取 JSON {path.name}：{error}") from error
    if not isinstance(value, dict):
        raise WorkerError(f"JSON 必须是对象：{path.name}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _short_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))[:2000]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def worker_lock_path(config: WorkerConfig) -> Path:
    if sys.platform == "win32":
        local_value = os.environ.get("LOCALAPPDATA")
        local_root = Path(local_value) if local_value else Path.cwd()
        return local_root / "PromptHub" / f"{config.worker_id}.lock"
    return config.bridge_root / "worker.lock"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt Hub Windows 5060 Ti worker")
    parser.add_argument("--config", default="worker-config.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--once", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = WorkerConfig.load(Path(args.config).resolve())
        worker = WindowsWorker(config)
        with WorkerLock(worker_lock_path(config)):
            if args.self_test:
                print(json.dumps(worker.self_test(), ensure_ascii=False, indent=2))
                return 0
            if args.once:
                worker.recover_processing()
                return 0 if worker.run_once() else 3
            worker.run_forever()
    except KeyboardInterrupt:
        print("\nworker 已停止。", flush=True)
        return 0
    except WorkerError as error:
        print(f"worker 无法启动：{error}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
