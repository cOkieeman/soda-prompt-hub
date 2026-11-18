from prompt_hub.web_resources import read_web_asset

OPTIONAL_MODELS_STYLES = "<style>" + read_web_asset("optional_models.css") + "</style>"
OPTIONAL_MODELS_SCRIPT = "<script>" + read_web_asset("optional_models.js") + "</script>"
OPTIONAL_MODELS_HTML = """
<dialog id="optionalModelsDialog" class="model-installer" data-i18n-ignore aria-labelledby="optionalModelsTitle" aria-describedby="optionalModelsIntro">
  <header class="model-installer-head"><div><h2 id="optionalModelsTitle" data-model-text="选择需要的本地模型">选择需要的本地模型</h2><p id="optionalModelsIntro" data-model-text="勾选需要的功能，再开始下载。以后也可以从设置中的「管理可选模型」安装。">勾选需要的功能，再开始下载。以后也可以从设置中的「管理可选模型」安装。</p></div><button type="button" id="optionalModelsClose" class="model-close" data-model-text="关闭">关闭</button></header>
  <div class="model-host"><strong id="optionalModelsHost"></strong><code id="optionalModelsRoot"></code></div>
  <p id="optionalModelsNotice" class="model-notice" role="status" aria-live="polite">正在读取模型状态…</p>
  <p id="optionalModelsRuntime" class="model-notice" hidden></p>
  <div id="optionalModelsList" class="model-install-list"></div>
  <footer class="model-installer-foot"><p data-model-text="支持取消与续传。关闭此窗口，下载仍会继续。">支持取消与续传。关闭此窗口，下载仍会继续。</p><p data-model-text="SAM3 场景图需要视觉 API，默认 CPU 推理。">SAM3 场景图需要视觉 API，默认 CPU 推理。</p><div class="model-installer-summary"><span id="optionalModelsSelection" role="status"></span><div><button type="button" id="optionalModelsSkip" class="model-secondary" data-model-text="稍后再说">稍后再说</button><button type="button" id="optionalModelsInstall" disabled data-model-text="下载所选模型">下载所选模型</button></div></div><button type="button" id="optionalModelsServices" class="model-service-link" data-model-text="管理连接">管理连接</button></footer>
</dialog>
"""
