from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from prompt_hub.dataset_tagging import DatasetTaggingError, normalize_tag_draft
from prompt_hub.dataset_workspace import DatasetWorkspaceError
from prompt_hub.tag_locale import TagLocaleError, resolve_canonical_tag

if TYPE_CHECKING:
    from pathlib import Path

CaptionProfile = Literal["anima", "krea2"]
MAX_CAPTION_CHARS = 12000


def _normalize_caption(profile_id: CaptionProfile, caption: str) -> str:
    clean = caption.strip()[:MAX_CAPTION_CHARS]
    if clean and not clean.isascii():
        message = "最终 caption 必须使用英文"
        raise DatasetWorkspaceError(message)
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
        message = f"Invalid JSON object: {path}"
        raise DatasetWorkspaceError(message)
    return loaded


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _inside_directory(root: Path, relative_path: str) -> Path:
    clean_root = root.resolve()
    path = (clean_root / relative_path).resolve()
    if not path.is_relative_to(clean_root):
        message = "Dataset export path escapes its version directory"
        raise DatasetWorkspaceError(message)
    return path


def _safe_directory_name(value: str) -> str:
    clean = "".join(
        character if character.isalnum() or character in "-_." else "-" for character in value
    )
    clean = re.sub(r"-+", "-", clean).strip("-.")[:80]
    return clean or "dataset"


def _directory_stats(root: Path) -> tuple[int, int]:
    files = [path for path in root.rglob("*") if path.is_file()] if root.is_dir() else []
    return len(files), sum(path.stat().st_size for path in files)


def _source_result_asset_ids(items: Iterable[Mapping[str, Any]]) -> list[str]:
    result = []
    for item in items:
        source = item.get("source", {})
        if isinstance(source, Mapping) and source.get("asset_id"):
            result.append(str(source["asset_id"]))
    return result


def _directory_digest_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_hash_manifest(root: Path) -> None:
    lines = [
        f"{digest}  {relative_path}"
        for relative_path, digest in _directory_digest_map(root).items()
        if relative_path != "hashes.sha256"
    ]
    (root / "hashes.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
