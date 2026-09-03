from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_COMFY_IMAGE_BYTES = 50 * 1024 * 1024
MAX_COMFY_IMAGE_PIXELS = 60_000_000
MAX_DIRECTORY_IMAGES = 2000
SUPPORTED_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}
DISPOSITIONS = {"unreviewed", "candidate", "failed_test", "reference"}


class ComfyResultError(ValueError):
    pass


class ComfyResultStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.index_path = root / "index.json"
        self._lock = Lock()

    def initialize(self) -> None:
        (self.root / "original").mkdir(parents=True, exist_ok=True)
        (self.root / "thumbnail").mkdir(parents=True, exist_ok=True)
        if not self.index_path.is_file():
            self._write_index({"format": "soda-comfy-results-v1", "items": []})

    def list_results(self, *, limit: int = 100) -> list[dict[str, Any]]:
        items = self._read_index()["items"]
        return [self._decorate(dict(item)) for item in reversed(items[-limit:])]

    def get(self, result_id: str) -> dict[str, Any] | None:
        item = next(
            (item for item in self._read_index()["items"] if item["result_id"] == result_id),
            None,
        )
        return self._decorate(dict(item)) if item is not None else None

    def import_bytes(
        self,
        raw: bytes,
        *,
        filename: str,
        source_path: str = "",
    ) -> dict[str, Any]:
        inspected = inspect_comfy_image(raw, filename=filename)
        digest = inspected["sha256"]
        with self._lock:
            index = self._read_index()
            existing = next((item for item in index["items"] if item["sha256"] == digest), None)
            if existing is not None:
                return {"result": self._decorate(dict(existing)), "duplicate": True}
            result_id = f"comfy-{uuid4().hex}"
            suffix = inspected.pop("suffix")
            original_name = f"{result_id}{suffix}"
            thumbnail_name = f"{result_id}.webp"
            (self.root / "original" / original_name).write_bytes(raw)
            _write_thumbnail(raw, self.root / "thumbnail" / thumbnail_name)
            item = {
                **inspected,
                "result_id": result_id,
                "filename": Path(filename).name[:180] or original_name,
                "source_path": source_path,
                "original_name": original_name,
                "thumbnail_name": thumbnail_name,
                "disposition": "unreviewed",
                "note": "",
                "associations": [],
                "created_at": _now(),
                "updated_at": _now(),
            }
            index["items"].append(item)
            self._write_index(index)
        return {"result": self._decorate(dict(item)), "duplicate": False}

    def import_directory(self, source_path: Path | str) -> dict[str, Any]:
        source = _validate_directory(source_path, self.root)
        paths = _collect_images(source)
        if len(paths) > MAX_DIRECTORY_IMAGES:
            raise ComfyResultError(f"目录图片超过 {MAX_DIRECTORY_IMAGES} 张，请拆分后导入")
        imported = 0
        duplicates = 0
        failed = []
        results = []
        for path in paths:
            try:
                outcome = self.import_bytes(
                    path.read_bytes(),
                    filename=path.name,
                    source_path=path.relative_to(source).as_posix(),
                )
            except (ComfyResultError, OSError) as error:
                failed.append({"path": path.relative_to(source).as_posix(), "error": str(error)})
                continue
            results.append(outcome["result"])
            duplicates += int(outcome["duplicate"])
            imported += int(not outcome["duplicate"])
        return {
            "source_path": str(source),
            "source_mode": "read-only",
            "scanned": len(paths),
            "imported": imported,
            "duplicates": duplicates,
            "failed": failed,
            "results": results,
        }

    def update(self, result_id: str, values: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            index = self._read_index()
            item = next((item for item in index["items"] if item["result_id"] == result_id), None)
            if item is None:
                raise ComfyResultError("ComfyUI result not found")
            if "disposition" in values:
                disposition = str(values["disposition"])
                if disposition not in DISPOSITIONS:
                    raise ComfyResultError("Invalid ComfyUI result disposition")
                item["disposition"] = disposition
            if "note" in values:
                item["note"] = str(values["note"])[:3000]
            if association := values.get("association"):
                if not isinstance(association, Mapping):
                    raise ComfyResultError("Invalid ComfyUI result association")
                clean = {
                    "kind": str(association.get("kind", ""))[:40],
                    "id": str(association.get("id", ""))[:180],
                    "created_at": _now(),
                }
                if (
                    clean["kind"]
                    and clean["id"]
                    and not any(
                        known.get("kind") == clean["kind"] and known.get("id") == clean["id"]
                        for known in item["associations"]
                    )
                ):
                    item["associations"].append(clean)
            item["updated_at"] = _now()
            self._write_index(index)
        return self._decorate(dict(item))

    def resolve_media(self, result_id: str, variant: str) -> Path | None:
        item = self.get(result_id)
        if item is None or variant not in {"original", "thumbnail"}:
            return None
        key = "original_name" if variant == "original" else "thumbnail_name"
        filename = str(item[key])
        if Path(filename).name != filename:
            return None
        root = (self.root / variant).resolve()
        path = (root / filename).resolve()
        return path if path.is_relative_to(root) and path.is_file() else None

    def read_original(self, result_id: str) -> bytes:
        path = self.resolve_media(result_id, "original")
        if path is None:
            raise ComfyResultError("ComfyUI result file not found")
        return path.read_bytes()

    def _decorate(self, item: dict[str, Any]) -> dict[str, Any]:
        result_id = item["result_id"]
        item["original_url"] = f"/comfy-results/{result_id}/original"
        item["thumbnail_url"] = f"/comfy-results/{result_id}/thumbnail"
        return item

    def _read_index(self) -> dict[str, Any]:
        if not self.index_path.is_file():
            return {"format": "soda-comfy-results-v1", "items": []}
        value = json.loads(self.index_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not isinstance(value.get("items"), list):
            raise ComfyResultError("ComfyUI result index is invalid")
        return value

    def _write_index(self, value: Mapping[str, Any]) -> None:
        temporary = self.index_path.with_name(f".{self.index_path.name}.{uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.index_path)


def inspect_comfy_image(raw: bytes, *, filename: str) -> dict[str, Any]:
    if not raw:
        raise ComfyResultError("图片文件为空")
    if len(raw) > MAX_COMFY_IMAGE_BYTES:
        raise ComfyResultError("图片超过 50 MiB 限制")
    try:
        with Image.open(BytesIO(raw)) as opened:
            image_format = str(opened.format or "").upper()
            if image_format not in SUPPORTED_FORMATS:
                raise ComfyResultError("只支持 PNG、JPEG 或 WebP 图片")
            width, height = opened.size
            if width <= 0 or height <= 0 or width * height > MAX_COMFY_IMAGE_PIXELS:
                raise ComfyResultError("图片尺寸无效或超过 6000 万像素限制")
            raw_info = {str(key): value for key, value in opened.info.items()}
            opened.load()
    except ComfyResultError:
        raise
    except (Image.DecompressionBombError, OSError, UnidentifiedImageError) as error:
        raise ComfyResultError("无法识别或读取这张图片") from error
    suffix, content_type = SUPPORTED_FORMATS[image_format]
    metadata = parse_generation_metadata(raw_info, width=width, height=height)
    return {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "width": width,
        "height": height,
        "image_format": image_format,
        "content_type": content_type,
        "suffix": suffix,
        "metadata": metadata,
        "metadata_present": metadata["metadata_present"],
        "metadata_source": metadata["source"],
        "original_filename": Path(filename).name[:180],
    }


def parse_generation_metadata(
    raw_info: Mapping[str, Any],
    *,
    width: int,
    height: int,
) -> dict[str, Any]:
    prompt = _json_value(raw_info.get("prompt"))
    workflow = _json_value(raw_info.get("workflow"))
    parameters = str(raw_info.get("parameters", ""))[:200_000]
    nodes = _prompt_nodes(prompt)
    extracted = _extract_nodes(nodes)
    if parameters:
        extracted = {**_parse_parameters(parameters), **{k: v for k, v in extracted.items() if v}}
    source = "comfyui" if prompt or workflow else "parameters" if parameters else "none"
    return {
        "metadata_present": bool(prompt or workflow or parameters),
        "source": source,
        "seed": extracted.get("seed"),
        "steps": extracted.get("steps"),
        "cfg": extracted.get("cfg"),
        "sampler": extracted.get("sampler", ""),
        "scheduler": extracted.get("scheduler", ""),
        "denoise": extracted.get("denoise"),
        "checkpoint": extracted.get("checkpoint", ""),
        "loras": extracted.get("loras", []),
        "positive_prompts": extracted.get("positive_prompts", []),
        "negative_prompts": extracted.get("negative_prompts", []),
        "text_prompts": extracted.get("text_prompts", []),
        "width": extracted.get("width") or width,
        "height": extracted.get("height") or height,
        "prompt": prompt,
        "workflow": workflow,
        "parameters": parameters,
    }


def _extract_nodes(nodes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    node_list = list(nodes)
    text_by_node: dict[str, str] = {}
    for node in node_list:
        class_type = str(node.get("class_type", "")).casefold()
        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            continue
        if "textencode" in class_type or "cliptext" in class_type:
            text = _first_string(inputs, "text", "prompt")
            node_id = str(node.get("_node_id", ""))
            if text and node_id:
                text_by_node[node_id] = text

    result: dict[str, Any] = {
        "loras": [],
        "text_prompts": [],
        "positive_prompts": [],
        "negative_prompts": [],
    }
    for node in node_list:
        class_type = str(node.get("class_type", "")).casefold()
        inputs = node.get("inputs", {})
        if not isinstance(inputs, Mapping):
            continue
        if "ksampler" in class_type or class_type in {"samplercustom", "sampler"}:
            result.update(
                {
                    "seed": _first_number(inputs, "seed", "noise_seed"),
                    "steps": _first_number(inputs, "steps"),
                    "cfg": _first_number(inputs, "cfg"),
                    "sampler": _first_string(inputs, "sampler_name", "sampler"),
                    "scheduler": _first_string(inputs, "scheduler"),
                    "denoise": _first_number(inputs, "denoise"),
                }
            )
            positive = _linked_text(inputs.get("positive"), text_by_node)
            negative = _linked_text(inputs.get("negative"), text_by_node)
            if positive:
                result["positive_prompts"].append(positive)
            if negative:
                result["negative_prompts"].append(negative)
        if any(token in class_type for token in ("checkpointloader", "unetloader")):
            result["checkpoint"] = _first_string(inputs, "ckpt_name", "unet_name", "model_name")
        if "loraloader" in class_type or class_type.startswith("lora"):
            name = _first_string(inputs, "lora_name", "model_name")
            if name:
                result["loras"].append(
                    {
                        "name": name,
                        "strength_model": _first_number(inputs, "strength_model", "strength"),
                        "strength_clip": _first_number(inputs, "strength_clip"),
                    }
                )
        if "emptylatent" in class_type:
            result["width"] = _first_number(inputs, "width")
            result["height"] = _first_number(inputs, "height")
        if "textencode" in class_type or "cliptext" in class_type:
            text = _first_string(inputs, "text", "prompt")
            if text:
                result["text_prompts"].append(text)
    result["loras"] = list({item["name"]: item for item in result["loras"]}.values())
    for key in ("text_prompts", "positive_prompts", "negative_prompts"):
        result[key] = list(dict.fromkeys(result[key]))
    return result


def _parse_parameters(value: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "text_prompts": [],
        "positive_prompts": [],
        "negative_prompts": [],
    }
    lines = value.strip().splitlines()
    if lines:
        positive = lines[0].strip()
        if positive:
            result["text_prompts"] = [positive]
            result["positive_prompts"] = [positive]
    negative = re.search(
        r"Negative prompt:\s*(.*?)(?:\nSteps:|$)", value, re.IGNORECASE | re.DOTALL
    )
    if negative and negative.group(1).strip():
        result["negative_prompts"] = [negative.group(1).strip()]
    match = re.search(r"Steps:\s*(\d+)", value, re.IGNORECASE)
    if match:
        result["steps"] = int(match.group(1))
    for key, label in (("seed", "Seed"), ("cfg", "CFG scale")):
        match = re.search(rf"{label}:\s*([0-9.]+)", value, re.IGNORECASE)
        if match:
            result[key] = float(match.group(1)) if "." in match.group(1) else int(match.group(1))
    for key, label in (("sampler", "Sampler"), ("checkpoint", "Model")):
        match = re.search(rf"{label}:\s*([^,\n]+)", value, re.IGNORECASE)
        if match:
            result[key] = match.group(1).strip()
    match = re.search(r"Size:\s*(\d+)x(\d+)", value, re.IGNORECASE)
    if match:
        result["width"], result["height"] = int(match.group(1)), int(match.group(2))
    return result


def _prompt_nodes(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return []
    return [
        {**item, "_node_id": str(node_id)}
        for node_id, item in value.items()
        if isinstance(item, Mapping)
    ]


def _linked_text(value: Any, text_by_node: Mapping[str, str]) -> str:
    if isinstance(value, (list, tuple)) and value:
        return text_by_node.get(str(value[0]), "")
    return ""


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value[:200_000]


def _first_string(inputs: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = inputs.get(key)
        if isinstance(value, str):
            return value[:20_000]
    return ""


def _first_number(inputs: Mapping[str, Any], *keys: str) -> int | float | None:
    for key in keys:
        value = inputs.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def _write_thumbnail(raw: bytes, path: Path) -> None:
    with Image.open(BytesIO(raw)) as opened:
        thumbnail = ImageOps.exif_transpose(opened).convert("RGB")
        thumbnail.thumbnail((640, 640), Image.Resampling.LANCZOS)
        thumbnail.save(path, "WEBP", quality=84, method=6)


def _validate_directory(source_path: Path | str, store_root: Path) -> Path:
    try:
        source = Path(source_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ComfyResultError("回流目录不存在或无法读取") from error
    if not source.is_dir():
        raise ComfyResultError("回流来源必须是文件夹")
    home = Path.home().resolve()
    if source in {Path("/").resolve(), home, store_root.resolve()}:
        raise ComfyResultError("请不要选择系统根目录、个人主目录或回流库根目录")
    if store_root.resolve().is_relative_to(source):
        raise ComfyResultError("回流目录不能包含 Prompt Hub 回流库")
    return source


def _collect_images(source: Path) -> list[Path]:
    paths = []
    for directory, names, filenames in os.walk(source, followlinks=False):
        names[:] = sorted(name for name in names if not (Path(directory) / name).is_symlink())
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if not path.is_symlink() and path.suffix.casefold() in {
                ".png",
                ".jpg",
                ".jpeg",
                ".webp",
            }:
                paths.append(path)
    return paths


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
