from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_CSS = (ROOT / "src/prompt_hub/web_assets/base.css").read_text(encoding="utf-8")
BASE_JS = (ROOT / "src/prompt_hub/web_assets/base.js").read_text(encoding="utf-8")
CREATIVE_CSS = (ROOT / "src/prompt_hub/web_assets/creative.css").read_text(encoding="utf-8")
CREATIVE_JS = (ROOT / "src/prompt_hub/web_assets/creative.js").read_text(encoding="utf-8")
SOURCE_CENTER = (ROOT / "src/prompt_hub/source_center_web.py").read_text(encoding="utf-8") + (
    ROOT / "src/prompt_hub/web_assets/source_center.css"
).read_text(encoding="utf-8")
CREATIVE_LAYOUT = (ROOT / "src/prompt_hub/creative_web_layout.py").read_text(encoding="utf-8")
COMFY_WEB = (ROOT / "src/prompt_hub/comfy_web.py").read_text(encoding="utf-8") + (
    ROOT / "src/prompt_hub/web_assets/comfy.css"
).read_text(encoding="utf-8")
LORA_WEB = (ROOT / "src/prompt_hub/lora_web.py").read_text(encoding="utf-8") + (
    ROOT / "src/prompt_hub/web_assets/lora.css"
).read_text(encoding="utf-8")


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


def _token(name: str) -> str:
    value = re.search(rf"{name}:\s*(#[0-9a-fA-F]{{6}});", BASE_CSS)
    assert value is not None, name
    return value.group(1)


def test_motion_is_local_lightweight_and_reduced_motion_safe() -> None:
    assert "--motion-press: 90ms" in BASE_CSS
    assert "--motion-page: 180ms" in BASE_CSS
    assert 'button:not(:disabled):not([data-motion="none"]):active' in BASE_CSS
    assert "translate: 0 1px" in BASE_CSS
    assert "scroll-behavior: auto !important" in BASE_CSS
    assert "translate: none !important" in BASE_CSS
    assert ".prompt-hub-view-enter" in BASE_CSS
    assert "@keyframes prompt-hub-view-enter" in BASE_CSS

    assert "function prefersReducedMotion()" in BASE_JS
    assert "function restartCssMotion(element, className)" in BASE_JS
    assert "function playViewEnter(view)" in BASE_JS
    assert "target.animate(" in BASE_JS
    assert "offsetWidth" not in BASE_JS
    assert "window.playPromptHubStatusPulse" in BASE_JS

    view_motion = BASE_JS[
        BASE_JS.index("const VIEW_MOTION_SELECTORS") : BASE_JS.index("async function setView")
    ]
    assert ".dataset-card" not in view_motion
    assert ".result-card" not in view_motion
    assert ".comfy-result" not in view_motion


def test_success_feedback_does_not_animate_each_edit() -> None:
    queue_start = CREATIVE_JS.index("function queueCreativeSave")
    save_start = CREATIVE_JS.index("function saveCreative")
    workflow_start = CREATIVE_JS.index("async function sendWorkflowProfile")
    queue_source = CREATIVE_JS[queue_start:save_start]
    save_source = CREATIVE_JS[save_start:workflow_start]

    assert "playPromptHubStatusPulse" not in queue_source
    assert "playPromptHubStatusPulse" in save_source
    assert "offsetWidth" not in CREATIVE_JS
    script = (
        queue_source
        + save_source
        + r"""
const assert=require('node:assert/strict');
let dom='first',pulses=0,pending=[],creativeSaveQueue=Promise.resolve();
const creativeState={project:{project_id:'a',revision:1},projects:[]},sceneState={projectId:''};
const window={playPromptHubStatusPulse:()=>pulses++};
const $=()=>({textContent:''}),renderOutput=()=>{},renderCreativeProjects=()=>{};
const collectCreative=()=>({...creativeState.project,brief_zh:dom});
const creativeContentSnapshot=project=>JSON.stringify((project||collectCreative()).brief_zh);
const creativeJson=(url,options)=>new Promise((resolve,reject)=>{
 pending.push({resolve,reject,body:JSON.parse(options.body)});
});
const setTimeout=()=>1,clearTimeout=()=>{},showCreativeError=()=>{};
const loadIterationContext=async()=>{},refreshProjectJourney=async()=>{};
const tick=()=>new Promise(setImmediate);
(async()=>{
 queueCreativeSave();dom='typing';queueCreativeSave();
 assert.equal(pulses,0);
 const saved=saveCreative();await tick();assert.equal(pulses,0);
 dom='edited during save';queueCreativeSave();
 const first=pending.shift();first.resolve({...first.body,revision:2});await tick();
 assert.equal(pulses,0);assert.equal(pending.length,1);
 const last=pending.shift();last.resolve({...last.body,revision:3});await saved;
 assert.equal(pulses,1);
 const failed=saveCreative();await tick();pending.shift().reject(Error('write failed'));
 await assert.rejects(failed,/write failed/);assert.equal(pulses,1);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )
    node = shutil.which("node")
    assert node is not None
    subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)  # noqa: S603


def test_known_dark_surface_text_meets_normal_text_contrast() -> None:
    disabled = re.search(
        r"\.wd14-toolbar button:disabled\s*\{[^}]*background:\s*var\((--[a-z-]+)\);"
        r"[^}]*color:\s*var\((--[a-z-]+)\)",
        CREATIVE_CSS,
    )
    assert disabled is not None
    assert _contrast(_token(disabled.group(1)), _token(disabled.group(2))) >= 4.5

    no_image = re.search(
        r"\.workflow-lora-selected \.workflow-lora-no-image\s*\{[^}]*color:\s*var\((--[a-z-]+)\)",
        CREATIVE_CSS,
    )
    assert no_image is not None
    assert _contrast(_token("--ink-line"), _token(no_image.group(1))) >= 4.5

    assert "input::placeholder, textarea::placeholder" in BASE_CSS
    assert "opacity: 1" in BASE_CSS

    signal = re.search(r"--signal:\s*(#[0-9a-fA-F]{6})", BASE_CSS)
    assert signal is not None
    assert _contrast(signal.group(1), "#d8d1bf") >= 4.5
    assert "color:var(--signal)" in SOURCE_CENTER


def test_navigation_does_not_interpolate_through_low_contrast_colors() -> None:
    nav_rule = re.search(r"\.app-nav-button\s*\{([^}]*)\}", BASE_CSS)
    assert nav_rule is not None
    transition = re.search(r"transition:\s*([^;]+)", nav_rule.group(1))
    assert transition is not None
    assert "color" not in transition.group(1)
    assert "background" not in transition.group(1)


def test_motion_fallback_targets_only_the_page_heading() -> None:
    start = BASE_JS.index("const VIEW_MOTION_SELECTORS")
    end = BASE_JS.index("async function setView")
    motion_source = BASE_JS[start:end]
    script = f"""
const assert = require('node:assert/strict');
const pending = [];
const classes = new Set();
const queried = [];
let reduced = false;
const target = {{
  classList: {{
    add(value) {{ classes.add(value); }},
    remove(value) {{ classes.delete(value); }},
  }},
  addEventListener() {{}},
}};
const window = {{
  matchMedia() {{ return {{matches: reduced}}; }},
  requestAnimationFrame(callback) {{ pending.push(callback); return pending.length; }},
  cancelAnimationFrame() {{}},
}};
const document = {{
  documentElement: {{dataset: {{usageMode: 'windows_local'}}}},
  querySelector(selector) {{ queried.push(selector); return target; }},
}};
const motion = new Function('window', 'document', {motion_source!r} + `
  return {{playViewEnter, playPromptHubStatusPulse}};
`)(window, document);
motion.playViewEnter('datasets');
assert.equal(queried.at(-1), '#workspacePage .dataset-heading');
assert.equal(classes.size, 0);
pending.shift()();
pending.shift()();
assert.equal(classes.has('prompt-hub-view-enter'), true);
assert.equal(queried.some(value => value.includes('dataset-card')), false);
motion.playPromptHubStatusPulse(target);
pending.shift()();
pending.shift()();
assert.equal(classes.has('prompt-hub-status-pulse'), true);
reduced = true;
const count = queried.length;
motion.playViewEnter('comfy');
assert.equal(queried.length, count);
"""
    node = shutil.which("node")
    assert node is not None
    subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)  # noqa: S603


def test_save_state_is_announced_to_assistive_technology() -> None:
    assert 'id="creativeSaveState" role="status" aria-live="polite"' in CREATIVE_LAYOUT


def test_dense_result_surfaces_do_not_gain_mount_animations() -> None:
    for selector in (".dataset-card", ".result-card", ".comfy-result"):
        rules = re.findall(rf"{re.escape(selector)}[^{{]*\{{([^}}]*)\}}", BASE_CSS + CREATIVE_CSS)
        assert all("animation:" not in rule for rule in rules)


def test_checkbox_controls_are_not_sized_like_text_fields() -> None:
    assert 'input:not([type="checkbox"]):not([type="radio"]), select' in BASE_CSS
    assert (
        '.comfy-panel input:not([type="checkbox"]):not([type="radio"]), .comfy-panel select'
    ) in COMFY_WEB
    assert 'class="comfy-check"' in COMFY_WEB
    assert '.comfy-check input[type="checkbox"]' in COMFY_WEB
    assert "width: 16px" in COMFY_WEB
    assert "height: 16px" in COMFY_WEB

    assert (
        '.lora-form input:not([type="checkbox"]):not([type="radio"]), '
        ".lora-form select, .lora-form textarea"
    ) in LORA_WEB
    assert '.lora-checks input[type="checkbox"]' in LORA_WEB
    assert "width: 16px" in LORA_WEB
    assert "height: 16px" in LORA_WEB
