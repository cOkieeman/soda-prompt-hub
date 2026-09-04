from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import urllib.parse
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import Any
from uuid import uuid4

from prompt_hub.compute_bridge import COMPUTE_PROTOCOL_VERSION, compute_contract

NODE_ROLES = {"compute_5060ti"}
BRIDGE_DIRECTORIES = ("outbox", "inbox", "processing", "completed", "failed")
SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
CIVITAI_MODEL_PATH_RE = re.compile(r"^/models/(?P<model_id>[1-9]\d*)(?:/[^/?#]+)?/?$")
CIVITAI_HOSTS = {"civitai.com", "www.civitai.com", "civitai.red", "www.civitai.red"}
RESULT_FORMAT = "soda-compute-result-v1"
LORA_PREVIEW_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
MODEL_ASSET_TYPES = {
    "checkpoint",
    "controlnet",
    "diffusion_model",
    "text_encoder",
    "upscaler",
    "vae",
}
MAX_LORA_PREVIEW_BYTES = 32 * 1024 * 1024
MAX_LORA_PREVIEW_COUNT = 1024
MAX_LORA_PREVIEW_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_CIVITAI_URL_LENGTH = 2000
TASK_LOCATION_STATUS = {
    "outbox": "queued",
    "processing": "running",
    "inbox": "returned",
    "completed": "completed",
    "failed": "failed",
}
TASK_LOCATION_PRIORITY = {
    "local": 0,
    "outbox": 1,
    "processing": 2,
    "inbox": 3,
    "completed": 4,
    "failed": 5,
}
SENSITIVE_TASK_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "credential",
    "credentials",
    "private_key",
}


class RemoteNodeError(ValueError):
    pass


class RemoteNodeStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.nodes_path = root / "nodes.json"
        self.catalog_root = root / "lora-catalog"
        self.model_catalog_root = root / "model-catalog"
        self.preview_root = root / "lora-previews"
        self.model_preview_root = root / "model-previews"
        self.task_records_root = root / "tasks"
        self._lock = Lock()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.catalog_root.mkdir(parents=True, exist_ok=True)
        self.model_catalog_root.mkdir(parents=True, exist_ok=True)
        self.preview_root.mkdir(parents=True, exist_ok=True)
        self.model_preview_root.mkdir(parents=True, exist_ok=True)
        self.task_records_root.mkdir(parents=True, exist_ok=True)

    def list_nodes(self) -> list[dict[str, Any]]:
        payload = _read_json(self.nodes_path, {"nodes": []})
        nodes = payload.get("nodes", [])
        return nodes if isinstance(nodes, list) else []

    def save_node(self, node_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean_id = _safe_id(node_id, "node_id")
        role = str(payload.get("role", ""))
        if role not in NODE_ROLES:
            raise RemoteNodeError("设备角色无效")
        smb_mount = str(payload.get("smb_mount", "")).strip()
        if smb_mount and not Path(smb_mount).expanduser().is_absolute():
            raise RemoteNodeError("SMB 挂载路径必须是 Mac 上的绝对路径")
        node = {
            "node_id": clean_id,
            "label": str(payload.get("label", "")).strip()[:160] or clean_id,
            "role": role,
            "host": str(payload.get("host", "")).strip()[:255],
            "smb_mount": smb_mount[:4096],
            "enabled": bool(payload.get("enabled", False)),
            "capabilities": sorted(
                {
                    str(value).strip()[:120]
                    for value in payload.get("capabilities", [])
                    if str(value).strip()
                }
            ),
            "notes": str(payload.get("notes", "")).strip()[:1000],
            "updated_at": _now(),
        }
        with self._lock:
            nodes = self.list_nodes()
            existing = next(
                (index for index, item in enumerate(nodes) if item["node_id"] == clean_id), -1
            )
            if existing >= 0:
                nodes[existing] = node
            else:
                nodes.append(node)
            _write_json(self.nodes_path, {"format": "soda-remote-nodes-v1", "nodes": nodes})
        return node

    def diagnostics(self, node_id: str) -> dict[str, Any]:
        clean_id = _safe_id(node_id, "node_id")
        node = next((item for item in self.list_nodes() if item["node_id"] == clean_id), None)
        if node is None:
            raise RemoteNodeError("设备尚未登记")
        mount_value = str(node.get("smb_mount", ""))
        mount = Path(mount_value).expanduser() if mount_value else None
        mount_exists = bool(mount and mount.is_dir())
        bridge_root = mount / "prompt-hub" if mount else None
        prepared = bool(
            bridge_root
            and bridge_root.is_dir()
            and all((bridge_root / name).is_dir() for name in BRIDGE_DIRECTORIES)
        )
        writable = bool(bridge_root and bridge_root.is_dir() and os.access(bridge_root, os.W_OK))
        worker_status = (
            _read_json(bridge_root / "worker-status.json", {})
            if bridge_root and bridge_root.is_dir()
            else {}
        )
        worker_ready = bool(
            worker_status.get("status") == "ready"
            and worker_status.get("protocol_version") == COMPUTE_PROTOCOL_VERSION
            and worker_status.get("role") == node.get("role")
            and worker_status.get("comfyui_reachable") is True
        )
        configured = bool(node.get("host") and mount_value)
        if not configured:
            state = "not_configured"
        elif not mount_exists:
            state = "mount_missing"
        elif not prepared:
            state = "mount_ready_bridge_unprepared"
        elif not writable:
            state = "bridge_read_only"
        else:
            state = "ready"
        return {
            "node": node,
            "state": state,
            "configured": configured,
            "mount_exists": mount_exists,
            "bridge_prepared": prepared,
            "bridge_writable": writable,
            "bridge_root": str(bridge_root) if bridge_root else "",
            "worker_ready": worker_ready,
            "worker_status": worker_status,
            "credentials_stored": False,
        }

    def prepare_bridge(self, node_id: str) -> dict[str, Any]:
        diagnostic = self.diagnostics(node_id)
        if not diagnostic["mount_exists"]:
            raise RemoteNodeError("SMB 挂载目录不存在，不能建立交付桥")
        bridge_root = Path(str(diagnostic["bridge_root"]))
        bridge_root.mkdir(parents=True, exist_ok=True)
        for name in BRIDGE_DIRECTORIES:
            (bridge_root / name).mkdir(exist_ok=True)
        return self.diagnostics(node_id)

    def submit_task(
        self,
        node_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        node = self._required_node(node_id)
        if not node.get("enabled"):
            raise RemoteNodeError("设备尚未启用，不能投递任务")
        contract = compute_contract()
        task_type = str(values.get("task_type", ""))
        payload = values.get("payload", {})
        if not isinstance(payload, dict):
            raise RemoteNodeError("任务 payload 必须是对象")
        task_spec = contract["task_types"].get(task_type)
        if not isinstance(task_spec, dict):
            raise RemoteNodeError("任务类型不在 compute contract 中")
        if task_spec.get("target_role") != node.get("role"):
            raise RemoteNodeError("任务类型与设备角色不匹配")
        declared_capabilities = node.get("capabilities", [])
        if not isinstance(declared_capabilities, list):
            declared_capabilities = []
        if task_type not in declared_capabilities:
            diagnostic = self.diagnostics(node_id)
            worker_status = diagnostic.get("worker_status", {})
            runtime_capabilities = (
                worker_status.get("capabilities", [])
                if diagnostic.get("worker_ready") and isinstance(worker_status, dict)
                else []
            )
            if not isinstance(runtime_capabilities, list) or task_type not in runtime_capabilities:
                raise RemoteNodeError("设备与已自检 Worker 均未声明此任务 capability")
        _reject_task_credentials(payload)
        required = task_spec.get("payload_required", [])
        missing = [str(key) for key in required if not _present(payload.get(str(key)))]
        if missing:
            raise RemoteNodeError(f"任务 payload 缺少字段: {', '.join(missing)}")
        clean_manifest = _normalize_task_manifest(values.get("manifest", []))
        clean_project = _optional_safe_id(str(values.get("project_id", "")), "project_id")
        clean_workspace = _optional_safe_id(str(values.get("workspace_id", "")), "workspace_id")
        clean_run = _optional_safe_id(str(values.get("run_id", "")), "run_id")
        clean_retry = _optional_safe_id(str(values.get("retry_of", "")), "retry_of")
        clean_attempt = max(1, min(int(values.get("attempt", 1)), 1000))
        task_id = _new_task_id()
        envelope = {
            "format": "soda-compute-task-v1",
            "protocol_version": COMPUTE_PROTOCOL_VERSION,
            "task_id": task_id,
            "task_type": task_type,
            "target_role": node["role"],
            "created_at": _now(),
            "payload": payload,
            "manifest": clean_manifest,
            "attempt": clean_attempt,
            "priority": max(-100, min(int(values.get("priority", 0)), 100)),
        }
        envelope.update(
            {
                key: value
                for key, value in (
                    ("project_id", clean_project),
                    ("workspace_id", clean_workspace),
                    ("run_id", clean_run),
                    ("retry_of", clean_retry),
                )
                if value
            }
        )
        bridge_root = self._ready_bridge(node_id)
        record_path = self._task_record_path(node_id, task_id)
        with self._lock:
            _write_json(record_path, envelope)
            _write_json(bridge_root / "outbox" / f"{task_id}.json", envelope)
        return _task_summary(envelope, location="outbox", local=envelope)

    def list_tasks(self, node_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        self._required_node(node_id)
        local_records = self._local_task_records(node_id)
        summaries = {
            task_id: _task_summary(record, location="local", local=record)
            for task_id, record in local_records.items()
        }
        diagnostic = self.diagnostics(node_id)
        bridge_root_value = str(diagnostic.get("bridge_root", ""))
        bridge_root = Path(bridge_root_value) if bridge_root_value else None
        if bridge_root and bridge_root.is_dir():
            for location in TASK_LOCATION_STATUS:
                directory = bridge_root / location
                if not directory.is_dir():
                    continue
                for path in directory.glob("*.json"):
                    exchange = _read_json(path, {})
                    task_id = str(exchange.get("task_id", path.stem))
                    if not SAFE_ID_RE.fullmatch(task_id):
                        continue
                    local = local_records.get(task_id, {})
                    summary = _task_summary(exchange, location=location, local=local)
                    current = summaries.get(task_id)
                    if current is None or TASK_LOCATION_PRIORITY[
                        location
                    ] >= TASK_LOCATION_PRIORITY.get(str(current.get("location", "local")), 0):
                        summaries[task_id] = summary
        return sorted(
            summaries.values(),
            key=lambda item: str(item.get("updated_at") or item.get("created_at", "")),
            reverse=True,
        )[: max(1, min(limit, 1000))]

    def get_task(self, node_id: str, task_id: str) -> dict[str, Any]:
        clean_task = _safe_id(task_id, "task_id")
        local = _read_json(self._task_record_path(node_id, clean_task), {})
        exchanges = []
        diagnostic = self.diagnostics(node_id)
        bridge_root_value = str(diagnostic.get("bridge_root", ""))
        bridge_root = Path(bridge_root_value) if bridge_root_value else None
        if bridge_root and bridge_root.is_dir():
            for location in TASK_LOCATION_STATUS:
                path = bridge_root / location / f"{clean_task}.json"
                if path.is_file():
                    exchanges.append({"location": location, "envelope": _read_json(path, {})})
        if not local and not exchanges:
            raise RemoteNodeError("任务不存在")
        if exchanges:
            exchange = max(
                exchanges,
                key=lambda item: TASK_LOCATION_PRIORITY[str(item["location"])],
            )
            location = str(exchange["location"])
            raw_envelope = exchange["envelope"]
            envelope = raw_envelope if isinstance(raw_envelope, dict) else {}
        else:
            location = "local"
            envelope = local
        return {
            "summary": _task_summary(
                envelope,
                location=location,
                local=local,
            ),
            "local_task": local,
            "exchange": exchanges,
        }

    def retry_task(self, node_id: str, task_id: str) -> dict[str, Any]:
        current = self.get_task(node_id, task_id)
        summary = current["summary"]
        if summary["status"] not in {"failed", "canceled"} and summary.get("result_status") not in {
            "failed",
            "canceled",
        }:
            raise RemoteNodeError("只有失败或取消的任务可以重试")
        original = current["local_task"]
        if not original:
            raise RemoteNodeError("缺少 Mac 本地任务事实副本，不能安全重试")
        return self.submit_task(
            node_id,
            {
                "task_type": str(original["task_type"]),
                "payload": dict(original.get("payload", {})),
                "manifest": list(original.get("manifest", [])),
                "project_id": str(original.get("project_id", "")),
                "workspace_id": str(original.get("workspace_id", "")),
                "run_id": str(original.get("run_id", "")),
                "priority": int(original.get("priority", 0)),
                "attempt": int(original.get("attempt", 1)) + 1,
                "retry_of": str(original["task_id"]),
            },
        )

    def verify_returned_task(self, node_id: str, task_id: str) -> dict[str, Any]:
        clean_task = _safe_id(task_id, "task_id")
        bridge_root = self._ready_bridge(node_id)
        result_path = bridge_root / "inbox" / f"{clean_task}.json"
        if not result_path.is_file():
            raise RemoteNodeError("任务尚未进入 inbox，不能验收")
        local = _read_json(self._task_record_path(node_id, clean_task), {})
        if not local:
            raise RemoteNodeError("缺少 Mac 本地任务事实副本，不能验收")
        result = _read_json(result_path, {})
        errors: list[str] = []
        if result.get("format") != RESULT_FORMAT:
            errors.append("result format 不匹配")
        if result.get("protocol_version") != COMPUTE_PROTOCOL_VERSION:
            errors.append("protocol_version 不匹配")
        if result.get("task_id") != clean_task:
            errors.append("task_id 不匹配")
        if result.get("task_type") != local.get("task_type"):
            errors.append("task_type 不匹配")
        if result.get("status") != "completed":
            errors.append("inbox 结果不是 completed")

        expected_sources = {
            str(item.get("relative_path", "")): str(item.get("sha256", ""))
            for item in local.get("manifest", [])
            if isinstance(item, dict)
        }
        returned_sources = result.get("source_hashes", [])
        if not isinstance(returned_sources, list):
            errors.append("source_hashes 不是列表")
            returned_sources = []
        actual_sources = {
            str(item.get("relative_path", "")): str(item.get("sha256", ""))
            for item in returned_sources
            if isinstance(item, dict)
        }
        if actual_sources != expected_sources:
            errors.append("回显源文件哈希与 Mac manifest 不一致")

        checked_outputs = []
        outputs = result.get("outputs", [])
        if not isinstance(outputs, list) or not outputs:
            errors.append("结果没有输出文件")
            outputs = []
        for raw in outputs:
            try:
                checked_outputs.append(_verify_result_output(bridge_root, clean_task, raw))
            except RemoteNodeError as error:
                errors.append(str(error))
        return {
            "task_id": clean_task,
            "verified": not errors,
            "errors": errors,
            "source_count": len(actual_sources),
            "output_count": len(checked_outputs),
            "outputs": checked_outputs,
        }

    def cancel_task(self, node_id: str, task_id: str) -> dict[str, Any]:
        clean_task = _safe_id(task_id, "task_id")
        bridge_root = self._ready_bridge(node_id)
        current = self.get_task(node_id, clean_task)
        summary = current["summary"]
        local = current["local_task"]
        if not local:
            raise RemoteNodeError("缺少 Mac 本地任务事实副本，不能取消")
        if summary["status"] == "queued":
            source = bridge_root / "outbox" / f"{clean_task}.json"
            if source.is_file():
                now = _now()
                result = {
                    "format": RESULT_FORMAT,
                    "protocol_version": COMPUTE_PROTOCOL_VERSION,
                    "task_id": clean_task,
                    "task_type": local.get("task_type", ""),
                    "worker_id": "mac-hub",
                    "status": "canceled",
                    "started_at": now,
                    "finished_at": now,
                    "source_hashes": local.get("manifest", []),
                    "outputs": [],
                    "error": "任务在领取前由 Mac 取消",
                }
                with self._lock:
                    source.unlink(missing_ok=True)
                    _write_json(bridge_root / "failed" / f"{clean_task}.json", result)
                return _task_summary(result, location="failed", local=local)
        if summary["status"] == "running":
            _write_json(
                bridge_root / "processing" / f"{clean_task}.cancel",
                {"task_id": clean_task, "requested_at": _now()},
            )
            return {**summary, "cancel_requested": True}
        raise RemoteNodeError("只有等待领取或执行中的任务可以取消")

    def _required_node(self, node_id: str) -> dict[str, Any]:
        clean_id = _safe_id(node_id, "node_id")
        node = next((item for item in self.list_nodes() if item["node_id"] == clean_id), None)
        if node is None:
            raise RemoteNodeError("设备尚未登记")
        return node

    def _ready_bridge(self, node_id: str) -> Path:
        diagnostic = self.diagnostics(node_id)
        if diagnostic["state"] != "ready":
            raise RemoteNodeError("共享目录尚未就绪，不能投递任务")
        return Path(str(diagnostic["bridge_root"]))

    def _task_record_path(self, node_id: str, task_id: str) -> Path:
        clean_node = _safe_id(node_id, "node_id")
        clean_task = _safe_id(task_id, "task_id")
        return self.task_records_root / clean_node / f"{clean_task}.json"

    def _local_task_records(self, node_id: str) -> dict[str, dict[str, Any]]:
        directory = self.task_records_root / _safe_id(node_id, "node_id")
        if not directory.is_dir():
            return {}
        records = {}
        for path in directory.glob("*.json"):
            payload = _read_json(path, {})
            task_id = str(payload.get("task_id", path.stem))
            if SAFE_ID_RE.fullmatch(task_id):
                records[task_id] = payload
        return records

    def submit_lora_catalog_snapshot(self, node_id: str) -> dict[str, Any]:
        diagnostic = self.diagnostics(node_id)
        worker_status = diagnostic.get("worker_status", {})
        if not isinstance(worker_status, dict):
            worker_status = {}
        capabilities = worker_status.get("capabilities", [])
        if not isinstance(capabilities, list) or "lora_catalog_snapshot" not in capabilities:
            raise RemoteNodeError("Windows Worker 尚未启用 LoRA 清单能力，请先更新并自检")
        raw_roots = worker_status.get("lora_roots", [])
        root_ids = [
            str(item.get("root_id", ""))
            for item in raw_roots
            if isinstance(item, dict)
            and item.get("exists") is True
            and _present(item.get("root_id"))
        ]
        if not root_ids:
            raise RemoteNodeError("Windows Worker 没有可用的 LoRA 根目录")
        return self.submit_task(
            node_id,
            {
                "task_type": "lora_catalog_snapshot",
                "payload": {
                    "source_manager": "ComfyUI LoRA Manager + LoraLoader",
                    "lora_roots": root_ids,
                },
                "manifest": [],
                "priority": 10,
            },
        )

    def import_returned_lora_catalog(self, node_id: str, task_id: str) -> dict[str, Any]:
        clean_task = _safe_id(task_id, "task_id")
        task = self.get_task(node_id, clean_task)
        if task["local_task"].get("task_type") != "lora_catalog_snapshot":
            raise RemoteNodeError("该任务不是 LoRA 清单快照")
        verified = self.verify_returned_task(node_id, clean_task)
        if not verified["verified"]:
            raise RemoteNodeError("LoRA 清单回传完整性校验失败")
        output = next(
            (item for item in verified["outputs"] if item.get("kind") == "lora_catalog"),
            None,
        )
        if output is None:
            raise RemoteNodeError("LoRA 清单任务没有 catalog 输出")
        bridge_root = self._ready_bridge(node_id)
        catalog = _read_required_json(bridge_root / str(output["relative_path"]))
        if catalog.get("format") != "soda-windows-lora-catalog-v1":
            raise RemoteNodeError("LoRA catalog format 不匹配")
        result_path = bridge_root / "inbox" / f"{clean_task}.json"
        result = _read_required_json(result_path)
        if catalog.get("worker_id") != result.get("worker_id"):
            raise RemoteNodeError("LoRA catalog worker_id 与任务回传不匹配")
        items = catalog.get("items")
        if not isinstance(items, list):
            raise RemoteNodeError("LoRA catalog items 不是列表")
        catalog_items = [item for item in items if isinstance(item, dict)]
        preview_outputs = [
            item for item in verified["outputs"] if item.get("kind") == "lora_preview"
        ]
        preview_files = self._import_lora_previews(
            snapshot_id=str(catalog.get("snapshot_id", "")),
            items=catalog_items,
            outputs=preview_outputs,
            bridge_root=bridge_root,
        )
        for item in catalog_items:
            item["preview_files"] = preview_files.get(str(item.get("lora_id", "")), [])
        imported = self.import_lora_catalog(
            snapshot_id=str(catalog.get("snapshot_id", "")),
            worker_id=str(catalog.get("worker_id", "")),
            source_manager=str(catalog.get("source_manager", "")),
            items=catalog_items,
        )
        return {**imported, "task_id": clean_task, "integrity_verified": True}

    def _import_lora_previews(
        self,
        *,
        snapshot_id: str,
        items: list[dict[str, Any]],
        outputs: list[dict[str, Any]],
        bridge_root: Path,
    ) -> dict[str, list[dict[str, Any]]]:
        clean_snapshot = _safe_id(snapshot_id, "snapshot_id")
        if len(outputs) > MAX_LORA_PREVIEW_COUNT:
            raise RemoteNodeError("LoRA 预览图数量超过安全上限")
        total_bytes = sum(int(item.get("size_bytes", 0)) for item in outputs)
        if total_bytes > MAX_LORA_PREVIEW_TOTAL_BYTES:
            raise RemoteNodeError("LoRA 预览图总容量超过安全上限")
        known_ids = {_safe_id(str(item.get("lora_id", "")), "lora_id") for item in items}
        grouped: dict[str, list[dict[str, Any]]] = {}
        ordered = sorted(
            outputs,
            key=lambda item: (str(item.get("lora_id", "")), int(item.get("preview_index", 0))),
        )
        for output in ordered:
            lora_id = _safe_id(str(output.get("lora_id", "")), "lora_id")
            if lora_id not in known_ids:
                raise RemoteNodeError("LoRA 预览图引用了清单外的 lora_id")
            size = int(output.get("size_bytes", 0))
            if not 0 < size <= MAX_LORA_PREVIEW_BYTES:
                raise RemoteNodeError("LoRA 预览图大小超过安全上限")
            source = bridge_root / Path(*PurePosixPath(str(output["relative_path"])).parts)
            suffix = source.suffix.casefold()
            if suffix not in LORA_PREVIEW_SUFFIXES:
                raise RemoteNodeError("LoRA 预览图扩展名不受支持")
            filename = f"{int(output.get('preview_index', 0)):03d}{suffix}"
            target = self.preview_root / clean_snapshot / lora_id / filename
            _copy_verified_file(source, target, str(output["sha256"]))
            grouped.setdefault(lora_id, []).append(
                {
                    "filename": filename,
                    "sha256": str(output["sha256"]),
                    "size_bytes": size,
                    "media_type": str(output.get("media_type", "")),
                    "source_relative_path": str(output.get("source_relative_path", "")),
                }
            )
        return grouped

    def import_lora_catalog(
        self,
        *,
        snapshot_id: str,
        worker_id: str,
        source_manager: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        clean_snapshot = _safe_id(snapshot_id, "snapshot_id")
        clean_worker = _safe_id(worker_id, "worker_id")
        prepared = [_normalize_lora_item(item) for item in items]
        if not prepared:
            raise RemoteNodeError("LoRA 清单不能为空")
        payload = {
            "format": "soda-windows-lora-catalog-v1",
            "snapshot_id": clean_snapshot,
            "worker_id": clean_worker,
            "source_manager": source_manager.strip()[:200],
            "created_at": _now(),
            "items": prepared,
        }
        snapshot_path = self.catalog_root / f"{clean_snapshot}.json"
        with self._lock:
            if snapshot_path.exists():
                existing = _read_json(snapshot_path, {})
                comparable_existing = {**existing, "created_at": ""}
                comparable_payload = {**payload, "created_at": ""}
                if comparable_existing != comparable_payload:
                    raise RemoteNodeError("同名 LoRA snapshot 已存在且内容不同")
                payload = existing
            else:
                _write_json(snapshot_path, payload)
            _write_json(
                self.catalog_root / "current.json",
                {"snapshot_id": clean_snapshot, "updated_at": _now()},
            )
        return {
            "snapshot_id": clean_snapshot,
            "worker_id": clean_worker,
            "source_manager": payload["source_manager"],
            "count": len(prepared),
            "metadata_only": True,
            "preview_count": sum(len(item.get("preview_files", [])) for item in prepared),
            "with_preview_count": sum(bool(item.get("preview_files")) for item in prepared),
            "with_source_count": sum(bool(_catalog_source_url(item)) for item in prepared),
        }

    def lora_catalog_status(self) -> dict[str, Any]:
        current = _read_json(self.catalog_root / "current.json", {})
        snapshot_id = str(current.get("snapshot_id", ""))
        if not snapshot_id:
            return {
                "available": False,
                "count": 0,
                "snapshot_id": "",
                "metadata_only": True,
                "with_source_count": 0,
            }
        snapshot = _read_json(self.catalog_root / f"{snapshot_id}.json", {})
        items = snapshot.get("items", [])
        prepared_items = items if isinstance(items, list) else []
        return {
            "available": True,
            "count": len(prepared_items),
            "snapshot_id": snapshot_id,
            "worker_id": snapshot.get("worker_id", ""),
            "source_manager": snapshot.get("source_manager", ""),
            "created_at": snapshot.get("created_at", ""),
            "metadata_only": True,
            "preview_count": sum(len(item.get("preview_files", [])) for item in prepared_items),
            "with_preview_count": sum(bool(item.get("preview_files")) for item in prepared_items),
            "with_source_count": sum(bool(_catalog_source_url(item)) for item in prepared_items),
        }

    def search_loras(self, query: str = "", *, limit: int = 100) -> list[dict[str, Any]]:
        status = self.lora_catalog_status()
        if not status["available"]:
            return []
        snapshot = _read_json(self.catalog_root / f"{status['snapshot_id']}.json", {})
        items = snapshot.get("items", [])
        needle = query.strip().casefold()
        matched = []
        for item in items if isinstance(items, list) else []:
            metadata = item.get("metadata", {})
            metadata = metadata if isinstance(metadata, dict) else {}
            search_text = " ".join(
                str(value)
                for value in (
                    item.get("name", ""),
                    item.get("base_model", ""),
                    item.get("model_family", ""),
                    " ".join(item.get("trigger_words", [])),
                    " ".join(item.get("tags", [])),
                    item.get("source_url", ""),
                    metadata.get("civitai_model_id", ""),
                    metadata.get("civitai_version_id", ""),
                )
            ).casefold()
            if not needle or needle in search_text:
                result = dict(item)
                result["source_url"] = _catalog_source_url(item)
                preview_files = item.get("preview_files", [])
                if not isinstance(preview_files, list):
                    preview_files = []
                result["preview_urls"] = [
                    "/api/windows-loras/previews/"
                    f"{status['snapshot_id']}/{item.get('lora_id', '')}/"
                    f"{preview.get('filename', '')}"
                    for preview in preview_files
                    if isinstance(preview, dict) and preview.get("filename")
                ]
                result["preview_count"] = len(result["preview_urls"])
                matched.append(result)
            if len(matched) >= max(1, min(limit, 500)):
                break
        return matched

    def get_lora(self, lora_id: str) -> dict[str, Any]:
        clean_id = _safe_id(lora_id, "lora_id")
        status = self.lora_catalog_status()
        if not status["available"]:
            raise RemoteNodeError("Windows LoRA 清单尚未同步")
        snapshot = _read_json(self.catalog_root / f"{status['snapshot_id']}.json", {})
        items = snapshot.get("items", [])
        item = next(
            (
                value
                for value in items
                if isinstance(items, list)
                and isinstance(value, dict)
                and value.get("lora_id") == clean_id
            ),
            None,
        )
        if item is None:
            raise RemoteNodeError("Windows LoRA 不存在或清单已更新")
        result = dict(item)
        result["source_url"] = _catalog_source_url(item)
        return result

    def submit_model_catalog_snapshot(self, node_id: str) -> dict[str, Any]:
        diagnostic = self.diagnostics(node_id)
        worker_status = diagnostic.get("worker_status", {})
        if not isinstance(worker_status, dict):
            worker_status = {}
        capabilities = worker_status.get("capabilities", [])
        if not isinstance(capabilities, list) or "model_catalog_snapshot" not in capabilities:
            raise RemoteNodeError("Windows Worker 尚未启用模型清单能力，请先更新并自检")
        raw_roots = worker_status.get("model_roots", [])
        root_ids = [
            str(item.get("root_id", ""))
            for item in raw_roots
            if isinstance(item, dict)
            and item.get("exists") is True
            and _present(item.get("root_id"))
        ]
        if not root_ids:
            raise RemoteNodeError("Windows Worker 没有可用的模型根目录")
        return self.submit_task(
            node_id,
            {
                "task_type": "model_catalog_snapshot",
                "payload": {
                    "source_manager": "ComfyUI model folders",
                    "model_roots": root_ids,
                },
                "manifest": [],
                "priority": 10,
            },
        )

    def import_returned_model_catalog(self, node_id: str, task_id: str) -> dict[str, Any]:
        clean_task = _safe_id(task_id, "task_id")
        task = self.get_task(node_id, clean_task)
        if task["local_task"].get("task_type") != "model_catalog_snapshot":
            raise RemoteNodeError("该任务不是模型清单快照")
        verified = self.verify_returned_task(node_id, clean_task)
        if not verified["verified"]:
            raise RemoteNodeError("模型清单回传完整性校验失败")
        output = next(
            (item for item in verified["outputs"] if item.get("kind") == "model_catalog"),
            None,
        )
        if output is None:
            raise RemoteNodeError("模型清单任务没有 catalog 输出")
        bridge_root = self._ready_bridge(node_id)
        catalog = _read_required_json(bridge_root / str(output["relative_path"]))
        if catalog.get("format") != "soda-windows-model-catalog-v1":
            raise RemoteNodeError("模型 catalog format 不匹配")
        result = _read_required_json(bridge_root / "inbox" / f"{clean_task}.json")
        if catalog.get("worker_id") != result.get("worker_id"):
            raise RemoteNodeError("模型 catalog worker_id 与任务回传不匹配")
        items = catalog.get("items")
        if not isinstance(items, list):
            raise RemoteNodeError("模型 catalog items 不是列表")
        catalog_items = [item for item in items if isinstance(item, dict)]
        preview_outputs = [
            item for item in verified["outputs"] if item.get("kind") == "model_preview"
        ]
        preview_files = self._import_model_previews(
            snapshot_id=str(catalog.get("snapshot_id", "")),
            items=catalog_items,
            outputs=preview_outputs,
            bridge_root=bridge_root,
        )
        for item in catalog_items:
            item["preview_files"] = preview_files.get(str(item.get("asset_id", "")), [])
        imported = self.import_model_catalog(
            snapshot_id=str(catalog.get("snapshot_id", "")),
            worker_id=str(catalog.get("worker_id", "")),
            source_manager=str(catalog.get("source_manager", "")),
            items=catalog_items,
        )
        return {**imported, "task_id": clean_task, "integrity_verified": True}

    def _import_model_previews(
        self,
        *,
        snapshot_id: str,
        items: list[dict[str, Any]],
        outputs: list[dict[str, Any]],
        bridge_root: Path,
    ) -> dict[str, list[dict[str, Any]]]:
        clean_snapshot = _safe_id(snapshot_id, "snapshot_id")
        if len(outputs) > MAX_LORA_PREVIEW_COUNT:
            raise RemoteNodeError("模型预览图数量超过安全上限")
        total_bytes = sum(int(item.get("size_bytes", 0)) for item in outputs)
        if total_bytes > MAX_LORA_PREVIEW_TOTAL_BYTES:
            raise RemoteNodeError("模型预览图总容量超过安全上限")
        known_ids = {_safe_id(str(item.get("asset_id", "")), "asset_id") for item in items}
        grouped: dict[str, list[dict[str, Any]]] = {}
        ordered = sorted(
            outputs,
            key=lambda item: (str(item.get("asset_id", "")), int(item.get("preview_index", 0))),
        )
        for output in ordered:
            asset_id = _safe_id(str(output.get("asset_id", "")), "asset_id")
            if asset_id not in known_ids:
                raise RemoteNodeError("模型预览图引用了清单外的 asset_id")
            size = int(output.get("size_bytes", 0))
            if not 0 < size <= MAX_LORA_PREVIEW_BYTES:
                raise RemoteNodeError("模型预览图大小超过安全上限")
            source = bridge_root / Path(*PurePosixPath(str(output["relative_path"])).parts)
            suffix = source.suffix.casefold()
            if suffix not in LORA_PREVIEW_SUFFIXES:
                raise RemoteNodeError("模型预览图扩展名不受支持")
            filename = f"{int(output.get('preview_index', 0)):03d}{suffix}"
            target = self.model_preview_root / clean_snapshot / asset_id / filename
            _copy_verified_file(source, target, str(output["sha256"]))
            grouped.setdefault(asset_id, []).append(
                {
                    "filename": filename,
                    "sha256": str(output["sha256"]),
                    "size_bytes": size,
                    "media_type": str(output.get("media_type", "")),
                    "source_relative_path": str(output.get("source_relative_path", "")),
                }
            )
        return grouped

    def import_model_catalog(
        self,
        *,
        snapshot_id: str,
        worker_id: str,
        source_manager: str,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        clean_snapshot = _safe_id(snapshot_id, "snapshot_id")
        clean_worker = _safe_id(worker_id, "worker_id")
        prepared = [_normalize_model_item(item) for item in items]
        if not prepared:
            raise RemoteNodeError("模型清单不能为空")
        payload = {
            "format": "soda-windows-model-catalog-v1",
            "snapshot_id": clean_snapshot,
            "worker_id": clean_worker,
            "source_manager": source_manager.strip()[:200],
            "created_at": _now(),
            "items": prepared,
        }
        snapshot_path = self.model_catalog_root / f"{clean_snapshot}.json"
        with self._lock:
            if snapshot_path.exists():
                existing = _read_json(snapshot_path, {})
                comparable_existing = {**existing, "created_at": ""}
                comparable_payload = {**payload, "created_at": ""}
                if comparable_existing != comparable_payload:
                    raise RemoteNodeError("同名模型 snapshot 已存在且内容不同")
                payload = existing
            else:
                _write_json(snapshot_path, payload)
            _write_json(
                self.model_catalog_root / "current.json",
                {"snapshot_id": clean_snapshot, "updated_at": _now()},
            )
        return {
            "snapshot_id": clean_snapshot,
            "worker_id": clean_worker,
            "source_manager": payload["source_manager"],
            "count": len(prepared),
            "type_counts": _model_type_counts(prepared),
            "preview_count": sum(len(item.get("preview_files", [])) for item in prepared),
            "with_preview_count": sum(bool(item.get("preview_files")) for item in prepared),
            "with_source_count": sum(bool(_catalog_source_url(item)) for item in prepared),
            "metadata_only": True,
            "weights_read": False,
        }

    def model_catalog_status(self) -> dict[str, Any]:
        current = _read_json(self.model_catalog_root / "current.json", {})
        snapshot_id = str(current.get("snapshot_id", ""))
        if not snapshot_id:
            return {
                "available": False,
                "count": 0,
                "snapshot_id": "",
                "type_counts": {},
                "preview_count": 0,
                "with_preview_count": 0,
                "with_source_count": 0,
                "metadata_only": True,
                "weights_read": False,
            }
        snapshot = _read_json(self.model_catalog_root / f"{snapshot_id}.json", {})
        items = snapshot.get("items", [])
        prepared = items if isinstance(items, list) else []
        return {
            "available": True,
            "count": len(prepared),
            "snapshot_id": snapshot_id,
            "worker_id": snapshot.get("worker_id", ""),
            "source_manager": snapshot.get("source_manager", ""),
            "created_at": snapshot.get("created_at", ""),
            "type_counts": _model_type_counts(prepared),
            "preview_count": sum(len(item.get("preview_files", [])) for item in prepared),
            "with_preview_count": sum(bool(item.get("preview_files")) for item in prepared),
            "with_source_count": sum(bool(_catalog_source_url(item)) for item in prepared),
            "metadata_only": True,
            "weights_read": False,
        }

    def search_models(
        self,
        query: str = "",
        *,
        asset_type: str = "",
        model_family: str = "",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        status = self.model_catalog_status()
        if not status["available"]:
            return []
        if asset_type and asset_type not in MODEL_ASSET_TYPES:
            raise RemoteNodeError("模型类型无效")
        snapshot = _read_json(self.model_catalog_root / f"{status['snapshot_id']}.json", {})
        items = snapshot.get("items", [])
        needle = query.strip().casefold()
        family = model_family.strip().casefold()
        matched = []
        for item in items if isinstance(items, list) else []:
            if asset_type and item.get("asset_type") != asset_type:
                continue
            if family and str(item.get("model_family", "")).casefold() != family:
                continue
            metadata = item.get("metadata", {})
            metadata = metadata if isinstance(metadata, dict) else {}
            search_text = " ".join(
                str(value)
                for value in (
                    *(
                        item.get(key, "")
                        for key in (
                            "name",
                            "relative_path",
                            "root_id",
                            "asset_type",
                            "model_family",
                            "source_url",
                        )
                    ),
                    metadata.get("civitai_model_id", ""),
                    metadata.get("civitai_version_id", ""),
                )
            ).casefold()
            if not needle or needle in search_text:
                result = dict(item)
                result["source_url"] = _catalog_source_url(item)
                preview_files = item.get("preview_files", [])
                if not isinstance(preview_files, list):
                    preview_files = []
                result["preview_urls"] = [
                    "/api/windows-models/previews/"
                    f"{status['snapshot_id']}/{item.get('asset_id', '')}/"
                    f"{preview.get('filename', '')}"
                    for preview in preview_files
                    if isinstance(preview, dict) and preview.get("filename")
                ]
                result["preview_count"] = len(result["preview_urls"])
                matched.append(result)
            if len(matched) >= max(1, min(limit, 2000)):
                break
        return matched

    def get_model(self, asset_id: str) -> dict[str, Any]:
        clean_id = _safe_id(asset_id, "asset_id")
        status = self.model_catalog_status()
        if not status["available"]:
            raise RemoteNodeError("Windows 模型清单尚未同步")
        snapshot = _read_json(self.model_catalog_root / f"{status['snapshot_id']}.json", {})
        items = snapshot.get("items", [])
        item = next(
            (
                value
                for value in items
                if isinstance(items, list)
                and isinstance(value, dict)
                and value.get("asset_id") == clean_id
            ),
            None,
        )
        if item is None:
            raise RemoteNodeError("Windows 模型不存在或清单已更新")
        result = dict(item)
        result["source_url"] = _catalog_source_url(item)
        return result

    def resolve_lora_preview(
        self,
        snapshot_id: str,
        lora_id: str,
        filename: str,
    ) -> tuple[Path, str]:
        clean_snapshot = _safe_id(snapshot_id, "snapshot_id")
        clean_lora = _safe_id(lora_id, "lora_id")
        clean_filename = _safe_id(filename, "filename")
        snapshot = _read_json(self.catalog_root / f"{clean_snapshot}.json", {})
        items = snapshot.get("items", [])
        item = next(
            (
                value
                for value in items
                if isinstance(items, list) and isinstance(value, dict)
                if value.get("lora_id") == clean_lora
            ),
            None,
        )
        if item is None:
            raise RemoteNodeError("LoRA 预览图不存在")
        previews = item.get("preview_files", [])
        preview = next(
            (
                value
                for value in previews
                if isinstance(previews, list) and isinstance(value, dict)
                if value.get("filename") == clean_filename
            ),
            None,
        )
        if preview is None:
            raise RemoteNodeError("LoRA 预览图不存在")
        path = (self.preview_root / clean_snapshot / clean_lora / clean_filename).resolve()
        try:
            path.relative_to(self.preview_root.resolve())
        except ValueError as error:
            raise RemoteNodeError("LoRA 预览图路径无效") from error
        if not path.is_file() or _sha256(path) != preview.get("sha256"):
            raise RemoteNodeError("LoRA 预览图文件缺失或校验失败")
        return path, _lora_preview_media_type(path)

    def resolve_model_preview(
        self,
        snapshot_id: str,
        asset_id: str,
        filename: str,
    ) -> tuple[Path, str]:
        clean_snapshot = _safe_id(snapshot_id, "snapshot_id")
        clean_asset = _safe_id(asset_id, "asset_id")
        clean_filename = _safe_id(filename, "filename")
        snapshot = _read_json(self.model_catalog_root / f"{clean_snapshot}.json", {})
        items = snapshot.get("items", [])
        item = next(
            (
                value
                for value in items
                if isinstance(items, list) and isinstance(value, dict)
                if value.get("asset_id") == clean_asset
            ),
            None,
        )
        if item is None:
            raise RemoteNodeError("模型预览图不存在")
        previews = item.get("preview_files", [])
        preview = next(
            (
                value
                for value in previews
                if isinstance(previews, list) and isinstance(value, dict)
                if value.get("filename") == clean_filename
            ),
            None,
        )
        if preview is None:
            raise RemoteNodeError("模型预览图不存在")
        path = (self.model_preview_root / clean_snapshot / clean_asset / clean_filename).resolve()
        try:
            path.relative_to(self.model_preview_root.resolve())
        except ValueError as error:
            raise RemoteNodeError("模型预览图路径无效") from error
        if not path.is_file() or _sha256(path) != preview.get("sha256"):
            raise RemoteNodeError("模型预览图文件缺失或校验失败")
        return path, _lora_preview_media_type(path)


def _normalize_task_manifest(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise RemoteNodeError("任务 manifest 必须是列表")
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise RemoteNodeError("任务 manifest 条目无效")
        relative = PurePosixPath(str(item.get("relative_path", "")))
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise RemoteNodeError("任务 manifest relative_path 无效")
        digest = str(item.get("sha256", "")).strip().lower()
        if not SHA256_RE.fullmatch(digest):
            raise RemoteNodeError("任务 manifest SHA-256 无效")
        result.append(
            {
                "relative_path": relative.as_posix(),
                "sha256": digest,
                "size_bytes": max(0, int(item.get("size_bytes", 0))),
            }
        )
    return result


def _verify_result_output(
    bridge_root: Path,
    task_id: str,
    value: object,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RemoteNodeError("结果 output 条目无效")
    relative = PurePosixPath(str(value.get("relative_path", "")))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise RemoteNodeError("结果 output relative_path 无效")
    expected_prefix = PurePosixPath("inbox") / task_id
    if relative.parts[: len(expected_prefix.parts)] != expected_prefix.parts:
        raise RemoteNodeError("结果 output 不属于该任务 inbox 目录")
    root_resolved = bridge_root.resolve()
    path = (root_resolved / Path(*relative.parts)).resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError as error:
        raise RemoteNodeError("结果 output 越过共享目录") from error
    if not path.is_file():
        raise RemoteNodeError(f"结果文件不存在: {relative.as_posix()}")
    expected_hash = str(value.get("sha256", "")).strip().lower()
    if not SHA256_RE.fullmatch(expected_hash):
        raise RemoteNodeError(f"结果 SHA-256 无效: {relative.as_posix()}")
    actual_hash = _sha256(path)
    if actual_hash != expected_hash:
        raise RemoteNodeError(f"结果 SHA-256 不匹配: {relative.as_posix()}")
    actual_size = path.stat().st_size
    expected_size = int(value.get("size_bytes", 0) or 0)
    if expected_size != actual_size:
        raise RemoteNodeError(f"结果文件大小不匹配: {relative.as_posix()}")
    kind = str(value.get("kind", ""))
    result = {
        "kind": kind,
        "relative_path": relative.as_posix(),
        "sha256": actual_hash,
        "size_bytes": actual_size,
    }
    if kind in {"lora_preview", "model_preview"}:
        if actual_size > MAX_LORA_PREVIEW_BYTES:
            raise RemoteNodeError(f"预览图超过安全上限: {relative.as_posix()}")
        preview_fields = {
            "preview_index": max(0, min(int(value.get("preview_index", 0)), 9999)),
            "source_relative_path": _safe_relative_value(
                str(value.get("source_relative_path", "")),
                "preview source_relative_path",
            ),
            "media_type": _lora_preview_media_type(path),
        }
        if kind == "model_preview":
            preview_fields["asset_id"] = _safe_id(
                str(value.get("asset_id", "")),
                "asset_id",
            )
        else:
            preview_fields["lora_id"] = _safe_id(
                str(value.get("lora_id", "")),
                "lora_id",
            )
        result.update(preview_fields)
    return result


def _copy_verified_file(source: Path, target: Path, expected_hash: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        if _sha256(target) != expected_hash:
            raise RemoteNodeError("同名预览缓存已存在且内容不同")
        return
    temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
    try:
        shutil.copyfile(source, temporary)
        if _sha256(temporary) != expected_hash:
            raise RemoteNodeError("预览图复制后 SHA-256 不匹配")
        temporary.replace(target)
    finally:
        with suppress(FileNotFoundError):
            temporary.unlink()


def _lora_preview_media_type(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix not in LORA_PREVIEW_SUFFIXES:
        raise RemoteNodeError("LoRA 预览图扩展名不受支持")
    try:
        with path.open("rb") as handle:
            header = handle.read(16)
    except OSError as error:
        raise RemoteNodeError("无法读取 LoRA 预览图") from error
    if suffix == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if suffix in {".jpg", ".jpeg"} and header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if suffix == ".webp" and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    if suffix == ".gif" and header[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    raise RemoteNodeError("LoRA 预览图内容与扩展名不匹配")


def _safe_relative_value(value: str, label: str) -> str:
    relative = PurePosixPath(value.strip().replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise RemoteNodeError(f"{label} 无效")
    return relative.as_posix()


def _reject_task_credentials(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().casefold().replace("-", "_")
            if normalized in SENSITIVE_TASK_KEYS:
                raise RemoteNodeError("任务 payload 不允许包含密码、token 或其他凭据")
            _reject_task_credentials(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_task_credentials(nested)


def _task_summary(
    envelope: dict[str, Any],
    *,
    location: str,
    local: dict[str, Any],
) -> dict[str, Any]:
    merged = {**local, **envelope}
    result_status = str(envelope.get("status", ""))
    status = TASK_LOCATION_STATUS.get(location, "recorded")
    if location == "failed" and result_status == "canceled":
        status = "canceled"
    return {
        "task_id": str(merged.get("task_id", "")),
        "task_type": str(merged.get("task_type", "")),
        "target_role": str(merged.get("target_role", "")),
        "status": status,
        "result_status": result_status,
        "location": location,
        "attempt": int(local.get("attempt", merged.get("attempt", 1)) or 1),
        "retry_of": str(local.get("retry_of", merged.get("retry_of", ""))),
        "project_id": str(local.get("project_id", merged.get("project_id", ""))),
        "workspace_id": str(local.get("workspace_id", merged.get("workspace_id", ""))),
        "run_id": str(local.get("run_id", merged.get("run_id", ""))),
        "worker_id": str(envelope.get("worker_id", "")),
        "created_at": str(local.get("created_at", merged.get("created_at", ""))),
        "started_at": str(envelope.get("started_at", "")),
        "finished_at": str(envelope.get("finished_at", "")),
        "updated_at": str(
            envelope.get("finished_at")
            or envelope.get("started_at")
            or local.get("created_at")
            or merged.get("created_at", "")
        ),
        "error": str(envelope.get("error", ""))[:2000],
    }


def _present(value: object) -> bool:
    return value is not None and value not in ("", [], {})


def _optional_safe_id(value: str, label: str) -> str:
    return _safe_id(value, label) if value.strip() else ""


def _positive_civitai_id(value: object) -> int | None:
    text = str(value).strip() if isinstance(value, (str, int, float)) else ""
    if not text.isdigit():
        return None
    parsed = int(text)
    return parsed if parsed > 0 else None


def _metadata_civitai_ids(metadata: object) -> tuple[int | None, int | None]:
    if not isinstance(metadata, dict):
        return None, None
    model_id = _positive_civitai_id(metadata.get("civitai_model_id", metadata.get("modelId")))
    version_id = _positive_civitai_id(
        metadata.get("civitai_version_id", metadata.get("modelVersionId"))
    )
    return model_id, version_id


def _safe_civitai_source_url(value: object, metadata: object) -> str:
    model_id, version_id = _metadata_civitai_ids(metadata)
    if isinstance(value, str) and len(value) <= MAX_CIVITAI_URL_LENGTH:
        with suppress(ValueError):
            parsed = urllib.parse.urlsplit(value.strip())
            host = (parsed.hostname or "").casefold()
            matched = CIVITAI_MODEL_PATH_RE.fullmatch(parsed.path)
            if parsed.scheme in {"http", "https"} and host in CIVITAI_HOSTS and matched:
                source_model_id = int(matched.group("model_id"))
                query = urllib.parse.parse_qs(parsed.query)
                source_version_id = _positive_civitai_id((query.get("modelVersionId") or [""])[0])
                chosen_version = source_version_id or version_id
                base = f"https://{host}/models/{source_model_id}"
                return f"{base}?modelVersionId={chosen_version}" if chosen_version else base
    if model_id is None:
        return ""
    base = f"https://civitai.com/models/{model_id}"
    return f"{base}?modelVersionId={version_id}" if version_id else base


def _catalog_source_url(item: object) -> str:
    if not isinstance(item, dict):
        return ""
    return _safe_civitai_source_url(
        item.get("source_url", ""),
        item.get("metadata", {}),
    )


def _new_task_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"task-{stamp}-{uuid4().hex[:12]}"


def _normalize_lora_item(item: dict[str, Any]) -> dict[str, Any]:
    lora_id = _safe_id(str(item.get("lora_id", "")), "lora_id")
    relative = PurePosixPath(str(item.get("relative_path", "")))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise RemoteNodeError("LoRA relative_path 无效")
    digest = str(item.get("sha256", "")).strip().lower()
    if digest and not SHA256_RE.fullmatch(digest):
        raise RemoteNodeError("LoRA SHA-256 无效")
    preview = str(item.get("preview_relative_path", "")).strip()
    if preview:
        preview_path = PurePosixPath(preview)
        if preview_path.is_absolute() or ".." in preview_path.parts:
            raise RemoteNodeError("LoRA preview_relative_path 无效")
    preview_relative_paths = _string_list(item.get("preview_relative_paths", []), 100)
    for value in preview_relative_paths:
        _safe_relative_value(value, "LoRA preview_relative_paths")
    preview_files = _normalize_lora_preview_files(item.get("preview_files", []))
    metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
    return {
        "lora_id": lora_id,
        "name": str(item.get("name", "")).strip()[:300] or relative.stem,
        "relative_path": relative.as_posix(),
        "sha256": digest,
        "size_bytes": max(0, int(item.get("size_bytes", 0))),
        "base_model": str(item.get("base_model", "")).strip()[:300],
        "model_family": str(item.get("model_family", "")).strip()[:160],
        "source_url": _safe_civitai_source_url(item.get("source_url", ""), metadata),
        "trigger_words": _string_list(item.get("trigger_words", []), 100),
        "tags": _string_list(item.get("tags", []), 300),
        "preview_relative_path": preview,
        "preview_relative_paths": preview_relative_paths,
        "preview_files": preview_files,
        "notes": str(item.get("notes", "")).strip()[:2000],
        "metadata": metadata,
    }


def _normalize_model_item(item: dict[str, Any]) -> dict[str, Any]:
    asset_id = _safe_id(str(item.get("asset_id", "")), "asset_id")
    asset_type = str(item.get("asset_type", "")).strip()
    if asset_type not in MODEL_ASSET_TYPES:
        raise RemoteNodeError("模型 asset_type 无效")
    root_id = _safe_id(str(item.get("root_id", "")), "root_id")
    relative_value = _safe_relative_value(
        str(item.get("relative_path", "")),
        "模型 relative_path",
    )
    relative = PurePosixPath(relative_value)
    preview = str(item.get("preview_relative_path", "")).strip()
    if preview:
        _safe_relative_value(preview, "模型 preview_relative_path")
    preview_relative_paths = _string_list(item.get("preview_relative_paths", []), 100)
    for value in preview_relative_paths:
        _safe_relative_value(value, "模型 preview_relative_paths")
    preview_files = _normalize_lora_preview_files(item.get("preview_files", []))
    metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
    return {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "root_id": root_id,
        "name": str(item.get("name", "")).strip()[:300] or relative.stem,
        "relative_path": relative.as_posix(),
        "size_bytes": max(0, int(item.get("size_bytes", 0))),
        "modified_at": str(item.get("modified_at", "")).strip()[:80],
        "model_family": str(item.get("model_family", "")).strip()[:160],
        "source_url": _safe_civitai_source_url(item.get("source_url", ""), metadata),
        "preview_relative_path": preview,
        "preview_relative_paths": preview_relative_paths,
        "preview_files": preview_files,
        "metadata": metadata,
    }


def _model_type_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        asset_type = str(item.get("asset_type", ""))
        if asset_type in MODEL_ASSET_TYPES:
            counts[asset_type] = counts.get(asset_type, 0) + 1
    return dict(sorted(counts.items()))


def _normalize_lora_preview_files(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:100]:
        if not isinstance(item, dict):
            continue
        filename = _safe_id(str(item.get("filename", "")), "preview filename")
        digest = str(item.get("sha256", "")).strip().lower()
        if not SHA256_RE.fullmatch(digest):
            raise RemoteNodeError("LoRA preview SHA-256 无效")
        source_relative = str(item.get("source_relative_path", ""))
        result.append(
            {
                "filename": filename,
                "sha256": digest,
                "size_bytes": max(0, int(item.get("size_bytes", 0))),
                "media_type": str(item.get("media_type", ""))[:100],
                "source_relative_path": _safe_relative_value(
                    source_relative,
                    "LoRA preview source_relative_path",
                ),
            }
        )
    return result


def _string_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip()[:300] for item in value[:limit] if str(item).strip()]


def _safe_id(value: str, label: str) -> str:
    clean = value.strip()
    if not SAFE_ID_RE.fullmatch(clean):
        raise RemoteNodeError(f"{label} 无效")
    return clean


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return fallback
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return fallback
    return payload if isinstance(payload, dict) else fallback


def _read_required_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise RemoteNodeError(f"无法读取回传 JSON：{path.name}") from error
    if not isinstance(payload, dict):
        raise RemoteNodeError(f"回传 JSON 必须是对象：{path.name}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{hashlib.sha256(os.urandom(16)).hexdigest()[:8]}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
