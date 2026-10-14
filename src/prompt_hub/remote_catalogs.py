from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from prompt_hub.remote_nodes_support import (
    LORA_PREVIEW_SUFFIXES,
    MAX_LORA_PREVIEW_BYTES,
    MAX_LORA_PREVIEW_COUNT,
    MAX_LORA_PREVIEW_TOTAL_BYTES,
    MODEL_ASSET_TYPES,
    RemoteNodeError,
    _catalog_source_url,
    _copy_verified_file,
    _lora_preview_media_type,
    _model_type_counts,
    _normalize_lora_item,
    _normalize_model_item,
    _now,
    _present,
    _read_json,
    _read_required_json,
    _safe_id,
    _sha256,
    _write_json,
)

if TYPE_CHECKING:
    from threading import Lock


class RemoteCatalogMixin:
    catalog_root: Path
    model_catalog_root: Path
    preview_root: Path
    model_preview_root: Path
    _lock: Lock

    def diagnostics(self, node_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def submit_task(self, node_id: str, values: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def get_task(self, node_id: str, task_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def verify_returned_task(self, node_id: str, task_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def mark_task_received(
        self,
        node_id: str,
        task_id: str,
        *,
        receipt_kind: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def _ready_bridge(self, node_id: str) -> Path:
        raise NotImplementedError

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
        receipt = self.mark_task_received(node_id, clean_task, receipt_kind="lora_catalog")
        return {
            **imported,
            "task_id": clean_task,
            "integrity_verified": True,
            "received_at": receipt["received_at"],
        }

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

    def search_loras(
        self, query: str = "", *, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        return self.search_lora_page(query, limit=limit, offset=offset)["results"]

    def search_lora_page(
        self, query: str = "", *, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        page = {
            "results": [],
            "count": 0,
            "total": 0,
            "offset": max(0, offset),
            "limit": max(1, min(limit, 500)),
            "snapshot_id": "",
        }
        status = self.lora_catalog_status()
        if not status["available"]:
            return page
        page["snapshot_id"] = status["snapshot_id"]
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
                page["total"] += 1
                if page["total"] <= page["offset"] or len(matched) >= page["limit"]:
                    continue
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
        return {**page, "results": matched, "count": len(matched)}

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
        receipt = self.mark_task_received(node_id, clean_task, receipt_kind="model_catalog")
        return {
            **imported,
            "task_id": clean_task,
            "integrity_verified": True,
            "received_at": receipt["received_at"],
        }

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
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self.search_model_page(
            query, asset_type=asset_type, model_family=model_family, limit=limit, offset=offset
        )["results"]

    def search_model_page(
        self,
        query: str = "",
        *,
        asset_type: str = "",
        model_family: str = "",
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        page = {
            "results": [],
            "count": 0,
            "total": 0,
            "offset": max(0, offset),
            "limit": max(1, min(limit, 2000)),
            "snapshot_id": "",
        }
        status = self.model_catalog_status()
        if not status["available"]:
            return page
        page["snapshot_id"] = status["snapshot_id"]
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
                page["total"] += 1
                if page["total"] <= page["offset"] or len(matched) >= page["limit"]:
                    continue
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
        return {**page, "results": matched, "count": len(matched)}

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
