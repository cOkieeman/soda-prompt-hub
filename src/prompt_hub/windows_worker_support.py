from __future__ import annotations

# standalone-bundle: omit-start
import hashlib
import json
import os
import re
import shutil
import urllib.parse
from collections import Counter
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

# standalone-bundle: omit-end

WORKER_BUILD_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
COMPUTE_PROTOCOL_VERSION = "soda-compute-bridge-v2"
WORKER_RELEASE_FORMAT = "soda-windows-worker-release-v1"


def _release_channel(version_value: str) -> str:
    normalized = version_value.casefold()
    if "dev" in normalized:
        return "development"
    if "rc" in normalized:
        return "candidate"
    return "stable"


def _load_worker_release() -> dict[str, str]:
    try:
        fallback_version = package_version("prompt-hub")
    except PackageNotFoundError:  # pragma: no cover - standalone release supplies RELEASE.json
        fallback_version = "0+unknown"
    fallback = {
        "format": WORKER_RELEASE_FORMAT,
        "worker_version": fallback_version,
        "release_channel": _release_channel(fallback_version),
        "protocol_version": COMPUTE_PROTOCOL_VERSION,
    }
    release_path = Path(__file__).with_name("RELEASE.json")
    if not release_path.is_file():
        return fallback
    try:
        raw = json.loads(release_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return fallback
    if not isinstance(raw, dict) or raw.get("format") != WORKER_RELEASE_FORMAT:
        return fallback
    return {
        "format": WORKER_RELEASE_FORMAT,
        "worker_version": str(raw.get("worker_version", fallback_version)),
        "release_channel": str(raw.get("release_channel", fallback["release_channel"])),
        "protocol_version": str(raw.get("protocol_version", COMPUTE_PROTOCOL_VERSION)),
    }


WORKER_RELEASE = _load_worker_release()
WORKER_VERSION = WORKER_RELEASE["worker_version"]
TASK_FORMAT = "soda-compute-task-v1"
RESULT_FORMAT = "soda-compute-result-v1"
PACKAGE_FORMAT = "soda-comfyui-package-v1"
TARGET_ROLE = "compute_5060ti"
SAFE_TASK_TYPES = {"comfyui_generate", "lora_catalog_snapshot", "model_catalog_snapshot"}
FINAL_DIRECTORIES = ("inbox", "completed", "failed")
LORA_MODEL_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".pth"}
MODEL_ASSET_SUFFIXES = {
    ".bin",
    ".ckpt",
    ".gguf",
    ".onnx",
    ".pt",
    ".pth",
    ".safetensors",
}
MODEL_ASSET_TYPES = {
    "checkpoint",
    "controlnet",
    "diffusion_model",
    "text_encoder",
    "upscaler",
    "vae",
}
LORA_PREVIEW_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")
LORA_PREVIEW_SIDECAR_STEMS = ("civitai_bak", "preview")
MODEL_METADATA_SIDECARS = (".metadata.json", ".civitai.info", ".info.json", ".json")
CIVITAI_HOSTS = {"civitai.com", "www.civitai.com", "civitai.red", "www.civitai.red"}
CIVITAI_MODEL_PATH_RE = re.compile(r"^/models/(?P<model_id>[1-9]\d*)(?:/[^/?#]+)?/?$")
MAX_LORA_METADATA_BYTES = 2 * 1024 * 1024
MAX_LORA_PREVIEW_BYTES = 32 * 1024 * 1024
MAX_LORA_PREVIEW_COUNT = 1024
MAX_LORA_PREVIEW_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_CIVITAI_URL_LENGTH = 2000


class WorkerError(RuntimeError):
    pass


class TaskCanceledError(WorkerError):
    pass


@dataclass(frozen=True, slots=True)
class LoraRootConfig:
    root_id: str
    path: Path


@dataclass(frozen=True, slots=True)
class ModelRootConfig:
    root_id: str
    asset_type: str
    path: Path
    model_family: str = ""


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    bridge_root: Path
    comfyui_url: str
    worker_id: str
    role: str = TARGET_ROLE
    poll_interval_seconds: float = 2.0
    history_poll_seconds: float = 1.0
    task_timeout_seconds: float = 900.0
    http_timeout_seconds: float = 30.0
    lora_roots: tuple[LoraRootConfig, ...] = ()
    model_roots: tuple[ModelRootConfig, ...] = ()

    @classmethod
    def load(cls, path: Path) -> WorkerConfig:
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkerError(f"无法读取 worker 配置：{error}") from error
        if not isinstance(raw, dict):
            raise WorkerError("worker 配置必须是 JSON 对象")
        root_value = str(raw.get("bridge_root", "")).strip()
        worker_id = str(raw.get("worker_id", "")).strip()
        role = str(raw.get("role", TARGET_ROLE)).strip()
        comfyui_url = str(raw.get("comfyui_url", "")).strip().rstrip("/")
        if not root_value or not Path(root_value).is_absolute():
            raise WorkerError("bridge_root 必须是绝对路径")
        if not worker_id or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for char in worker_id
        ):
            raise WorkerError("worker_id 只能包含字母、数字、点、下划线和连字符")
        if role != TARGET_ROLE:
            raise WorkerError(f"role 必须是 {TARGET_ROLE}")
        parsed = urllib.parse.urlsplit(comfyui_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise WorkerError("comfyui_url 必须是带主机名的 http(s) 地址")
        lora_roots = _parse_lora_roots(raw.get("lora_roots", []))
        model_roots = _parse_model_roots(raw.get("model_roots", []))
        return cls(
            bridge_root=Path(root_value),
            comfyui_url=comfyui_url,
            worker_id=worker_id,
            role=role,
            poll_interval_seconds=_positive_float(raw, "poll_interval_seconds", 2.0),
            history_poll_seconds=_positive_float(raw, "history_poll_seconds", 1.0),
            task_timeout_seconds=_positive_float(raw, "task_timeout_seconds", 900.0),
            http_timeout_seconds=_positive_float(raw, "http_timeout_seconds", 30.0),
            lora_roots=lora_roots,
            model_roots=model_roots,
        )


def _parse_lora_roots(value: object) -> tuple[LoraRootConfig, ...]:
    if value in (None, []):
        return ()
    if not isinstance(value, list):
        raise WorkerError("lora_roots 配置必须是列表")
    roots = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            raise WorkerError("lora_roots 配置条目必须是对象")
        root_id = str(item.get("root_id", "")).strip()
        path = Path(str(item.get("path", "")).strip())
        if not _safe_identifier(root_id) or root_id in seen:
            raise WorkerError(f"LoRA root_id 无效或重复：{root_id}")
        if not path.is_absolute():
            raise WorkerError(f"LoRA 根目录必须是绝对路径：{root_id}")
        roots.append(LoraRootConfig(root_id=root_id, path=path))
        seen.add(root_id)
    return tuple(roots)


def _parse_model_roots(value: object) -> tuple[ModelRootConfig, ...]:
    if value in (None, []):
        return ()
    if not isinstance(value, list):
        raise WorkerError("model_roots 配置必须是列表")
    roots = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            raise WorkerError("model_roots 配置条目必须是对象")
        root_id = str(item.get("root_id", "")).strip()
        asset_type = str(item.get("asset_type", "")).strip()
        path = Path(str(item.get("path", "")).strip())
        if not _safe_identifier(root_id) or root_id in seen:
            raise WorkerError(f"模型 root_id 无效或重复：{root_id}")
        if asset_type not in MODEL_ASSET_TYPES:
            raise WorkerError(f"模型 asset_type 无效：{asset_type}")
        if not path.is_absolute():
            raise WorkerError(f"模型根目录必须是绝对路径：{root_id}")
        roots.append(
            ModelRootConfig(
                root_id=root_id,
                asset_type=asset_type,
                path=path,
                model_family=str(item.get("model_family", "")).strip()[:160],
            )
        )
        seen.add(root_id)
    return tuple(roots)


def _lora_root_status(root: LoraRootConfig) -> dict[str, Any]:
    exists = root.path.is_dir()
    count = 0
    if exists:
        count = sum(
            path.is_file() and path.suffix.casefold() in LORA_MODEL_SUFFIXES
            for path in root.path.rglob("*")
        )
    return {
        "root_id": root.root_id,
        "path": str(root.path),
        "exists": exists,
        "model_count": count,
    }


def _model_root_status(root: ModelRootConfig) -> dict[str, Any]:
    exists = root.path.is_dir()
    count = 0
    if exists:
        count = sum(
            path.is_file() and path.suffix.casefold() in MODEL_ASSET_SUFFIXES
            for path in root.path.rglob("*")
        )
    return {
        "root_id": root.root_id,
        "asset_type": root.asset_type,
        "model_family": root.model_family,
        "path": str(root.path),
        "exists": exists,
        "model_count": count,
    }


def _scan_model_root(root: ModelRootConfig) -> list[dict[str, Any]]:
    items = []
    for path in root.path.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in MODEL_ASSET_SUFFIXES:
            continue
        relative = path.relative_to(root.path).as_posix()
        stat = path.stat()
        metadata, metadata_path = _read_asset_metadata(path)
        previews = _find_model_previews(root.path, path, metadata)
        public_metadata = _public_lora_metadata(metadata)
        public_metadata.update(
            {
                "suffix": path.suffix.casefold(),
                "metadata_sidecar": bool(metadata_path),
                "metadata_sidecar_name": metadata_path.name if metadata_path else "",
            }
        )
        items.append(
            {
                "asset_id": _model_asset_id(root.root_id, root.asset_type, relative),
                "asset_type": root.asset_type,
                "root_id": root.root_id,
                "name": path.stem,
                "relative_path": relative,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                "model_family": _model_family(relative, root.model_family),
                "source_url": _civitai_source_url(metadata),
                "preview_relative_path": previews[0] if previews else "",
                "preview_relative_paths": previews,
                "metadata": public_metadata,
            }
        )
    return items


def _model_asset_id(root_id: str, asset_type: str, relative_path: str) -> str:
    raw = f"{asset_type}\0{root_id}\0{relative_path.casefold()}".encode()
    return f"asset-{hashlib.sha256(raw).hexdigest()[:24]}"


def _model_snapshot_id(items: list[dict[str, Any]]) -> str:
    compact = [
        {
            "asset_id": item["asset_id"],
            "size_bytes": item["size_bytes"],
            "modified_at": item["modified_at"],
        }
        for item in items
    ]
    raw = json.dumps(compact, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"models-{stamp}-{hashlib.sha256(raw).hexdigest()[:12]}"


def _scan_lora_root(
    root: LoraRootConfig,
    visible_names: set[str],
) -> list[dict[str, Any]]:
    items = []
    for path in root.path.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in LORA_MODEL_SUFFIXES:
            continue
        relative = path.relative_to(root.path).as_posix()
        metadata, metadata_path = _read_asset_metadata(path)
        civitai = metadata.get("civitai")
        civitai = civitai if isinstance(civitai, dict) else {}
        civitai_model = civitai.get("model")
        civitai_model = civitai_model if isinstance(civitai_model, dict) else {}
        previews = _find_lora_previews(root.path, path, metadata)
        trigger_words = _metadata_strings(
            metadata,
            "trigger_words",
            "triggerWords",
            "trained_words",
            "trainedWords",
        )
        if not trigger_words:
            trigger_words = _metadata_strings(civitai, "trainedWords", "triggerWords")
        tags = _unique_strings(
            _metadata_strings(metadata, "tags", "tag_list", "tagList")
            + _metadata_strings(civitai_model, "tags")
        )
        base_model = _metadata_text(metadata, "base_model", "baseModel", "base_model_name") or (
            _metadata_text(civitai, "baseModel", "base_model")
        )
        family = _model_family(relative, base_model)
        item_metadata = _public_lora_metadata(metadata)
        item_metadata.update(
            {
                "root_id": root.root_id,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                "comfyui_visible": relative.casefold() in visible_names,
                "metadata_sidecar": bool(metadata_path),
                "metadata_sidecar_name": metadata_path.name if metadata_path else "",
            }
        )
        items.append(
            {
                "lora_id": _lora_id(root.root_id, relative),
                "name": _metadata_text(metadata, "name", "model_name", "modelName") or path.stem,
                "relative_path": relative,
                "sha256": _metadata_sha256(metadata),
                "size_bytes": path.stat().st_size,
                "base_model": base_model,
                "model_family": family,
                "source_url": _civitai_source_url(metadata),
                "trigger_words": trigger_words,
                "tags": tags,
                "preview_relative_path": previews[0] if previews else "",
                "preview_relative_paths": previews,
                "notes": _metadata_text(metadata, "notes")[:2000],
                "metadata": item_metadata,
            }
        )
    return items


def _read_lora_metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        if path.stat().st_size > MAX_LORA_METADATA_BYTES:
            return {"metadata_error": "sidecar_too_large"}
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"metadata_error": "sidecar_unreadable"}
    return value if isinstance(value, dict) else {"metadata_error": "sidecar_not_object"}


def _read_asset_metadata(model: Path) -> tuple[dict[str, Any], Path | None]:
    candidates = [model.with_name(f"{model.stem}{suffix}") for suffix in MODEL_METADATA_SIDECARS]
    first_error: tuple[dict[str, Any], Path] | None = None
    for candidate in candidates:
        if not candidate.is_file():
            continue
        metadata = _read_lora_metadata(candidate)
        if "metadata_error" not in metadata:
            return metadata, candidate
        if first_error is None:
            first_error = metadata, candidate
    return first_error if first_error is not None else ({}, None)


def _find_lora_previews(root: Path, model: Path, metadata: dict[str, Any]) -> list[str]:
    return _find_asset_previews(root, model, metadata)


def _find_model_previews(
    root: Path,
    model: Path,
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    return _find_asset_previews(root, model, metadata or {})


def _find_asset_previews(root: Path, model: Path, metadata: dict[str, Any]) -> list[str]:
    discovered: list[Path] = []
    preview_value = _metadata_text(metadata, "preview_url", "previewUrl", "preview")
    if preview_value:
        candidate = Path(preview_value)
        if not candidate.is_absolute():
            candidate = model.parent / candidate
        with suppress(OSError, ValueError):
            resolved = candidate.resolve()
            if resolved.is_file() and resolved.is_relative_to(root.resolve()):
                discovered.append(resolved)
    model_stem = model.stem.casefold()
    accepted_stems = {model_stem}
    accepted_stems.update(f"{model_stem}.{sidecar}" for sidecar in LORA_PREVIEW_SIDECAR_STEMS)
    candidates = [
        path
        for path in model.parent.iterdir()
        if path.is_file()
        and path.suffix.casefold() in LORA_PREVIEW_SUFFIXES
        and path.stem.casefold() in accepted_stems
    ]
    preferred = sorted(
        (path.resolve() for path in candidates if path.is_file()),
        key=lambda path: (
            "civitai_bak" in path.name.casefold(),
            len(path.name),
            path.name.casefold(),
        ),
    )
    discovered.extend(preferred)
    unique = []
    root_resolved = root.resolve()
    for path in discovered:
        with suppress(OSError, ValueError):
            relative = path.relative_to(root_resolved).as_posix()
            if relative not in unique:
                unique.append(relative)
    return unique


def _copy_lora_previews(
    items: list[dict[str, Any]],
    roots: dict[str, Path],
    bridge_root: Path,
    output_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return _copy_asset_previews(
        items,
        roots,
        bridge_root,
        output_root,
        id_field="lora_id",
        target_directory="lora-previews",
        output_kind="lora_preview",
    )


def _copy_model_previews(
    items: list[dict[str, Any]],
    roots: dict[str, Path],
    bridge_root: Path,
    output_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    return _copy_asset_previews(
        items,
        roots,
        bridge_root,
        output_root,
        id_field="asset_id",
        target_directory="model-previews",
        output_kind="model_preview",
    )


def _copy_asset_previews(
    items: list[dict[str, Any]],
    roots: dict[str, Path],
    bridge_root: Path,
    output_root: Path,
    *,
    id_field: str,
    target_directory: str,
    output_kind: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    total_bytes = 0
    skipped = 0
    skipped_reasons: Counter[str] = Counter()
    for item in items:
        copied_sources = []
        root_id = str(item.get("root_id") or item.get("metadata", {}).get("root_id", ""))
        root = roots.get(root_id)
        if root is None:
            continue
        for source_relative in item.get("preview_relative_paths", []):
            if len(outputs) >= MAX_LORA_PREVIEW_COUNT:
                skipped += 1
                skipped_reasons["count_limit"] += 1
                continue
            try:
                clean_relative = _safe_relative_path(str(source_relative))
                source = _inside_root(root, clean_relative)
                suffix = source.suffix.casefold()
                size = source.stat().st_size
            except (OSError, WorkerError):
                skipped += 1
                skipped_reasons["source_unavailable"] += 1
                continue
            if suffix not in LORA_PREVIEW_SUFFIXES:
                skipped += 1
                skipped_reasons["unsupported_format"] += 1
                continue
            if size <= 0:
                skipped += 1
                skipped_reasons["empty_file"] += 1
                continue
            if size > MAX_LORA_PREVIEW_BYTES:
                skipped += 1
                skipped_reasons["file_too_large"] += 1
                continue
            try:
                detected_suffix = _lora_preview_suffix(source)
            except OSError:
                skipped += 1
                skipped_reasons["source_unavailable"] += 1
                continue
            if not detected_suffix:
                skipped += 1
                skipped_reasons["invalid_image_header"] += 1
                continue
            if total_bytes + size > MAX_LORA_PREVIEW_TOTAL_BYTES:
                skipped += 1
                skipped_reasons["total_size_limit"] += 1
                continue
            index = len(copied_sources)
            target = (
                output_root
                / target_directory
                / str(item[id_field])
                / f"{index:03d}{detected_suffix}"
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
            try:
                shutil.copyfile(source, temporary)
                os.replace(temporary, target)
            finally:
                with suppress(OSError):
                    temporary.unlink()
            record = _output_record(bridge_root, target, output_kind)
            record.update(
                {
                    id_field: item[id_field],
                    "preview_index": index,
                    "source_relative_path": clean_relative,
                }
            )
            outputs.append(record)
            copied_sources.append(clean_relative)
            total_bytes += size
        item["preview_relative_paths"] = copied_sources
        item["preview_relative_path"] = copied_sources[0] if copied_sources else ""
    return outputs, {
        "preview_count": len(outputs),
        "preview_total_bytes": total_bytes,
        "preview_skipped_count": skipped,
        "preview_skipped_reasons": dict(sorted(skipped_reasons.items())),
    }


def _lora_preview_suffix(path: Path) -> str:
    with path.open("rb") as handle:
        header = handle.read(16)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if header.startswith(b"\xff\xd8\xff"):
        return ".jpeg"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    if header[:6] in {b"GIF87a", b"GIF89a"}:
        return ".gif"
    return ""


def _metadata_text(metadata: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, (str, int, float)) and str(value).strip():
            return str(value).strip()[:1000]
    return ""


def _metadata_strings(metadata: dict[str, Any], *keys: str) -> list[str]:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str):
            return [part.strip()[:300] for part in value.split(",") if part.strip()][:300]
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict):
                    text = _metadata_text(item, "word", "name", "tag")
                else:
                    text = str(item).strip()[:300]
                if text and text not in result:
                    result.append(text)
                if len(result) >= 300:
                    break
            return result
    return []


def _unique_strings(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result[:300]


def _metadata_sha256(metadata: dict[str, Any]) -> str:
    value = _metadata_text(metadata, "sha256").casefold()
    if len(value) == 64 and all(char in "0123456789abcdef" for char in value):
        return value
    return ""


def _positive_metadata_id(value: object) -> int | None:
    text = str(value).strip() if isinstance(value, (str, int, float)) else ""
    if not text.isdigit():
        return None
    parsed = int(text)
    return parsed if parsed > 0 else None


def _civitai_ids(metadata: dict[str, Any]) -> tuple[int | None, int | None]:
    civitai = metadata.get("civitai")
    civitai = civitai if isinstance(civitai, dict) else {}
    model_id = next(
        (
            value
            for value in (
                _positive_metadata_id(metadata.get("modelId")),
                _positive_metadata_id(metadata.get("civitai_model_id")),
                _positive_metadata_id(civitai.get("modelId")),
                _positive_metadata_id(civitai.get("civitai_model_id")),
            )
            if value is not None
        ),
        None,
    )
    version_id = next(
        (
            value
            for value in (
                _positive_metadata_id(metadata.get("modelVersionId")),
                _positive_metadata_id(metadata.get("civitai_version_id")),
                _positive_metadata_id(civitai.get("modelVersionId")),
                _positive_metadata_id(civitai.get("civitai_version_id")),
                _positive_metadata_id(civitai.get("id")),
                _positive_metadata_id(metadata.get("id")) if model_id else None,
            )
            if value is not None
        ),
        None,
    )
    return model_id, version_id


def _normalize_civitai_page_url(value: object) -> tuple[str, int | None, int | None]:
    if not isinstance(value, str) or len(value) > MAX_CIVITAI_URL_LENGTH:
        return "", None, None
    with suppress(ValueError):
        parsed = urllib.parse.urlsplit(value.strip())
        host = (parsed.hostname or "").casefold()
        matched = CIVITAI_MODEL_PATH_RE.fullmatch(parsed.path)
        if parsed.scheme in {"http", "https"} and host in CIVITAI_HOSTS and matched:
            model_id = int(matched.group("model_id"))
            query = urllib.parse.parse_qs(parsed.query)
            version_id = _positive_metadata_id((query.get("modelVersionId") or [""])[0])
            base = f"https://{host}/models/{model_id}"
            suffix = f"?modelVersionId={version_id}" if version_id else ""
            return f"{base}{suffix}", model_id, version_id
    return "", None, None


def _explicit_civitai_page_url(metadata: dict[str, Any]) -> tuple[str, int | None, int | None]:
    pending: list[tuple[object, int]] = [(metadata, 0)]
    inspected = 0
    while pending and inspected < 500:
        value, depth = pending.pop()
        inspected += 1
        if isinstance(value, dict) and depth < 4:
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list) and depth < 4:
            pending.extend((item, depth + 1) for item in value[:100])
        elif isinstance(value, str):
            normalized = _normalize_civitai_page_url(value)
            if normalized[0]:
                return normalized
    return "", None, None


def _civitai_source_url(metadata: dict[str, Any]) -> str:
    explicit_url, explicit_model_id, explicit_version_id = _explicit_civitai_page_url(metadata)
    model_id, version_id = _civitai_ids(metadata)
    if explicit_url:
        chosen_version = explicit_version_id or version_id
        base = explicit_url.split("?", 1)[0]
        return f"{base}?modelVersionId={chosen_version}" if chosen_version else base
    chosen_model = explicit_model_id or model_id
    if chosen_model is None:
        return ""
    base = f"https://civitai.com/models/{chosen_model}"
    return f"{base}?modelVersionId={version_id}" if version_id else base


def _public_lora_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "modelId",
        "modelVersionId",
        "civitai_model_id",
        "civitai_version_id",
        "metadata_source",
        "preview_nsfw_level",
        "description",
        "version_name",
    )
    result = {}
    for key in allowed:
        value = metadata.get(key)
        if isinstance(value, (str, int, float, bool)):
            result[key] = str(value)[:2000] if isinstance(value, str) else value
    if error := _metadata_text(metadata, "metadata_error"):
        result["metadata_error"] = error
    civitai = metadata.get("civitai")
    if isinstance(civitai, dict):
        for source_key, target_key in (
            ("modelId", "civitai_model_id"),
            ("id", "civitai_version_id"),
            ("name", "civitai_version_name"),
        ):
            value = civitai.get(source_key)
            if isinstance(value, (str, int, float)):
                result[target_key] = str(value)[:1000] if isinstance(value, str) else value
    model_id, version_id = _civitai_ids(metadata)
    if model_id is not None:
        result["civitai_model_id"] = model_id
    if version_id is not None:
        result["civitai_version_id"] = version_id
    return result


def _model_family(relative: str, base_model: str) -> str:
    directory_aliases = {
        "anima": "anima",
        "flux": "flux",
        "flux.1": "flux",
        "flux1_dev": "flux",
        "illustrious": "illustrious",
        "krea2": "krea2",
        "noobai": "illustrious",
        "pony": "sdxl",
        "sdxl": "sdxl",
    }
    parts = PurePosixPath(relative.replace("\\", "/")).parts
    for part in parts[:-1]:
        if family := directory_aliases.get(part.casefold()):
            return family
    text = f"{relative} {base_model}".casefold()
    patterns = (
        ("anima", r"(?<![a-z0-9])anima(?![a-z0-9])"),
        ("krea2", r"(?<![a-z0-9])krea(?:[ ._-]*2)?(?![a-z0-9])"),
        ("illustrious", r"(?<![a-z0-9])(?:illustrious|noob(?:ai)?)(?![a-z0-9])"),
        ("flux", r"(?<![a-z0-9])flux(?:[ ._-]*1)?(?![a-z0-9])"),
        ("sdxl", r"(?<![a-z0-9])(?:sdxl|pony)(?![a-z0-9])"),
    )
    for family, pattern in patterns:
        if re.search(pattern, text):
            return family
    return "unknown"


def _lora_id(root_id: str, relative: str) -> str:
    value = f"{root_id}:{relative.casefold()}".encode()
    return f"lora-{hashlib.sha256(value).hexdigest()[:24]}"


def _lora_snapshot_id(items: list[dict[str, Any]]) -> str:
    facts = [
        {
            "lora_id": item["lora_id"],
            "relative_path": item["relative_path"],
            "size_bytes": item["size_bytes"],
            "modified_at": item["metadata"].get("modified_at", ""),
        }
        for item in items
    ]
    digest = hashlib.sha256(
        json.dumps(facts, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"catalog-{stamp}-{digest}"


def _positive_float(raw: dict[str, Any], key: str, default: float) -> float:
    try:
        value = float(raw.get(key, default))
    except (TypeError, ValueError) as error:
        raise WorkerError(f"{key} 必须是数字") from error
    if value <= 0:
        raise WorkerError(f"{key} 必须大于 0")
    return value


def _safe_identifier(value: str) -> bool:
    return (
        bool(value)
        and len(value) <= 160
        and all(
            char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
            for char in value
        )
    )


def _safe_relative_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or ":" in normalized
        or any(part in {"", "."} for part in path.parts)
    ):
        raise WorkerError(f"相对路径无效：{value}")
    return path.as_posix()


def _inside_root(root: Path, relative: str) -> Path:
    root_resolved = root.resolve()
    candidate = (root_resolved / Path(*PurePosixPath(relative).parts)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as error:
        raise WorkerError(f"路径越过 bridge_root：{relative}") from error
    return candidate


def _safe_output_name(name: str, index: int) -> str:
    stem = "".join(char if char.isalnum() or char in "._-" else "_" for char in Path(name).stem)
    suffix = "".join(char for char in Path(name).suffix if char.isalnum() or char == ".")[:12]
    return f"{index:03d}-{stem[:120] or 'output'}{suffix}"


def _output_record(root: Path, path: Path, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "relative_path": path.resolve().relative_to(root.resolve()).as_posix(),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkerError(f"无法读取 JSON {path.name}：{error}") from error
    if not isinstance(value, dict):
        raise WorkerError(f"JSON 必须是对象：{path.name}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _short_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))[:2000]


def _now() -> str:
    return datetime.now(UTC).isoformat()
