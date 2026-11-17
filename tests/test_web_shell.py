import re
from importlib.resources import files

from prompt_hub.remote_web import REMOTE_STYLES
from prompt_hub.web import INDEX_HTML, render_index_html


def test_web_shell_assembles_packaged_assets() -> None:
    asset_root = files("prompt_hub").joinpath("web_assets")
    template = asset_root.joinpath("index.html").read_text(encoding="utf-8")
    styles = asset_root.joinpath("base.css").read_text(encoding="utf-8")
    script = asset_root.joinpath("base.js").read_text(encoding="utf-8")
    i18n_script = asset_root.joinpath("i18n.js").read_text(encoding="utf-8")

    assert "__PROMPT_HUB_BASE_STYLES__" in template
    assert "__PROMPT_HUB_BASE_SCRIPT__" in template
    assert "__PROMPT_HUB_I18N_SCRIPT__" in template
    assert "__PROMPT_HUB_BASE_STYLES__" not in INDEX_HTML
    assert "__PROMPT_HUB_BASE_SCRIPT__" not in INDEX_HTML
    assert "__PROMPT_HUB_I18N_SCRIPT__" not in INDEX_HTML
    assert styles in INDEX_HTML
    assert re.sub(r"<button\b(?![^>]*\btype\s*=)", '<button type="button"', script) in INDEX_HTML
    assert i18n_script in INDEX_HTML

    creative_styles = asset_root.joinpath("creative.css").read_text(encoding="utf-8")
    creative_script = asset_root.joinpath("creative.js").read_text(encoding="utf-8")
    assert creative_styles in INDEX_HTML
    assert (
        re.sub(r"<button\b(?![^>]*\btype\s*=)", '<button type="button"', creative_script)
        in INDEX_HTML
    )
    assert re.search(r"<button\b(?![^>]*\btype\s*=)", INDEX_HTML) is None


def test_web_shell_keeps_device_name_escaping() -> None:
    rendered = render_index_html('</script><script>alert("x")</script>')

    assert "__PROMPT_HUB_DEVICE_NAME_HTML__" not in rendered
    assert "__PROMPT_HUB_DEVICE_NAME_JSON__" not in rendered
    assert "&lt;/script&gt;" in rendered
    assert r"\u003c/script\u003e\u003cscript\u003ealert" in rendered


def test_web_shell_exposes_persistent_interface_language_switcher() -> None:
    assert 'id="uiLanguageSelect"' in INDEX_HTML
    assert '<option value="zh-CN" data-i18n-ignore>简体中文</option>' in INDEX_HTML
    assert '<option value="zh-TW" data-i18n-ignore>繁體中文</option>' in INDEX_HTML
    assert '<option value="en" data-i18n-ignore>English</option>' in INDEX_HTML
    assert "soda-prompt-hub-ui-language" in INDEX_HTML
    assert "window.promptHubI18n" in INDEX_HTML
    assert "window.location.reload()" in INDEX_HTML
    assert "if (record.type === 'characterData')" in INDEX_HTML
    assert "characterData:true" in INDEX_HTML
    assert "attributeFilter:['placeholder', 'aria-label', 'title', 'alt']" in INDEX_HTML
    assert "traditionalProtectedPatterns" in INDEX_HTML


def test_tagger_has_a_standalone_navigation_entry_and_route_host() -> None:
    assert 'data-view="tagger">打标器</button>' in INDEX_HTML
    assert 'id="workbenchTagger"' in INDEX_HTML
    assert 'id="workbenchTaggerStudioHost"' in INDEX_HTML
    assert '"tagger"' in INDEX_HTML


def test_interface_language_preserves_user_defined_device_name() -> None:
    assert "data-remote-device-name data-i18n-ignore" in INDEX_HTML
    assert "\uff1b <span data-remote-device-name data-i18n-ignore>" in INDEX_HTML
    assert "</span> 的 ComfyUI" in INDEX_HTML


def test_english_local_search_has_no_mixed_language_copy() -> None:
    assert "'智能':'Local'" in INDEX_HTML
    assert "Choose text search or image search." in INDEX_HTML
    assert '"文件检查已经通过": "File checks passed"' in INDEX_HTML
    assert "Seed ${match[1]} · Steps ${match[2]}" in INDEX_HTML
    assert '"翻译与改写用哪个模型": "Model for Translation and Rewriting"' in INDEX_HTML
    assert "Model files are not copied" in INDEX_HTML


def test_mobile_remote_tabs_keep_long_labels_inside_each_tab() -> None:
    assert ".remote-section-tab-copy { width: 100%; }" in REMOTE_STYLES
    assert (
        ".remote-section-tab-copy strong { font-size: .875rem; line-height: 1.05; "
        "overflow-wrap: anywhere; white-space: normal; }"
    ) in REMOTE_STYLES


def test_comfy_result_legacy_prompt_summary_prefers_richer_text() -> None:
    assert "function displayPrompts(metadata)" in INDEX_HTML
    assert "longestPositive.length<12&&richerText.length>longestPositive.length" in INDEX_HTML
    assert "const prompts=displayPrompts(metadata)" in INDEX_HTML


def test_interface_translations_do_not_embed_personal_runtime_values() -> None:
    assert "/Users/soda" not in INDEX_HTML
    assert "CHINAMI-5E1E3GQ" not in INDEX_HTML
    assert "linhuieroc" not in INDEX_HTML
    assert re.search(r"project-[0-9a-f]{24,}", INDEX_HTML) is None
    assert "Local project directory: ${match[1]}" in INDEX_HTML
    assert "Device / ${match[2]}" in INDEX_HTML
    assert "Associated: ${match[1]}" in INDEX_HTML


def test_pr11_dataset_copy_has_three_language_entries() -> None:
    assert '"说明文字设置": "Caption Settings"' in INDEX_HTML
    assert '"训练内容": "Training Content"' in INDEX_HTML
    assert '"打标模型": "Tagging Model"' in INDEX_HTML
    assert "打标方式" not in INDEX_HTML
    assert "training, regularization, and final tag filtering" in INDEX_HTML
    assert "No need to generate tags again. Continue to manual review." in INDEX_HTML
    assert "Each export is saved as a separate version." in INDEX_HTML
    assert '"图片类型": "Image Type"' in INDEX_HTML
    assert '"二次元与插画": "Anime & Illustration"' in INDEX_HTML
    assert '"真人与摄影": "People & Photography"' in INDEX_HTML
