from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote
from uuid import uuid4

CONCEPT_TYPES = {"character", "outfit", "character_outfit", "style"}
ASSET_STATUSES = {"candidate", "approved", "excluded", "needs_more", "regularization"}
TARGET_FAMILIES = {"anima", "krea2"}
RISK_FLAGS = {
    "character_inconsistent",
    "outfit_contamination",
    "background_bias",
    "anatomy_issue",
    "concept_drift",
}
RISK_LABELS_ZH = {
    "character_inconsistent": "角色特征不一致",
    "outfit_contamination": "服装概念污染",
    "background_bias": "背景偏置",
    "anatomy_issue": "肢体结构问题",
    "concept_drift": "概念漂移",
}

COVERAGE_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "shot": ("close_up", "upper_body", "cowboy_shot", "full_body", "detail"),
    "view": ("front", "three_quarter", "profile", "back", "high_angle", "low_angle"),
    "pose": ("standing", "sitting", "walking", "turning", "dynamic", "interaction"),
    "expression": ("neutral", "smile", "serious", "angry", "sad", "surprised"),
    "outfit": ("default", "alternate", "casual", "formal", "themed"),
    "background": ("simple", "indoor", "outdoor", "urban", "nature"),
    "lighting": ("soft", "dramatic", "backlight", "night", "daylight"),
    "composition": ("centered", "rule_of_thirds", "portrait", "landscape", "dynamic"),
}

COVERAGE_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "shot": {
        "close_up": ("close up", "closeup", "headshot", "face closeup"),
        "upper_body": ("upper body", "bust shot", "waist up"),
        "cowboy_shot": ("cowboy shot", "thigh up", "knee up"),
        "full_body": ("full body", "full length"),
        "detail": ("detail shot", "detail view", "close detail"),
    },
    "view": {
        "front": ("front view", "from front", "facing viewer", "looking at viewer"),
        "three_quarter": ("three quarter", "3 4 view"),
        "profile": ("profile view", "side view", "from side"),
        "back": ("back view", "from behind"),
        "high_angle": ("high angle", "from above", "bird eye view"),
        "low_angle": ("low angle", "from below", "worm eye view"),
    },
    "pose": {
        "standing": ("standing",),
        "sitting": ("sitting", "seated"),
        "walking": ("walking",),
        "turning": ("looking back", "turning back", "over shoulder"),
        "dynamic": ("dynamic pose", "action pose"),
        "interaction": ("holding hands", "hugging", "interacting"),
    },
    "expression": {
        "neutral": ("neutral expression",),
        "smile": ("smile", "smiling"),
        "serious": ("serious",),
        "angry": ("angry",),
        "sad": ("sad",),
        "surprised": ("surprised",),
    },
    "outfit": {
        "alternate": ("alternate outfit", "alternate costume"),
        "casual": ("casual clothes", "casual outfit"),
        "formal": ("formal wear", "formal outfit", "business suit"),
        "themed": ("themed outfit", "stage costume", "fantasy costume"),
    },
    "background": {
        "simple": ("simple background", "plain background"),
        "indoor": ("indoors", "indoor background", "interior"),
        "outdoor": ("outdoors", "outdoor background", "exterior"),
        "urban": ("urban", "city", "cityscape", "street"),
        "nature": ("nature", "forest", "garden", "mountain", "beach"),
    },
    "lighting": {
        "soft": ("soft lighting", "soft light", "diffused light"),
        "dramatic": ("dramatic lighting", "chiaroscuro"),
        "backlight": ("backlight", "backlighting", "backlit"),
        "night": ("night lighting", "night scene", "moonlight"),
        "daylight": ("daylight", "sunlight", "daytime"),
    },
    "composition": {
        "centered": ("centered", "center composition", "symmetrical composition"),
        "rule_of_thirds": ("rule of thirds", "thirds composition"),
        "dynamic": ("dynamic composition", "diagonal composition"),
    },
}

COVERAGE_LABELS_ZH = {
    "shot": "景别",
    "view": "视角",
    "pose": "姿态",
    "expression": "表情",
    "outfit": "服装",
    "background": "背景",
    "lighting": "光线",
    "composition": "构图",
    "close_up": "头部特写",
    "upper_body": "上半身",
    "cowboy_shot": "膝上构图",
    "full_body": "全身",
    "detail": "局部细节",
    "front": "正面",
    "three_quarter": "四分之三",
    "profile": "侧面",
    "back": "背面",
    "high_angle": "俯视",
    "low_angle": "仰视",
    "standing": "站立",
    "sitting": "坐姿",
    "walking": "行走",
    "turning": "回头",
    "dynamic": "动态",
    "interaction": "交互",
    "neutral": "平静",
    "smile": "微笑",
    "serious": "严肃",
    "angry": "生气",
    "sad": "悲伤",
    "surprised": "惊讶",
    "default": "默认服装",
    "alternate": "替换服装",
    "casual": "便装",
    "formal": "正式装",
    "themed": "主题装",
    "simple": "简单背景",
    "indoor": "室内",
    "outdoor": "室外",
    "urban": "城市",
    "nature": "自然",
    "soft": "柔光",
    "dramatic": "戏剧光",
    "backlight": "逆光",
    "night": "夜景光",
    "daylight": "日光",
    "centered": "居中",
    "rule_of_thirds": "三分法",
    "portrait": "竖构图",
    "landscape": "横构图",
}

PROJECT_DIRECTORIES = (
    "00_项目管理",
    "01_原始素材",
    "02_设计候选",
    "03_训练候选",
    "04_正式训练集",
    "05_淘汰区",
    "06_正则集",
    "07_导出",
    "08_测试样图",
    "08_丹炉导入",
    "09_训练产物",
    "outputs",
)

_TRIGGER_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")


class LoraProjectError(ValueError):
    pass


class LoraProjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._write_lock = Lock()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def options(self) -> dict[str, Any]:
        return {
            "concept_types": sorted(CONCEPT_TYPES),
            "asset_statuses": sorted(ASSET_STATUSES),
            "target_families": sorted(TARGET_FAMILIES),
            "risk_flags": sorted(RISK_FLAGS),
            "risk_flag_labels_zh": RISK_LABELS_ZH,
            "coverage_dimensions": {
                dimension: [
                    {"id": value, "label_zh": COVERAGE_LABELS_ZH[value]} for value in values
                ]
                for dimension, values in COVERAGE_DIMENSIONS.items()
            },
            "coverage_labels_zh": COVERAGE_LABELS_ZH,
        }

    def list_projects(self) -> list[dict[str, Any]]:
        projects = []
        if not self.root.is_dir():
            return projects
        for path in self.root.glob("lora-*/project.json"):
            try:
                projects.append(self._read_project_file(path))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return sorted(projects, key=lambda item: str(item["updated_at"]), reverse=True)

    def get(self, project_id: str) -> dict[str, Any] | None:
        path = self._project_file(project_id)
        if path is None or not path.is_file():
            return None
        return self._decorate(self._read_project_file(path))

    def create(
        self,
        values: Mapping[str, Any],
        *,
        oc_snapshot: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        concept_type = _concept_type(values.get("concept_type", "character"))
        trigger_word = _trigger_word(values.get("trigger_word", ""))
        target_families = _target_families(values.get("target_families", ["anima"]))
        project_id = f"lora-{uuid4().hex}"
        now = _now()
        project = {
            "format": "soda-prompt-hub-lora-project-v1",
            "project_id": project_id,
            "name": str(values.get("name", "")).strip()[:160] or "未命名 LoRA 项目",
            "concept_type": concept_type,
            "trigger_word": trigger_word,
            "outfit_trigger": _optional_trigger(values.get("outfit_trigger", "")),
            "target_families": target_families,
            "features": _features(values.get("features", {})),
            "source_oc": _oc_snapshot(oc_snapshot),
            "dataset_notes": str(values.get("dataset_notes", ""))[:6000],
            "target_models": _string_list(values.get("target_models", []), max_items=10),
            "training_resolution": _resolution(values.get("training_resolution", 1024)),
            "training_node": str(values.get("training_node", "5060ti"))[:120],
            "test_plan": str(values.get("test_plan", ""))[:6000],
            "status": "draft",
            "assets": [],
            "exports": [],
            "revision": 1,
            "created_at": now,
            "updated_at": now,
        }
        directory = self._project_directory(project_id)
        with self._write_lock:
            directory.mkdir(parents=True, exist_ok=False)
            for relative in PROJECT_DIRECTORIES:
                (directory / relative).mkdir()
            self._write_project(project)
            self._write_management_files(project, event="创建 LoRA 项目")
        return self._decorate(project)

    def update(self, project_id: str, values: Mapping[str, Any]) -> dict[str, Any]:
        project = self._required(project_id)
        if "concept_type" in values:
            project["concept_type"] = _concept_type(values["concept_type"])
        if "trigger_word" in values:
            project["trigger_word"] = _trigger_word(values["trigger_word"])
        if "outfit_trigger" in values:
            project["outfit_trigger"] = _optional_trigger(values["outfit_trigger"])
        if "target_families" in values:
            project["target_families"] = _target_families(values["target_families"])
        if "features" in values:
            project["features"] = _features(values["features"])
        text_fields = (
            ("name", 160),
            ("dataset_notes", 6000),
            ("training_node", 120),
            ("test_plan", 6000),
        )
        for key, limit in text_fields:
            if key in values:
                project[key] = str(values[key]).strip()[:limit]
        if "target_models" in values:
            project["target_models"] = _string_list(values["target_models"], max_items=10)
        if "training_resolution" in values:
            project["training_resolution"] = _resolution(values["training_resolution"])
        return self._persist(project, event="更新项目定义")

    def add_assets(
        self,
        project_id: str,
        workspace_id: str,
        records: Iterable[Mapping[str, Any]],
    ) -> dict[str, Any]:
        project = self._required(project_id)
        known = {
            (str(item["workspace_id"]), str(item["relative_path"])) for item in project["assets"]
        }
        added = 0
        for record in records:
            relative_path = str(record.get("relative_path", ""))
            key = (workspace_id, relative_path)
            if key in known:
                continue
            digest = str(record.get("sha256", ""))
            if len(digest) != 64:
                raise LoraProjectError("数据集图片缺少有效 SHA-256")
            project["assets"].append(
                {
                    "asset_id": f"asset-{uuid4().hex}",
                    "workspace_id": workspace_id,
                    "relative_path": relative_path,
                    "sha256": digest,
                    "phash": str(record.get("phash", "")),
                    "thumbnail": str(record.get("thumbnail", "")),
                    "width": int(record.get("width", 0)),
                    "height": int(record.get("height", 0)),
                    "status": "candidate",
                    "coverage": {},
                    "risk_flags": [],
                    "note": "",
                    "added_at": _now(),
                    "updated_at": _now(),
                }
            )
            known.add(key)
            added += 1
        result = self._persist(project, event=f"引用数据集图片 {added} 张")
        result["added"] = added
        return result

    def update_asset(
        self,
        project_id: str,
        asset_id: str,
        values: Mapping[str, Any],
    ) -> dict[str, Any]:
        project = self._required(project_id)
        asset = next((item for item in project["assets"] if item["asset_id"] == asset_id), None)
        if asset is None:
            raise LoraProjectError("LoRA project asset not found")
        if "status" in values:
            status = str(values["status"])
            if status not in ASSET_STATUSES:
                raise LoraProjectError("Invalid LoRA asset status")
            asset["status"] = status
        if "coverage" in values:
            asset["coverage"] = _coverage(values["coverage"])
        if "risk_flags" in values:
            flags = _string_list(values["risk_flags"], max_items=len(RISK_FLAGS))
            if unknown := set(flags) - RISK_FLAGS:
                raise LoraProjectError(f"Invalid LoRA risk flags: {', '.join(sorted(unknown))}")
            asset["risk_flags"] = flags
        if "note" in values:
            asset["note"] = str(values["note"])[:2000]
        asset["updated_at"] = _now()
        return self._persist(project, event=f"审核图片 {asset['relative_path']}")

    def preview_coverage(
        self,
        project_id: str,
        records: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        project = self._required(project_id)
        return _coverage_preview(project, records)

    def apply_coverage_review(
        self,
        project_id: str,
        records: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        project = self._required(project_id)
        preview = _coverage_preview(project, records)
        if not preview["suggested_values"]:
            return {"preview": preview, "project": self._decorate(project)}
        items = {str(item["asset_id"]): item for item in preview["items"]}
        for asset in project["assets"]:
            suggestion = items.get(str(asset["asset_id"]))
            if suggestion is None or not suggestion["additions"]:
                continue
            coverage = _coverage(asset.get("coverage", {}))
            for dimension, values in suggestion["additions"].items():
                coverage[dimension] = list(dict.fromkeys([*coverage.get(dimension, []), *values]))
            asset["coverage"] = coverage
            asset["coverage_review"] = {
                "status": "confirmed",
                "source": preview["source"],
                "confirmed_at": _now(),
                "evidence": suggestion["evidence"],
            }
            asset["updated_at"] = _now()
        updated = self._persist(
            project,
            event=f"确认保守覆盖初审 {preview['suggested_assets']} 张",
        )
        return {"preview": preview, "project": updated}

    def register_export(self, project_id: str, export: Mapping[str, Any]) -> dict[str, Any]:
        project = self._required(project_id)
        project.setdefault("exports", []).append(dict(export))
        return self._persist(project, event=f"冻结训练包 {export.get('version_id', '')}")

    def resolve_export(self, project_id: str, filename: str) -> Path | None:
        project = self.get(project_id)
        if project is None or Path(filename).name != filename or not filename.endswith(".zip"):
            return None
        known = {Path(str(item.get("archive", ""))).name for item in project.get("exports", [])}
        if filename not in known:
            return None
        root = self._project_directory(project_id) / "07_导出"
        path = (root / filename).resolve()
        return path if path.is_relative_to(root.resolve()) and path.is_file() else None

    def _required(self, project_id: str) -> dict[str, Any]:
        project = self.get(project_id)
        if project is None:
            raise LoraProjectError("LoRA project not found")
        result = {
            key: value
            for key, value in project.items()
            if key not in {"coverage_report", "project_path"}
        }
        for asset in result["assets"]:
            asset.pop("thumbnail_url", None)
            asset.pop("original_url", None)
        return result

    def _persist(self, project: dict[str, Any], *, event: str) -> dict[str, Any]:
        project["revision"] = int(project.get("revision", 0)) + 1
        project["updated_at"] = _now()
        with self._write_lock:
            self._write_project(project)
            self._write_management_files(project, event=event)
        return self._decorate(project)

    def _decorate(self, project: dict[str, Any]) -> dict[str, Any]:
        result = json.loads(json.dumps(project, ensure_ascii=False))
        result["project_path"] = str(self._project_directory(project["project_id"]))
        for asset in result["assets"]:
            workspace_id = asset["workspace_id"]
            relative = asset["relative_path"]
            thumbnail = Path(asset.get("thumbnail", "")).name
            asset["thumbnail_url"] = (
                f"/dataset-workspaces/{workspace_id}/thumbnails/{thumbnail}" if thumbnail else ""
            )
            asset["original_url"] = (
                f"/dataset-workspaces/{workspace_id}/original?relative_path={_quote(relative)}"
            )
        result["coverage_report"] = coverage_report(result)
        return result

    def _project_directory(self, project_id: str) -> Path:
        if not project_id.startswith("lora-") or not project_id[5:].isalnum():
            raise LoraProjectError("Invalid LoRA project id")
        path = (self.root / project_id).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise LoraProjectError("Invalid LoRA project path")
        return path

    def _project_file(self, project_id: str) -> Path | None:
        try:
            return self._project_directory(project_id) / "project.json"
        except LoraProjectError:
            return None

    def _read_project_file(self, path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("format") != "soda-prompt-hub-lora-project-v1":
            raise LoraProjectError("Unsupported LoRA project format")
        return value

    def _write_project(self, project: Mapping[str, Any]) -> None:
        path = self._project_directory(str(project["project_id"])) / "project.json"
        _atomic_json_write(path, project)

    def _write_management_files(self, project: Mapping[str, Any], *, event: str) -> None:
        root = self._project_directory(str(project["project_id"]))
        management = root / "00_项目管理"
        features = project["features"]
        config = [
            f"project_id: {project['project_id']}",
            f"display_name: {_yaml_string(project['name'])}",
            f"concept_type: {project['concept_type']}",
            f"trigger_word: {project['trigger_word']}",
            f"outfit_trigger: {project['outfit_trigger']}",
            "target_families:",
            *[f"  - {family}" for family in project["target_families"]],
            "features:",
        ]
        for group in ("fixed", "controllable", "variable", "forbidden_drift"):
            config.append(f"  {group}:")
            config.extend(f"    - {_yaml_string(value)}" for value in features[group])
        config.extend(
            (
                f"training_resolution: {project['training_resolution']}",
                f"training_node: {_yaml_string(project['training_node'])}",
            )
        )
        _atomic_text_write(management / "角色配置.yaml", "\n".join(config) + "\n")
        report = coverage_report(project)
        approved = report["status_counts"].get("approved", 0)
        status = (
            f"# {project['name']}\n\n"
            f"- 状态：{project['status']}\n"
            f"- 类型：{project['concept_type']}\n"
            f"- Trigger：`{project['trigger_word']}`\n"
            f"- 目标：{', '.join(project['target_families'])}\n"
            f"- 图片：{report['total_assets']} 张；已保留 {approved} 张\n"
            f"- 待补覆盖：{report['gap_count']} 项\n"
            f"- 更新：{project['updated_at']}\n"
        )
        _atomic_text_write(management / "项目状态.md", status)
        self._write_asset_csv(management / "图片清单.csv", project["assets"])
        for name, heading in (
            ("task_plan.md", "LoRA 项目计划"),
            ("findings.md", "LoRA 项目发现"),
            ("progress.md", "LoRA 项目进度"),
        ):
            path = root / name
            if not path.exists():
                _atomic_text_write(path, f"# {heading}\n\n")
        with (root / "progress.md").open("a", encoding="utf-8") as handle:
            handle.write(f"- {project['updated_at']}：{event}。\n")

    @staticmethod
    def _write_asset_csv(path: Path, assets: Iterable[Mapping[str, Any]]) -> None:
        temporary = path.with_suffix(".csv.tmp")
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=(
                    "asset_id",
                    "workspace_id",
                    "relative_path",
                    "sha256",
                    "status",
                    "coverage",
                    "risk_flags",
                    "note",
                ),
            )
            writer.writeheader()
            for asset in assets:
                writer.writerow(
                    {
                        "asset_id": asset["asset_id"],
                        "workspace_id": asset["workspace_id"],
                        "relative_path": asset["relative_path"],
                        "sha256": asset["sha256"],
                        "status": asset["status"],
                        "coverage": json.dumps(
                            asset["coverage"], ensure_ascii=False, sort_keys=True
                        ),
                        "risk_flags": ",".join(asset["risk_flags"]),
                        "note": asset["note"],
                    }
                )
        temporary.replace(path)


def coverage_report(project: Mapping[str, Any]) -> dict[str, Any]:
    active_assets = [
        item
        for item in project.get("assets", [])
        if item.get("status") in {"candidate", "approved", "needs_more"}
    ]
    counts = {
        dimension: Counter(
            value
            for asset in active_assets
            for value in asset.get("coverage", {}).get(dimension, [])
        )
        for dimension in COVERAGE_DIMENSIONS
    }
    requirements = _coverage_requirements(str(project.get("concept_type", "character")))
    dimensions = []
    gap_count = 0
    for dimension, values in COVERAGE_DIMENSIONS.items():
        items = []
        for value in values:
            minimum = requirements.get(dimension, {}).get(value, 1)
            count = counts[dimension][value]
            missing = max(0, minimum - count)
            gap_count += int(missing > 0)
            items.append(
                {
                    "id": value,
                    "label_zh": COVERAGE_LABELS_ZH[value],
                    "count": count,
                    "minimum": minimum,
                    "missing": missing,
                    "complete": missing == 0,
                }
            )
        dimensions.append(
            {"id": dimension, "label_zh": COVERAGE_LABELS_ZH[dimension], "items": items}
        )
    digest_counts = Counter(str(asset.get("sha256", "")) for asset in active_assets)
    duplicate_assets = sum(
        count - 1 for digest, count in digest_counts.items() if digest and count > 1
    )
    risk_counts = Counter(flag for asset in active_assets for flag in asset.get("risk_flags", []))
    biases = []
    if len(active_assets) >= 5:
        for dimension in ("background", "pose", "composition"):
            if not counts[dimension]:
                continue
            value, count = counts[dimension].most_common(1)[0]
            if count / len(active_assets) > 0.6:
                biases.append(
                    {
                        "dimension": dimension,
                        "value": value,
                        "count": count,
                        "ratio": round(count / len(active_assets), 3),
                    }
                )
    return {
        "total_assets": len(project.get("assets", [])),
        "active_assets": len(active_assets),
        "status_counts": dict(
            Counter(str(item.get("status", "")) for item in project.get("assets", []))
        ),
        "dimensions": dimensions,
        "gap_count": gap_count,
        "exact_duplicate_assets": duplicate_assets,
        "risk_counts": dict(risk_counts),
        "biases": biases,
    }


def _coverage_preview(
    project: Mapping[str, Any],
    records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for asset in project.get("assets", []):
        if asset.get("status") not in {"candidate", "approved", "needs_more"}:
            continue
        asset_id = str(asset.get("asset_id", ""))
        suggestions, evidence = _suggest_coverage(records.get(asset_id, {}))
        current = _coverage(asset.get("coverage", {}))
        additions = {
            dimension: [value for value in values if value not in current.get(dimension, [])]
            for dimension, values in suggestions.items()
        }
        additions = {dimension: values for dimension, values in additions.items() if values}
        if additions:
            items.append(
                {
                    "asset_id": asset_id,
                    "relative_path": str(asset.get("relative_path", "")),
                    "additions": additions,
                    "evidence": evidence,
                }
            )
    return {
        "project_id": str(project.get("project_id", "")),
        "source": "filename-original-caption-rules-v1",
        "inspected_assets": len(project.get("assets", [])),
        "suggested_assets": len(items),
        "suggested_values": sum(
            len(values) for item in items for values in item["additions"].values()
        ),
        "items": items,
    }


def _suggest_coverage(record: Mapping[str, Any]) -> tuple[dict[str, list[str]], list[str]]:
    source_parts = [str(record.get("relative_path", "")), str(record.get("caption", ""))]
    curation = record.get("curation", {})
    if isinstance(curation, Mapping):
        captions = curation.get("captions", {})
        if isinstance(captions, Mapping):
            for profile_id in ("anima", "krea2"):
                caption = captions.get(profile_id, {})
                if isinstance(caption, Mapping):
                    source_parts.append(str(caption.get("current", "")))
    normalized = f" {_coverage_text(' '.join(source_parts))} "
    suggestions: dict[str, list[str]] = {}
    evidence: list[str] = []
    for dimension, values in COVERAGE_ALIASES.items():
        for value, aliases in values.items():
            matched = next(
                (alias for alias in aliases if f" {_coverage_text(alias)} " in normalized),
                "",
            )
            if matched:
                suggestions.setdefault(dimension, []).append(value)
                evidence.append(f"{dimension}.{value} ← {matched}")
    width = int(record.get("width", 0) or 0)
    height = int(record.get("height", 0) or 0)
    if width > 0 and height > 0 and width != height:
        orientation = "portrait" if height > width else "landscape"
        suggestions.setdefault("composition", []).append(orientation)
        evidence.append(f"composition.{orientation} ← {width}×{height}")
    return suggestions, evidence


def _coverage_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _coverage_requirements(concept_type: str) -> dict[str, dict[str, int]]:
    if concept_type == "style":
        return {
            dimension: dict.fromkeys(values, 2) for dimension, values in COVERAGE_DIMENSIONS.items()
        }
    requirements = {
        dimension: dict.fromkeys(values, 1) for dimension, values in COVERAGE_DIMENSIONS.items()
    }
    if concept_type == "character":
        requirements["shot"].update({"close_up": 2, "upper_body": 2, "full_body": 2})
        requirements["view"].update({"front": 2, "three_quarter": 2})
    elif concept_type in {"outfit", "character_outfit"}:
        requirements["shot"].update({"upper_body": 3, "cowboy_shot": 2, "full_body": 3})
        requirements["view"].update({"front": 2, "three_quarter": 2, "back": 3})
    return requirements


def _concept_type(value: Any) -> str:
    result = str(value)
    if result not in CONCEPT_TYPES:
        raise LoraProjectError("Invalid LoRA concept type")
    return result


def _trigger_word(value: Any) -> str:
    result = str(value).strip()
    if not _TRIGGER_RE.fullmatch(result):
        raise LoraProjectError("触发词必须是 3–64 位小写英文字母、数字或下划线")
    return result


def _optional_trigger(value: Any) -> str:
    result = str(value).strip()
    return _trigger_word(result) if result else ""


def _target_families(value: Any) -> list[str]:
    families = _string_list(value, max_items=2)
    if not families or set(families) - TARGET_FAMILIES:
        raise LoraProjectError("目标模型只能选择 Anima、Krea 2 或两者")
    return sorted(set(families))


def _features(value: Any) -> dict[str, list[str]]:
    source = value if isinstance(value, Mapping) else {}
    return {
        key: _string_list(source.get(key, []), max_items=60)
        for key in ("fixed", "controllable", "variable", "forbidden_drift")
    }


def _coverage(value: Any) -> dict[str, list[str]]:
    source = value if isinstance(value, Mapping) else {}
    result = {}
    for dimension, allowed in COVERAGE_DIMENSIONS.items():
        selected = _string_list(source.get(dimension, []), max_items=len(allowed))
        if unknown := set(selected) - set(allowed):
            raise LoraProjectError(
                f"Invalid coverage values for {dimension}: {', '.join(sorted(unknown))}"
            )
        if selected:
            result[dimension] = selected
    return result


def _string_list(value: Any, *, max_items: int) -> list[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, Mapping)):
        items = [str(part).strip() for part in value]
    else:
        items = []
    return list(dict.fromkeys(item[:300] for item in items if item))[:max_items]


def _resolution(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise LoraProjectError("训练尺寸必须是整数") from error
    if result not in {512, 768, 1024, 1280, 1536}:
        raise LoraProjectError("训练尺寸必须是 512、768、1024、1280 或 1536")
    return result


def _oc_snapshot(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    profile = value.get("profile", {})
    encoded = json.dumps(profile, ensure_ascii=False, sort_keys=True).encode()
    return {
        "character_id": str(value.get("character_id", "")),
        "name": str(value.get("name", "")),
        "world": str(value.get("world", "")),
        "source_file": str(value.get("source_file", "")),
        "imported_at": str(value.get("imported_at", "")),
        "profile_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _yaml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _quote(value: str) -> str:
    return quote(value, safe="")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _atomic_json_write(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_text_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _atomic_text_write(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)
