from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from typing import Any

MAX_METADATA_LENGTH = 200_000
MAX_METADATA_ROWS = 512
MAX_RESOURCE_NAME = 1000
HASH_PATTERN = re.compile(r"(?:[0-9a-f]{10}|[0-9a-f]{64})", re.IGNORECASE)
LORA_TYPES = {"lora", "locon", "dora"}
FIELDS = ("resources_json", "Lora hashes", "Civitai resources", "additional_hashes")
INVALID = object()


def _canonical_field(name: object) -> str | None:
    normalized = re.sub(r"[ _]+", " ", name.strip().casefold()) if isinstance(name, str) else ""
    return next(
        (field for field in FIELDS if field.replace("_", " ").casefold() == normalized), None
    )


def _split_settings(value: str) -> list[str]:
    parts, start, depth, quoted, escaped = [], 0, 0, False, False
    for position, char in enumerate(value):
        if escaped:
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted and char in "[{":
            depth += 1
        elif not quoted and char in "]}":
            depth = max(0, depth - 1)
        elif not quoted and not depth and char == ",":
            parts.append(value[start:position].strip())
            start = position + 1
    parts.append(value[start:].strip())
    return parts


def _saved_fields(parameters: str, metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(parameters, str) and len(parameters) <= MAX_METADATA_LENGTH:
        settings = re.findall(r"(?:^|\n)Steps:[^\n]*", parameters)
        for part in _split_settings(settings[-1] if settings else ""):
            name, separator, value = part.partition(":")
            canonical = _canonical_field(name)
            if separator and canonical:
                result[canonical] = value.strip()
    if isinstance(metadata, Mapping):
        for name, value in metadata.items():
            canonical = _canonical_field(name)
            if canonical:
                result[canonical] = value
    return result


def _decode(value: object) -> object:
    for _ in range(2):
        if not isinstance(value, str):
            return value
        if len(value) > MAX_METADATA_LENGTH:
            return INVALID
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return INVALID
        if isinstance(value, str) and not value.lstrip().startswith(("[", "{", '"')):
            return value
    return value


def _hash(value: object) -> str | None:
    return value.upper() if isinstance(value, str) and HASH_PATTERN.fullmatch(value) else None


def _weight(value: object, warnings: list[str]) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            if math.isfinite(value):
                return value
        except OverflowError:
            pass
    warnings.append("保存的 LoRA 权重无效, 已保留为未知值。")
    return None


def _record(name: str, digest: str | None, weight: float | None, field: str) -> dict[str, Any]:
    return {
        "name": name,
        "hash": digest,
        "air": None,
        "weight": weight,
        "strength_model": weight,
        "strength_clip": None,
        "source": {"kind": "saved_image_metadata", "field": field},
    }


def _resource_rows(value: object, warnings: list[str]) -> list[Mapping[str, Any]] | None:
    decoded = _decode(value)
    if not isinstance(decoded, list) or len(decoded) > MAX_METADATA_ROWS:
        warnings.append("保存的 LoRA 资源清单无法解析或超过读取上限。")
        return None
    if any(not isinstance(row, Mapping) for row in decoded):
        warnings.append("保存的资源清单含无效条目, 未将其视为使用记录。")
    return [row for row in decoded if isinstance(row, Mapping)]


def _runtime_records(value: object, warnings: list[str]) -> list[dict[str, Any]] | None:
    rows = _resource_rows(value, warnings)
    if rows is None:
        return None
    records = []
    for row in rows:
        if row.get("kind") != "lora":
            warnings.append("手动资源声明不属于 LoRA 运行输出记录, 未加入使用清单。")
            continue
        if row.get("status") != "resolved":
            if row.get("status") != "duplicate":
                warnings.append("存在未成功解析的 LoRA 运行记录, 清单可能不完整。")
            continue
        name = row.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_RESOURCE_NAME:
            warnings.append("LoRA 保存条目的名称无效, 未加入使用清单。")
            continue
        records.append(
            _record(
                name, _hash(row.get("hash")), _weight(row.get("weight"), warnings), "resources_json"
            )
        )
    return records


def _hash_records(value: object, warnings: list[str]) -> list[dict[str, Any]] | None:
    if isinstance(value, str):
        value = re.sub(r"^\s*lora[ _]+hashes\s*:\s*", "", value, count=1, flags=re.IGNORECASE)
    if isinstance(value, str) and value.lstrip().startswith('"'):
        value = _decode(value)
    if not isinstance(value, str) or len(value) > MAX_METADATA_LENGTH:
        warnings.append("PNG 的 Lora hashes 字段无法解析。")
        return None
    if not value.strip():
        return []
    parts = value.split(",")
    if len(parts) > MAX_METADATA_ROWS:
        warnings.append("PNG 的 Lora hashes 超过读取上限。")
        return None
    records = []
    for part in parts:
        name, separator, raw_hash = part.rpartition(":")
        digest = _hash(raw_hash.strip())
        if not separator or not name.strip() or len(name) > MAX_RESOURCE_NAME or digest is None:
            warnings.append("PNG 的 Lora hashes 含无效条目, 清单可能不完整。")
            continue
        records.append(_record(name.strip(), digest, None, "Lora hashes"))
    return records or None


def _resource_kind(row: Mapping[str, Any]) -> str:
    kind = str(row.get("type", "")).casefold()
    if kind:
        return kind
    air = row.get("air")
    match = (
        re.fullmatch(r"urn:air:[^:]+:([^:]+):civitai:[0-9]+@[0-9]+(?:\+[0-9]+)?", air)
        if isinstance(air, str)
        else None
    )
    return match[1].casefold() if match else ""


def _civitai_records(value: object, warnings: list[str]) -> list[dict[str, Any]] | None:
    rows = _resource_rows(value, warnings)
    if rows is None:
        return None
    records = []
    for row in rows:
        if _resource_kind(row) not in LORA_TYPES:
            continue
        name = row.get("modelName", row.get("name"))
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_RESOURCE_NAME:
            warnings.append("LoRA 保存资源名称无效, 清单可能不完整。")
            continue
        item = _record(
            name, _hash(row.get("hash")), _weight(row.get("weight"), warnings), "Civitai resources"
        )
        if isinstance(row.get("air"), str) and len(row["air"]) <= MAX_RESOURCE_NAME:
            item["air"] = row["air"]
        records.append(item)
    return records


def _additional_records(value: object, warnings: list[str]) -> list[dict[str, Any]]:
    if isinstance(value, str) and value.lstrip().startswith('"'):
        value = _decode(value)
    if not isinstance(value, str) or len(value) > MAX_METADATA_LENGTH:
        warnings.append("additional_hashes 无法解析, 未补充权重。")
        return []
    result = []
    for part in value.split(",")[:MAX_METADATA_ROWS]:
        name_hash, separator, raw_weight = part.rpartition(":")
        name, hash_separator, raw_hash = name_hash.rpartition(":")
        digest = _hash(raw_hash.strip())
        if not separator or not hash_separator or digest is None or not name.strip():
            continue
        try:
            number = float(raw_weight)
        except ValueError:
            continue
        result.append(_record(name.strip(), digest, _weight(number, warnings), "additional_hashes"))
    return result


def _same_resource(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    if first.get("hash") and second.get("hash"):
        return first["hash"] == second["hash"]
    if first.get("air") and second.get("air"):
        return first["air"] == second["air"]
    return first["name"] == second["name"]


def _enrich(
    records: list[dict[str, Any]], extra: list[dict[str, Any]], warnings: list[str]
) -> None:
    for item in records:
        matches = [row for row in extra if _same_resource(item, row) and row["weight"] is not None]
        if (
            sum(row["name"] == item["name"] for row in records) > 1
            or sum(row["name"] == item["name"] for row in extra) > 1
        ):
            keyed = [
                row
                for row in matches
                if (item.get("hash") and row.get("hash")) or (item.get("air") and row.get("air"))
            ]
            if len(keyed) != len(matches):
                warnings.append("同名 LoRA 无法唯一匹配保存权重, 未按顺序或相似名称补充。")
            matches = keyed
        weights = {row["weight"] for row in matches}
        if len(weights) > 1 or (
            weights and item["weight"] is not None and item["weight"] not in weights
        ):
            warnings.append("同一 LoRA 的保存权重存在冲突, 未猜测替代值。")
        elif len(weights) == 1 and item["weight"] is None:
            item["weight"] = item["strength_model"] = next(iter(weights))
            item["weight_source"] = matches[0]["source"]


def inspect_saved_loras(
    parameters: str, metadata: Mapping[str, Any] | None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fields = _saved_fields(parameters, metadata)
    warnings: list[str] = []
    source: dict[str, Any] = {
        "status": "missing",
        "kind": "saved_image_metadata",
        "fields": [],
        "warnings": warnings,
    }
    readers = {
        "resources_json": _runtime_records,
        "Lora hashes": _hash_records,
        "Civitai resources": _civitai_records,
    }
    selected = next((name for name in readers if name in fields), None)
    if selected is None:
        warnings.append("PNG 未保存可确认的 LoRA 清单, 未从工作流候选或画面推测。")
        return [], source
    source["fields"].append(selected)
    records = readers[selected](fields[selected], warnings)
    if records is None:
        source["status"] = "invalid"
        return [], source
    for field, reader in (
        ("Civitai resources", _civitai_records),
        ("additional_hashes", _additional_records),
    ):
        if field != selected and field in fields:
            extra = reader(fields[field], warnings)
            if extra:
                _enrich(records, extra, warnings)
                source["fields"].append(field)
    unique: list[dict[str, Any]] = []
    for item in records:
        previous = next((row for row in unique if _same_resource(item, row)), None)
        if previous:
            _enrich([previous], [item], warnings)
        else:
            unique.append(item)
    source["warnings"] = list(dict.fromkeys(warnings))
    source["status"] = "partial" if warnings else "recorded" if unique else "recorded_empty"
    return unique, source
