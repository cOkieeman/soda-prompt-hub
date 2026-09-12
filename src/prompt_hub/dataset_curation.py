from __future__ import annotations

import re
from collections import Counter
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from prompt_hub.config import DEFAULT_TAGGER_MODEL_ID
from prompt_hub.dataset_curation_export import DatasetExportMixin
from prompt_hub.dataset_curation_jobs import (
    DatasetCurationJobsMixin,
    Krea2Captioner,
    TaggerFactory,
)
from prompt_hub.dataset_curation_records import (
    CaptionProfile,
    _caption_record,
    _current_caption,
    _set_caption,
    _snapshot_profile,
    _state_item,
    _vlm_record,
)
from prompt_hub.dataset_curation_support import (
    _apply_krea2_operation,
    _apply_tag_operation,
    _atomic_json_write,
    _change_summary,
    _load_json,
    _normalize_caption,
    _normalize_tag_list,
    _now,
    _operation_profile,
    _split_tags,
    _suspicious_tag,
    _timestamp_token,
    is_prepend_only_operation,
    normalize_caption_settings,
    normalize_caption_with_settings,
)
from prompt_hub.dataset_workspace import DatasetWorkspaceError, DatasetWorkspaceStore

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from prompt_hub.config import Settings
    from prompt_hub.model_connections import ModelConnectionStore

CURATION_FORMAT = "soda-prompt-hub-dataset-curation-v1"
LOW_FREQUENCY_MAX = 2
MIN_CONFLICT_TAGS = 2
DEFAULT_CONFLICT_RULES = [
    {"rule_id": "hair-grey-white", "tags": ["grey_hair", "white_hair"]},
    {"rule_id": "hair-black-white", "tags": ["black_hair", "white_hair"]},
    {"rule_id": "subject-girl-boy", "tags": ["1girl", "1boy"]},
    {"rule_id": "count-solo-multiple", "tags": ["solo", "multiple_girls"]},
]


class DatasetCurationStore(DatasetCurationJobsMixin, DatasetExportMixin):
    def __init__(
        self,
        settings: Settings,
        workspace_store: DatasetWorkspaceStore,
        *,
        tagger_factory: TaggerFactory | None = None,
        krea2_captioner: Krea2Captioner | None = None,
        model_connections: ModelConnectionStore | None = None,
    ) -> None:
        self.settings = settings
        self.workspace_store = workspace_store
        self._lock = RLock()
        self._tagger_factory = tagger_factory or self._default_tagger_factory
        self._krea2_captioner = krea2_captioner or self._default_krea2_captioner
        self._model_connections = model_connections

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
        report["tagger_model_id"] = str(state.get("tagger_model_id", DEFAULT_TAGGER_MODEL_ID))
        return report

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
        caption_settings: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._known_record(workspace_id, relative_path)
        clean = (
            normalize_caption_with_settings(
                profile_id,
                caption,
                normalize_caption_settings(profile_id, caption_settings),
            )
            if caption_settings is not None
            else _normalize_caption(profile_id, caption)
        )
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
        profile_id = _operation_profile(operation)
        changes = []
        for relative_path in dict.fromkeys(str(path) for path in paths):
            self._known_record(workspace_id, relative_path)
            item = _state_item(state, relative_path)
            before = _current_caption(item, profile_id)
            after = (
                _apply_tag_operation(before, operation)
                if profile_id == "anima"
                else _apply_krea2_operation(before, operation)
            )
            if before != after:
                changes.append({"relative_path": relative_path, "before": before, "after": after})
        return {
            "workspace_id": workspace_id,
            "profile_id": profile_id,
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
                operation=f"bulk-{preview['profile_id']}-caption",
                profile_id=preview["profile_id"],
                changes=changes,
            )
            state = self.read_state(workspace_id)
            keep_status = is_prepend_only_operation(operation)
            for change in changes:
                item = _state_item(state, str(change["relative_path"]))
                before = _caption_record(item.get("captions", {}).get(preview["profile_id"]))
                confirmed = keep_status and str(before.get("status", "")) == "reviewed"
                _set_caption(
                    item,
                    preview["profile_id"],
                    str(change["after"]),
                    status="reviewed" if confirmed else "draft",
                    source="prepend-trigger" if keep_status else "bulk-edit",
                    snapshot=snapshot,
                )
            self._write_state(workspace_id, state)
        return {**preview, "snapshot": snapshot}

    def confirm_captions(
        self,
        workspace_id: str,
        paths: Iterable[str],
        *,
        profile_id: CaptionProfile,
    ) -> dict[str, Any]:
        """把一批已经有内容的说明标记为人工确认。

        说明文字本身一个字都不改。改的只是「这段我看过了」这个判断。
        接续原说明、批量整理都会落成草稿。交付前检查要求确认过。
        没有这条路的话。几百张就得一张一张开详情页点确认。
        空白的说明不会被确认——确认一段不存在的内容没有意义。
        """
        requested = [path for path in dict.fromkeys(str(path) for path in paths) if path]
        if not requested:
            raise DatasetWorkspaceError("请先选择要确认说明的图片")
        for relative_path in requested:
            self._known_record(workspace_id, relative_path)
        skipped_empty = 0
        skipped_reviewed = 0
        with self._lock:
            state = self.read_state(workspace_id)
            pending: list[tuple[str, dict[str, Any], str]] = []
            for relative_path in requested:
                item = _state_item(state, relative_path)
                record = _caption_record(item["captions"][profile_id])
                caption = str(record["current"]).strip()
                if not caption:
                    skipped_empty += 1
                    continue
                if str(record.get("status", "")) == "reviewed":
                    skipped_reviewed += 1
                    continue
                pending.append((relative_path, item, str(record["current"])))
            snapshot = ""
            if pending:
                snapshot = self._write_snapshot(
                    workspace_id,
                    operation=f"confirm-{profile_id}-caption",
                    profile_id=profile_id,
                    changes=[
                        {"relative_path": relative_path, "before": caption, "after": caption}
                        for relative_path, _item, caption in pending
                    ],
                )
                for _relative_path, item, caption in pending:
                    _set_caption(
                        item,
                        profile_id,
                        caption,
                        status="reviewed",
                        source="manual-confirmed",
                        snapshot=snapshot,
                    )
                self._write_state(workspace_id, state)
        return {
            "workspace_id": workspace_id,
            "profile_id": profile_id,
            "requested": len(requested),
            "confirmed": len(pending),
            "skipped_empty": skipped_empty,
            "skipped_reviewed": skipped_reviewed,
            "snapshot": snapshot,
        }

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
