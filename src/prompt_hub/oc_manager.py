from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SUPPORTED_FORMATS = {
    "oc-manager-single-character",
    "oc-manager-world-folders",
    "oc-manager-full-database",
    "oc-manager-app-data",
    "oc-manager-character-array",
}

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class OCImportBundle:
    format_name: str
    characters: list[dict[str, Any]]
    worlds: list[dict[str, Any]]
    lore: dict[str, dict[str, Any]]


def parse_oc_manager_json(raw: bytes) -> OCImportBundle:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        msg = "Invalid OC Manager JSON"
        raise ValueError(msg) from error

    if isinstance(payload, list):
        return OCImportBundle(
            format_name="oc-manager-character-array",
            characters=_validate_characters(payload),
            worlds=[],
            lore={},
        )
    if not isinstance(payload, dict):
        msg = "OC Manager export must be a JSON object or character array"
        raise TypeError(msg)

    format_name = str(payload.get("format", "")).strip()
    if format_name == "oc-manager-single-character":
        characters = _validate_characters([payload.get("character")])
        return OCImportBundle(format_name, characters, [], {})
    if format_name == "oc-manager-world-folders":
        return _parse_world_folders(payload)
    if format_name == "oc-manager-full-database" or isinstance(payload.get("characters"), list):
        normalized_format = format_name or "oc-manager-app-data"
        if normalized_format not in SUPPORTED_FORMATS:
            normalized_format = "oc-manager-app-data"
        return OCImportBundle(
            format_name=normalized_format,
            characters=_validate_characters(payload.get("characters", [])),
            worlds=_mapping_list(payload.get("worlds", []), "worlds"),
            lore=_lore_map(payload.get("lore", {})),
        )

    msg = f"Unsupported OC Manager export format: {format_name or 'unknown'}"
    raise ValueError(msg)


def archive_import(root: Path, filename: str, raw: bytes) -> tuple[Path, str]:
    digest = hashlib.sha256(raw).hexdigest()
    destination = root / "sources" / "imports" / "oc-manager"
    destination.mkdir(parents=True, exist_ok=True)
    existing = next(destination.glob(f"*-{digest[:12]}-*.json"), None)
    if existing is not None:
        return existing, digest

    safe_name = _safe_filename(filename)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = destination / f"{timestamp}-{digest[:12]}-{safe_name}"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_bytes(raw)
    temporary.replace(target)
    return target, digest


def character_search_text(character: Mapping[str, Any]) -> str:
    fields = (
        character.get("name"),
        character.get("gender"),
        character.get("age"),
        character.get("race"),
        character.get("affiliation"),
        character.get("identity"),
        character.get("residence"),
        character.get("faction"),
        character.get("birthplace"),
        character.get("world"),
        character.get("story"),
        character.get("modules"),
        character.get("preferences"),
        character.get("timeline"),
        character.get("relationships"),
        character.get("prompts"),
    )
    return "\n".join(_text_values(fields))


def lore_search_text(lore: Mapping[str, Any]) -> str:
    return "\n".join(_text_values(lore.values()))


def _parse_world_folders(payload: dict[str, Any]) -> OCImportBundle:
    raw_worlds = payload.get("worlds", {})
    if not isinstance(raw_worlds, dict):
        msg = "worlds must be an object in oc-manager-world-folders"
        raise TypeError(msg)
    characters: list[Any] = []
    worlds: list[dict[str, Any]] = []
    for world_name, folder in raw_worlds.items():
        if not isinstance(folder, dict):
            continue
        clean_name = str(world_name).strip()
        if clean_name:
            worlds.append({"id": f"folder:{clean_name}", "name": clean_name, "system": "generic"})
        for raw_character in folder.get("characters", []):
            character = raw_character
            if isinstance(character, dict) and clean_name and not character.get("world"):
                character = {**character, "world": clean_name}
            characters.append(character)
    characters.extend(payload.get("unassigned", []))
    return OCImportBundle(
        format_name="oc-manager-world-folders",
        characters=_validate_characters(characters),
        worlds=worlds,
        lore=_lore_map(payload.get("lore", {})),
    )


def _validate_characters(raw_characters: Iterable[Any]) -> list[dict[str, Any]]:
    characters: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_character in enumerate(raw_characters):
        if not isinstance(raw_character, dict):
            msg = f"Character at index {index} is not an object"
            raise TypeError(msg)
        character_id = str(raw_character.get("id", "")).strip()
        name = str(raw_character.get("name", "")).strip()
        if not character_id or not name:
            msg = f"Character at index {index} requires id and name"
            raise ValueError(msg)
        if character_id in seen:
            msg = f"Duplicate character id: {character_id}"
            raise ValueError(msg)
        seen.add(character_id)
        characters.append(dict(raw_character))
    return characters


def _mapping_list(value: object, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        msg = f"{field_name} must be an array"
        raise TypeError(msg)
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            msg = f"{field_name}[{index}] is not an object"
            raise TypeError(msg)
        result.append(dict(item))
    return result


def _lore_map(value: object) -> dict[str, dict[str, Any]]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        msg = "lore must be an object"
        raise TypeError(msg)
    return {str(key): dict(item) for key, item in value.items() if isinstance(item, dict)}


def _text_values(values: Iterable[Any]) -> Iterable[str]:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            clean = value.strip()
            if clean and not clean.startswith(("http://", "https://", "data:")):
                yield clean
        elif isinstance(value, (int, float, bool)):
            yield str(value)
        elif isinstance(value, Mapping):
            yield from _text_values(value.values())
        elif isinstance(value, Iterable):
            yield from _text_values(value)


def _safe_filename(filename: str) -> str:
    original = Path(filename).name[:120]
    safe = _SAFE_FILENAME_RE.sub("-", original).strip("-.") or "oc-manager-export.json"
    if not safe.lower().endswith(".json"):
        safe += ".json"
    return safe
