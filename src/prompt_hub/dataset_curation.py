from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal, Protocol
from uuid import uuid4

from prompt_hub.dataset_tagging import DatasetTaggingError, normalize_tag_draft
from prompt_hub.dataset_workspace import DatasetWorkspaceError, DatasetWorkspaceStore
from prompt_hub.local_model import draft_krea2_caption
from prompt_hub.tag_locale import TagLocaleError, resolve_canonical_tag
from prompt_hub.wd14 import ProviderMode, WD14Tagger

if TYPE_CHECKING:
    from prompt_hub.config import Settings

CaptionProfile = Literal["anima", "krea2"]
Tagger = Callable[[Path], dict[str, object]]
TaggerFactory = Callable[[float, float, ProviderMode], Tagger]
Krea2Captioner = Callable[[Path, str, str], dict[str, Any]]

CURATION_FORMAT = "soda-prompt-hub-dataset-curation-v1"
MAX_CAPTION_CHARS = 12000
LOW_FREQUENCY_MAX = 2
MIN_CONFLICT_TAGS = 2
DEFAULT_CONFLICT_RULES = [
    {"rule_id": "hair-grey-white", "tags": ["grey_hair", "white_hair"]},
    {"rule_id": "hair-black-white", "tags": ["black_hair", "white_hair"]},
    {"rule_id": "subject-girl-boy", "tags": ["1girl", "1boy"]},
    {"rule_id": "count-solo-multiple", "tags": ["solo", "multiple_girls"]},
]


class DatasetCurationStore:
    def __init__(
        self,
        settings: Settings,
        workspace_store: DatasetWorkspaceStore,
        *,
        tagger_factory: TaggerFactory | None = None,
        krea2_captioner: Krea2Captioner | None = None,
    ) -> None:
        self.settings = settings
        self.workspace_store = workspace_store
        self._lock = RLock()
        self._tagger_factory = tagger_factory or self._default_tagger_factory
        self._krea2_captioner = krea2_captioner or self._default_krea2_captioner

    def initialize(self) -> None:
        self.settings.dataset_exports_root.mkdir(parents=True, exist_ok=True)

    def read_state(self, workspace_id: str) -> dict[str, Any]:
        self._require_workspace(workspace_id)
        path = self._workspace_directory(workspace_id) / "curation.json"
        if not path.is_file():
            return {
                "format": CURATION_FORMAT,
                "workspace_id": workspace_id,
                "revision": 0,
                "items": {},
                "exports": [],
                "updated_at": "",
            }
        payload = _load_json(path)
        payload.setdefault("format", CURATION_FORMAT)
        payload.setdefault("workspace_id", workspace_id)
        payload.setdefault("revision", 0)
        payload.setdefault("items", {})
        payload.setdefault("exports", [])
        return payload

    def decorate_report(self, workspace_id: str, report: dict[str, Any]) -> dict[str, Any]:
        state = self.read_state(workspace_id)
        raw_items = state.get("items", {})
        items = raw_items if isinstance(raw_items, dict) else {}
        for image in report.get("images", []):
            if not isinstance(image, dict):
                continue
            relative_path = str(image.get("relative_path", ""))
            raw_curation = items.get(relative_path, {})
            curation = dict(raw_curation) if isinstance(raw_curation, dict) else {}
            curation.setdefault("wd14", {"status": "untagged"})
            curation["krea2_vlm"] = _vlm_record(curation.get("krea2_vlm"))
            captions = curation.get("captions", {})
            if not isinstance(captions, dict):
                captions = {}
            curation["captions"] = {
                "anima": _caption_record(captions.get("anima")),
                "krea2": _caption_record(captions.get("krea2")),
            }
            image["curation"] = curation
        report["curation_revision"] = int(state.get("revision", 0))
        report["curation_updated_at"] = str(state.get("updated_at", ""))
        return report

    def tag_job(self, payload: Mapping[str, Any], context: JobProgress) -> dict[str, Any]:
        workspace_id = str(payload.get("workspace_id", ""))
        if not workspace_id:
            raise DatasetWorkspaceError("WD14 job is missing workspace_id")
        general_threshold = float(payload.get("general_threshold", 0.35))
        character_threshold = float(payload.get("character_threshold", 0.85))
        provider = str(payload.get("provider", "auto"))
        if provider not in {"auto", "coreml", "cpu"}:
            raise DatasetWorkspaceError("Unsupported WD14 provider")
        paths = self._select_tag_paths(workspace_id, payload)
        job_id = str(getattr(context, "job_id", ""))
        state = self.read_state(workspace_id)
        if job_id:
            paths = [
                path for path in paths if not _completed_by_job(_state_item(state, path), job_id)
            ]
        if not paths:
            return {
                "workspace_id": workspace_id,
                "requested": 0,
                "completed": 0,
                "failed": 0,
                "skipped": 0,
            }
        context.update(0, len(paths), "正在加载 WD14 模型")
        tagger = self._tagger_factory(
            general_threshold,
            character_threshold,
            provider,  # type: ignore[arg-type]
        )
        completed = 0
        failed = 0
        skipped = 0
        overwrite = bool(payload.get("overwrite", False))
        for index, relative_path in enumerate(paths, start=1):
            context.update(index - 1, len(paths), f"WD14 {index}/{len(paths)} · {relative_path}")
            current = _state_item(state, relative_path)
            wd14 = current.get("wd14", {})
            if (
                not overwrite
                and isinstance(wd14, dict)
                and str(wd14.get("status", "")) == "completed"
            ):
                skipped += 1
                context.update(index, len(paths), f"已跳过 {relative_path}")
                continue
            image_path = self.workspace_store.resolve_source_image(workspace_id, relative_path)
            if image_path is None:
                self._store_tag_failure(
                    workspace_id,
                    state,
                    relative_path,
                    "图片不存在或已变更",
                    job_id=job_id,
                )
                failed += 1
                continue
            try:
                result = tagger(image_path)
            except Exception as error:  # noqa: BLE001
                self._store_tag_failure(
                    workspace_id,
                    state,
                    relative_path,
                    str(error),
                    job_id=job_id,
                )
                failed += 1
            else:
                self._store_tag_result(
                    workspace_id,
                    state,
                    relative_path,
                    result,
                    job_id=job_id,
                )
                completed += 1
            context.update(index, len(paths), f"已处理 {index}/{len(paths)}")
        if paths and completed == 0 and failed:
            raise DatasetWorkspaceError(f"WD14 队列全部失败, 共 {failed} 张")
        return {
            "workspace_id": workspace_id,
            "requested": len(paths),
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
        }

    def krea2_vlm_job(self, payload: Mapping[str, Any], context: JobProgress) -> dict[str, Any]:
        workspace_id = str(payload.get("workspace_id", ""))
        if not workspace_id:
            raise DatasetWorkspaceError("Krea 2 VLM job is missing workspace_id")
        model = str(payload.get("model", "")).strip()
        if not model:
            raise DatasetWorkspaceError("Krea 2 VLM job is missing model")
        paths = self._select_krea2_paths(workspace_id, payload)
        job_id = str(getattr(context, "job_id", ""))
        state = self.read_state(workspace_id)
        if job_id:
            paths = [
                path
                for path in paths
                if not _completed_vlm_by_job(_state_item(state, path), job_id)
            ]
        if not paths:
            return {
                "workspace_id": workspace_id,
                "model": model,
                "requested": 0,
                "completed": 0,
                "failed": 0,
                "skipped": 0,
            }
        completed = 0
        failed = 0
        skipped = 0
        for index, relative_path in enumerate(paths, start=1):
            context.update(
                index - 1,
                len(paths),
                f"Krea 2 VLM {index}/{len(paths)} · {relative_path}",
            )
            record = self._known_record(workspace_id, relative_path)
            image_path = self.workspace_store.resolve_source_image(workspace_id, relative_path)
            expected_sha256 = str(record.get("sha256", ""))
            if image_path is None or not expected_sha256 or _sha256(image_path) != expected_sha256:
                self._store_krea2_failure(
                    workspace_id,
                    state,
                    relative_path,
                    "图片不存在或扫描后已变更",
                    model=model,
                    job_id=job_id,
                    source_sha256=expected_sha256,
                )
                failed += 1
                continue
            item = _state_item(state, relative_path)
            existing_caption = _current_caption(item, "krea2")
            try:
                result = self._krea2_captioner(image_path, model, existing_caption)
                draft = _normalize_caption("krea2", str(result.get("draft", "")))
                if not draft:
                    raise DatasetWorkspaceError("本地视觉模型返回了空的 Krea 2 草稿")
            except Exception as error:  # noqa: BLE001
                self._store_krea2_failure(
                    workspace_id,
                    state,
                    relative_path,
                    str(error),
                    model=model,
                    job_id=job_id,
                    source_sha256=expected_sha256,
                )
                failed += 1
            else:
                self._store_krea2_result(
                    workspace_id,
                    state,
                    relative_path,
                    result,
                    draft=draft,
                    model=model,
                    job_id=job_id,
                    source_sha256=expected_sha256,
                )
                completed += 1
            context.update(index, len(paths), f"已处理 {index}/{len(paths)}")
        if paths and completed == 0 and failed:
            raise DatasetWorkspaceError(f"Krea 2 VLM 队列全部失败, 共 {failed} 张")
        return {
            "workspace_id": workspace_id,
            "model": model,
            "requested": len(paths),
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
        }

    def update_krea2_draft(
        self,
        workspace_id: str,
        relative_path: str,
        *,
        draft: str,
        confirm: bool,
    ) -> dict[str, Any]:
        self._known_record(workspace_id, relative_path)
        clean = _normalize_caption("krea2", draft)
        if confirm and not clean:
            raise DatasetWorkspaceError("确认前需要一份英文 Krea 2 草稿")
        with self._lock:
            state = self.read_state(workspace_id)
            item = _state_item(state, relative_path)
            vlm = _vlm_record(item.get("krea2_vlm"))
            vlm.update(
                {
                    "status": "confirmed" if confirm else "completed" if clean else "empty",
                    "draft": clean,
                    "edited_at": _now(),
                    "error": "",
                }
            )
            snapshot = ""
            if confirm:
                before = _current_caption(item, "krea2")
                snapshot = self._write_snapshot(
                    workspace_id,
                    operation="confirm-krea2-vlm",
                    profile_id="krea2",
                    changes=[{"relative_path": relative_path, "before": before, "after": clean}],
                )
                _set_caption(
                    item,
                    "krea2",
                    clean,
                    status="reviewed",
                    source="vlm-confirmed",
                    snapshot=snapshot,
                )
                vlm["confirmed_at"] = _now()
                vlm["confirmed_snapshot"] = snapshot
            item["krea2_vlm"] = vlm
            self._write_state(workspace_id, state)
        return {
            "workspace_id": workspace_id,
            "relative_path": relative_path,
            "krea2_vlm": vlm,
            "caption": _caption_record(item["captions"]["krea2"]),
            "snapshot": snapshot,
        }

    def import_krea2_vlm_results(
        self,
        workspace_id: str,
        *,
        model: str,
        worker_id: str,
        task_id: str,
        items: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        report = self._require_report(workspace_id)
        records = {
            str(item.get("relative_path", "")): str(item.get("sha256", ""))
            for item in report.get("images", [])
            if isinstance(item, dict)
        }
        prepared = []
        for raw in items:
            relative_path = str(raw.get("relative_path", ""))
            source_sha256 = str(raw.get("source_sha256", ""))
            expected = records.get(relative_path, "")
            if not expected or source_sha256 != expected:
                raise DatasetWorkspaceError(f"源 SHA-256 回验失败: {relative_path}")
            error = str(raw.get("error", "")).strip()
            draft = "" if error else _normalize_caption("krea2", str(raw.get("caption_draft", "")))
            if not error and not draft:
                raise DatasetWorkspaceError(f"远程 Krea 2 草稿为空: {relative_path}")
            prepared.append((relative_path, source_sha256, draft, error, raw))
        if not prepared:
            raise DatasetWorkspaceError("没有可导入的 Krea 2 VLM 结果")
        state = self.read_state(workspace_id)
        imported = 0
        failed = 0
        for relative_path, source_sha256, draft, error, raw in prepared:
            if error:
                self._store_krea2_failure(
                    workspace_id,
                    state,
                    relative_path,
                    error,
                    model=model,
                    job_id=task_id,
                    source_sha256=source_sha256,
                )
                failed += 1
                continue
            self._store_krea2_result(
                workspace_id,
                state,
                relative_path,
                {
                    "model": model,
                    "observations": raw.get("observations", {}),
                    "safety_warning": raw.get("safety_warning", ""),
                    "worker_id": worker_id,
                },
                draft=draft,
                model=model,
                job_id=task_id,
                source_sha256=source_sha256,
            )
            imported += 1
        return {
            "workspace_id": workspace_id,
            "task_id": task_id,
            "worker_id": worker_id,
            "model": model,
            "imported": imported,
            "failed": failed,
        }

    def analytics(self, workspace_id: str) -> dict[str, Any]:
        state = self.read_state(workspace_id)
        counts: Counter[str] = Counter()
        suspicious: Counter[str] = Counter()
        conflicts: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        rules = self.read_conflict_rules(workspace_id)
        raw_items = state.get("items", {})
        items = raw_items if isinstance(raw_items, dict) else {}
        for relative_path, raw_item in items.items():
            item = raw_item if isinstance(raw_item, dict) else {}
            wd14 = item.get("wd14", {})
            status_value = wd14.get("status", "untagged") if isinstance(wd14, dict) else "untagged"
            status_counts[str(status_value)] += 1
            caption = _current_caption(item, "anima")
            tags = _split_tags(caption)
            counts.update(tags)
            suspicious.update(tag for tag in tags if _suspicious_tag(tag))
            tag_set = set(tags)
            for rule in rules:
                matched = [tag for tag in rule["tags"] if tag in tag_set]
                if len(matched) > 1:
                    conflicts.append(
                        {
                            "relative_path": str(relative_path),
                            "rule_id": rule["rule_id"],
                            "tags": matched,
                        }
                    )
        frequencies: list[dict[str, Any]] = [
            {"tag": tag, "count": count}
            for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        return {
            "workspace_id": workspace_id,
            "captioned_images": sum(
                bool(_current_caption(item, "anima")) for item in items.values()
            ),
            "unique_tags": len(counts),
            "frequencies": frequencies,
            "low_frequency": [item for item in frequencies if item["count"] <= LOW_FREQUENCY_MAX],
            "suspicious": [{"tag": tag, "count": count} for tag, count in suspicious.most_common()],
            "conflicts": conflicts,
            "tag_status": dict(status_counts),
            "rules": rules,
        }

    def read_conflict_rules(self, workspace_id: str) -> list[dict[str, Any]]:
        self._require_workspace(workspace_id)
        path = self._workspace_directory(workspace_id) / "conflict-rules.json"
        if not path.is_file():
            return [dict(rule) for rule in DEFAULT_CONFLICT_RULES]
        payload = _load_json(path)
        rules = payload.get("rules", [])
        return [dict(rule) for rule in rules if isinstance(rule, dict)]

    def update_conflict_rules(
        self,
        workspace_id: str,
        rules: Iterable[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, rule in enumerate(rules, start=1):
            tags = _normalize_tag_list(rule.get("tags", []))
            if len(tags) < MIN_CONFLICT_TAGS:
                raise DatasetWorkspaceError("每条冲突规则至少需要两个英文标签")
            rule_id = str(rule.get("rule_id", "")).strip() or f"custom-{index}"
            normalized.append({"rule_id": rule_id[:120], "tags": tags})
        _atomic_json_write(
            self._workspace_directory(workspace_id) / "conflict-rules.json",
            {"format": "soda-prompt-hub-conflict-rules-v1", "rules": normalized},
        )
        return normalized

    def update_caption(
        self,
        workspace_id: str,
        relative_path: str,
        *,
        profile_id: CaptionProfile,
        caption: str,
        status: Literal["draft", "reviewed"] = "reviewed",
    ) -> dict[str, Any]:
        self._known_record(workspace_id, relative_path)
        clean = _normalize_caption(profile_id, caption)
        with self._lock:
            state = self.read_state(workspace_id)
            item = _state_item(state, relative_path)
            before = _current_caption(item, profile_id)
            snapshot = self._write_snapshot(
                workspace_id,
                operation=f"edit-{profile_id}",
                profile_id=profile_id,
                changes=[{"relative_path": relative_path, "before": before, "after": clean}],
            )
            _set_caption(
                item,
                profile_id,
                clean,
                status=status,
                source="manual",
                snapshot=snapshot,
            )
            self._write_state(workspace_id, state)
        return {
            "relative_path": relative_path,
            "profile_id": profile_id,
            "caption": _caption_record(item["captions"][profile_id]),
            "snapshot": snapshot,
        }

    def source_caption_preview(
        self,
        workspace_id: str,
        *,
        profile_id: CaptionProfile,
        paths: Iterable[str] = (),
        overwrite_existing: bool = False,
    ) -> dict[str, Any]:
        report = self._require_report(workspace_id)
        requested = list(dict.fromkeys(str(path) for path in paths if str(path)))
        requested_set = set(requested)
        records = [
            item
            for item in report.get("images", [])
            if isinstance(item, dict)
            and (not requested_set or str(item.get("relative_path", "")) in requested_set)
        ]
        found = {str(item.get("relative_path", "")) for item in records}
        if missing := sorted(requested_set - found):
            raise DatasetWorkspaceError(f"Dataset image not found: {missing[0]}")

        state = self.read_state(workspace_id)
        changes: list[dict[str, Any]] = []
        invalid: list[dict[str, str]] = []
        skipped_existing = 0
        skipped_empty = 0
        unchanged = 0
        paired = 0
        for record in records:
            relative_path = str(record.get("relative_path", ""))
            source_caption = str(record.get("caption", "")).strip()
            if not source_caption:
                skipped_empty += 1
                continue
            paired += 1
            try:
                after = _normalize_caption(profile_id, source_caption)
            except DatasetWorkspaceError as error:
                invalid.append({"relative_path": relative_path, "reason": str(error)})
                continue
            item = _state_item(state, relative_path)
            before = _current_caption(item, profile_id)
            if before and not overwrite_existing:
                skipped_existing += 1
                continue
            if before == after:
                unchanged += 1
                continue
            changes.append(
                {
                    "relative_path": relative_path,
                    "caption_path": str(record.get("caption_path", "")),
                    "before": before,
                    "after": after,
                }
            )
        return {
            "workspace_id": workspace_id,
            "profile_id": profile_id,
            "scope": "selected" if requested else "all",
            "inspected": len(records),
            "paired": paired,
            "changed": len(changes),
            "skipped_existing": skipped_existing,
            "skipped_empty": skipped_empty,
            "unchanged": unchanged,
            "invalid": invalid,
            "changes": changes,
        }

    def apply_source_captions(
        self,
        workspace_id: str,
        *,
        profile_id: CaptionProfile,
        paths: Iterable[str] = (),
        overwrite_existing: bool = False,
        status: Literal["draft", "reviewed"] = "draft",
    ) -> dict[str, Any]:
        with self._lock:
            preview = self.source_caption_preview(
                workspace_id,
                profile_id=profile_id,
                paths=paths,
                overwrite_existing=overwrite_existing,
            )
            changes = preview["changes"]
            if not changes:
                return {**preview, "snapshot": None, "caption_status": status}
            snapshot = self._write_snapshot(
                workspace_id,
                operation=f"source-caption-to-{profile_id}",
                profile_id=profile_id,
                changes=changes,
            )
            state = self.read_state(workspace_id)
            for change in changes:
                item = _state_item(state, str(change["relative_path"]))
                _set_caption(
                    item,
                    profile_id,
                    str(change["after"]),
                    status=status,
                    source="original-caption",
                    snapshot=snapshot,
                )
            self._write_state(workspace_id, state)
        return {**preview, "snapshot": snapshot, "caption_status": status}

    def bulk_preview(
        self,
        workspace_id: str,
        paths: Iterable[str],
        operation: Mapping[str, Any],
    ) -> dict[str, Any]:
        state = self.read_state(workspace_id)
        changes = []
        for relative_path in dict.fromkeys(str(path) for path in paths):
            self._known_record(workspace_id, relative_path)
            item = _state_item(state, relative_path)
            before = _current_caption(item, "anima")
            after = _apply_tag_operation(before, operation)
            if before != after:
                changes.append({"relative_path": relative_path, "before": before, "after": after})
        return {
            "workspace_id": workspace_id,
            "changed": len(changes),
            "changes": changes,
            "summary": _change_summary(changes),
            "conflicts": self._conflicts_for_changes(workspace_id, changes),
        }

    def apply_bulk_edit(
        self,
        workspace_id: str,
        paths: Iterable[str],
        operation: Mapping[str, Any],
    ) -> dict[str, Any]:
        with self._lock:
            preview = self.bulk_preview(workspace_id, paths, operation)
            changes = preview["changes"]
            if not changes:
                return {**preview, "snapshot": None}
            snapshot = self._write_snapshot(
                workspace_id,
                operation="bulk-anima-tags",
                profile_id="anima",
                changes=changes,
            )
            state = self.read_state(workspace_id)
            for change in changes:
                item = _state_item(state, str(change["relative_path"]))
                _set_caption(
                    item,
                    "anima",
                    str(change["after"]),
                    status="draft",
                    source="bulk-edit",
                    snapshot=snapshot,
                )
            self._write_state(workspace_id, state)
        return {**preview, "snapshot": snapshot}

    def list_snapshots(self, workspace_id: str) -> list[dict[str, Any]]:
        root = self._workspace_directory(workspace_id) / "caption-snapshots"
        if not root.is_dir():
            return []
        snapshots = []
        for path in sorted(root.glob("snapshot-*.json"), reverse=True):
            payload = _load_json(path)
            snapshots.append(
                {
                    "snapshot_id": path.stem,
                    "operation": payload.get("operation", ""),
                    "profile_id": _snapshot_profile(payload),
                    "created_at": payload.get("created_at", ""),
                    "changed": len(payload.get("changes", [])),
                }
            )
        return snapshots

    def rollback_snapshot(self, workspace_id: str, snapshot_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"snapshot-[0-9A-Za-z-]+", snapshot_id):
            raise DatasetWorkspaceError("Invalid caption snapshot id")
        path = self._workspace_directory(workspace_id) / "caption-snapshots" / f"{snapshot_id}.json"
        if not path.is_file():
            raise DatasetWorkspaceError("Caption snapshot not found")
        payload = _load_json(path)
        profile_id = _snapshot_profile(payload)
        if profile_id not in {"anima", "krea2"}:
            raise DatasetWorkspaceError("Invalid caption snapshot profile")
        profile = profile_id
        raw_changes = payload.get("changes", [])
        changes = [dict(item) for item in raw_changes if isinstance(item, dict)]
        rollback_changes = [
            {
                "relative_path": str(change["relative_path"]),
                "before": str(change.get("after", "")),
                "after": str(change.get("before", "")),
            }
            for change in changes
        ]
        rollback_id = self._write_snapshot(
            workspace_id,
            operation=f"rollback-{snapshot_id}",
            profile_id=profile,
            changes=rollback_changes,
        )
        with self._lock:
            state = self.read_state(workspace_id)
            for change in rollback_changes:
                item = _state_item(state, change["relative_path"])
                _set_caption(
                    item,
                    profile,
                    change["after"],
                    status="draft",
                    source="rollback",
                    snapshot=rollback_id,
                )
            self._write_state(workspace_id, state)
        return {
            "rolled_back": snapshot_id,
            "profile_id": profile_id,
            "snapshot": rollback_id,
            "changed": len(changes),
        }

    def export_version(
        self,
        workspace_id: str,
        *,
        profile_id: CaptionProfile,
        paths: Iterable[str],
    ) -> dict[str, Any]:
        workspace = self._require_workspace(workspace_id)
        report = self._require_report(workspace_id)
        review = self.workspace_store.read_review_state(workspace_id)
        state = self.read_state(workspace_id)
        records = {
            str(item.get("relative_path", "")): item
            for item in report.get("images", [])
            if isinstance(item, dict)
        }
        selected = list(dict.fromkeys(str(path) for path in paths))
        if not selected:
            raise DatasetWorkspaceError("导出前请至少选择一张已审核图片")
        prepared = []
        seen_hashes: set[str] = set()
        seen_captions: set[str] = set()
        for relative_path in selected:
            record = records.get(relative_path)
            if record is None or not record.get("valid"):
                raise DatasetWorkspaceError(f"无法导出无效图片: {relative_path}")
            if review.get(relative_path, {}).get("status") != "approved":
                raise DatasetWorkspaceError(f"图片尚未标记保留: {relative_path}")
            item = _state_item(state, relative_path)
            caption = _current_caption(item, profile_id)
            if not caption:
                raise DatasetWorkspaceError(f"缺少 {profile_id} caption: {relative_path}")
            if not caption.isascii():
                raise DatasetWorkspaceError(f"最终 caption 必须是英文: {relative_path}")
            digest = str(record.get("sha256", ""))
            if digest in seen_hashes:
                raise DatasetWorkspaceError("导出集合含完全重复图片, 请先排除重复项")
            seen_hashes.add(digest)
            caption_relative = str(Path(relative_path).with_suffix(".txt"))
            if caption_relative in seen_captions:
                raise DatasetWorkspaceError("不同图片会生成同名 caption, 请先调整来源文件名")
            seen_captions.add(caption_relative)
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
                target_image = train_root / relative_path
                target_caption = train_root / caption_relative
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
                    }
                )
            audit = self._export_audit(workspace_id, selected, profile_id)
            manifest = {
                "format": "soda-prompt-hub-dataset-export-v2",
                "version_id": version_id,
                "workspace_id": workspace_id,
                "workspace_name": workspace.get("name", ""),
                "profile_id": profile_id,
                "caption_language": "en",
                "source_mode": "read-only",
                "created_at": _now(),
                "items": manifest_items,
            }
            _atomic_json_write(version_root / "manifest.json", manifest)
            _atomic_json_write(version_root / "audit.json", audit)
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(version_root.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(version_root).as_posix())
        except Exception:
            shutil.rmtree(version_root, ignore_errors=True)
            archive_path.unlink(missing_ok=True)
            raise

        export = {
            "version_id": version_id,
            "profile_id": profile_id,
            "image_count": len(prepared),
            "directory": str(version_root),
            "archive_name": archive_path.name,
            "download_url": f"/dataset-workspaces/{workspace_id}/exports/{archive_path.name}",
            "created_at": manifest["created_at"],
        }
        state = self.read_state(workspace_id)
        raw_exports = state.get("exports", [])
        state["exports"] = [*raw_exports, export] if isinstance(raw_exports, list) else [export]
        self._write_state(workspace_id, state)
        return {**export, "manifest": manifest, "audit": audit}

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

    def _default_tagger_factory(
        self,
        general_threshold: float,
        character_threshold: float,
        provider: ProviderMode,
    ) -> Tagger:
        return WD14Tagger(
            model_root=self.settings.wd14_model_root,
            general_threshold=general_threshold,
            character_threshold=character_threshold,
            provider=provider,
        ).tag

    @staticmethod
    def _default_krea2_captioner(
        image_path: Path,
        model: str,
        existing_caption: str,
    ) -> dict[str, Any]:
        return draft_krea2_caption(
            image_path=image_path,
            model=model,
            existing_caption=existing_caption,
        )

    def _select_tag_paths(
        self,
        workspace_id: str,
        payload: Mapping[str, Any],
    ) -> list[str]:
        report = self._require_report(workspace_id)
        valid = [
            str(item.get("relative_path", ""))
            for item in report.get("images", [])
            if isinstance(item, dict) and item.get("valid") is True
        ]
        scope = str(payload.get("scope", "untagged"))
        requested = payload.get("paths", [])
        requested_set = (
            {str(path) for path in requested if isinstance(path, str)}
            if isinstance(requested, list)
            else set()
        )
        if scope in {"selected", "filtered"}:
            return [path for path in valid if path in requested_set]
        state = self.read_state(workspace_id)
        if scope == "all":
            return valid
        if scope == "untagged":
            return [
                path
                for path in valid
                if str(_state_item(state, path).get("wd14", {}).get("status", "untagged"))
                != "completed"
            ]
        if scope == "failed":
            return [
                path
                for path in valid
                if str(_state_item(state, path).get("wd14", {}).get("status", "")) == "failed"
            ]
        raise DatasetWorkspaceError("Unsupported WD14 queue scope")

    def _select_krea2_paths(
        self,
        workspace_id: str,
        payload: Mapping[str, Any],
    ) -> list[str]:
        report = self._require_report(workspace_id)
        valid = [
            str(item.get("relative_path", ""))
            for item in report.get("images", [])
            if isinstance(item, dict) and item.get("valid") is True
        ]
        scope = str(payload.get("scope", "missing"))
        requested = payload.get("paths", [])
        requested_set = (
            {str(path) for path in requested if isinstance(path, str)}
            if isinstance(requested, list)
            else set()
        )
        if scope == "selected":
            return [path for path in valid if path in requested_set]
        if scope == "all":
            return valid
        state = self.read_state(workspace_id)
        if scope == "missing":
            return [
                path
                for path in valid
                if not str(_vlm_record(_state_item(state, path).get("krea2_vlm"))["draft"])
            ]
        if scope == "failed":
            return [
                path
                for path in valid
                if _vlm_record(_state_item(state, path).get("krea2_vlm"))["status"] == "failed"
            ]
        raise DatasetWorkspaceError("Unsupported Krea 2 VLM queue scope")

    def _store_krea2_result(
        self,
        workspace_id: str,
        state: dict[str, Any],
        relative_path: str,
        result: Mapping[str, Any],
        *,
        draft: str,
        model: str,
        job_id: str,
        source_sha256: str,
    ) -> None:
        with self._lock:
            latest = self.read_state(workspace_id)
            item = _state_item(latest, relative_path)
            raw_observations = result.get("observations", {})
            observations = raw_observations if isinstance(raw_observations, dict) else {}
            item["krea2_vlm"] = {
                "status": "completed",
                "job_id": job_id,
                "worker_id": str(result.get("worker_id", "")),
                "model": str(result.get("model", model)) or model,
                "draft": draft,
                "observations": observations,
                "safety_warning": str(result.get("safety_warning", ""))[:2000],
                "source_sha256": source_sha256,
                "created_at": _now(),
                "error": "",
            }
            self._write_state(workspace_id, latest)
            state.clear()
            state.update(latest)

    def _store_krea2_failure(
        self,
        workspace_id: str,
        state: dict[str, Any],
        relative_path: str,
        error: str,
        *,
        model: str,
        job_id: str,
        source_sha256: str,
    ) -> None:
        with self._lock:
            latest = self.read_state(workspace_id)
            item = _state_item(latest, relative_path)
            previous = _vlm_record(item.get("krea2_vlm"))
            previous.update(
                {
                    "status": "failed",
                    "job_id": job_id,
                    "model": model,
                    "source_sha256": source_sha256,
                    "created_at": _now(),
                    "error": error[:2000],
                }
            )
            item["krea2_vlm"] = previous
            self._write_state(workspace_id, latest)
            state.clear()
            state.update(latest)

    def _store_tag_result(
        self,
        workspace_id: str,
        state: dict[str, Any],
        relative_path: str,
        result: Mapping[str, object],
        *,
        job_id: str,
    ) -> None:
        with self._lock:
            latest = self.read_state(workspace_id)
            item = _state_item(latest, relative_path)
            draft = normalize_tag_draft(str(result.get("tag_string", "")))
            item["wd14"] = {
                "status": "completed",
                "job_id": job_id,
                "model": str(result.get("model", "SmilingWolf/wd-swinv2-tagger-v3")),
                "provider": str(result.get("provider", "")),
                "tagged_at": _now(),
                "general_threshold": result.get("general_threshold", 0.35),
                "character_threshold": result.get("character_threshold", 0.85),
                "rating": result.get("rating"),
                "general": result.get("general", []),
                "characters": result.get("characters", []),
                "elapsed_seconds": result.get("elapsed_seconds"),
                "error": "",
            }
            current = _caption_record(item.get("captions", {}).get("anima"))
            if current["status"] != "reviewed":
                _set_caption(
                    item,
                    "anima",
                    draft,
                    status="draft",
                    source="wd14",
                    snapshot="",
                )
            self._write_state(workspace_id, latest)
            state.clear()
            state.update(latest)

    def _store_tag_failure(
        self,
        workspace_id: str,
        state: dict[str, Any],
        relative_path: str,
        error: str,
        *,
        job_id: str,
    ) -> None:
        with self._lock:
            latest = self.read_state(workspace_id)
            item = _state_item(latest, relative_path)
            item["wd14"] = {
                "status": "failed",
                "job_id": job_id,
                "error": error[:2000],
                "tagged_at": _now(),
            }
            self._write_state(workspace_id, latest)
            state.clear()
            state.update(latest)

    def _write_snapshot(
        self,
        workspace_id: str,
        *,
        operation: str,
        profile_id: CaptionProfile,
        changes: list[dict[str, Any]],
    ) -> str:
        snapshot_id = f"snapshot-{_timestamp_token()}-{uuid4().hex[:8]}"
        root = self._workspace_directory(workspace_id) / "caption-snapshots"
        _atomic_json_write(
            root / f"{snapshot_id}.json",
            {
                "format": "soda-prompt-hub-caption-snapshot-v1",
                "snapshot_id": snapshot_id,
                "operation": operation,
                "profile_id": profile_id,
                "created_at": _now(),
                "changes": changes,
            },
        )
        return snapshot_id

    def _write_state(self, workspace_id: str, state: dict[str, Any]) -> None:
        with self._lock:
            state["format"] = CURATION_FORMAT
            state["workspace_id"] = workspace_id
            state["revision"] = int(state.get("revision", 0)) + 1
            state["updated_at"] = _now()
            _atomic_json_write(self._workspace_directory(workspace_id) / "curation.json", state)

    def _workspace_directory(self, workspace_id: str) -> Path:
        if not workspace_id.startswith("dataset-") or not workspace_id[8:].isalnum():
            raise DatasetWorkspaceError("Invalid dataset workspace id")
        root = self.settings.dataset_workspaces_root.resolve()
        path = (root / workspace_id).resolve()
        if not path.is_relative_to(root):
            raise DatasetWorkspaceError("Invalid dataset workspace path")
        return path

    def _require_workspace(self, workspace_id: str) -> dict[str, Any]:
        workspace = self.workspace_store.get(workspace_id)
        if workspace is None:
            raise DatasetWorkspaceError("Dataset workspace not found")
        return workspace

    def _require_report(self, workspace_id: str) -> dict[str, Any]:
        report = self.workspace_store.read_current_report(workspace_id)
        if report is None:
            raise DatasetWorkspaceError("Dataset scan report not found")
        return report

    def _known_record(self, workspace_id: str, relative_path: str) -> dict[str, Any]:
        report = self._require_report(workspace_id)
        record = next(
            (
                item
                for item in report.get("images", [])
                if isinstance(item, dict) and item.get("relative_path") == relative_path
            ),
            None,
        )
        if record is None:
            raise DatasetWorkspaceError(f"Dataset image not found: {relative_path}")
        return record

    def _conflicts_for_changes(
        self,
        workspace_id: str,
        changes: Iterable[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        rules = self.read_conflict_rules(workspace_id)
        conflicts = []
        for change in changes:
            tags = set(_split_tags(str(change.get("after", ""))))
            for rule in rules:
                matched = [tag for tag in rule["tags"] if tag in tags]
                if len(matched) > 1:
                    conflicts.append(
                        {
                            "relative_path": change["relative_path"],
                            "rule_id": rule["rule_id"],
                            "tags": matched,
                        }
                    )
        return conflicts

    def _export_audit(
        self,
        workspace_id: str,
        paths: list[str],
        profile_id: CaptionProfile,
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
            "created_at": _now(),
        }


def _state_item(state: dict[str, Any], relative_path: str) -> dict[str, Any]:
    raw_items = state.setdefault("items", {})
    if not isinstance(raw_items, dict):
        raw_items = {}
        state["items"] = raw_items
    raw_item = raw_items.get(relative_path)
    item = dict(raw_item) if isinstance(raw_item, dict) else {}
    item.setdefault("wd14", {"status": "untagged"})
    item["krea2_vlm"] = _vlm_record(item.get("krea2_vlm"))
    raw_captions = item.setdefault("captions", {})
    captions = raw_captions if isinstance(raw_captions, dict) else {}
    captions.setdefault("anima", _caption_record(None))
    captions.setdefault("krea2", _caption_record(None))
    item["captions"] = captions
    raw_items[relative_path] = item
    return item


class JobProgress(Protocol):
    job_id: str

    def update(self, current: int, total: int, message: str = "") -> None: ...


def _caption_record(value: object) -> dict[str, Any]:
    record = dict(value) if isinstance(value, dict) else {}
    record.setdefault("current", "")
    record.setdefault("status", "empty")
    record.setdefault("source", "")
    record.setdefault("updated_at", "")
    record.setdefault("versions", [])
    return record


def _snapshot_profile(payload: Mapping[str, Any]) -> str:
    explicit = str(payload.get("profile_id", ""))
    if explicit:
        return explicit
    operation = str(payload.get("operation", ""))
    return "krea2" if operation.startswith("edit-krea2") else "anima"


def _completed_by_job(item: object, job_id: str) -> bool:
    if not isinstance(item, dict):
        return False
    wd14 = item.get("wd14", {})
    return bool(
        isinstance(wd14, dict)
        and wd14.get("status") == "completed"
        and wd14.get("job_id") == job_id
    )


def _completed_vlm_by_job(item: object, job_id: str) -> bool:
    if not isinstance(item, dict):
        return False
    vlm = _vlm_record(item.get("krea2_vlm"))
    return bool(vlm["status"] in {"completed", "confirmed"} and vlm["job_id"] == job_id)


def _vlm_record(value: object) -> dict[str, Any]:
    record = dict(value) if isinstance(value, dict) else {}
    record.setdefault("status", "empty")
    record.setdefault("job_id", "")
    record.setdefault("worker_id", "")
    record.setdefault("model", "")
    record.setdefault("draft", "")
    record.setdefault("observations", {})
    record.setdefault("safety_warning", "")
    record.setdefault("source_sha256", "")
    record.setdefault("created_at", "")
    record.setdefault("error", "")
    return record


def _current_caption(item: object, profile_id: CaptionProfile) -> str:
    if not isinstance(item, dict):
        return ""
    captions = item.get("captions", {})
    if not isinstance(captions, dict):
        return ""
    return str(_caption_record(captions.get(profile_id))["current"])


def _set_caption(
    item: dict[str, Any],
    profile_id: CaptionProfile,
    caption: str,
    *,
    status: str,
    source: str,
    snapshot: str,
) -> None:
    raw_captions = item.setdefault("captions", {})
    if not isinstance(raw_captions, dict):
        raw_captions = {}
        item["captions"] = raw_captions
    record = _caption_record(raw_captions.get(profile_id))
    if str(record.get("current", "")) != caption:
        versions = record.get("versions", [])
        if not isinstance(versions, list):
            versions = []
        versions.append(
            {
                "version_id": f"caption-{uuid4().hex[:12]}",
                "caption": caption,
                "status": status,
                "source": source,
                "snapshot": snapshot,
                "created_at": _now(),
            }
        )
        record["versions"] = versions
    record.update(
        {
            "current": caption,
            "status": status if caption else "empty",
            "source": source,
            "updated_at": _now(),
        }
    )
    raw_captions[profile_id] = record


def _normalize_caption(profile_id: CaptionProfile, caption: str) -> str:
    clean = caption.strip()[:MAX_CAPTION_CHARS]
    if clean and not clean.isascii():
        raise DatasetWorkspaceError("最终 caption 必须使用英文")
    if profile_id == "anima":
        try:
            return normalize_tag_draft(clean)
        except DatasetTaggingError as error:
            raise DatasetWorkspaceError(str(error)) from error
    return " ".join(clean.split())


def _apply_tag_operation(caption: str, operation: Mapping[str, Any]) -> str:
    tags = _split_tags(caption)
    remove = set(_normalize_tag_list(operation.get("remove", [])))
    replacements_raw = operation.get("replace", {})
    replacements = (
        {
            _normalize_tag(str(before)): _normalize_tag(str(after))
            for before, after in replacements_raw.items()
        }
        if isinstance(replacements_raw, dict)
        else {}
    )
    edited = [replacements.get(tag, tag) for tag in tags if tag not in remove]
    edited.extend(_normalize_tag_list(operation.get("add", [])))
    deduped = list(dict.fromkeys(tag for tag in edited if tag))
    if bool(operation.get("sort", False)):
        deduped.sort()
    return ", ".join(deduped)


def _normalize_tag_list(value: object) -> list[str]:
    if isinstance(value, str):
        values = value.replace("\n", ",").split(",")
    elif isinstance(value, Iterable):
        values = value
    else:
        return []
    return list(dict.fromkeys(_normalize_tag(str(item)) for item in values if str(item).strip()))


def _normalize_tag(value: str) -> str:
    try:
        canonical = resolve_canonical_tag(value)
        return normalize_tag_draft(canonical)
    except (DatasetTaggingError, TagLocaleError) as error:
        raise DatasetWorkspaceError(str(error)) from error


def _split_tags(caption: str) -> list[str]:
    return [tag.strip() for tag in caption.split(",") if tag.strip()]


def _suspicious_tag(tag: str) -> bool:
    return not tag.isascii() or tag != tag.casefold() or " " in tag or "__" in tag


def _change_summary(changes: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    added = 0
    removed = 0
    for change in changes:
        before = set(_split_tags(str(change.get("before", ""))))
        after = set(_split_tags(str(change.get("after", ""))))
        added += len(after - before)
        removed += len(before - after)
    return {"added_instances": added, "removed_instances": removed}


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise DatasetWorkspaceError(f"Invalid JSON object: {path}")
    return loaded


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timestamp_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
