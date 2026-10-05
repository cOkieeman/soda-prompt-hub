from __future__ import annotations

# standalone-bundle: omit-start
import base64
import json
import os
import socket
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from contextlib import AbstractContextManager, suppress
from pathlib import Path
from threading import Event, Thread
from typing import Any, BinaryIO, Self
from uuid import uuid4

from prompt_hub.windows_worker_support import (
    COMPUTE_PROTOCOL_VERSION,
    FINAL_DIRECTORIES,
    PACKAGE_FORMAT,
    RESULT_FORMAT,
    SAFE_TASK_TYPES,
    TASK_FORMAT,
    WORKER_BUILD_SHA256,
    WORKER_RELEASE,
    WORKER_VERSION,
    TaskCanceledError,
    WorkerConfig,
    WorkerError,
    _copy_lora_previews,
    _copy_model_previews,
    _inside_root,
    _lora_root_status,
    _lora_snapshot_id,
    _model_root_status,
    _model_snapshot_id,
    _now,
    _output_record,
    _read_json,
    _safe_identifier,
    _safe_output_name,
    _safe_relative_path,
    _scan_lora_root,
    _scan_model_root,
    _sha256,
    _short_json,
    _write_json,
)

# standalone-bundle: omit-end


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
        self.base_url, self._authorization = _split_credentials(base_url)
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
        headers: dict[str, str] = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self._authorization:
            headers["Authorization"] = self._authorization
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise WorkerError(f"无法访问 ComfyUI：{error}") from error


def _split_credentials(base_url: str) -> tuple[str, str]:
    """Split ``http(s)://user:password@host`` into a clean URL and an Authorization value.

    A ComfyUI behind a reverse proxy (or simply on another machine) is often protected by
    HTTP Basic auth. Keeping the credentials inside ``comfyui_url`` avoids a second
    configuration field, and urllib itself would not send them.
    """
    parts = urllib.parse.urlsplit(base_url)
    if not parts.username:
        return base_url.rstrip("/"), ""
    credentials = (
        f"{urllib.parse.unquote(parts.username)}:{urllib.parse.unquote(parts.password or '')}"
    )
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    clean = urllib.parse.urlunsplit((parts.scheme, host, parts.path.rstrip("/"), "", ""))
    token = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    return clean, f"Basic {token}"


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
        model_roots = [_model_root_status(root) for root in self.config.model_roots]
        result = {
            "format": "soda-worker-status-v1",
            "status": "ready",
            "worker_id": self.config.worker_id,
            "worker_version": WORKER_VERSION,
            "release_channel": WORKER_RELEASE["release_channel"],
            "release_format": WORKER_RELEASE["format"],
            "worker_build_sha256": WORKER_BUILD_SHA256,
            "hostname": socket.gethostname(),
            "python": sys.version.split()[0],
            "protocol_version": COMPUTE_PROTOCOL_VERSION,
            "role": self.config.role,
            "comfyui_url": self.config.comfyui_url,
            "comfyui_reachable": True,
            "capabilities": sorted(SAFE_TASK_TYPES),
            "lora_roots": lora_roots,
            "model_roots": model_roots,
            "checked_at": _now(),
            "system_stats": stats,
        }
        _write_json(self.config.bridge_root / "worker-status.json", result)
        return result

    def run_forever(self) -> None:
        self.initialize()
        stop = Event()
        heartbeat = Thread(target=self._heartbeat_loop, args=(stop,), daemon=True)
        heartbeat.start()
        try:
            self.recover_processing()
            print(f"[{_now()}] worker 已启动；等待任务。按 Ctrl+C 停止。", flush=True)
            while True:
                worked = self.run_once()
                if not worked:
                    time.sleep(self.config.poll_interval_seconds)
        finally:
            stop.set()
            heartbeat.join(timeout=5)
            if not heartbeat.is_alive():
                self.write_heartbeat(running=False)

    def write_heartbeat(self, *, running: bool = True) -> None:
        reachable = False
        if running:
            try:
                ComfyUIClient(self.config.comfyui_url, timeout=3).system_stats()
                reachable = True
            except WorkerError:
                pass
        payload = {
            "format": "soda-worker-heartbeat-v1",
            "running": running,
            "checked_at": _now(),
            "worker_id": self.config.worker_id,
            "worker_version": WORKER_VERSION,
            "release_channel": WORKER_RELEASE["release_channel"],
            "protocol_version": COMPUTE_PROTOCOL_VERSION,
            "role": self.config.role,
            "hostname": socket.gethostname(),
            "comfyui_reachable": reachable,
        }
        with suppress(OSError):
            _write_json(self.config.bridge_root / "worker-heartbeat.json", payload)

    def _heartbeat_loop(self, stop: Event) -> None:
        while not stop.is_set():
            self.write_heartbeat()
            if stop.wait(5):
                break

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
        if task["task_type"] == "model_catalog_snapshot":
            return self._run_model_catalog_snapshot(task)
        raise WorkerError(f"当前 worker 不支持任务类型：{task['task_type']}")

    def _run_model_catalog_snapshot(
        self,
        task: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = task["payload"]
        requested = payload.get("model_roots")
        if not isinstance(requested, list) or not requested:
            raise WorkerError("model_roots 必须是非空 root_id 列表")
        configured = {root.root_id: root for root in self.config.model_roots}
        roots = []
        for value in requested:
            root_id = str(value).strip()
            if not _safe_identifier(root_id) or root_id not in configured:
                raise WorkerError(f"模型根目录未在 Worker 配置中登记：{root_id}")
            root = configured[root_id]
            if not root.path.is_dir():
                raise WorkerError(f"模型根目录不存在：{root_id}")
            roots.append(root)

        items = [item for root in roots for item in _scan_model_root(root)]
        if not items:
            raise WorkerError("配置的模型根目录中没有可用模型")
        items.sort(
            key=lambda item: (
                str(item["asset_type"]),
                str(item["relative_path"]).casefold(),
                str(item["asset_id"]),
            )
        )
        snapshot_id = _model_snapshot_id(items)
        output_root = self.config.bridge_root / "inbox" / str(task["task_id"])
        preview_outputs, preview_summary = _copy_model_previews(
            items,
            {root.root_id: root.path for root in roots},
            self.config.bridge_root,
            output_root,
        )
        catalog = {
            "format": "soda-windows-model-catalog-v1",
            "snapshot_id": snapshot_id,
            "worker_id": self.config.worker_id,
            "source_manager": str(payload.get("source_manager", "ComfyUI model folders"))[:200],
            "created_at": _now(),
            "items": items,
        }
        output_path = output_root / "model-catalog.json"
        _write_json(output_path, catalog)
        output = _output_record(self.config.bridge_root, output_path, "model_catalog")
        return [output, *preview_outputs], {
            "snapshot_id": snapshot_id,
            "item_count": len(items),
            **preview_summary,
            "model_roots": [root.root_id for root in roots],
            "type_counts": dict(Counter(str(item["asset_type"]) for item in items)),
            "weights_read": False,
            "weights_copied": False,
        }

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
            "worker_version": WORKER_VERSION,
            "worker_build_sha256": WORKER_BUILD_SHA256,
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
            "worker_version": WORKER_VERSION,
            "worker_build_sha256": WORKER_BUILD_SHA256,
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
