from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from prompt_hub.creative import SLOT_ORDER

if TYPE_CHECKING:
    from prompt_hub.database import PromptDatabase

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
_STOP_WORDS = {
    "and",
    "the",
    "with",
    "from",
    "into",
    "that",
    "this",
    "while",
    "where",
    "their",
    "about",
    "scene",
    "style",
}
_MIN_QUERY_LENGTH = 2
_MAX_QUERY_LENGTH = 80

_SAFETY_LEVELS = {
    "sfw": {"sfw"},
    "suggestive": {"sfw", "suggestive"},
    "adult": {"sfw", "suggestive", "adult"},
    "explicit-adult": {"sfw", "suggestive", "adult", "explicit-adult"},
}

# One concept may feed more than one slot, such as dusk affecting both scene and lighting.
_CONCEPT_RULES: tuple[tuple[tuple[str, ...], Mapping[str, tuple[str, ...]]], ...] = (
    (("银发", "silver hair", "silver-haired"), {"character": ("silver hair",)}),
    (("金发", "blonde hair", "blond hair"), {"character": ("blonde hair",)}),
    (("黑发", "black hair"), {"character": ("black hair",)}),
    (("红发", "red hair"), {"character": ("red hair",)}),
    (("调查员", "侦探", "investigator", "detective"), {"character": ("investigator", "detective")}),
    (("成年女性", "adult woman", "woman"), {"character": ("adult woman", "woman")}),
    (("男性", "man", "male"), {"character": ("man", "male")}),
    (("精灵", "elf"), {"character": ("elf",)}),
    (("机器人", "robot", "android"), {"character": ("android", "robot")}),
    (
        ("维多利亚", "victorian"),
        {"outfit": ("victorian", "victorian fashion"), "style": ("victorian",)},
    ),
    (("军装", "military uniform"), {"outfit": ("military uniform", "uniform")}),
    (("手套", "gloves"), {"outfit": ("gloves",)}),
    (("大衣", "外套", "coat"), {"outfit": ("coat",)}),
    (("连衣裙", "礼服", "dress", "gown"), {"outfit": ("dress", "gown")}),
    (("西装", "suit"), {"outfit": ("suit",)}),
    (("盔甲", "铠甲", "armor", "armour"), {"outfit": ("armor",)}),
    (("打开信", "拆开密信", "拆信", "opening a letter"), {"action": ("reading", "letter")}),
    (("读信", "阅读", "reading"), {"action": ("reading",)}),
    (("奔跑", "running"), {"action": ("running",)}),
    (("行走", "walking"), {"action": ("walking",)}),
    (("坐着", "sitting"), {"action": ("sitting",)}),
    (("回头", "looking back"), {"action": ("looking back",)}),
    (("特写", "close-up", "close up"), {"composition": ("close-up",)}),
    (("半身", "medium shot", "upper body"), {"composition": ("medium shot", "upper body")}),
    (("全身", "full body"), {"composition": ("full body",)}),
    (("低角度", "仰视", "low angle"), {"composition": ("low angle",)}),
    (("俯视", "high angle", "overhead"), {"composition": ("high angle", "overhead")}),
    (("图书馆", "library"), {"scene": ("library", "old library")}),
    (("森林", "forest"), {"scene": ("forest",)}),
    (("城市", "city"), {"scene": ("city", "cityscape")}),
    (("卧室", "bedroom"), {"scene": ("bedroom",)}),
    (("教堂", "cathedral", "church"), {"scene": ("cathedral", "church")}),
    (("海边", "海滩", "beach"), {"scene": ("beach", "seaside")}),
    (("雨夜", "rainy night"), {"scene": ("rainy night", "rain"), "lighting": ("night lighting",)}),
    (
        ("黄昏", "夕阳", "dusk", "sunset"),
        {"scene": ("sunset",), "lighting": ("golden hour", "sunset lighting")},
    ),
    (("轮廓光", "rim light"), {"lighting": ("rim light",)}),
    (("霓虹", "neon"), {"lighting": ("neon lighting", "neon")}),
    (("烛光", "candlelight"), {"lighting": ("candlelight",)}),
    (("柔光", "soft light"), {"lighting": ("soft lighting",)}),
    (("哥特", "gothic"), {"style": ("gothic", "gothic illustration")}),
    (("电影感", "cinematic"), {"style": ("cinematic",)}),
    (("写实", "realistic"), {"style": ("realistic",)}),
    (("动漫", "二次元", "anime"), {"style": ("anime",)}),
    (("水彩", "watercolor"), {"style": ("watercolor",)}),
    (("油画", "oil painting"), {"style": ("oil painting",)}),
    (("墨水", "ink illustration", "ink drawing"), {"style": ("ink illustration",)}),
)

_CATEGORY_HINTS = {
    "character": ("class", "character", "hair", "eye", "face", "body", "race", "species", "name"),
    "outfit": (
        "clothing",
        "outfit",
        "fashion",
        "kisega",
        "accessory",
        "uniform",
        "footwear",
        "dress",
        "gown",
        "coat",
    ),
    "action": ("action", "movement", "pose", "gesture", "activity", "subject", "scenario"),
    "composition": (
        "framing",
        "portrait-type",
        "camera",
        "composition",
        "angle",
        "shot",
        "subject",
    ),
    "scene": ("location", "background", "interior", "architecture", "scenery", "environment"),
    "lighting": ("lighting", "photography", "weather", "time"),
    "style": ("style", "movement", "genre", "illustration", "photography", "fineart"),
}

_KIND_BONUS = {
    "character": {"tag": 12, "caption": 9, "wildcard": 6},
    "outfit": {"tag": 18, "caption": 16, "wildcard": 7},
    "action": {"tag": 10, "caption": 10, "wildcard": 7, "prompt": 7},
    "composition": {"modifier": 11, "wildcard": 8, "prompt": 8},
    "scene": {"wildcard": 10, "modifier": 8, "prompt": 8},
    "lighting": {"modifier": 14, "style": 10, "wildcard": 9},
    "style": {"style": 20, "modifier": 14, "wildcard": 6},
}


def allowed_safety_levels(safety_mode: str) -> set[str]:
    return set(_SAFETY_LEVELS.get(safety_mode, _SAFETY_LEVELS["sfw"]))


def build_slot_queries(
    brief: str,
    *,
    slots: Mapping[str, str] | None = None,
    locks: Mapping[str, bool] | None = None,
    query_hints: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, list[str]]:
    clean_brief = brief.casefold()
    slot_values = slots or {}
    slot_locks = locks or {}
    hints = query_hints or {}
    queries = {slot: [] for slot in SLOT_ORDER}
    for needles, destinations in _CONCEPT_RULES:
        if any(needle.casefold() in clean_brief for needle in needles):
            for slot, values in destinations.items():
                queries[slot].extend(values)
    for slot in SLOT_ORDER:
        if slot_locks.get(slot, False):
            queries[slot] = []
            continue
        queries[slot].extend(str(value) for value in hints.get(slot, ()) if value)
        queries[slot].extend(_slot_value_queries(str(slot_values.get(slot, ""))))
        queries[slot] = _unique_queries(queries[slot])[:10]
    return queries


def source_candidates(
    database: PromptDatabase,
    *,
    brief: str,
    safety_mode: str,
    slots: Mapping[str, str] | None = None,
    locks: Mapping[str, bool] | None = None,
    query_hints: Mapping[str, Sequence[str]] | None = None,
    limit_per_slot: int = 6,
) -> dict[str, Any]:
    allowed_safety = allowed_safety_levels(safety_mode)
    clean_locks = locks or {}
    slot_queries = build_slot_queries(
        brief,
        slots=slots,
        locks=clean_locks,
        query_hints=query_hints,
    )
    groups: dict[str, dict[str, Any]] = {}
    total = 0
    for slot in SLOT_ORDER:
        locked = bool(clean_locks.get(slot, False))
        candidates = (
            []
            if locked
            else _search_slot(
                database,
                slot,
                slot_queries[slot],
                allowed_safety,
                limit_per_slot,
            )
        )
        total += len(candidates)
        groups[slot] = {
            "locked": locked,
            "queries": slot_queries[slot],
            "candidates": candidates,
        }
    return {
        "brief": brief,
        "safety_mode": safety_mode,
        "candidate_count": total,
        "slots": groups,
    }


def _search_slot(
    database: PromptDatabase,
    slot: str,
    queries: list[str],
    allowed_safety: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for query_index, query in enumerate(queries):
        for variant_index, variant in enumerate(_query_variants(query)):
            results = database.search(variant, limit=15)
            for result_index, result in enumerate(results):
                if str(result.get("safety", "sfw")) not in allowed_safety:
                    continue
                if not _matches_query_context(query, result):
                    continue
                exact_match = _is_exact_match(variant, result)
                affinity = _slot_affinity(slot, result)
                if affinity <= 0 and exact_match and slot == "action":
                    affinity = 8
                if affinity <= 0:
                    continue
                key = f"{result.get('source_id', '')}:{result.get('external_id', '')}"
                score = (
                    120
                    - query_index * 7
                    - variant_index * 4
                    - result_index
                    + affinity
                    + (30 if exact_match else 0)
                    + (8 if _has_visual(result) else 0)
                    + (8 if result.get("favorite") else 0)
                    + int(result.get("user_rating") or 0)
                )
                candidate = {
                    **result,
                    "recommended_slot": slot,
                    "match_query": query,
                    "search_variant": variant,
                    "match_reason": _match_reason(slot, result),
                    "sourcing_score": score,
                }
                if key not in merged or score > int(merged[key]["sourcing_score"]):
                    merged[key] = candidate
    return sorted(merged.values(), key=lambda item: int(item["sourcing_score"]), reverse=True)[
        :limit
    ]


def _slot_affinity(slot: str, result: Mapping[str, Any]) -> int:
    category = str(result.get("category", "")).casefold()
    kind = str(result.get("kind", "")).casefold()
    category_score = 18 if any(hint in category for hint in _CATEGORY_HINTS[slot]) else 0
    kind_score = _KIND_BONUS[slot].get(kind, 0)
    if slot == "style" and kind in {"style", "modifier"}:
        return category_score + kind_score
    if slot == "outfit" and kind in {"tag", "caption"}:
        return category_score + kind_score
    return category_score + kind_score if category_score else 0


def _match_reason(slot: str, result: Mapping[str, Any]) -> str:
    category = str(result.get("category", "")).strip()
    kind = str(result.get("kind", "")).strip()
    if category:
        return f"{kind} · {category} · 适合{slot}槽位"
    return f"{kind} · 适合{slot}槽位"


def _is_exact_match(query: str, result: Mapping[str, Any]) -> bool:
    needle = query.strip().casefold()
    return needle in {
        str(result.get("title", "")).strip().casefold(),
        str(result.get("content", "")).strip().casefold(),
    }


def _matches_query_context(query: str, result: Mapping[str, Any]) -> bool:
    searchable = " ".join(
        str(result.get(field, "")).casefold() for field in ("title", "content", "category")
    )
    topic_words = ("hair", "eye", "lighting", "fashion", "uniform", "dress", "coat")
    query_words = [word.casefold() for word in _WORD_RE.findall(query)]
    required = query_words if any(word in query_words for word in topic_words) else []
    return not required or all(word in searchable for word in required)


def _query_variants(query: str) -> list[str]:
    variants = [query.strip()]
    words = [
        word.casefold() for word in _WORD_RE.findall(query) if word.casefold() not in _STOP_WORDS
    ]
    variants.extend(sorted(words, key=len, reverse=True))
    return _unique_queries(variants)[:4]


def _slot_value_queries(value: str) -> list[str]:
    chunks = re.split(r"[,，;；\n]", value)
    return [
        chunk.strip()
        for chunk in chunks
        if _MIN_QUERY_LENGTH <= len(chunk.strip()) <= _MAX_QUERY_LENGTH
    ][:4]


def _unique_queries(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique = []
    for value in values:
        clean = " ".join(str(value).strip().split())[:80]
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            unique.append(clean)
    return unique


def _has_visual(result: Mapping[str, Any]) -> bool:
    metadata = result.get("metadata", {})
    return isinstance(metadata, Mapping) and bool(metadata.get("image_refs"))
