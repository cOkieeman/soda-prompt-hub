from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_hub.studio_store import StudioError

if TYPE_CHECKING:
    from collections.abc import Callable

TAG_KEYS = ("style", "line", "clothing")
TAG_HEADER = re.compile(r"\[\s*([a-zA-Z][\w-]*)\s*:\s*([^\[\]\r\n]+?)\s*\]")
SQUARE_BRACKETS = str.maketrans("", "", "[]\uff3b\uff3d")
POOL_REF = re.compile(r"__([\w.\-+/*\\]+?)__")
MAX_POOL_BYTES = 1_000_000
MAX_INDEX_DIGITS = len(str(MAX_POOL_BYTES))


def strip_tag_headers(text: str) -> str:
    """Remove metadata and keep bracket delimiters out of model-facing text."""
    return TAG_HEADER.sub("", text).translate(SQUARE_BRACKETS)


def _roots(comfy_root: str) -> tuple[Path, ...]:
    if not comfy_root:
        return ()
    root = Path(comfy_root).expanduser()
    install = next(
        (path for path in (root, root / "ComfyUI") if (path / "custom_nodes").is_dir()),
        root,
    )
    impact = install / "custom_nodes" / "ComfyUI-Impact-Pack"
    return tuple(path.resolve() for path in (impact / "custom_wildcards", impact / "wildcards"))


def _entries(ref: str, roots: tuple[Path, ...]) -> list[tuple[str, dict[str, set[str]]]]:
    parts = ref.replace("\\", "/").lower().split("/")
    if any(part in {"", ".", ".."} or "*" in part for part in parts):
        return []
    relative = Path(*parts[:-1], parts[-1] + ".txt")
    for root in roots:
        try:
            path = (root / relative).resolve()
            if (
                path.is_relative_to(root)
                and path.is_file()
                and path.stat().st_size <= MAX_POOL_BYTES
            ):
                return _parse_entries(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError):
            continue
    return []


def _parse_entries(text: str) -> list[tuple[str, dict[str, set[str]]]]:
    result = []
    tags: dict[str, set[str]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        for name, value in TAG_HEADER.findall(line):
            key = name.lower()
            if key in TAG_KEYS and value.strip():
                tags.setdefault(key, set()).add(value.strip())
        if line.lstrip().startswith("#"):
            continue
        entry = strip_tag_headers(line).strip()
        if entry:
            result.append((entry, tags))
            tags = {}
    return result


def wildcard_v2_tags_by_pool(
    pools: list[str], *, comfy_root: str
) -> dict[str, dict[str, list[str]]]:
    roots = _roots(comfy_root)
    catalogue = {}
    for pool in pools:
        match = POOL_REF.fullmatch(pool)
        if match is None:
            continue
        found: dict[str, set[str]] = {}
        for _, tags in _entries(match[1], roots):
            for key, values in tags.items():
                found.setdefault(key, set()).update(values)
        if found:
            catalogue[pool] = {
                key: sorted(values, key=str.casefold) for key, values in found.items()
            }
    return catalogue


def route_tagged_template(
    text: str,
    filters: dict[str, list[str]],
    *,
    comfy_root: str,
    seed: int,
    expand: Callable[[str, int], str],
) -> str:
    text = strip_tag_headers(text)
    wanted = {
        key: {value.casefold() for value in values} for key, values in filters.items() if values
    }
    if not wanted:
        return text

    roots = _roots(comfy_root)
    matched: set[str] = set()
    choices: list[list[str]] = []
    pieces: list[str | int] = []
    end = 0
    for match in POOL_REF.finditer(text):
        entries = _entries(match[1], roots)
        keys = wanted.keys() & {key for _, tags in entries for key in tags}
        if not keys:
            continue
        candidates = [
            entry
            for entry, tags in entries
            if all(wanted[key] & {tag.casefold() for tag in tags.get(key, ())} for key in keys)
        ]
        if not candidates:
            msg = f"詞池 {match[0]} 沒有符合所選標籤的詞條"
            raise StudioError(msg)
        pieces += [text[end : match.start()], len(choices)]
        choices.append(candidates)
        matched.update(keys)
        end = match.end()

    if missing := wanted.keys() - matched:
        msg = f"目前詞池沒有以下標籤分類 {', '.join(sorted(missing))}"
        raise StudioError(msg)

    # Let Impact draw indexes first so literal pipes and nested choices in a selected
    # library row keep their original interpretation in the actual expansion request.
    draw = "\n".join(
        "{" + "|".join(map(str, range(len(candidates)))) + "}" if len(candidates) > 1 else "0"
        for candidates in choices
    )
    picked = (
        expand(draw, seed).splitlines()
        if any(len(items) > 1 for items in choices)
        else ["0"] * len(choices)
    )
    if len(picked) != len(choices) or any(
        not index.isascii()
        or not index.isdecimal()
        or len(index) > MAX_INDEX_DIGITS
        or int(index) >= len(items)
        for index, items in zip(picked, choices, strict=True)
    ):
        msg = "Impact Pack 未返回有效的標籤詞條索引"
        raise StudioError(msg)
    selected = [items[int(index)] for items, index in zip(choices, picked, strict=True)]
    return (
        "".join(selected[item] if isinstance(item, int) else item for item in pieces) + text[end:]
    )
