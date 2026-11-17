from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from prompt_hub.studio_store import FIELDS, StudioError, StudioStore


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


def prepare_batch(
    store: StudioStore,
    recipe: dict[str, Any],
    config: dict[str, Any],
    locked: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
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
