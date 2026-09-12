from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from prompt_hub.config import DEFAULT_TAGGER_MODEL_ID, TaggerModelConfig
from prompt_hub.dataset_curation_records import (
    CaptionProfile,
    JobProgress,
    _caption_record,
    _completed_by_job,
    _completed_vlm_by_job,
    _current_caption,
    _set_caption,
    _state_item,
    _vlm_record,
)
from prompt_hub.dataset_curation_support import (
    _normalize_caption,
    _now,
    _sha256,
    normalize_caption_settings,
    normalize_caption_with_settings,
)
from prompt_hub.dataset_tagging import normalize_tag_draft
from prompt_hub.dataset_workspace import DatasetWorkspaceError
from prompt_hub.local_model import draft_anima_tags, draft_krea2_caption
from prompt_hub.tag_locale import TagLocaleError, translate_caption_with_model
from prompt_hub.wd14 import ProviderMode, WD14Tagger

if TYPE_CHECKING:
    from threading import RLock

    from prompt_hub.config import Settings
    from prompt_hub.dataset_workspace import DatasetWorkspaceStore
    from prompt_hub.model_connections import ModelConnectionStore

Tagger = Callable[[Path], dict[str, object]]
TaggerFactory = Callable[[TaggerModelConfig, ProviderMode], Tagger]
Krea2Captioner = Callable[[Path, str, str, Mapping[str, Any]], dict[str, Any]]


def _batch_failure_message(label: str, failed: int, reasons: list[str]) -> str:
    """整批失败时把最常见的原因说出来。

    只写「共 N 张失败」的话。使用者得自己去翻每一张的记录才知道为什么。
    而整批失败几乎总是同一个原因——送错模型。服务没开。来源不见了。
    """
    base = f"{label} 队列全部失败, 共 {failed} 张"
    if not reasons:
        return base
    top, count = Counter(reasons).most_common(1)[0]
    return f"{base}。{count} 张的原因是 {top}"


def _locale_record(value: object) -> dict[str, Any]:
    record = dict(value) if isinstance(value, dict) else {}
    record.setdefault("status", "empty")
    record.setdefault("source", "")
    record.setdefault("localized", "")
    record.setdefault("updated_at", "")
    record.setdefault("error", "")
    return record


def _krea2_locale_source(item: Mapping[str, Any]) -> str:
    """要对照的是人最终会看的那段英文。

    已经确认的正式说明优先。还没确认时才看视觉草稿。
    """
    caption = _current_caption(item, "krea2")
    if caption:
        return caption
    return str(_vlm_record(item.get("krea2_vlm"))["draft"])


class DatasetCurationJobsMixin:
    settings: Settings
    workspace_store: DatasetWorkspaceStore
    _lock: RLock
    _tagger_factory: TaggerFactory
    _krea2_captioner: Krea2Captioner
    _model_connections: ModelConnectionStore | None

    def read_state(self, workspace_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def _write_state(self, workspace_id: str, state: dict[str, Any]) -> None:
        raise NotImplementedError

    def _require_report(self, workspace_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def _known_record(self, workspace_id: str, relative_path: str) -> dict[str, Any]:
        raise NotImplementedError

    def _write_snapshot(
        self,
        workspace_id: str,
        *,
        operation: str,
        profile_id: CaptionProfile,
        changes: list[dict[str, Any]],
    ) -> str:
        raise NotImplementedError

    def tag_job(self, payload: Mapping[str, Any], context: JobProgress) -> dict[str, Any]:
        workspace_id = str(payload.get("workspace_id", ""))
        if not workspace_id:
            raise DatasetWorkspaceError("WD14 job is missing workspace_id")
        self.workspace_store.require_source(workspace_id)
        caption_settings = normalize_caption_settings("anima", payload)
        provider = str(payload.get("provider", "auto"))
        if provider not in {"auto", "coreml", "cpu"}:
            raise DatasetWorkspaceError("Unsupported WD14 provider")
        tagger_mode = str(payload.get("tagger", "wd14"))
        if tagger_mode not in {"wd14", "model"}:
            raise DatasetWorkspaceError("Unsupported tagger")
        model = str(payload.get("model", "")).strip()
        if tagger_mode == "model" and not model:
            raise DatasetWorkspaceError("使用模型打标时必须选择打标模型")
        try:
            tagger_config = self.settings.tagger_model_config(
                str(payload.get("tagger_model_id", DEFAULT_TAGGER_MODEL_ID))
            )
        except ValueError as error:
            raise DatasetWorkspaceError(str(error)) from error
        paths = self._select_tag_paths(workspace_id, payload)
        job_id = str(getattr(context, "job_id", ""))
        state = self.read_state(workspace_id)
        if tagger_mode == "wd14" and state.get("tagger_model_id") != tagger_config.id:
            state["tagger_model_id"] = tagger_config.id
            self._write_state(workspace_id, state)
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
        label = "模型打标" if tagger_mode == "model" else "WD14"
        context.update(0, len(paths), f"正在准备{label}")
        tagger = (
            None
            if tagger_mode == "model"
            else self._tagger_factory(
                tagger_config,
                provider,  # type: ignore[arg-type]
            )
        )
        completed = 0
        failed = 0
        skipped = 0
        reasons: list[str] = []
        overwrite = bool(payload.get("overwrite", False))
        for index, relative_path in enumerate(paths, start=1):
            context.update(index - 1, len(paths), f"{label} {index}/{len(paths)} · {relative_path}")
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
                if tagger_mode == "model":
                    result = draft_anima_tags(
                        image_path=image_path,
                        model=model,
                        existing_tags=_current_caption(current, "anima"),
                        mode=caption_settings["mode"],
                        trigger=caption_settings["trigger"],
                        media_tags=caption_settings["media_tags"],
                        options=caption_settings["options"],
                        max_tokens=caption_settings["max_tokens"],
                        connections=self._model_connections,
                    )
                elif tagger is not None:
                    tagger_result = tagger(image_path)
                    result = {
                        **tagger_result,
                        "model": tagger_config.model_name,
                        "tagger_model_id": tagger_config.id,
                        "tagger_model_label": tagger_config.label,
                        "general_threshold": tagger_config.general_threshold,
                        "character_threshold": tagger_config.character_threshold,
                        "tag_string": normalize_caption_with_settings(
                            "anima",
                            str(tagger_result.get("tag_string", "")),
                            caption_settings,
                        ),
                        "caption_settings": caption_settings,
                    }
                else:
                    raise DatasetWorkspaceError("WD14 模型尚未准备完成")
            except Exception as error:  # noqa: BLE001
                self._store_tag_failure(
                    workspace_id,
                    state,
                    relative_path,
                    str(error),
                    job_id=job_id,
                    tagger=tagger_mode,
                    model=model,
                )
                reasons.append(str(error))
                failed += 1
            else:
                self._store_tag_result(
                    workspace_id,
                    state,
                    relative_path,
                    result,
                    job_id=job_id,
                    tagger=tagger_mode,
                    model=model,
                )
                completed += 1
            context.update(index, len(paths), f"已处理 {index}/{len(paths)}")
        if paths and completed == 0 and failed:
            raise DatasetWorkspaceError(_batch_failure_message(label, failed, reasons))
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
        self.workspace_store.require_source(workspace_id)
        model = str(payload.get("model", "")).strip()
        if not model:
            raise DatasetWorkspaceError("Krea 2 VLM job is missing model")
        caption_settings = normalize_caption_settings("krea2", payload)
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
        reasons: list[str] = []
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
                reasons.append("图片不存在或扫描后已变更")
                failed += 1
                continue
            item = _state_item(state, relative_path)
            existing_caption = _current_caption(item, "krea2")
            try:
                result = self._krea2_captioner(
                    image_path, model, existing_caption, caption_settings
                )
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
                reasons.append(str(error))
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
            raise DatasetWorkspaceError(_batch_failure_message("Krea 2 VLM", failed, reasons))
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

    def krea2_locale_job(self, payload: Mapping[str, Any], context: JobProgress) -> dict[str, Any]:
        """把一批 Krea 2 英文说明翻成中文供人工对照。

        逐张点「翻译成中文对照」在几百张的数据集上不现实。
        译文只是对照。交付的永远是英文原文——所以这里不碰任何说明文字。
        每张翻完就落盘。中断或重跑时已经翻好的不再送一次模型。
        """
        workspace_id = str(payload.get("workspace_id", ""))
        if not workspace_id:
            raise DatasetWorkspaceError("Krea 2 locale job is missing workspace_id")
        overwrite = bool(payload.get("overwrite", False))
        paths = self._select_krea2_locale_paths(workspace_id, payload)
        completed = 0
        failed = 0
        skipped = 0
        reasons: list[str] = []
        state = self.read_state(workspace_id)
        for index, relative_path in enumerate(paths, start=1):
            context.update(
                index - 1,
                len(paths),
                f"中文对照 {index}/{len(paths)} · {relative_path}",
            )
            item = _state_item(state, relative_path)
            source_text = _krea2_locale_source(item)
            if not source_text:
                skipped += 1
                continue
            existing = _locale_record(item.get("krea2_locale"))
            if not overwrite and existing["localized"] and existing["source"] == source_text:
                skipped += 1
                continue
            try:
                localized = translate_caption_with_model(
                    source_text,
                    connections=self._model_connections,
                )
            except TagLocaleError as error:
                reasons.append(str(error))
                self._store_krea2_locale(workspace_id, relative_path, source_text, "", str(error))
                failed += 1
                continue
            if not localized:
                reason = "翻译服务没有返回结果"
                reasons.append(reason)
                self._store_krea2_locale(workspace_id, relative_path, source_text, "", reason)
                failed += 1
                continue
            self._store_krea2_locale(workspace_id, relative_path, source_text, localized, "")
            completed += 1
        context.update(len(paths), len(paths), f"已翻译 {completed}/{len(paths)}")
        if paths and completed == 0 and failed:
            raise DatasetWorkspaceError(_batch_failure_message("中文对照", failed, reasons))
        return {
            "workspace_id": workspace_id,
            "requested": len(paths),
            "completed": completed,
            "failed": failed,
            "skipped": skipped,
        }

    def _select_krea2_locale_paths(
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
        scope = str(payload.get("scope", "selected"))
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
        if scope == "missing":
            state = self.read_state(workspace_id)
            missing = []
            for path in valid:
                item = _state_item(state, path)
                source_text = _krea2_locale_source(item)
                locale = _locale_record(item.get("krea2_locale"))
                if source_text and (not locale["localized"] or locale["source"] != source_text):
                    missing.append(path)
            return missing
        raise DatasetWorkspaceError("Unsupported Krea 2 locale queue scope")

    def _store_krea2_locale(
        self,
        workspace_id: str,
        relative_path: str,
        source_text: str,
        localized: str,
        error: str,
    ) -> None:
        with self._lock:
            latest = self.read_state(workspace_id)
            item = _state_item(latest, relative_path)
            item["krea2_locale"] = {
                "status": "completed" if localized else "failed",
                "source": source_text,
                "localized": localized,
                "updated_at": _now(),
                "error": error,
            }
            self._write_state(workspace_id, latest)

    def confirm_krea2_drafts(
        self,
        workspace_id: str,
        paths: Iterable[str],
        *,
        overwrite_reviewed: bool = False,
    ) -> dict[str, Any]:
        """把一批已有草稿的 Krea 2 视觉草稿一次写入正式说明。

        逐张确认在人工审核阶段太慢。一个数据集几百张。全部要开详情页再点一次。
        这里只处理已经有草稿的图片。并且默认不覆盖人工确认过的说明——
        批量操作看不到每一张的内容。覆盖别人手写的判断没有回头路。
        真要覆盖时由调用方显式传 overwrite_reviewed。
        """
        requested = [path for path in dict.fromkeys(str(path) for path in paths) if path]
        if not requested:
            raise DatasetWorkspaceError("请先选择要写入 Krea 2 的图片")
        for relative_path in requested:
            self._known_record(workspace_id, relative_path)
        skipped_empty: list[str] = []
        skipped_unchanged: list[str] = []
        skipped_reviewed: list[str] = []
        with self._lock:
            state = self.read_state(workspace_id)
            pending: list[tuple[dict[str, Any], dict[str, Any], str]] = []
            changes: list[dict[str, str]] = []
            for relative_path in requested:
                item = _state_item(state, relative_path)
                vlm = _vlm_record(item.get("krea2_vlm"))
                draft = _normalize_caption("krea2", str(vlm.get("draft", "")))
                if not draft:
                    skipped_empty.append(relative_path)
                    continue
                before = _current_caption(item, "krea2")
                if before == draft:
                    skipped_unchanged.append(relative_path)
                    continue
                caption = _caption_record(item["captions"]["krea2"])
                if not overwrite_reviewed and caption.get("status") == "reviewed":
                    skipped_reviewed.append(relative_path)
                    continue
                pending.append((item, vlm, draft))
                changes.append({"relative_path": relative_path, "before": before, "after": draft})
            snapshot = ""
            if changes:
                snapshot = self._write_snapshot(
                    workspace_id,
                    operation="confirm-krea2-vlm-batch",
                    profile_id="krea2",
                    changes=changes,
                )
                confirmed_at = _now()
                for item, vlm, draft in pending:
                    vlm.update(
                        {
                            "status": "confirmed",
                            "draft": draft,
                            "edited_at": confirmed_at,
                            "error": "",
                            "confirmed_at": confirmed_at,
                            "confirmed_snapshot": snapshot,
                        }
                    )
                    _set_caption(
                        item,
                        "krea2",
                        draft,
                        status="reviewed",
                        source="vlm-confirmed",
                        snapshot=snapshot,
                    )
                    item["krea2_vlm"] = vlm
                self._write_state(workspace_id, state)
        return {
            "workspace_id": workspace_id,
            "requested": len(requested),
            "confirmed": len(changes),
            "skipped_empty": len(skipped_empty),
            "skipped_unchanged": len(skipped_unchanged),
            "skipped_reviewed": len(skipped_reviewed),
            "skipped_reviewed_paths": skipped_reviewed[:50],
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

    def _default_tagger_factory(
        self,
        config: TaggerModelConfig,
        provider: ProviderMode,
    ) -> Tagger:
        return WD14Tagger(
            model_root=self.settings.tagger_model_root(config.id),
            model_name=config.model_name,
            general_threshold=config.general_threshold,
            character_threshold=config.character_threshold,
            provider=provider,
        ).tag

    @staticmethod
    def _default_krea2_captioner(
        image_path: Path,
        model: str,
        existing_caption: str,
        caption_settings: Mapping[str, Any],
    ) -> dict[str, Any]:
        return draft_krea2_caption(
            image_path=image_path,
            model=model,
            existing_caption=existing_caption,
            mode=caption_settings["mode"],
            trigger=str(caption_settings["trigger"]),
            media_tags=bool(caption_settings["media_tags"]),
            options=dict(caption_settings["options"]),
            max_tokens=int(caption_settings["max_tokens"]),
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
                "caption_settings": result.get("caption_settings", {}),
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
        tagger: str = "wd14",
        model: str = "",
    ) -> None:
        with self._lock:
            latest = self.read_state(workspace_id)
            item = _state_item(latest, relative_path)
            draft = normalize_tag_draft(str(result.get("tag_string", "")))
            item["wd14"] = {
                "status": "completed",
                "job_id": job_id,
                "tagger": tagger,
                "model": str(result.get("model", "SmilingWolf/wd-swinv2-tagger-v3")),
                "tagger_model_id": str(result.get("tagger_model_id", "")),
                "tagger_model_label": str(result.get("tagger_model_label", "")),
                "provider": str(result.get("provider", "")),
                "tagged_at": _now(),
                "general_threshold": result.get(
                    "general_threshold",
                    self.settings.wd14_general_threshold,
                ),
                "character_threshold": result.get(
                    "character_threshold",
                    self.settings.wd14_character_threshold,
                ),
                "caption_settings": result.get("caption_settings", {}),
                "rating": result.get("rating"),
                "general": result.get("general", []),
                "characters": result.get("characters", []),
                "elapsed_seconds": result.get("elapsed_seconds"),
                "safety_warning": str(result.get("safety_warning", ""))[:2000],
                "error": "",
            }
            if tagger == "model" and model:
                item["wd14"]["model"] = model
            current = _caption_record(item.get("captions", {}).get("anima"))
            if current["status"] != "reviewed":
                _set_caption(
                    item,
                    "anima",
                    draft,
                    status="draft",
                    source=tagger,
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
        tagger: str = "wd14",
        model: str = "",
    ) -> None:
        with self._lock:
            latest = self.read_state(workspace_id)
            item = _state_item(latest, relative_path)
            item["wd14"] = {
                "status": "failed",
                "job_id": job_id,
                "tagger": tagger,
                "model": model,
                "error": error[:2000],
                "tagged_at": _now(),
            }
            self._write_state(workspace_id, latest)
            state.clear()
            state.update(latest)
