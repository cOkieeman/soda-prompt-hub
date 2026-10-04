from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import tomllib
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import quote

from prompt_hub.config import Settings
from prompt_hub.database import EntryInput, PromptDatabase
from prompt_hub.local_sources import local_source_mapping, mapped_catalogue_path, mapped_source_path
from prompt_hub.media import build_kisega_thumbnails
from prompt_hub.style_explorers import discover_style_explorers, load_style_entries


class SourceVersionError(RuntimeError):
    """Raised when a local source directory has no usable Git version."""


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source_id: str
    name: str
    url: str
    path: Path
    license_name: str
    notes: str
    importer: str
    backup_path: Path | None = None
    backup_revision: str = ""
    local_only: bool = False
    local_error: str = ""
    data_path: Path | None = None


_ADULT_TAGS = {
    "nude",
    "naked",
    "sex",
    "vaginal",
    "anal",
    "fellatio",
    "penis",
    "pussy",
    "vagina",
    "cum",
    "masturbation",
    "explicit",
}
_SUGGESTIVE_TAGS = {
    "revealing clothes",
    "underboob",
    "sideboob",
    "cleavage",
    "bikini",
    "lingerie",
    "leotard",
    "panties",
    "see-through",
}
_MAX_TAG_EXAMPLES = 3
_ANIMADEX_HAIR_COLORS = {
    "aqua hair",
    "black hair",
    "blonde hair",
    "blue hair",
    "brown hair",
    "dark blue hair",
    "gradient hair",
    "green hair",
    "grey hair",
    "light blue hair",
    "light brown hair",
    "light green hair",
    "light purple hair",
    "multicolored hair",
    "orange hair",
    "pink hair",
    "purple hair",
    "red hair",
    "silver hair",
    "split-color hair",
    "streaked hair",
    "two-tone hair",
    "white hair",
}
_ANIMADEX_EYE_COLORS = {
    "aqua eyes",
    "black eyes",
    "blue eyes",
    "brown eyes",
    "gradient eyes",
    "green eyes",
    "grey eyes",
    "multicolored eyes",
    "orange eyes",
    "pink eyes",
    "purple eyes",
    "red eyes",
    "two-tone eyes",
    "yellow eyes",
}


def discover_sources(settings: Settings) -> list[SourceSpec]:
    root = settings.git_sources_root
    sources = [
        SourceSpec(
            source_id="clio-style-preview",
            name="Clio Style Library",
            url="https://github.com/lumenastrum/clio-style-preview",
            path=root / "clio-style-preview",
            license_name="MIT (code); community prompt text",
            notes="397 long-form style prompts; keep attribution from upstream README.",
            importer="clio",
        ),
        SourceSpec(
            source_id="krea-open-prompts",
            name="Krea Open Prompts",
            url="https://github.com/krea-ai/open-prompts",
            path=root / "open-prompts",
            license_name="unknown",
            notes="Repository subset only; external 3GB+ CSV intentionally excluded.",
            importer="krea",
        ),
        SourceSpec(
            source_id="sd-wildcards",
            name="SD Wildcards",
            url="https://github.com/mattjaybe/sd-wildcards",
            path=root / "sd-wildcards",
            license_name="MIT",
            notes="Community wildcard lists; quality varies and requires user testing.",
            importer="wildcards",
        ),
        SourceSpec(
            source_id="kisegaeningyou",
            name="Kisegaeningyou",
            url="https://github.com/hayde0096/Kisegaeningyou",
            path=root / "Kisegaeningyou",
            license_name="unknown",
            notes="Paired images and captions; local personal indexing and research only.",
            importer="kisega",
        ),
        SourceSpec(
            source_id="animadex",
            name="AnimaDex",
            url="https://github.com/zetaneko/AnimaDex",
            path=root / "AnimaDex",
            license_name="MIT",
            notes=(
                "Character, artist, and copyright visual references. The Git checkout "
                "contains a small sample; a personal animadex.net export can populate "
                "the separate animadex-data directory with the full thumbnail catalogue."
            ),
            importer="animadex",
        ),
        SourceSpec(
            source_id="neons-style-explorer",
            name="Neons Style Explorer",
            url="https://github.com/Neon-Sparks/ComfyUI-NeonsStyleExplorer",
            path=root / "ComfyUI-NeonsStyleExplorer",
            license_name="MIT; see THIRD-PARTY-NOTICES.md",
            notes=(
                "Style, format and finish text catalog only; no ComfyUI code is executed. "
                "Extra entries imported from Krea2 are excluded to avoid duplicates. "
                "No previews bundled; model compatibility requires testing."
            ),
            importer="neons_styles",
        ),
    ]
    sources.extend(
        SourceSpec(
            source_id=source.source_id,
            name=source.name,
            url=f"https://github.com/ThetaCursed/{source.repository}",
            path=source.path,
            license_name="See upstream LICENSE; image and artist references",
            notes=source.notes,
            importer="style-explorer",
            backup_path=source.backup_path,
            backup_revision=source.backup_revision,
        )
        for source in discover_style_explorers(settings)
    )
    mappings, error = local_source_mapping(settings)
    return [
        replace(
            spec,
            path=mapped_source_path(settings, spec.source_id, spec.path),
            local_only=True,
            data_path=mapped_catalogue_path(settings, spec.source_id),
            local_error=error or _mapping_error(mappings.get(spec.source_id)),
            notes=spec.notes + " 本地只读映射。刷新仅重建索引。" + error,
        )
        if error or spec.source_id in mappings
        else spec
        for spec in sources
    ]


def _mapping_error(details: object) -> str:
    if (
        not isinstance(details, dict)
        or not isinstance(details.get("path"), str)
        or not Path(details["path"]).expanduser().is_absolute()
    ):
        return "本地映射需要绝对路径。已禁止自动拉取资料。"
    return ""


def _local_revision(spec: SourceSpec) -> str:
    # Hash catalogue text only. Large preview libraries stay in place.
    patterns = {
        "style-explorer": ["app/data.js"],
        "neons_styles": ["styles/*.json"],
        "clio": ["styles.json"],
        "krea": ["*.json"],
        "wildcards": ["**/*.txt"],
        "kisega": ["images*/*.desc.txt"],
        "animadex": ["samples/*.csv", "config.toml"],
    }
    digest = hashlib.sha256()
    for pattern in patterns[spec.importer]:
        for path in sorted(spec.path.glob(pattern)):
            if path.is_file() and path.resolve().is_relative_to(spec.path.resolve()):
                digest.update(path.relative_to(spec.path).as_posix().encode())
                digest.update(path.read_bytes())
    if spec.data_path is not None:
        for name in ("characters.csv", "artists.csv"):
            digest.update((spec.data_path / "import" / name).read_bytes())
    return "local:" + digest.hexdigest()


def import_all(settings: Settings, database: PromptDatabase) -> dict[str, int]:
    """Rebuild indexes and return only the per-source entry counts."""
    return import_report(settings, database)["sources"]


def import_report(settings: Settings, database: PromptDatabase) -> dict[str, Any]:
    """Rebuild indexes source by source and report what was skipped or failed.

    One unusable source never aborts the rest of the rebuild, and a source that
    scans to zero entries never silently replaces entries that are already indexed.
    """
    database.initialize()
    build_kisega_thumbnails(settings)
    previous_counts = _existing_entry_counts(database)
    sources: dict[str, int] = {}
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for spec in discover_sources(settings):
        outcome = _import_one(spec, database, previous_counts.get(spec.source_id, 0))
        if outcome["status"] == "imported":
            sources[spec.source_id] = int(outcome["count"])
        elif outcome["status"] == "missing":
            skipped.append(outcome)
        else:
            failed.append(outcome)
    _write_manifest(settings, database.list_sources())
    return {"sources": sources, "skipped": skipped, "failed": failed}


def _import_one(spec: SourceSpec, database: PromptDatabase, previous_count: int) -> dict[str, Any]:
    outcome = {
        "source_id": spec.source_id,
        "name": spec.name,
        "local_path": str(spec.path),
        "previous_count": previous_count,
        "count": 0,
    }
    if spec.local_error:
        return {**outcome, "status": "load_error", "message": spec.local_error}
    if not spec.path.is_dir():
        return {**outcome, "status": "missing", "message": "本地资料目录不存在，本次未重建这个来源"}
    try:
        commit_hash = _local_revision(spec) if spec.local_only else _git_commit(spec.path)
    except (SourceVersionError, OSError) as error:
        return {
            **outcome,
            "status": "not_git" if isinstance(error, SourceVersionError) else "load_error",
            "message": _error_message(error),
        }
    try:
        entries = _load_entries(spec, commit_hash)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {**outcome, "status": "load_error", "message": _error_message(error)}
    if not entries and previous_count > 0:
        return {
            **outcome,
            "status": "empty_result",
            "message": (
                f"本次扫描到 0 条，已保留原有 {previous_count} 条，未覆盖。"
                "请确认资料目录内容是否缺失。"
            ),
        }
    with database.connect() as connection:
        database.upsert_source(
            source_id=spec.source_id,
            name=spec.name,
            source_type="local" if spec.local_only else "git",
            url=spec.url,
            local_path=str(spec.path),
            commit_hash=commit_hash,
            license_name=spec.license_name,
            notes=spec.notes,
            connection=connection,
        )
        count = database.replace_source_entries(spec.source_id, entries, connection=connection)
        connection.commit()
    return {**outcome, "status": "imported", "count": count, "message": ""}


def _existing_entry_counts(database: PromptDatabase) -> dict[str, int]:
    return {
        str(source["source_id"]): int(source.get("entry_count") or 0)
        for source in database.list_sources()
    }


def _error_message(error: Exception) -> str:
    detail = str(error).strip() or error.__class__.__name__
    return detail[:400]


def _load_entries(spec: SourceSpec, commit_hash: str) -> list[EntryInput]:
    if spec.importer == "style-explorer":
        return load_style_entries(
            spec.source_id,
            spec.path,
            spec.url,
            commit_hash,
            backup=(spec.backup_path, spec.backup_revision)
            if spec.backup_path is not None
            else None,
        )
    loaders = {
        "clio": _load_clio,
        "krea": _load_krea,
        "wildcards": _load_wildcards,
        "kisega": _load_kisega,
        "animadex": _load_animadex,
        "neons_styles": _load_neons_styles,
    }
    return loaders[spec.importer](spec, commit_hash)


def _required_style_text(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"Invalid style field: {key}"
        raise ValueError(msg)
    return value.strip()


def _read_neons_catalog(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema") != 1:
        msg = f"Unsupported Neons catalog schema: {path.name}"
        raise ValueError(msg)
    styles = data.get("styles")
    if not isinstance(styles, list) or any(not isinstance(item, dict) for item in styles):
        msg = f"Invalid Neons styles list: {path.name}"
        raise TypeError(msg)
    if data.get("family") == "Extra":
        return []
    return [item for item in styles if item.get("family") != "Extra"]


def _load_neons_styles(spec: SourceSpec, commit_hash: str) -> list[EntryInput]:
    entries = []
    seen: set[str] = set()
    paths = sorted((spec.path / "styles").glob("*.json"))
    if not paths:
        msg = "Neons styles/*.json catalog is missing"
        raise ValueError(msg)
    for path in paths:
        # Upstream's Extra pack copies ThetaCursed's Krea2 catalog.
        if path.name == "10_other.json":
            continue
        for item in _read_neons_catalog(path):
            style_id = _required_style_text(item, "id")
            if style_id in seen:
                msg = f"Duplicate Neons style id: {style_id}"
                raise ValueError(msg)
            seen.add(style_id)
            axis = _required_style_text(item, "axis")
            if axis not in {"style", "format", "finish"}:
                msg = f"Unknown Neons style axis: {axis}"
                raise ValueError(msg)
            relative_path = path.relative_to(spec.path).as_posix()
            entries.append(
                EntryInput(
                    source_id=spec.source_id,
                    external_id=f"style:{style_id}",
                    kind="style" if axis == "style" else "modifier",
                    title=_required_style_text(item, "name"),
                    content=_required_style_text(item, "nl"),
                    negative_content=str(item.get("negative", "")),
                    category=(
                        f"{'composition' if axis == 'format' else axis}/"
                        f"{_required_style_text(item, 'family')}"
                    ),
                    model_family="",
                    safety="unrated",
                    source_path=relative_path,
                    source_url=_blob_url(spec, commit_hash, relative_path),
                    metadata={
                        "axis": axis,
                        "medium": item.get("medium", ""),
                        "tags": item.get("tags", []),
                        "tags_negative": item.get("tags_negative", []),
                        "aliases": item.get("aliases", []),
                        "prompt_syntax": "natural_language",
                        "compatibility": "untested",
                        "image_paths": [],
                        "image_refs": [],
                    },
                )
            )
    return entries


def _load_clio(spec: SourceSpec, commit_hash: str) -> list[EntryInput]:
    data = json.loads((spec.path / "styles.json").read_text(encoding="utf-8"))
    manifest_path = spec.path / "gallery" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    preview_by_style = {
        str(item["style"]): f"gallery/{item['thumb']}"
        for item in manifest["sections"]["krea2"]["images"]
    }
    entries = []
    for index, item in enumerate(data):
        name = str(item.get("name", f"Style {index + 1}"))
        entries.append(
            EntryInput(
                source_id=spec.source_id,
                external_id=f"style:{index}",
                kind="style",
                title=name,
                content=str(item.get("prompt", "")).strip(),
                category=str(item.get("section", "style")),
                model_family="krea2",
                source_path="styles.json",
                source_url=_blob_url(spec, commit_hash, "styles.json"),
                metadata={
                    "index": index,
                    "image_paths": [preview_by_style[name]] if name in preview_by_style else [],
                    "image_refs": (
                        [{"path": preview_by_style[name], "safety": "sfw"}]
                        if name in preview_by_style
                        else []
                    ),
                },
            )
        )
    return entries


def _load_krea(spec: SourceSpec, commit_hash: str) -> list[EntryInput]:
    entries: list[EntryInput] = []
    modifiers = json.loads((spec.path / "modifiers.json").read_text(encoding="utf-8"))
    for group in modifiers:
        group_name = str(group.get("name", "modifier"))
        for subcategory in group.get("subcategories", []):
            category = f"{group_name}/{subcategory.get('name', 'general')}"
            for modifier in subcategory.get("modifiers", []):
                name = str(modifier.get("name", "")).strip()
                if not name:
                    continue
                entries.append(
                    EntryInput(
                        source_id=spec.source_id,
                        external_id=f"modifier:{category}:{modifier.get('id', name)}",
                        kind="modifier",
                        title=name,
                        content=name,
                        category=category,
                        source_path="modifiers.json",
                        source_url=_blob_url(spec, commit_hash, "modifiers.json"),
                    )
                )
    presets = json.loads((spec.path / "presets.json").read_text(encoding="utf-8"))
    for group in presets:
        group_name = str(group.get("name", "preset"))
        for subcategory in group.get("subcategories", []):
            category = f"{group_name}/{subcategory.get('name', 'general')}"
            for preset in subcategory.get("presets", []):
                content = str(preset.get("name", "")).strip()
                if not content:
                    continue
                entries.append(
                    EntryInput(
                        source_id=spec.source_id,
                        external_id=f"preset:{category}:{preset.get('id', content)}",
                        kind="prompt",
                        title=str(subcategory.get("name", "Krea preset")),
                        content=content,
                        category=category,
                        model_family="stable-diffusion-legacy",
                        source_path="presets.json",
                        source_url=_blob_url(spec, commit_hash, "presets.json"),
                    )
                )
    return entries


def _load_wildcards(spec: SourceSpec, commit_hash: str) -> list[EntryInput]:
    root = spec.path / "wildcards"
    entries: list[EntryInput] = []
    for path in sorted(root.rglob("*.txt")):
        relative = path.relative_to(spec.path).as_posix()
        category = path.relative_to(root).with_suffix("").as_posix()
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            content = raw_line.strip()
            if not content or content.startswith("#"):
                continue
            entries.append(
                EntryInput(
                    source_id=spec.source_id,
                    external_id=f"{relative}:{line_number}",
                    kind="wildcard",
                    title=content,
                    content=content,
                    category=category,
                    source_path=relative,
                    source_url=_blob_url(spec, commit_hash, relative),
                    metadata={"line": line_number},
                )
            )
    return entries


def _load_kisega(spec: SourceSpec, commit_hash: str) -> list[EntryInput]:
    entries: list[EntryInput] = []
    tag_counts: Counter[str] = Counter()
    tag_examples: dict[str, list[str]] = {}
    tag_image_refs: dict[str, list[dict[str, str]]] = {}
    for path in sorted(spec.path.glob("images*/*.desc.txt")):
        relative = path.relative_to(spec.path).as_posix()
        image_path = relative.removesuffix(".desc.txt")
        tags = [tag.strip() for tag in path.read_text(encoding="utf-8").split(",") if tag.strip()]
        if not tags:
            continue
        safety = _classify_safety(tags)
        entries.append(
            EntryInput(
                source_id=spec.source_id,
                external_id=f"caption:{relative}",
                kind="caption",
                title=path.name.removesuffix(".png.desc.txt"),
                content=", ".join(tags),
                category="outfit-reference",
                model_family="danbooru-tags",
                safety=safety,
                source_path=relative,
                source_url=_blob_url(spec, commit_hash, relative),
                metadata={
                    "tags": tags,
                    "image_paths": [image_path] if (spec.path / image_path).is_file() else [],
                    "image_refs": (
                        [{"path": image_path, "safety": safety}]
                        if (spec.path / image_path).is_file()
                        else []
                    ),
                },
            )
        )
        for tag in tags:
            normalized = tag.casefold()
            tag_counts[normalized] += 1
            tag_examples.setdefault(normalized, [])
            tag_image_refs.setdefault(normalized, [])
            if len(tag_examples[normalized]) < _MAX_TAG_EXAMPLES:
                tag_examples[normalized].append(relative)
                if (spec.path / image_path).is_file():
                    tag_image_refs[normalized].append({"path": image_path, "safety": safety})
    for tag, count in sorted(tag_counts.items()):
        entries.append(
            EntryInput(
                source_id=spec.source_id,
                external_id=f"tag:{tag}",
                kind="tag",
                title=tag,
                content=tag,
                category="kisega-tag",
                model_family="danbooru-tags",
                safety=_classify_safety([tag]),
                source_path=tag_examples[tag][0],
                source_url=_blob_url(spec, commit_hash, tag_examples[tag][0]),
                metadata={
                    "count": count,
                    "examples": tag_examples[tag],
                    "image_paths": [image_ref["path"] for image_ref in tag_image_refs[tag]],
                    "image_refs": tag_image_refs[tag],
                },
            )
        )
    return entries


def _load_animadex(spec: SourceSpec, commit_hash: str) -> list[EntryInput]:
    catalogue_root, csv_root, image_prefix = _animadex_catalogue_paths(spec.path, spec.data_path)
    characters_path = csv_root / "characters.csv"
    artists_path = csv_root / "artists.csv"
    if not characters_path.is_file() or not artists_path.is_file():
        msg = "AnimaDex 缺少 characters.csv 或 artists.csv"
        raise ValueError(msg)

    entries: list[EntryInput] = []
    copyright_rows: dict[str, dict[str, str]] = {}
    for row in _read_csv_rows(characters_path):
        slug = row.get("character", "").strip()
        trigger = row.get("trigger", "").strip() or slug.replace("_", " ")
        copyright_name = row.get("copyright", "").strip()
        tags = _csv_tags(row.get("core_tags", ""))
        if not slug or not copyright_name or not trigger:
            continue
        thumb = catalogue_root / "characters" / "thumbs" / f"{_animadex_filename(trigger)}.webp"
        image_path = f"{image_prefix}characters/thumbs/{thumb.name}"
        image_refs = _animadex_image_refs(thumb, image_path)
        hair_colors = [tag for tag in tags if tag in _ANIMADEX_HAIR_COLORS]
        eye_colors = [tag for tag in tags if tag in _ANIMADEX_EYE_COLORS]
        entries.append(
            EntryInput(
                source_id=spec.source_id,
                external_id=f"character:{slug}",
                kind="character_reference",
                title=trigger,
                content=", ".join(dict.fromkeys([trigger, copyright_name, *tags])),
                category=copyright_name,
                model_family="danbooru-tags",
                safety="unrated",
                source_path=_animadex_source_path(characters_path, spec.path, image_prefix),
                source_url=row.get("url", "").strip()
                or _blob_url(spec, commit_hash, "samples/characters.csv"),
                metadata={
                    "record_type": "character",
                    "character": slug,
                    "copyright": copyright_name,
                    "trigger": trigger,
                    "tags": tags,
                    "hair_colors": hair_colors,
                    "eye_colors": eye_colors,
                    "popularity": _safe_int(row.get("count", "")),
                    "image_paths": [image_path] if image_refs else [],
                    "image_refs": image_refs,
                    "upstream_fields": _extra_animadex_fields(row),
                },
            )
        )
        copyright_rows.setdefault(copyright_name, row)

    for row in _read_csv_rows(artists_path):
        slug = row.get("artist", "").strip()
        trigger = row.get("trigger", "").strip() or slug.replace("_", " ")
        if not slug:
            continue
        thumb = catalogue_root / "artists" / "thumbs" / f"{_animadex_filename(trigger)}.webp"
        image_path = f"{image_prefix}artists/thumbs/{thumb.name}"
        image_refs = _animadex_image_refs(thumb, image_path)
        entries.append(
            EntryInput(
                source_id=spec.source_id,
                external_id=f"artist:{slug}",
                kind="artist_reference",
                title=trigger,
                content=", ".join(dict.fromkeys([trigger, slug])),
                category="artist",
                model_family="danbooru-tags",
                safety="unrated",
                source_path=_animadex_source_path(artists_path, spec.path, image_prefix),
                source_url=row.get("url", "").strip()
                or _blob_url(spec, commit_hash, "samples/artists.csv"),
                metadata={
                    "record_type": "artist",
                    "artist": slug,
                    "trigger": trigger,
                    "popularity": _safe_int(row.get("count", "")),
                    "image_paths": [image_path] if image_refs else [],
                    "image_refs": image_refs,
                    "upstream_fields": _extra_animadex_fields(row),
                },
            )
        )

    for copyright_name, row in sorted(copyright_rows.items()):
        thumb = (
            catalogue_root / "copyrights" / "thumbs" / f"{_animadex_filename(copyright_name)}.webp"
        )
        image_path = f"{image_prefix}copyrights/thumbs/{thumb.name}"
        image_refs = _animadex_image_refs(thumb, image_path)
        entries.append(
            EntryInput(
                source_id=spec.source_id,
                external_id=f"copyright:{copyright_name}",
                kind="copyright_reference",
                title=copyright_name.replace("_", " "),
                content=copyright_name,
                category=copyright_name,
                model_family="danbooru-tags",
                safety="unrated",
                source_path=_animadex_source_path(characters_path, spec.path, image_prefix),
                source_url=row.get("url", "").strip()
                or _blob_url(spec, commit_hash, "samples/characters.csv"),
                metadata={
                    "record_type": "copyright",
                    "copyright": copyright_name,
                    "image_paths": [image_path] if image_refs else [],
                    "image_refs": image_refs,
                },
            )
        )
    return entries


def _animadex_catalogue_paths(
    repo_root: Path, mapped_data: Path | None = None
) -> tuple[Path, Path, str]:
    if mapped_data is not None:
        return mapped_data, mapped_data / "import", "catalogue/"
    data_root = repo_root.parent / "animadex-data"
    config_path = repo_root / "config.toml"
    if config_path.is_file():
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        configured = str(raw.get("paths", {}).get("data_dir", "")).strip()
        if configured:
            data_root = Path(configured).expanduser()
            if not data_root.is_absolute():
                data_root = (repo_root / data_root).resolve()
    if (data_root / "import" / "characters.csv").is_file() and (
        data_root / "import" / "artists.csv"
    ).is_file():
        return data_root, data_root / "import", "catalogue/"
    return repo_root / "samples" / "images", repo_root / "samples", "samples/images/"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            {str(key): str(value or "") for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def _csv_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def _animadex_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", value).rstrip(". ")


def _animadex_image_refs(path: Path, virtual_path: str) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    return [{"path": virtual_path, "safety": "unrated", "original_variant": "thumbnail"}]


def _animadex_source_path(path: Path, repo_root: Path, image_prefix: str) -> str:
    if image_prefix.startswith("samples/"):
        return path.relative_to(repo_root).as_posix()
    return f"catalogue/import/{path.name}"


def _safe_int(value: str) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def _extra_animadex_fields(row: dict[str, str]) -> dict[str, str]:
    known = {"character", "copyright", "trigger", "core_tags", "count", "url", "artist"}
    return {key: value for key, value in row.items() if key not in known and value}


def _classify_safety(tags: list[str]) -> str:
    normalized = {tag.casefold() for tag in tags}
    if normalized & _ADULT_TAGS:
        return "explicit-adult"
    if normalized & _SUGGESTIVE_TAGS:
        return "suggestive"
    return "sfw"


def _git_commit(path: Path) -> str:
    git_executable = shutil.which("git")
    if git_executable is None:
        msg = "本机找不到 git 命令，无法确定资料版本"
        raise SourceVersionError(msg)
    if not (path / ".git").exists():
        msg = "本地目录不是 Git 仓库，无法确定资料版本"
        raise SourceVersionError(msg)
    result = subprocess.run(  # noqa: S603 - executable is resolved locally; args are static.
        [git_executable, "rev-parse", "HEAD"],
        cwd=path,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        msg = result.stderr.strip() or "git rev-parse HEAD 执行失败"
        raise SourceVersionError(msg)
    return result.stdout.strip()


def _blob_url(spec: SourceSpec, commit_hash: str, relative_path: str) -> str:
    if spec.local_only:
        return spec.url
    return f"{spec.url}/blob/{commit_hash}/{quote(relative_path, safe='/')}"


def _write_manifest(settings: Settings, sources: list[dict[str, Any]]) -> None:
    target = settings.library_root / "sources" / "manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"sources": sources}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
