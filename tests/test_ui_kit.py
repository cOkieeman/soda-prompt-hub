from __future__ import annotations

import re
from pathlib import Path

from prompt_hub.search_web import SEARCH_STYLES

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src/prompt_hub/web_assets"
BASE_CSS = (ASSETS / "base.css").read_text(encoding="utf-8")
THEME_CSS = (ASSETS / "theme.css").read_text(encoding="utf-8")


def luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    bright, dark = sorted([luminance(first), luminance(second)], reverse=True)
    return (bright + 0.05) / (dark + 0.05)


def tokens(mode: str) -> dict[str, str]:
    base = re.search(r":root\s*\{([^}]+)", BASE_CSS).group(1)
    light = re.search(r":root\s*\{([^}]+)", THEME_CSS).group(1)
    dark = re.search(r'html\[data-theme="dark"\]\s*\{([^}]+)', THEME_CSS).group(1)
    return dict(
        re.findall(
            r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", base + light + (dark if mode == "dark" else "")
        )
    )


def test_shared_controls_keep_keyboard_focus_visible() -> None:
    assert "button:focus-visible" in BASE_CSS
    assert "textarea:focus-visible" in BASE_CSS
    assert "outline: 3px solid var(--acid)" in BASE_CSS
    assert 'html[data-theme="dark"] dialog' in THEME_CSS


def test_shared_surfaces_use_theme_colors() -> None:
    for token in ["--field-bg", "--on-signal", "--on-acid", "--studio-paper", "--studio-ink"]:
        assert f"var({token})" in THEME_CSS
    assert "@media" in THEME_CSS
    assert "prefers-reduced-motion" in BASE_CSS


def test_light_and_dark_text_pairs_stay_readable() -> None:
    for mode in ["light", "dark"]:
        palette = tokens(mode)
        for foreground, background in [
            ("--ink", "--paper"),
            ("--muted", "--paper"),
            ("--ink", "--field-bg"),
            ("--on-signal", "--signal-fill"),
            ("--on-acid", "--acid"),
        ]:
            assert contrast(palette[foreground], palette[background]) >= 4.5, (
                mode,
                foreground,
                background,
            )


def test_search_placeholder_text_stays_readable_on_dark_surface() -> None:
    assert ".discovery-placeholder" in SEARCH_STYLES
    assert "color: var(--inverse-muted)" in SEARCH_STYLES
    assert contrast(tokens("light")["--inverse-muted"], "#20211e") >= 4.5


def test_stylesheets_use_defined_custom_properties() -> None:
    styles = {path.name: path.read_text(encoding="utf-8") for path in ASSETS.glob("*.css")}
    for path in (ROOT / "src/prompt_hub").glob("*_web.py"):
        styles[path.name] = path.read_text(encoding="utf-8")
    declarations = set(re.findall(r"(--[\w-]+)\s*:", "\n".join(styles.values())))
    script_properties = {"--creation-height", "--position-aspect", "--visual-count"}
    for name, style in styles.items():
        used = set(re.findall(r"var\((--[\w-]+)", style))
        assert used <= declarations | script_properties, (
            name,
            used - declarations - script_properties,
        )
