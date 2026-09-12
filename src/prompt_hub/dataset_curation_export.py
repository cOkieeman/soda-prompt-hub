from __future__ import annotations

import hashlib
import os
import re
import shutil
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from prompt_hub.dataset_curation_records import (
    CaptionProfile,
    _current_caption,
    _state_item,
)
from prompt_hub.dataset_curation_support import (
    _atomic_json_write,
    _directory_digest_map,
    _directory_stats,
    _inside_directory,
    _now,
    _safe_directory_name,
    _sha256,
    _source_result_asset_ids,
    _timestamp_token,
    _write_hash_manifest,
)
from prompt_hub.dataset_workspace import DatasetWorkspaceError
from prompt_hub.project_journey import read_project_lineage

if TYPE_CHECKING:
    from collections.abc import Iterable
    from threading import RLock

    from prompt_hub.config import Settings
    from prompt_hub.dataset_workspace import DatasetWorkspaceStore


def _duplicate_files(group: Mapping[str, Any]) -> list[str]:
    """一组重复里涉及的所有文件。

    完全重复是一个 files 列表。近似重复是两张比出来的 left_files / right_files。
    两种形状。读错的一边不会报错。只会永远得到空。
    """
    files = group.get("files")
    if isinstance(files, list):
        return [str(path) for path in files]
    left = group.get("left_files", [])
    right = group.get("right_files", [])
    return [str(path) for side in (left, right) if isinstance(side, list) for path in side]


class DatasetExportMixin:
    settings: Settings
    workspace_store: DatasetWorkspaceStore
    _lock: RLock

    def read_state(self, workspace_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def analytics(self, workspace_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def _write_state(self, workspace_id: str, state: dict[str, Any]) -> None:
        raise NotImplementedError

    def _require_workspace(self, workspace_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def _require_report(self, workspace_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def export_version(
        self,
        workspace_id: str,
        *,
        profile_id: CaptionProfile,
        paths: Iterable[str],
    ) -> dict[str, Any]:
        workspace = self._require_workspace(workspace_id)
        report = self._require_report(workspace_id)
        state = self.read_state(workspace_id)
        records = {
            str(item.get("relative_path", "")): item
            for item in report.get("images", [])
            if isinstance(item, dict)
        }
        selected = list(dict.fromkeys(str(path) for path in paths))
        preflight = self.preflight_export(
            workspace_id,
            profile_id=profile_id,
            paths=selected,
        )
        if not preflight["ready"]:
            reasons = "; ".join(str(item["label"]) for item in preflight["blockers"][:3])
            raise DatasetWorkspaceError(f"交付前检查未通过: {reasons}")
        prepared = []
        source_lineage = read_project_lineage(Path(str(workspace["source_path"])))
        lineage_items = source_lineage.get("items", {})
        if not isinstance(lineage_items, Mapping):
            lineage_items = {}
        for relative_path in selected:
            record = records[relative_path]
            item = _state_item(state, relative_path)
            caption = _current_caption(item, profile_id)
            digest = str(record.get("sha256", ""))
            caption_relative = str(Path(relative_path).with_suffix(".txt"))
            prepared.append((relative_path, caption_relative, digest, caption, record))

        version_id = f"{profile_id}-{_timestamp_token()}-{uuid4().hex[:8]}"
        export_root = self.settings.dataset_exports_root / "workspaces" / workspace_id
        version_root = export_root / version_id
        archive_path = export_root / f"{version_id}.zip"
        try:
            train_root = version_root / "train"
            train_root.mkdir(parents=True, exist_ok=False)
            manifest_items = []
            for relative_path, caption_relative, digest, caption, record in prepared:
                source_path = self.workspace_store.resolve_source_image(workspace_id, relative_path)
                if source_path is None or _sha256(source_path) != digest:
                    raise DatasetWorkspaceError(f"来源图片在扫描后发生变化: {relative_path}")
                target_image = _inside_directory(train_root, relative_path)
                target_caption = _inside_directory(train_root, caption_relative)
                target_image.parent.mkdir(parents=True, exist_ok=True)
                target_caption.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_image)
                target_caption.write_text(caption, encoding="utf-8")
                manifest_items.append(
                    {
                        "relative_path": relative_path,
                        "caption_path": caption_relative,
                        "sha256": digest,
                        "caption_sha256": hashlib.sha256(caption.encode()).hexdigest(),
                        "width": record.get("width", 0),
                        "height": record.get("height", 0),
                        "source": dict(lineage_items.get(relative_path, {}))
                        if isinstance(lineage_items.get(relative_path), Mapping)
                        else {},
                    }
                )
            audit = self._export_audit(workspace_id, selected, profile_id, preflight=preflight)
            manifest = {
                "format": "soda-prompt-hub-dataset-export-v3",
                "version_id": version_id,
                "workspace_id": workspace_id,
                "workspace_name": workspace.get("name", ""),
                "profile_id": profile_id,
                "caption_language": "en",
                "source_mode": "read-only",
                "origin": dict(workspace.get("origin", {}))
                if isinstance(workspace.get("origin"), Mapping)
                else {},
                "created_at": _now(),
                "items": manifest_items,
            }
            _atomic_json_write(version_root / "manifest.json", manifest)
            _atomic_json_write(version_root / "audit.json", audit)
            _write_hash_manifest(version_root)
            file_count, total_bytes = _directory_stats(version_root)
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(version_root.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(version_root).as_posix())
        except Exception as error:
            shutil.rmtree(version_root, ignore_errors=True)
            archive_path.unlink(missing_ok=True)
            if isinstance(error, DatasetWorkspaceError):
                raise
            raise DatasetWorkspaceError(f"冻结数据集失败, 未完成文件已清理: {error}") from error

        export = {
            "version_id": version_id,
            "profile_id": profile_id,
            "image_count": len(prepared),
            "directory": str(version_root),
            "archive_name": archive_path.name,
            "download_url": f"/dataset-workspaces/{workspace_id}/exports/{archive_path.name}",
            "created_at": manifest["created_at"],
            "file_count": file_count,
            "total_bytes": total_bytes,
            "archive_bytes": archive_path.stat().st_size,
            "hashes_sha256": _sha256(version_root / "hashes.sha256"),
            "origin": manifest["origin"],
            "source_result_asset_ids": _source_result_asset_ids(manifest_items),
            "copies": [],
        }
        state = self.read_state(workspace_id)
        raw_exports = state.get("exports", [])
        state["exports"] = [*raw_exports, export] if isinstance(raw_exports, list) else [export]
        self._write_state(workspace_id, state)
        return {**export, "manifest": manifest, "audit": audit}

    def preflight_export(
        self,
        workspace_id: str,
        *,
        profile_id: CaptionProfile,
        paths: Iterable[str],
    ) -> dict[str, Any]:
        report = self._require_report(workspace_id)
        review = self.workspace_store.read_review_state(workspace_id)
        state = self.read_state(workspace_id)
        records = {
            str(item.get("relative_path", "")): item
            for item in report.get("images", [])
            if isinstance(item, dict)
        }
        selected = list(dict.fromkeys(str(path) for path in paths if str(path)))
        blockers: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        def add_issue(
            target: list[dict[str, Any]],
            code: str,
            label: str,
            issue_paths: Iterable[str],
        ) -> None:
            clean_paths = sorted(dict.fromkeys(str(path) for path in issue_paths if str(path)))
            if clean_paths or code == "nothing_selected":
                target.append(
                    {
                        "code": code,
                        "label": label,
                        "count": len(clean_paths),
                        "paths": clean_paths,
                    }
                )

        if not selected:
            add_issue(blockers, "nothing_selected", "尚未选择要交付的图片", [])
        unknown = [path for path in selected if path not in records]
        add_issue(blockers, "unknown_image", "选择中含有扫描报告外的图片", unknown)
        known = [path for path in selected if path in records]
        invalid = [path for path in known if not records[path].get("valid")]
        add_issue(blockers, "invalid_image", "选择中含有坏图或无法解码的图片", invalid)
        source_changed = []
        for relative_path in known:
            source_path = self.workspace_store.resolve_source_image(workspace_id, relative_path)
            expected = str(records[relative_path].get("sha256", ""))
            if source_path is None or not expected or _sha256(source_path) != expected:
                source_changed.append(relative_path)
        add_issue(
            blockers,
            "source_changed",
            "来源图片在扫描后缺失或发生变化",
            source_changed,
        )
        not_approved = [path for path in known if review.get(path, {}).get("status") != "approved"]
        add_issue(blockers, "image_not_approved", "图片尚未审核为保留", not_approved)

        missing_caption: list[str] = []
        caption_not_reviewed: list[str] = []
        non_english: list[str] = []
        digest_paths: dict[str, list[str]] = {}
        caption_paths: dict[str, list[str]] = {}
        for relative_path in known:
            item = _state_item(state, relative_path)
            caption_record = item.get("captions", {}).get(profile_id, {})
            caption = _current_caption(item, profile_id)
            if not caption:
                missing_caption.append(relative_path)
            elif not caption.isascii():
                non_english.append(relative_path)
            if caption and (
                not isinstance(caption_record, dict) or caption_record.get("status") != "reviewed"
            ):
                caption_not_reviewed.append(relative_path)
            digest = str(records[relative_path].get("sha256", ""))
            if digest:
                digest_paths.setdefault(digest, []).append(relative_path)
            caption_relative = str(Path(relative_path).with_suffix(".txt"))
            caption_paths.setdefault(caption_relative.casefold(), []).append(relative_path)
        add_issue(
            blockers,
            "missing_caption",
            f"缺少 {profile_id.upper()} Caption",
            missing_caption,
        )
        add_issue(
            blockers,
            "caption_not_reviewed",
            f"{profile_id.upper()} Caption 尚未人工确认",
            caption_not_reviewed,
        )
        add_issue(blockers, "caption_not_english", "最终 Caption 必须使用英文", non_english)
        exact_paths = [
            path for grouped in digest_paths.values() if len(grouped) > 1 for path in grouped
        ]
        add_issue(blockers, "exact_duplicate", "选择中含有完全重复图片", exact_paths)
        collision_paths = [
            path for grouped in caption_paths.values() if len(grouped) > 1 for path in grouped
        ]
        add_issue(
            blockers,
            "caption_path_conflict",
            "不同图片会生成同名 .txt",
            collision_paths,
        )

        selected_set = set(known)
        near_paths = []
        for group in report.get("near_duplicates", []):
            if not isinstance(group, dict):
                continue
            # 近似重复是两边比出来的。没有 files 这个键。
            # 照 files 读不会报错。只会永远读到空。提醒就成了摆设。
            grouped = [str(path) for path in _duplicate_files(group)]
            selected_in_group = [path for path in grouped if path in selected_set]
            if len(set(selected_in_group)) > 1:
                near_paths.extend(selected_in_group)
        add_issue(warnings, "near_duplicate", "选择中有近似重复图片, 建议人工确认", near_paths)
        workspace_invalid = [
            path
            for path, record in records.items()
            if not record.get("valid") and path not in selected_set
        ]
        add_issue(
            warnings,
            "unselected_invalid_image",
            "工作区还有未选中的坏图, 不会进入本次交付",
            workspace_invalid,
        )
        return {
            "workspace_id": workspace_id,
            "profile_id": profile_id,
            "selected_count": len(selected),
            "ready": not blockers,
            "blockers": blockers,
            "warnings": warnings,
            "checked_at": _now(),
        }

    def list_exports(self, workspace_id: str) -> list[dict[str, Any]]:
        state = self.read_state(workspace_id)
        exports = state.get("exports", [])
        if not isinstance(exports, list):
            return []
        result = []
        for raw in reversed(exports):
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            version_id = str(item.get("version_id", ""))
            directory = self.resolve_export_directory(workspace_id, version_id)
            archive = self.resolve_export(workspace_id, str(item.get("archive_name", "")))
            if directory is not None:
                file_count, total_bytes = _directory_stats(directory)
                item.setdefault("file_count", file_count)
                item.setdefault("total_bytes", total_bytes)
            item.setdefault("archive_bytes", archive.stat().st_size if archive else 0)
            item.setdefault("copies", [])
            item["directory_available"] = directory is not None
            item["archive_available"] = archive is not None
            item["reveal_url"] = (
                f"/api/dataset-workspaces/{workspace_id}/exports/{version_id}/reveal"
            )
            result.append(item)
        return result

    def resolve_export_directory(self, workspace_id: str, version_id: str) -> Path | None:
        if not re.fullmatch(r"(?:anima|krea2)-[0-9A-Za-z-]+", version_id):
            return None
        state = self.read_state(workspace_id)
        known = {
            str(item.get("version_id", ""))
            for item in state.get("exports", [])
            if isinstance(item, dict)
        }
        if version_id not in known:
            return None
        root = (self.settings.dataset_exports_root / "workspaces" / workspace_id).resolve()
        path = (root / version_id).resolve()
        return path if path.is_relative_to(root) and path.is_dir() else None

    def copy_export_to_share(
        self,
        workspace_id: str,
        version_id: str,
        *,
        node_id: str,
        bridge_root: Path,
    ) -> dict[str, Any]:
        source = self.resolve_export_directory(workspace_id, version_id)
        if source is None:
            raise DatasetWorkspaceError("Dataset export version not found")
        workspace = self._require_workspace(workspace_id)
        root = bridge_root.resolve()
        if not root.is_dir() or not os.access(root, os.W_OK):
            raise DatasetWorkspaceError("Windows 共享目录离线或不可写")
        dataset_root = (
            root / "datasets" / _safe_directory_name(str(workspace.get("name", "")))
        ).resolve()
        if not dataset_root.is_relative_to(root):
            raise DatasetWorkspaceError("Invalid Windows dataset delivery path")
        dataset_root.mkdir(parents=True, exist_ok=True)
        target = (dataset_root / version_id).resolve()
        if not target.is_relative_to(dataset_root):
            raise DatasetWorkspaceError("Invalid Windows dataset version path")
        if target.exists():
            if target.is_dir() and _directory_digest_map(source) == _directory_digest_map(target):
                return self._record_export_copy(
                    workspace_id,
                    version_id,
                    node_id=node_id,
                    status="already_present",
                    target=target,
                )
            message = "Windows 设备上已有同名版本, 但文件哈希不同; 已停止且未覆盖"
            self._record_export_copy(
                workspace_id,
                version_id,
                node_id=node_id,
                status="failed",
                target=target,
                error=message,
            )
            raise DatasetWorkspaceError(message)

        temporary = dataset_root / f".{version_id}.copying-{uuid4().hex[:8]}"
        try:
            shutil.copytree(source, temporary)
            if _directory_digest_map(source) != _directory_digest_map(temporary):
                raise DatasetWorkspaceError("复制后的文件哈希与 Mac 版本不一致")
            temporary.replace(target)
        except Exception as error:
            shutil.rmtree(temporary, ignore_errors=True)
            self._record_export_copy(
                workspace_id,
                version_id,
                node_id=node_id,
                status="failed",
                target=target,
                error=str(error),
            )
            if isinstance(error, DatasetWorkspaceError):
                raise
            raise DatasetWorkspaceError(f"复制到 Windows 共享目录失败: {error}") from error
        return self._record_export_copy(
            workspace_id,
            version_id,
            node_id=node_id,
            status="completed",
            target=target,
        )

    def _record_export_copy(
        self,
        workspace_id: str,
        version_id: str,
        *,
        node_id: str,
        status: str,
        target: Path,
        error: str = "",
    ) -> dict[str, Any]:
        file_count, total_bytes = _directory_stats(target) if target.is_dir() else (0, 0)
        record = {
            "node_id": node_id,
            "status": status,
            "target_directory": str(target),
            "file_count": file_count,
            "total_bytes": total_bytes,
            "copied_at": _now(),
            "error": error[:2000],
        }
        with self._lock:
            state = self.read_state(workspace_id)
            exports = state.get("exports", [])
            if not isinstance(exports, list):
                raise DatasetWorkspaceError("Dataset export history is invalid")
            found = False
            for export in exports:
                if not isinstance(export, dict) or export.get("version_id") != version_id:
                    continue
                copies = export.get("copies", [])
                if not isinstance(copies, list):
                    copies = []
                export["copies"] = [
                    item
                    for item in copies
                    if not isinstance(item, dict) or item.get("node_id") != node_id
                ] + [record]
                found = True
                break
            if not found:
                raise DatasetWorkspaceError("Dataset export version not found")
            self._write_state(workspace_id, state)
        return {"workspace_id": workspace_id, "version_id": version_id, **record}

    def resolve_export(self, workspace_id: str, filename: str) -> Path | None:
        if Path(filename).name != filename or not filename.endswith(".zip"):
            return None
        state = self.read_state(workspace_id)
        known = {
            str(item.get("archive_name", ""))
            for item in state.get("exports", [])
            if isinstance(item, dict)
        }
        if filename not in known:
            return None
        root = (self.settings.dataset_exports_root / "workspaces" / workspace_id).resolve()
        path = (root / filename).resolve()
        return path if path.is_relative_to(root) and path.is_file() else None

    def _export_audit(
        self,
        workspace_id: str,
        paths: list[str],
        profile_id: CaptionProfile,
        *,
        preflight: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        report = self._require_report(workspace_id)
        analytics = self.analytics(workspace_id)
        return {
            "format": "soda-prompt-hub-dataset-audit-v1",
            "workspace_id": workspace_id,
            "profile_id": profile_id,
            "exported_images": len(paths),
            "scan_summary": report.get("summary", {}),
            "tag_frequency": analytics["frequencies"] if profile_id == "anima" else [],
            "conflicts": [
                item for item in analytics["conflicts"] if item["relative_path"] in set(paths)
            ],
            "checks": {
                "source_unchanged": True,
                "all_approved": True,
                "all_captions_english": True,
                "exact_duplicate_hashes": False,
            },
            "preflight": dict(preflight or {}),
            "created_at": _now(),
        }
