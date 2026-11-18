import html
import json
import re

from prompt_hub.comfy_web import COMFY_HTML, COMFY_SCRIPT, COMFY_STYLES
from prompt_hub.creative_web import CREATIVE_HTML, CREATIVE_SCRIPT, CREATIVE_STYLES
from prompt_hub.gallery_web import GALLERY_HTML, GALLERY_SCRIPT, GALLERY_STYLES
from prompt_hub.lora_web import LORA_HTML, LORA_SCRIPT, LORA_STYLES
from prompt_hub.optional_models_web import (
    OPTIONAL_MODELS_HTML,
    OPTIONAL_MODELS_SCRIPT,
    OPTIONAL_MODELS_STYLES,
)
from prompt_hub.remote_web import REMOTE_HTML, REMOTE_SCRIPT, REMOTE_STYLES
from prompt_hub.search_web import SEARCH_HTML, SEARCH_SCRIPT, SEARCH_STYLES
from prompt_hub.source_center_web import (
    SOURCE_CENTER_HTML,
    SOURCE_CENTER_SCRIPT,
    SOURCE_CENTER_STYLES,
)
from prompt_hub.usage_modes import LINUX_LOCAL, USAGE_MODES, platform_usage_mode
from prompt_hub.web_resources import read_web_asset
from prompt_hub.workspace_web import WORKSPACE_HTML, WORKSPACE_SCRIPT, WORKSPACE_STYLES

INDEX_HTML = (
    read_web_asset("index.html")
    .replace("__PROMPT_HUB_BASE_STYLES__", read_web_asset("base.css"), 1)
    .replace(
        "__PROMPT_HUB_I18N_SCRIPT__",
        read_web_asset("workbench_i18n.js")
        + "\n"
        + read_web_asset("studio_i18n.js")
        + "\n"
        + read_web_asset("i18n.js"),
        1,
    )
    .replace(
        "__PROMPT_HUB_BASE_SCRIPT__",
        read_web_asset("navigation.js") + "\n" + read_web_asset("base.js"),
        1,
    )
)

navigation_start = INDEX_HTML.index('    <nav class="app-nav"')
navigation_end = INDEX_HTML.index("    </nav>", navigation_start) + len("    </nav>")
INDEX_HTML = (
    INDEX_HTML[:navigation_start] + read_web_asset("studio_nav.html") + INDEX_HTML[navigation_end:]
)
INDEX_HTML = INDEX_HTML.replace(
    '    <section class="management-page"',
    read_web_asset("studio_home.html")
    + "\n"
    + read_web_asset("studio.html")
    + '\n    <section class="management-page"',
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    '<button class="home-secondary" data-start="lora">',
    '<button type="button" class="home-secondary" data-start="projects">生成與整理訓練集</button>'
    '<button class="home-secondary" data-start="lora">',
    1,
)

INDEX_HTML = INDEX_HTML.replace(
    "</head>",
    f"{CREATIVE_STYLES}{GALLERY_STYLES}{WORKSPACE_STYLES}{LORA_STYLES}{COMFY_STYLES}{SEARCH_STYLES}{REMOTE_STYLES}{SOURCE_CENTER_STYLES}</head>",
    1,
)

INDEX_HTML = INDEX_HTML.replace(
    '<section class="management-page" id="managementPage" hidden>',
    f'{CREATIVE_HTML}{GALLERY_HTML}{SEARCH_HTML}{WORKSPACE_HTML}{LORA_HTML}{COMFY_HTML}{REMOTE_HTML}<section class="management-page" id="managementPage" hidden>',
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    '      </section>\n    </section>\n\n    <div class="workspace" id="archiveWorkspace" hidden>',
    f'      </section>\n{SOURCE_CENTER_HTML}\n    </section>\n\n    <div class="workspace" id="archiveWorkspace" hidden>',
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>",
    f"{OPTIONAL_MODELS_STYLES}{OPTIONAL_MODELS_HTML}{CREATIVE_SCRIPT}{GALLERY_SCRIPT}{SEARCH_SCRIPT}{WORKSPACE_SCRIPT}{LORA_SCRIPT}{COMFY_SCRIPT}{REMOTE_SCRIPT}{SOURCE_CENTER_SCRIPT}{OPTIONAL_MODELS_SCRIPT}<script>{read_web_asset('studio.js')}</script></body>",
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('studio.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace("<head>", f"<head><script>{read_web_asset('theme.js')}</script>", 1)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('theme.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('library.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>", f"<script>{read_web_asset('library.js')}</script></body>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('workbench.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>",
    read_web_asset("workbench.html") + f"<script>{read_web_asset('workbench.js')}</script></body>",
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('workbench_extra.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>",
    "".join(
        f"<script>{read_web_asset(name)}</script>"
        for name in (
            "gallery_workbench.js",
            "online_gallery.js",
            "agent_clients.js",
            "agent.js",
            "novelai.js",
            "local_styles_settings.js",
        )
    )
    + "</body>",
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('creation_canvas.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('prompt_editor.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>", f"<script>{read_web_asset('prompt_editor.js')}</script></body>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>",
    read_web_asset("creation_canvas.html")
    + "".join(
        f"<script>{read_web_asset(name)}</script>"
        for name in ("novelai_presets.js", "creation_canvas.js")
    )
    + "</body>",
    1,
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('online_gallery_viewer.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>", f"<script>{read_web_asset('online_gallery_viewer.js')}</script></body>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('approved_layout.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>", f"<script>{read_web_asset('approved_layout.js')}</script></body>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('novelai_characters.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>", f"<script>{read_web_asset('novelai_characters.js')}</script></body>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</head>", f"<style>{read_web_asset('novelai_account.css')}</style></head>", 1
)
INDEX_HTML = INDEX_HTML.replace(
    "</body>",
    read_web_asset("novelai_account.html")
    + f"<script>{read_web_asset('novelai_account.js')}</script></body>",
    1,
)
# Legacy action buttons and template strings also receive explicit semantics.
INDEX_HTML = re.sub(r"<button\b(?![^>]*\btype\s*=)", '<button type="button"', INDEX_HTML)


def render_index_html(device_name: str, *, usage_mode: str | None = None) -> str:
    mode = usage_mode or platform_usage_mode()
    if mode not in USAGE_MODES:
        message = f"Unsupported usage mode: {mode}"
        raise ValueError(message)
    dataset_example, model_example = _usage_mode_examples(mode)
    safe_name = device_name.strip() or (
        "Linux 绘图设备" if mode == LINUX_LOCAL else "Windows 绘图设备"
    )
    script_name = (
        json.dumps(safe_name, ensure_ascii=False)
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("&", r"\u0026")
    )
    markup = INDEX_HTML.replace(
        "__PROMPT_HUB_DEVICE_NAME_HTML__",
        html.escape(safe_name),
    ).replace(
        "__PROMPT_HUB_DEVICE_NAME_JSON__",
        script_name,
    )
    return (
        markup.replace("__PROMPT_HUB_USAGE_MODE__", mode)
        .replace("__PROMPT_HUB_DATASET_PATH__", dataset_example)
        .replace("__PROMPT_HUB_MODEL_PATH__", model_example)
    )


def _usage_mode_examples(mode: str) -> tuple[str, str]:
    """Example paths shown in placeholder text; they only illustrate the platform."""
    if mode == "windows_local":
        return "D:/Pictures/my-dataset", "D:/Models/vision_model.onnx"
    if mode == LINUX_LOCAL:
        return "~/Pictures/my-dataset", "~/models/vision_model.onnx"
    return "/Users/your-name/Pictures/my-dataset", "/Users/you/models/vision_model.onnx"
