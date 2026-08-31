from __future__ import annotations

import json
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

from prompt_hub.config import Settings
from prompt_hub.database import EntryInput, PromptDatabase
from prompt_hub.media import build_kisega_thumbnails


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source_id: str
    name: str
    url: str
    path: Path
    license_name: str
    notes: str
    importer: str


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


def discover_sources(settings: Settings) -> list[SourceSpec]:
    root = settings.git_sources_root
    return [
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
    ]


def import_all(settings: Settings, database: PromptDatabase) -> dict[str, int]:
    database.initialize()
    build_kisega_thumbnails(settings)
    results: dict[str, int] = {}
    for spec in discover_sources(settings):
        if not spec.path.exists():
            continue
        commit_hash = _git_commit(spec.path)
        entries = _load_entries(spec, commit_hash)
        with database.connect() as connection:
            database.upsert_source(
                source_id=spec.source_id,
                name=spec.name,
                source_type="git",
                url=spec.url,
                local_path=str(spec.path),
                commit_hash=commit_hash,
                license_name=spec.license_name,
                notes=spec.notes,
                connection=connection,
            )
            results[spec.source_id] = database.replace_source_entries(
                spec.source_id,
                entries,
                connection=connection,
            )
            connection.commit()
    _write_manifest(settings, database.list_sources())
    return results


def _load_entries(spec: SourceSpec, commit_hash: str) -> list[EntryInput]:
    loaders = {
        "clio": _load_clio,
        "krea": _load_krea,
        "wildcards": _load_wildcards,
        "kisega": _load_kisega,
    }
    return loaders[spec.importer](spec, commit_hash)


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
        msg = "git executable not found"
        raise RuntimeError(msg)
    result = subprocess.run(  # noqa: S603 - executable is resolved locally; args are static.
        [git_executable, "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _blob_url(spec: SourceSpec, commit_hash: str, relative_path: str) -> str:
    return f"{spec.url}/blob/{commit_hash}/{quote(relative_path, safe='/')}"


def _write_manifest(settings: Settings, sources: list[dict[str, Any]]) -> None:
    target = settings.library_root / "sources" / "manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"sources": sources}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
