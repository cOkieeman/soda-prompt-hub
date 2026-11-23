from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from contextlib import closing
from http import HTTPStatus
from http.client import HTTPConnection, HTTPException
from pathlib import Path
from string import Template
from typing import Any
from urllib.request import Request, urlopen

from prompt_hub.studio_store import (
    FIELDS,
    StudioError,
    StudioStore,
    wildcard_v2_active,
    wildcard_v2_slot_text_field,
)
from prompt_hub.studio_wildcard_v2_tags import route_tagged_template, strip_tag_headers

V2_WILDCARD = re.compile(r"__([\w.\-+/*\\]+?)__")
V2_COMFY_PORT = 8190
V2_TEMPLATE_PATH = Path(__file__).with_name("studio_wildcard_v2_templates.json")
V2_WHOLE_POOL_KEYS = {
    "moss_lora_v2/all",
    "moss_lora_v2/anima/editorial_design",
    "moss_lora_v2/anima/editorial_world",
    "moss_lora_v2/nl/editorial_design",
    "moss_lora_v2/nl/editorial_world",
    "moss_lora_v2/world/creature",
    "moss_lora_v2/world/scenery",
    "moss_lora_v2/world/still_life",
}
V2_GENERIC_CHARACTER_TAGS = {
    "1boy",
    "1girl",
    "1gril",
    "1man",
    "1woman",
    "adult",
    "adult female",
    "adult male",
    "adult man",
    "adult woman",
    "female",
    "girl",
    "male",
    "man",
    "one adult man",
    "one adult woman",
    "one girl",
    "one man",
    "one person",
    "one woman",
    "person",
    "single man",
    "single person",
    "single woman",
    "solo",
    "woman",
    "young adult woman",
    "young woman",
    "单人",
    "單人",
    "成年女性",
    "成年男性",
}
V2_SLOT_LABELS = {
    "layout": "版式構圖",
    "style": "畫風",
    "character": "角色",
    "outfit": "服裝",
    "action": "動作",
    "scene_light": "場景與光影",
    "test_lighting": "測試光線",
    "lighting": "光線",
}


def seed_value(start: int, mode: str, index: int, limit: int = 2**53) -> int:
    if mode == "random":
        return random.SystemRandom().randrange(0, limit)
    return (start + index) % limit if mode == "increment" else start % limit


def expand_local(text: str, seed: int, wordlists: dict[str, list[str]]) -> str:
    generator = random.Random(seed)  # noqa: S311 - seeded visual sampling, never used for credentials
    for _ in range(32):
        previous = text

        def replace_wordlist(match: re.Match[str]) -> str:
            options = wordlists.get(match.group(1))
            return generator.choice(options) if options else match.group(0)

        text = re.sub(r"__([\w/-]+)__", replace_wordlist, text)

        def replace_choice(match: re.Match[str]) -> str:
            options = match.group(1).split("|")
            choices, weights = [], []
            for option in options:
                weighted = re.fullmatch(r"(\d+(?:\.\d+)?)::(.*)", option, re.DOTALL)
                choices.append(weighted.group(2) if weighted else option)
                weights.append(float(weighted.group(1)) if weighted else 1.0)
            if not any(weights):
                msg = "隨機選項至少需要一個大於零的權重"
                raise StudioError(msg)
            return generator.choices(choices, weights=weights, k=1)[0]

        text = re.sub(r"\{([^{}]*\|[^{}]*)\}", replace_choice, text)
        if text == previous:
            return text
    msg = "詞庫循環引用或巢狀層數過多"
    raise StudioError(msg)


def expand_fields(
    store: StudioStore,
    recipe: dict[str, Any],
    *,
    text_seed: int,
    config: dict[str, Any],
    locked: dict[str, str] | None = None,
) -> dict[str, Any]:
    wordlists = {
        item["name"]: [
            line.strip()
            for line in item["content"].splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        for item in store.wordlists()
    }
    expanded: dict[str, Any] = {}
    debug = ""
    for offset, name in enumerate(FIELDS):
        text = str(recipe[name])
        if name == "prefix" and recipe.get("prefix_rows"):
            text = ", ".join(
                str(row.get("text", "")).strip().rstrip(",")
                for row in recipe["prefix_rows"]
                if row.get("enabled", True)
            )
        if recipe["locks"].get(name) and locked and name in locked:
            expanded[name] = locked[name]
            continue
        if name == "body" and recipe["text_mode"] == "raffle":
            options = {
                "exclude_taglists_containing": "",
                "taglists_must_include": "",
                "filter_out_tags": "",
                "use_general": True,
                "use_questionable": False,
                "use_sensitive": False,
                "use_explicit": False,
                "exclude_tag_categories": "",
                **recipe["raffle"],
                "seed": text_seed,
            }
            try:
                result = subprocess.run(  # noqa: S603 - local configured executable, argument list and no shell
                    [
                        sys.executable,
                        "-X",
                        "utf8",
                        str(Path(__file__).with_name("studio_raffle.py")),
                    ],
                    input=json.dumps({"root": config.get("comfy_root", ""), "options": options}),
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    timeout=90,
                    check=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                value = json.loads(result.stdout.strip().splitlines()[-1])
            except (subprocess.SubprocessError, ValueError, IndexError) as error:
                detail = getattr(error, "stderr", "") or str(error)
                msg = f"Raffle 抽詞失敗，請檢查詞池與設定。{detail[-700:]}"
                raise StudioError(msg) from error
            text = "\n\n".join(part for part in (text, value["text"]) if part.strip())
            debug = value["debug"]
        if recipe["text_mode"] != "manual":
            text = expand_local(text, text_seed + offset, wordlists)
            if re.search(r"__[\w/-]+__", text):
                endpoint = str(recipe.get("comfy_url", "")).rstrip("/")
                request = Request(  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
                    f"{endpoint}/impact/wildcards",
                    data=json.dumps({"text": text, "seed": text_seed + offset}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urlopen(request, timeout=20) as response:  # noqa: S310 - HTTP(S) endpoint validated by the connection or source adapter
                        text = json.load(response)["text"]
                except (OSError, ValueError, KeyError) as error:
                    msg = "外部詞庫無法展開，請檢查 ComfyUI 地址或匯入所需 TXT"
                    raise StudioError(msg) from error
                if re.search(r"__[\w/-]+__", text):
                    msg = "部分 Wildcard 找不到對應詞庫，請檢查名稱"
                    raise StudioError(msg)
        expanded[name] = text
    expanded["positive"] = "\n\n".join(
        expanded[name] for name in ("prefix", "body", "suffix") if expanded[name].strip()
    )
    expanded["text_seed"] = text_seed
    expanded["debug"] = debug
    return expanded


def _literal_slot(value: str, label: str) -> str:
    if not value.strip():
        msg = f"請填寫固定{label}提示詞"
        raise StudioError(msg)
    if (
        V2_WILDCARD.search(value)
        or re.search(r"\{[^{}]*\}", value)
        or any(line.lstrip().startswith("#") for line in value.splitlines())
    ):
        msg = f"固定{label}需要直接填寫文字，不能使用通配符、隨機選項或註解"
        raise StudioError(msg)
    return value


def _generic_v2_character(value: str) -> bool:
    tags = {
        " ".join(part.replace("_", " ").split())
        for part in re.split(r"[,，.。\r\n]+", value.casefold())
    }
    tags.discard("")
    return bool(tags) and tags <= V2_GENERIC_CHARACTER_TAGS


def _is_v2_whole_pool(key: str) -> bool:
    key = key.replace("\\", "/").lower()
    if key in V2_WHOLE_POOL_KEYS or key.startswith("moss_lora_v2/world/"):
        return True
    if key.startswith("*/") or ("/" not in key and "*" not in key):
        base = key.removeprefix("*/")
        return any(f"/{base}/" in f"/{pool}/" for pool in V2_WHOLE_POOL_KEYS)
    if "*" not in key:
        return False
    # Impact treats a glob as a regex prefix. Reject a selection that could include an empty scene.
    pattern = key.replace("*", ".*").replace("+", r"\+")
    return any(re.match(pattern, f"{pool}/") for pool in V2_WHOLE_POOL_KEYS)


def wildcard_v2_scene_pools(pools: list[str]) -> list[str]:
    return [
        pool
        for pool in pools
        if (match := V2_WILDCARD.fullmatch(pool)) and not _is_v2_whole_pool(match[1])
    ]


def _v2_slot(
    options: dict[str, Any],
    profile: dict[str, Any],
    slot: str,
    *,
    default: str = "",
) -> str:
    mode = options[f"{slot}_mode"]
    if mode in ("none", "preset"):
        return ""
    label = V2_SLOT_LABELS[slot]
    if mode == "fixed":
        value = _literal_slot(options[wildcard_v2_slot_text_field(slot)], label)
        if slot == "character" and _generic_v2_character(value):
            return Template(profile["generic_character"]).substitute(
                value=value.rstrip(" ,，.。\t\r\n"),
            )
        return value
    pool = options[f"{slot}_pool"].strip()
    if not pool and default:
        return default
    match = V2_WILDCARD.fullmatch(pool)
    if match is None:
        msg = f"請選擇{label}詞池或填寫 Impact 通配符引用 __詞池名稱__"
        raise StudioError(msg)
    if _is_v2_whole_pool(match[1]):
        msg = "整句詞池只能單獨使用，請改選人物場景或槽位詞池"
        raise StudioError(msg)
    return pool


def _v2_independent_defaults(profile: dict[str, Any], preset: str) -> dict[str, str]:
    defaults = {slot: profile["defaults"][slot] for slot in ("character", "outfit", "action")}
    return (
        defaults
        | profile["scene_presets"][preset]
        | {"test_lighting": profile["defaults"]["lighting"]}
    )


def wildcard_v2_default_pools() -> dict[str, dict[str, dict[str, list[str]]]]:
    profiles = json.loads(V2_TEMPLATE_PATH.read_text(encoding="utf-8"))
    recommendations = {}
    for family, profile in profiles.items():
        bundled = {slot: profile["defaults"][slot] for slot in ("character", "lighting")}
        bundled["theme"] = profile["bundled"]
        defaults = {"bundled": bundled} | {
            preset: _v2_independent_defaults(profile, preset) for preset in profile["scene_presets"]
        }
        recommendations[family] = {
            preset: {
                slot: [match[0] for match in V2_WILDCARD.finditer(value)]
                for slot, value in values.items()
            }
            for preset, values in defaults.items()
        }
    return recommendations


def _v2_template(recipe: dict[str, Any], *, workflow_style: str = "") -> str:
    options = recipe["wildcard_v2"]
    if str(recipe["comfy_url"]).rstrip("/") not in {
        "http://127.0.0.1:8190",
        "http://localhost:8190",
    }:
        msg = "Wildcard V2 需要本機 ComfyUI http://127.0.0.1:8190"
        raise StudioError(msg)
    profile = json.loads(V2_TEMPLATE_PATH.read_text(encoding="utf-8"))[options["family"]]
    defaults = profile["defaults"]
    segment = Template(profile["segment"])
    style = (
        workflow_style if options["style_mode"] == "preset" else _v2_slot(options, profile, "style")
    )
    if options["layout"] == "bundled":
        style = Template(profile["bundled_style_segment"]).substitute(value=style) if style else ""
        lighting = _v2_slot(options, profile, "lighting", default=defaults["lighting"])
        if (
            options["character_mode"] == "random"
            and not options["character_pool"].strip()
            and lighting == defaults["lighting"]
            and not any(options["tag_filters"].values())
        ):
            return Template(profile["random"]).substitute(style=style)
        character = _v2_slot(options, profile, "character", default=defaults["character"])
        character_segment = Template(profile["bundled_character_segment"])
        return Template(profile["bundled"]).substitute(
            style=style,
            character=character_segment.substitute(value=character) if character else "",
            lighting=segment.substitute(value=lighting) if lighting else "",
        )
    defaults = _v2_independent_defaults(profile, options["scene_preset"])
    segments = profile["independent_segments"]
    scene_slot = "scene_light" if options["test_lighting_mode"] == "none" else "test_lighting"
    values = {
        slot: _v2_slot(options, profile, slot, default=defaults[slot])
        for slot in ("layout", "character", "outfit", "action")
    }
    values["style"] = style
    values["scene_light"] = _v2_slot(options, profile, scene_slot, default=defaults[scene_slot])
    substitutions = {
        slot: Template(segments.get(slot, segments["default"])).substitute(value=value)
        if value
        else ""
        for slot, value in values.items()
    }
    return Template(profile["independent"]).substitute(substitutions)


def _request_v2_impact(
    method: str,
    path: str,
    payload: bytes | None,
    *,
    operation: str,
) -> object:
    try:
        with closing(HTTPConnection("127.0.0.1", V2_COMFY_PORT, timeout=20)) as connection:
            connection.request(
                method,
                path,
                body=payload,
                headers={"Content-Type": "application/json"} if payload is not None else {},
            )
            with connection.getresponse() as response:
                status = response.status
                result = json.load(response) if status == HTTPStatus.OK else None
    except (HTTPException, OSError, ValueError) as error:
        msg = f"無法讀取本機 Impact Pack {operation}，請確認 ComfyUI 與 Impact Pack 已啟動"
        raise StudioError(msg) from error
    if status != HTTPStatus.OK:
        msg = f"Impact Pack {operation}失敗，HTTP {status}"
        raise StudioError(msg)
    return result


def list_wildcard_v2_pools() -> list[str]:
    result = _request_v2_impact("GET", "/impact/wildcards/list", None, operation="詞庫列表")
    pools = result.get("data") if isinstance(result, dict) else None
    if not isinstance(pools, list):
        msg = "Impact Pack 詞庫列表格式有誤"
        raise StudioError(msg)
    return sorted({pool for pool in pools if isinstance(pool, str) and V2_WILDCARD.fullmatch(pool)})


def _expand_v2(text: str, seed: int) -> str:
    request_data = {"text": strip_tag_headers(text), "seed": seed}
    payload = json.dumps(request_data, ensure_ascii=False).encode("utf-8")
    result = _request_v2_impact("POST", "/impact/wildcards", payload, operation="抽詞")
    expanded = result.get("text") if isinstance(result, dict) else None
    cleaned = strip_tag_headers(expanded) if isinstance(expanded, str) else ""
    if not cleaned.strip() or V2_WILDCARD.search(cleaned):
        msg = "Impact Pack 未完整展開 Wildcard V2，請確認詞庫已安裝並重新載入"
        raise StudioError(msg)
    return cleaned


def _prepare_v2_batch(recipe: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    workflow_style = str(config.get("wildcard_v2_workflow_style") or "")
    template = _v2_template(recipe, workflow_style=workflow_style)
    filters = recipe["wildcard_v2"]["tag_filters"]
    comfy_root = str(config.get("comfy_root") or "")
    rows = []
    for index in range(recipe["count"]):
        text_seed = seed_value(recipe["text_seed"], "increment", index)
        routed = route_tagged_template(
            template,
            filters,
            comfy_root=comfy_root,
            seed=text_seed,
            expand=_expand_v2,
        )
        text = _expand_v2(routed, text_seed)
        rows.append(
            {
                "prefix": "",
                "body": text,
                "negative": recipe["negative"],
                "suffix": "",
                "positive": text,
                "text_seed": text_seed,
                "seed": seed_value(recipe["seed"], recipe["seed_mode"], index),
                "index": index,
                "debug": "",
            }
        )
    return rows


def prepare_batch(
    store: StudioStore,
    recipe: dict[str, Any],
    config: dict[str, Any],
    locked: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    if wildcard_v2_active(recipe):
        return _prepare_v2_batch(recipe, config)
    rows = []
    locked = dict(recipe.get("locked_values", {})) | (locked or {})
    first: dict[str, Any] | None = None
    for index in range(recipe["count"]):
        text_seed = seed_value(recipe["text_seed"], recipe["text_seed_mode"], index)
        if recipe["batch_mode"] == "same_text" and first is not None:
            expanded = dict(first)
        else:
            expanded = expand_fields(
                store, recipe, text_seed=text_seed, config=config, locked=locked
            )
            if first is None:
                first = expanded
                for name in FIELDS:
                    if recipe["locks"].get(name):
                        locked[name] = expanded[name]
        rows.append(
            {
                **expanded,
                "seed": seed_value(
                    recipe["seed"],
                    recipe["seed_mode"],
                    index,
                    2**32 if recipe["backend"] == "novelai" else 2**53,
                ),
                "index": index,
            }
        )
    return rows
