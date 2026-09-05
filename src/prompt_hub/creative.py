from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from prompt_hub.schema_migrations import record_schema_migration

SLOT_ORDER = (
    "character",
    "outfit",
    "action",
    "composition",
    "scene",
    "lighting",
    "style",
)

SLOT_LABELS = {
    "character": "角色",
    "outfit": "服装",
    "action": "动作",
    "composition": "构图",
    "scene": "场景",
    "lighting": "灯光",
    "style": "画风",
}

KREA2_SLOT_LABELS = {
    "character": "Character",
    "outfit": "Outfit",
    "action": "Action",
    "composition": "Composition",
    "scene": "Scene",
    "lighting": "Lighting",
    "style": "Style",
}

SAFETY_MODES = ("sfw", "suggestive", "adult", "explicit-adult")
PROFILE_IDS = ("anima", "krea2")

CREATIVE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS creative_projects (
    project_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    brief_zh TEXT NOT NULL DEFAULT '',
    safety_mode TEXT NOT NULL DEFAULT 'sfw'
        CHECK (safety_mode IN ('sfw', 'suggestive', 'adult', 'explicit-adult')),
    target_profile TEXT NOT NULL DEFAULT 'anima'
        CHECK (target_profile IN ('anima', 'krea2')),
    character_id TEXT NOT NULL DEFAULT '',
    slots_json TEXT NOT NULL DEFAULT '{}',
    slot_locks_json TEXT NOT NULL DEFAULT '{}',
    references_json TEXT NOT NULL DEFAULT '[]',
    generation_json TEXT NOT NULL DEFAULT '{}',
    lineage_json TEXT NOT NULL DEFAULT '{}',
    test_notes TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_creative_projects_updated
ON creative_projects(updated_at DESC);

CREATE TABLE IF NOT EXISTS creative_recipes (
    recipe_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    favorite INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_creative_recipes_updated
ON creative_recipes(updated_at DESC);
"""


class CreativeStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(CREATIVE_SCHEMA)
            record_schema_migration(
                connection,
                "creative_store",
                1,
                "Creative projects and recipes baseline",
            )
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(creative_projects)").fetchall()
            }
            if "lineage_json" not in columns:
                connection.execute(
                    "ALTER TABLE creative_projects "
                    "ADD COLUMN lineage_json TEXT NOT NULL DEFAULT '{}'"
                )
            record_schema_migration(
                connection,
                "creative_store",
                2,
                "Creative project lineage",
            )
            connection.commit()

    def create_project(self, values: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = normalize_project(values or {})
        now = _now()
        project_id = f"project-{uuid4().hex}"
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO creative_projects (
                    project_id, title, brief_zh, safety_mode, target_profile,
                    character_id, slots_json, slot_locks_json, references_json,
                    generation_json, lineage_json, test_notes, revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    project_id,
                    payload["title"],
                    payload["brief_zh"],
                    payload["safety_mode"],
                    payload["target_profile"],
                    payload["character_id"],
                    _dump(payload["slots"]),
                    _dump(payload["slot_locks"]),
                    _dump(payload["references"]),
                    _dump(payload["generation"]),
                    _dump(payload["lineage"]),
                    payload["test_notes"],
                    now,
                    now,
                ),
            )
            connection.commit()
        project = self.get_project(project_id)
        if project is None:  # pragma: no cover - guarded by the insert above
            raise RuntimeError("Creative project was not created")
        return project

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM creative_projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return _project_from_row(row) if row is not None else None

    def list_projects(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM creative_projects ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_project_from_row(row) for row in rows]

    def update_project(self, project_id: str, values: Mapping[str, Any]) -> dict[str, Any]:
        current = self.get_project(project_id)
        if current is None:
            raise KeyError(project_id)
        merged = {**current, **values}
        payload = normalize_project(merged)
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE creative_projects SET
                    title = ?, brief_zh = ?, safety_mode = ?, target_profile = ?,
                    character_id = ?, slots_json = ?, slot_locks_json = ?,
                    references_json = ?, generation_json = ?, lineage_json = ?, test_notes = ?,
                    revision = revision + 1, updated_at = ?
                WHERE project_id = ?
                """,
                (
                    payload["title"],
                    payload["brief_zh"],
                    payload["safety_mode"],
                    payload["target_profile"],
                    payload["character_id"],
                    _dump(payload["slots"]),
                    _dump(payload["slot_locks"]),
                    _dump(payload["references"]),
                    _dump(payload["generation"]),
                    _dump(payload["lineage"]),
                    payload["test_notes"],
                    _now(),
                    project_id,
                ),
            )
            connection.commit()
        project = self.get_project(project_id)
        if project is None:  # pragma: no cover - guarded by the update above
            raise RuntimeError("Creative project disappeared during update")
        return project

    def save_recipe(
        self,
        project_id: str,
        name: str,
        *,
        favorite: bool = False,
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        if project is None:
            raise KeyError(project_id)
        now = _now()
        recipe_id = f"recipe-{uuid4().hex}"
        snapshot = export_project(project)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO creative_recipes (
                    recipe_id, project_id, name, snapshot_json, favorite,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe_id,
                    project_id,
                    name.strip() or project["title"],
                    _dump(snapshot),
                    int(favorite),
                    now,
                    now,
                ),
            )
            connection.commit()
        recipe = self.get_recipe(recipe_id)
        if recipe is None:  # pragma: no cover - guarded by the insert above
            raise RuntimeError("Creative recipe was not created")
        return recipe

    def get_recipe(self, recipe_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM creative_recipes WHERE recipe_id = ?",
                (recipe_id,),
            ).fetchone()
        return _recipe_from_row(row) if row is not None else None

    def list_recipes(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM creative_recipes ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_recipe_from_row(row) for row in rows]


def empty_slots() -> dict[str, str]:
    return dict.fromkeys(SLOT_ORDER, "")


def empty_locks() -> dict[str, bool]:
    return dict.fromkeys(SLOT_ORDER, False)


def normalize_project(values: Mapping[str, Any]) -> dict[str, Any]:
    slots_value = values.get("slots")
    locks_value = values.get("slot_locks")
    raw_slots: Mapping[str, Any] = slots_value if isinstance(slots_value, Mapping) else {}
    raw_locks: Mapping[str, Any] = locks_value if isinstance(locks_value, Mapping) else {}
    raw_references = values.get("references")
    raw_generation = values.get("generation")
    raw_lineage = values.get("lineage")
    safety_mode = str(values.get("safety_mode", "sfw"))
    target_profile = str(values.get("target_profile", "anima"))
    return {
        "title": str(values.get("title", "未命名绘图项目")).strip() or "未命名绘图项目",
        "brief_zh": str(values.get("brief_zh", "")).strip(),
        "safety_mode": safety_mode if safety_mode in SAFETY_MODES else "sfw",
        "target_profile": target_profile if target_profile in PROFILE_IDS else "anima",
        "character_id": str(values.get("character_id", "")).strip(),
        "slots": {slot: str(raw_slots.get(slot, "")).strip() for slot in SLOT_ORDER},
        "slot_locks": {slot: bool(raw_locks.get(slot, False)) for slot in SLOT_ORDER},
        "references": list(raw_references) if isinstance(raw_references, list) else [],
        "generation": dict(raw_generation) if isinstance(raw_generation, Mapping) else {},
        "lineage": dict(raw_lineage) if isinstance(raw_lineage, Mapping) else {},
        "test_notes": str(values.get("test_notes", "")).strip(),
    }


def next_iteration_values(
    project: Mapping[str, Any],
    asset: Mapping[str, Any],
    analysis: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = normalize_project(project)
    parent_lineage = normalized["lineage"]
    try:
        parent_iteration = max(1, int(parent_lineage.get("iteration", 1)))
    except (TypeError, ValueError):
        parent_iteration = 1
    iteration = parent_iteration + 1
    parent_project_id = str(project.get("project_id", "")).strip()
    root_project_id = str(parent_lineage.get("root_project_id", "")).strip()
    if not root_project_id:
        root_project_id = parent_project_id
    title = _iteration_title(normalized["title"], iteration)
    generation = dict(normalized["generation"])
    generation.pop("result_assets", None)
    generation["result_images"] = []
    summary = str(analysis.get("summary_zh", "")).strip()
    issues = _clean_review_items(analysis.get("issues", []))
    improvements = _clean_review_items(analysis.get("improvements", []))
    strengths = _clean_review_items(analysis.get("strengths", []))
    observed_value = analysis.get("observed_slots", {})
    observed = observed_value if isinstance(observed_value, Mapping) else {}
    prompts_value = analysis.get("reconstructed_prompts", {})
    prompts = dict(prompts_value) if isinstance(prompts_value, Mapping) else {}
    source_filename = str(asset.get("filename", "结果图")).strip() or "结果图"
    review = {
        "model": str(analysis.get("model", "本地视觉模型")).strip(),
        "summary_zh": summary,
        "observed_slots": {slot: str(observed.get(slot, "")).strip() for slot in SLOT_ORDER},
        "strengths": strengths,
        "issues": issues,
        "improvements": improvements,
        "reconstructed_prompts": {
            key: str(prompts.get(key, "")).strip()
            for key in ("anima_positive", "anima_negative", "krea2_positive", "krea2_avoid")
        },
        "safety_warning": str(analysis.get("safety_warning", "")).strip(),
    }
    lineage = {
        "iteration": iteration,
        "root_project_id": root_project_id,
        "parent_project_id": parent_project_id,
        "parent_iteration": parent_iteration,
        "source_asset_id": str(asset.get("asset_id", "")).strip(),
        "source_asset_filename": source_filename,
        "created_from": "result-review",
        "review": review,
    }
    iteration_lines = [
        f"[创作迭代 · V{iteration}]",
        f"基于 V{parent_iteration} 的结果图：{source_filename}",
    ]
    if summary:
        iteration_lines.append(f"复盘摘要：{summary}")
    if improvements:
        iteration_lines.append("下一轮：" + "；".join(improvements))
    notes = "\n\n".join(
        part for part in (normalized["test_notes"], "\n".join(iteration_lines)) if part
    )[:6000]
    return {
        **normalized,
        "title": title,
        "generation": generation,
        "lineage": lineage,
        "test_notes": notes,
    }


def iteration_context(
    project: Mapping[str, Any],
    parent: Mapping[str, Any] | None,
) -> dict[str, Any]:
    current = normalize_project(project)
    lineage = current["lineage"]
    review_value = lineage.get("review", {})
    review = review_value if isinstance(review_value, Mapping) else {}
    observed_value = review.get("observed_slots", {})
    observed = observed_value if isinstance(observed_value, Mapping) else {}
    normalized_parent = normalize_project(parent) if parent is not None else None
    changes = []
    applicable_slots = []
    for slot in SLOT_ORDER:
        previous = normalized_parent["slots"].get(slot, "") if normalized_parent else ""
        current_value = current["slots"].get(slot, "")
        suggested = str(observed.get(slot, "")).strip()
        locked = current["slot_locks"].get(slot, False)
        if normalized_parent is None:
            status = "unknown"
        elif previous == current_value:
            status = "unchanged"
        elif not previous:
            status = "added"
        elif not current_value:
            status = "removed"
        else:
            status = "changed"
        applicable = bool(suggested and not current_value and not locked)
        if applicable:
            applicable_slots.append(slot)
        changes.append(
            {
                "slot": slot,
                "previous": previous,
                "current": current_value,
                "suggested": suggested,
                "status": status,
                "locked": locked,
                "applicable": applicable,
            }
        )
    return {
        "iteration": _positive_int(lineage.get("iteration"), 1),
        "parent_iteration": _positive_int(lineage.get("parent_iteration"), 0),
        "parent_project_id": str(lineage.get("parent_project_id", "")).strip(),
        "parent_available": normalized_parent is not None,
        "source_asset_id": str(lineage.get("source_asset_id", "")).strip(),
        "source_asset_filename": str(lineage.get("source_asset_filename", "")).strip(),
        "review": dict(review),
        "changes": changes,
        "applicable_slots": applicable_slots,
    }


def apply_iteration_suggestions(project: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_project(project)
    review_value = normalized["lineage"].get("review", {})
    review = review_value if isinstance(review_value, Mapping) else {}
    observed_value = review.get("observed_slots", {})
    observed = observed_value if isinstance(observed_value, Mapping) else {}
    slots = dict(normalized["slots"])
    applied_slots = []
    for slot in SLOT_ORDER:
        if normalized["slot_locks"].get(slot, False) or slots.get(slot, ""):
            continue
        suggested = str(observed.get(slot, "")).strip()
        if suggested:
            slots[slot] = suggested
            applied_slots.append(slot)
    notes = normalized["test_notes"]
    if applied_slots:
        marker = "[迭代建议已应用] " + "、".join(applied_slots)
        notes = "\n\n".join(part for part in (notes, marker) if part)[:6000]
    return {"slots": slots, "test_notes": notes, "applied_slots": applied_slots}


def compile_prompt(project: Mapping[str, Any], profile_id: str | None = None) -> dict[str, Any]:
    normalized = normalize_project(project)
    profile = profile_id or normalized["target_profile"]
    if profile not in PROFILE_IDS:
        raise ValueError(f"Unknown creative profile: {profile}")
    return _compile_anima(normalized) if profile == "anima" else _compile_krea2(normalized)


def export_project(project: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_project(project)
    return {
        "format": "soda-prompt-hub-creative-v1",
        "exported_at": _now(),
        "project": {
            key: project.get(key, normalized.get(key))
            for key in (
                "project_id",
                "title",
                "brief_zh",
                "safety_mode",
                "character_id",
                "slots",
                "slot_locks",
                "references",
                "generation",
                "lineage",
                "test_notes",
                "revision",
                "created_at",
                "updated_at",
            )
        },
        "outputs": {
            "anima": compile_prompt(normalized, "anima"),
            "krea2": compile_prompt(normalized, "krea2"),
        },
    }


def apply_result_review(
    project: Mapping[str, Any],
    analysis: Mapping[str, Any],
    *,
    fill_empty_slots: bool,
) -> dict[str, Any]:
    normalized = normalize_project(project)
    slots = dict(normalized["slots"])
    observed = analysis.get("observed_slots", {})
    observed_slots = observed if isinstance(observed, Mapping) else {}
    if fill_empty_slots:
        for slot in SLOT_ORDER:
            if normalized["slot_locks"].get(slot, False) or slots.get(slot, ""):
                continue
            value = str(observed_slots.get(slot, "")).strip()
            if value:
                slots[slot] = value
    review_lines = [f"[视觉复盘 · {str(analysis.get('model', '本地模型')).strip()}]"]
    summary = str(analysis.get("summary_zh", "")).strip()
    if summary:
        review_lines.append(summary)
    for key, label in (("strengths", "优点"), ("issues", "问题"), ("improvements", "下一轮")):
        raw_items = analysis.get(key, [])
        items = raw_items if isinstance(raw_items, list) else [raw_items]
        clean = [str(item).strip() for item in items if str(item).strip()]
        if clean:
            review_lines.append(f"{label}：" + "；".join(clean[:6]))
    warning = str(analysis.get("safety_warning", "")).strip()
    if warning:
        review_lines.append(f"安全提示：{warning}")
    existing = normalized["test_notes"]
    combined = "\n\n".join(part for part in (existing, "\n".join(review_lines)) if part)
    return {"slots": slots, "test_notes": combined[:6000]}


def _compile_anima(project: Mapping[str, Any]) -> dict[str, Any]:
    tags = ["masterpiece", "best quality", "very aesthetic"]
    for slot in SLOT_ORDER:
        tags.extend(_split_tags(str(project["slots"].get(slot, ""))))
    positive = ", ".join(_dedupe(tags))
    negatives = [
        "lowres",
        "worst quality",
        "low quality",
        "blurry",
        "bad anatomy",
        "bad hands",
        "text",
        "watermark",
    ]
    safety_mode = str(project["safety_mode"])
    if safety_mode == "sfw":
        negatives.extend(("nsfw", "nude", "explicit"))
    elif safety_mode == "suggestive":
        negatives.extend(("explicit sexual content", "genital focus"))
    warnings = _common_warnings(project)
    contains_cjk = any(_contains_cjk(str(value)) for value in project["slots"].values() if value)
    if contains_cjk:
        warnings.append("Anima 更适合英文 Booru 标签；当前中文内容可先用本地模型转换，再确认写回。")
    return {
        "profile_id": "anima",
        "profile_name": "Anima / Booru tags",
        "positive": positive,
        "negative": ", ".join(_dedupe(negatives)),
        "warnings": warnings,
        "safety_mode": safety_mode,
        "output_language": "mixed" if contains_cjk else "en",
        "ready": bool(positive) and not contains_cjk,
    }


def _compile_krea2(project: Mapping[str, Any]) -> dict[str, Any]:
    clauses = []
    for slot in SLOT_ORDER:
        value = str(project["slots"].get(slot, "")).strip().rstrip(".。")
        if value:
            clauses.append(f"{KREA2_SLOT_LABELS[slot]}: {value}")
    brief = str(project["brief_zh"]).strip()
    if brief and not _contains_cjk(brief):
        clauses.insert(0, f"Creative intent: {brief.rstrip('.')}")
    positive = ". ".join(clauses)
    if positive and not positive.endswith((".", "!")):
        positive += "."
    negative = "Avoid low resolution, blur, bad anatomy, malformed hands, text, and watermarks."
    safety_mode = str(project["safety_mode"])
    if safety_mode == "sfw":
        negative += " Keep the image non-explicit; avoid nudity and explicit sexual content."
    elif safety_mode == "suggestive":
        negative += " Avoid explicit sexual acts and genital close-ups."
    warnings = _common_warnings(project)
    contains_cjk = _contains_cjk(positive)
    if brief and _contains_cjk(brief):
        warnings.append(
            "Krea 2 最终输出只使用英文；中文创作想法未自动拼入 Prompt，请先完成英文转换。"
        )
    if contains_cjk:
        warnings.append("Krea 2 槽位仍含中文，当前输出未就绪；请先转换为英文自然语言。")
    if any(len(_split_tags(str(value))) >= 10 for value in project["slots"].values() if value):
        warnings.append("Krea 2 更适合连贯描述；当前槽位偏标签堆叠，可用本地模型润色为自然语言。")
    return {
        "profile_id": "krea2",
        "profile_name": "Krea 2 / natural language",
        "positive": positive,
        "negative": negative,
        "warnings": warnings,
        "safety_mode": safety_mode,
        "output_language": "mixed" if contains_cjk else "en",
        "ready": bool(positive) and not contains_cjk,
    }


def _common_warnings(project: Mapping[str, Any]) -> list[str]:
    warnings = []
    if not any(str(value).strip() for value in project["slots"].values()):
        warnings.append("七个槽位还是空的；先填写角色、服装或场景中的至少一项。")
    if not project["slots"].get("character"):
        warnings.append("角色槽位为空，主体一致性可能较弱。")
    return warnings


def _split_tags(value: str) -> list[str]:
    compact = value.replace("\n", ",").replace("，", ",").replace(";", ",").replace("；", ",")
    return [part.strip().rstrip(".。") for part in compact.split(",") if part.strip()]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _contains_cjk(value: str) -> bool:
    return any("\u3400" <= character <= "\u9fff" for character in value)


def _project_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "project_id": row["project_id"],
        "title": row["title"],
        "brief_zh": row["brief_zh"],
        "safety_mode": row["safety_mode"],
        "target_profile": row["target_profile"],
        "character_id": row["character_id"],
        "slots": _load(row["slots_json"], empty_slots()),
        "slot_locks": _load(row["slot_locks_json"], empty_locks()),
        "references": _load(row["references_json"], []),
        "generation": _load(row["generation_json"], {}),
        "lineage": _load(row["lineage_json"], {}),
        "test_notes": row["test_notes"],
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _recipe_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "recipe_id": row["recipe_id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "snapshot": _load(row["snapshot_json"], {}),
        "favorite": bool(row["favorite"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _iteration_title(title: str, iteration: int) -> str:
    base, separator, suffix = title.rpartition(" · V")
    if separator and suffix.isdigit():
        title = base
    return f"{title.strip()} · V{iteration}"


def _clean_review_items(value: Any) -> list[str]:
    items = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in items if str(item).strip()][:6]


def _positive_int(value: Any, default: int) -> int:
    try:
        return max(default, int(value))
    except (TypeError, ValueError):
        return default


def _load(value: str, default: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _now() -> str:
    return datetime.now(UTC).isoformat()
