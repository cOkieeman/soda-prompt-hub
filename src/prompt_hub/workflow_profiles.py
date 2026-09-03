from __future__ import annotations

import hashlib
import json
import re
import secrets
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

PROFILE_FORMAT = "soda-workflow-profile-v1"
PACKAGE_FORMAT = "soda-comfyui-package-v1"
MAX_WORKFLOW_BYTES = 2 * 1024 * 1024
MAX_PROMPT_LENGTH = 20_000
MAX_SEED = 2**50
_SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
_CREDENTIAL_KEYS = {"api_key", "apikey", "authorization", "password", "secret", "token"}


class WorkflowProfileError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WorkflowRule:
    profile_id: str
    model_family: str
    required_nodes: Mapping[str, str]
    output_node: str
    direct_image_node: str
    omitted_low_cost: tuple[str, ...]


RULES = {
    "anima-mansui": WorkflowRule(
        profile_id="anima-mansui",
        model_family="anima",
        required_nodes={
            "75": "String Literal",
            "81": "Image Saver",
            "84": "Seed (rgthree)",
            "150": "ResolutionMasterSimplify",
            "182": "String Literal",
            "184": "ImpactWildcardEncode",
            "135:103": "Int Literal",
            "135:104": "Cfg Literal",
            "148:139": "VAEDecode",
        },
        output_node="81",
        direct_image_node="148:139",
        omitted_low_cost=("SAM3 / face-hand detailer", "CR / Ultimate SD Upscale"),
    ),
    "krea2-ares-ocmanager": WorkflowRule(
        profile_id="krea2-ares-ocmanager",
        model_family="krea2",
        required_nodes={
            "87": "ImpactKSamplerBasicPipe",
            "121": "CLIPTextEncode",
            "129": "EmptyLatentImage",
            "132": "VAEDecode",
            "133": "SaveImage",
            "141": "ImpactWildcardEncode",
        },
        output_node="133",
        direct_image_node="132",
        omitted_low_cost=("SeedVR2 1920 upscaler",),
    ),
}


class WorkflowProfileStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def import_bytes(
        self,
        profile_id: str,
        raw: bytes,
        *,
        label: str,
        filename: str,
        replace: bool = False,
    ) -> dict[str, Any]:
        rule = _rule(profile_id)
        workflow = _parse_workflow(raw)
        _validate_workflow(workflow, rule)
        digest = hashlib.sha256(raw).hexdigest()
        directory = self.root / profile_id
        metadata_path = directory / "profile.json"
        if metadata_path.is_file():
            existing = _read_json(metadata_path)
            if existing.get("source_sha256") == digest:
                return {**self._decorate(existing), "duplicate": True}
            if not replace:
                raise WorkflowProfileError("Profile 已存在且来源不同；确认替换后再导入")
        directory.mkdir(parents=True, exist_ok=True)
        _write_bytes(directory / "source-workflow.json", raw)
        metadata = {
            "format": PROFILE_FORMAT,
            "profile_id": profile_id,
            "label": label.strip()[:160] or profile_id,
            "model_family": rule.model_family,
            "source_filename": Path(filename).name[:180],
            "source_sha256": digest,
            "node_count": len(workflow),
            "classes": sorted({str(node["class_type"]) for node in workflow.values()}),
            "models": _model_names(workflow),
            "low_cost_omits": list(rule.omitted_low_cost),
            "imported_at": _now(),
        }
        _write_json(metadata_path, metadata)
        return {**self._decorate(metadata), "duplicate": False}

    def list_profiles(self) -> list[dict[str, Any]]:
        self.initialize()
        profiles = []
        for path in sorted(self.root.glob("*/profile.json")):
            try:
                profiles.append(self._decorate(_read_json(path)))
            except (OSError, json.JSONDecodeError, WorkflowProfileError):
                continue
        return sorted(profiles, key=lambda item: (item["model_family"], item["label"]))

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        _rule(profile_id)
        path = self.root / profile_id / "profile.json"
        if not path.is_file():
            raise WorkflowProfileError("Workflow Profile 尚未导入")
        value = _read_json(path)
        if value.get("format") != PROFILE_FORMAT or value.get("profile_id") != profile_id:
            raise WorkflowProfileError("Workflow Profile metadata 无效")
        return self._decorate(value)

    def compile_package(
        self,
        profile_id: str,
        *,
        run_id: str,
        positive: str | None = None,
        negative: str | None = None,
        seed: int | None = None,
        width: int | None = None,
        height: int | None = None,
        steps: int | None = None,
        cfg: float | None = None,
        low_cost: bool = True,
    ) -> dict[str, Any]:
        profile = self.get_profile(profile_id)
        rule = _rule(profile_id)
        raw = (self.root / profile_id / "source-workflow.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != profile["source_sha256"]:
            raise WorkflowProfileError("原始 workflow 哈希已变化，拒绝编译")
        workflow = deepcopy(_parse_workflow(raw))
        values = {
            "positive": _optional_prompt(positive),
            "negative": _optional_prompt(negative),
            "seed": _seed(seed),
            "width": _dimension(width),
            "height": _dimension(height),
            "steps": _number(steps, minimum=1, maximum=200, label="steps"),
            "cfg": _number(cfg, minimum=0, maximum=30, label="CFG"),
        }
        if rule.model_family == "anima":
            _patch_anima(workflow, values, run_id=run_id, low_cost=low_cost)
        else:
            _patch_krea2(workflow, values, run_id=run_id, low_cost=low_cost)
        if low_cost:
            workflow = _dependency_closure(workflow, rule.output_node)
        return {
            "format": PACKAGE_FORMAT,
            "workflow_id": f"{profile_id}-{run_id}",
            "profile_id": profile_id,
            "model_family": rule.model_family,
            "source_sha256": profile["source_sha256"],
            "low_cost": low_cost,
            "compiled_at": _now(),
            "api_prompt": workflow,
        }

    def save_run_package(
        self,
        profile_id: str,
        run_id: str,
        package: Mapping[str, Any],
    ) -> Path:
        _rule(profile_id)
        if not _SAFE_ID.fullmatch(run_id):
            raise WorkflowProfileError("run_id 无效")
        path = self.root / profile_id / "runs" / f"{run_id}.json"
        _write_json(path, package)
        return path

    @staticmethod
    def _decorate(profile: Mapping[str, Any]) -> dict[str, Any]:
        result = dict(profile)
        result["ready"] = True
        result["source_workflow_saved"] = True
        return result


def _patch_anima(
    workflow: dict[str, dict[str, Any]],
    values: Mapping[str, Any],
    *,
    run_id: str,
    low_cost: bool,
) -> None:
    positive = values["positive"]
    if positive is not None:
        workflow["184"]["inputs"]["wildcard_text"] = positive
        workflow["184"]["inputs"]["populated_text"] = positive
        workflow["182"]["inputs"]["string"] = ""
    if values["negative"] is not None:
        workflow["75"]["inputs"]["string"] = values["negative"]
    workflow["84"]["inputs"]["seed"] = values["seed"]
    workflow["184"]["inputs"]["seed"] = values["seed"]
    _set_if_present(workflow["150"]["inputs"], "width", values["width"])
    _set_if_present(workflow["150"]["inputs"], "height", values["height"])
    _set_if_present(workflow["135:103"]["inputs"], "int", values["steps"])
    _set_if_present(workflow["135:104"]["inputs"], "float", values["cfg"])
    output = workflow["81"]["inputs"]
    output["filename"] = f"{run_id}_%time"
    output["path"] = "PromptHub/anima"
    output["steps"] = workflow["135:103"]["inputs"]["int"]
    output["cfg"] = workflow["135:104"]["inputs"]["float"]
    output["width"] = workflow["150"]["inputs"]["width"]
    output["height"] = workflow["150"]["inputs"]["height"]
    if low_cost:
        output["images"] = ["148:139", 0]


def _patch_krea2(
    workflow: dict[str, dict[str, Any]],
    values: Mapping[str, Any],
    *,
    run_id: str,
    low_cost: bool,
) -> None:
    positive = values["positive"]
    if positive is not None:
        workflow["141"]["inputs"]["wildcard_text"] = positive
        workflow["141"]["inputs"]["populated_text"] = positive
    if values["negative"] is not None:
        workflow["121"]["inputs"]["text"] = values["negative"]
    workflow["87"]["inputs"]["seed"] = values["seed"]
    workflow["141"]["inputs"]["seed"] = values["seed"]
    _set_if_present(workflow["87"]["inputs"], "steps", values["steps"])
    _set_if_present(workflow["87"]["inputs"], "cfg", values["cfg"])
    _set_if_present(workflow["129"]["inputs"], "width", values["width"])
    _set_if_present(workflow["129"]["inputs"], "height", values["height"])
    output = workflow["133"]["inputs"]
    output["filename_prefix"] = f"PromptHub/krea2/{run_id}"
    if low_cost:
        output["images"] = ["132", 0]


def _dependency_closure(
    workflow: Mapping[str, dict[str, Any]],
    output_node: str,
) -> dict[str, dict[str, Any]]:
    required: set[str] = set()
    pending = [output_node]
    while pending:
        node_id = pending.pop()
        if node_id in required:
            continue
        node = workflow.get(node_id)
        if node is None:
            raise WorkflowProfileError(f"workflow 引用了不存在的节点：{node_id}")
        required.add(node_id)
        pending.extend(
            str(value[0]) for value in node["inputs"].values() if _is_node_link(value, workflow)
        )
    return {node_id: workflow[node_id] for node_id in workflow if node_id in required}


def _is_node_link(value: Any, workflow: Mapping[str, Any]) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
        and value[0] in workflow
    )


def _parse_workflow(raw: bytes) -> dict[str, dict[str, Any]]:
    if not raw or len(raw) > MAX_WORKFLOW_BYTES:
        raise WorkflowProfileError("Workflow 文件为空或超过 2 MiB")
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkflowProfileError("Workflow 不是有效 UTF-8 JSON") from error
    if not isinstance(value, dict) or not value:
        raise WorkflowProfileError("Workflow 必须是非空 API Format 对象")
    workflow: dict[str, dict[str, Any]] = {}
    for raw_id, raw_node in value.items():
        node_id = str(raw_id)
        if not isinstance(raw_node, dict):
            raise WorkflowProfileError("普通 UI workflow 不能直接运行；请导出 API Format")
        class_type = raw_node.get("class_type")
        inputs = raw_node.get("inputs")
        if not isinstance(class_type, str) or not class_type or not isinstance(inputs, dict):
            raise WorkflowProfileError("普通 UI workflow 不能直接运行；请导出 API Format")
        _reject_credentials(inputs)
        workflow[node_id] = raw_node
    return workflow


def _validate_workflow(workflow: Mapping[str, Mapping[str, Any]], rule: WorkflowRule) -> None:
    for node_id, expected in rule.required_nodes.items():
        node = workflow.get(node_id)
        if node is None:
            raise WorkflowProfileError(f"Profile 缺少节点 {node_id}")
        if node.get("class_type") != expected:
            raise WorkflowProfileError(f"节点 {node_id} 类型不匹配：需要 {expected}")


def _reject_credentials(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in _CREDENTIAL_KEYS and str(item).strip():
                raise WorkflowProfileError(f"Workflow 含凭据字段：{key}")
            _reject_credentials(item)
    elif isinstance(value, list):
        for item in value:
            _reject_credentials(item)


def _model_names(workflow: Mapping[str, Mapping[str, Any]]) -> list[str]:
    names = []
    model_keys = {
        "ckpt_name",
        "clip_name",
        "lora_name",
        "model",
        "model_name",
        "unet_name",
        "vae_name",
    }
    for node in workflow.values():
        for key, value in node["inputs"].items():
            if key in model_keys and isinstance(value, str) and value.strip():
                names.append(value.strip())
    return sorted(set(names), key=str.casefold)


def _rule(profile_id: str) -> WorkflowRule:
    if not _SAFE_ID.fullmatch(profile_id):
        raise WorkflowProfileError("Workflow Profile ID 无效")
    rule = RULES.get(profile_id)
    if rule is None:
        raise WorkflowProfileError("当前版本没有这个 Workflow Profile 的节点映射")
    return rule


def _optional_prompt(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        raise WorkflowProfileError("Prompt 不能为空")
    if len(clean) > MAX_PROMPT_LENGTH:
        raise WorkflowProfileError("Prompt 超过 20000 字符")
    return clean


def _seed(value: int | None) -> int:
    if value is None or value < 0:
        return secrets.randbelow(MAX_SEED + 1)
    if value > MAX_SEED:
        raise WorkflowProfileError("seed 超出安全整数范围")
    return value


def _dimension(value: int | None) -> int | None:
    if value is None:
        return None
    if not 256 <= value <= 4096 or value % 8:
        raise WorkflowProfileError("尺寸必须在 256–4096 且为 8 的倍数")
    return value


def _number(
    value: float | None,
    *,
    minimum: float,
    maximum: float,
    label: str,
) -> float | None:
    if value is not None and not minimum <= value <= maximum:
        raise WorkflowProfileError(f"{label} 必须在 {minimum:g}–{maximum:g} 之间")
    return value


def _set_if_present(target: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        target[key] = value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowProfileError(f"无法读取 Profile：{path.name}") from error
    if not isinstance(value, dict):
        raise WorkflowProfileError(f"Profile JSON 必须是对象：{path.name}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    raw = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    _write_bytes(path, raw)


def _write_bytes(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
