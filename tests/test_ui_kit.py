from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_CSS = (ROOT / "src/prompt_hub/web_assets/base.css").read_text(encoding="utf-8")
KIT_CSS = BASE_CSS[BASE_CSS.index("/* Shared UI kit") : BASE_CSS.index("button:focus-visible")]
ROOT_BLOCK = BASE_CSS[BASE_CSS.index(":root {") : BASE_CSS.index('html[lang="zh-TW"]')]
# Pages already moved onto the shared tokens; each later PR appends its stylesheet here.
TOKENIZED_PAGE_CSS = ("workspace.css",)


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2])


def _contrast(first: str, second: str) -> float:
    bright, dark = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def _tokens() -> dict[str, str]:
    return dict(re.findall(r"(--[a-z-]+):\s*([^;]+);", ROOT_BLOCK))


def test_ui_kit_uses_only_defined_tokens_and_no_literal_colors() -> None:
    tokens = _tokens()
    used = set(re.findall(r"var\((--[a-z-]+)\)", KIT_CSS))

    assert used
    assert used <= set(tokens)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", KIT_CSS)


def test_ui_kit_provides_one_class_per_shared_component() -> None:
    for selector in (
        ".ui-btn {",
        ".ui-btn-primary {",
        ".ui-banner {",
        "select.ui-field",
        ".ui-card {",
        ".ui-chip {",
        ".ui-dialog {",
        ".ui-job {",
    ):
        assert selector in KIT_CSS


def test_ui_kit_text_pairs_stay_readable() -> None:
    tokens = _tokens()
    pairs = (
        ("--ink", "--paper-lift"),
        ("--ink", "--paper-surface"),
        ("--ink", "--paper-wash"),
        ("--muted", "--paper-wash"),
        ("--paper-lift", "--signal"),
        ("--paper-surface", "--ink"),
        ("--signal-deep", "--signal-wash"),
    )

    for foreground, background in pairs:
        assert _contrast(tokens[foreground], tokens[background]) >= 4.5, (foreground, background)


def test_tokenized_pages_use_defined_tokens_and_no_literal_colors() -> None:
    tokens = _tokens()

    for name in TOKENIZED_PAGE_CSS:
        styles = (ROOT / "src/prompt_hub/web_assets" / name).read_text(encoding="utf-8")
        assert set(re.findall(r"var\((--[a-z-]+)\)", styles)) <= set(tokens), name
        assert not re.findall(r"#[0-9a-fA-F]{3,8}\b", styles), name
        assert not re.findall(r":\s*(?:white|black)\b", styles), name
