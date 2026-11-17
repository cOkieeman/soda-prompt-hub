(() => {
  "use strict";
  const dialog = document.querySelector("#optionalModelsDialog");
  const list = document.querySelector("#optionalModelsList");
  const notice = document.querySelector("#optionalModelsNotice");
  const selected = new Set();
  const pending = new Map();
  let data = null, timer = null, fetching = false, highlighted = "", returnFocus = null;
  let rendered = "", submitting = false, firstRun = false, attempted = false;
  let restoredSelection = false;
  const messages = {
    "选择需要的本地模型": ["選擇需要的本地模型", "Choose local models"],
    "勾选需要的功能，再开始下载。以后也可以从设置中的「管理可选模型」安装。": ["勾選需要的功能，再開始下載。以後也可以從設定中的「管理可選模型」安裝。", "Choose the features you need, then download. You can also install models later in Settings → Manage optional models."],
    "关闭": ["關閉", "Close"], "稍后再说": ["稍後再說", "Maybe later"],
    "支持取消与续传。关闭此窗口，下载仍会继续。": ["支援取消與續傳。關閉此視窗，下載仍會繼續。", "Cancel or resume anytime. Downloads continue after closing."],
    "SAM3 场景图需要视觉 API，默认 CPU 推理。": ["SAM3 場景圖需要視覺 API，預設 CPU 推理。", "SAM3 scene graphs need a vision API. Inference defaults to CPU."],
    "下载所选模型": ["下載所選模型", "Download selected"], "管理连接": ["管理連接", "Manage connections"],
    "文件从 Hugging Face 下载，支持取消和续传。关闭此窗口，下载仍会继续。": ["檔案從 Hugging Face 下載，支援取消和續傳。關閉此視窗，下載仍會繼續。", "Files download from Hugging Face with cancel and resume support. Downloads continue after closing this window."],
    "SAM3 场景图还需要在「管理连接」配置视觉 API。推理设备默认使用 CPU，可在设置中调整。": ["SAM3 場景圖還需要在「管理連接」設定視覺 API。推理裝置預設使用 CPU，可在設定中調整。", "SAM3 scene graphs also need a vision API in Manage connections. Inference defaults to CPU and can be changed in Settings."],
    "WD14 · 二次元打标": ["WD14 · 二次元打標", "WD14 · Anime tagging"],
    "真人／摄影打标": ["真人／攝影打標", "Photography tagging"],
    "CLIP · 相似图检索": ["CLIP · 相似圖檢索", "CLIP · Image search"],
    "PixAI · 动漫标签": ["PixAI · 動漫標籤", "PixAI · Anime tags"],
    "SAM3 LiteText · 对象检测": ["SAM3 LiteText · 物件偵測", "SAM3 LiteText · Object detection"],
    "MiniLM · 关系去重": ["MiniLM · 關係去重", "MiniLM · Relation deduplication"],
    "为动漫、插画生成 Booru 标签草稿；安装后仍需人工审核。": ["為動漫、插畫生成 Booru 標籤草稿，安裝後仍需人工審核。", "Draft Booru tags for anime and illustrations. Review tags before use."],
    "为真人、摄影素材生成标签草稿；可在数据集工作区选择，不替换默认 WD14。": ["為真人、攝影素材生成標籤草稿，可在資料集工作區選擇。", "Draft tags for photographs. Select this model in the dataset workspace."],
    "为图片建立视觉特征，支持以图找图；安装后还需建立或更新图片索引。": ["為圖片建立視覺特徵，支援以圖找圖，安裝後需建立或更新圖片索引。", "Find visually similar images. Build or update the image index after installation."],
    "为图片生成 Danbooru 标签，供独立打标或 SAM3 场景图流程使用。": ["為圖片生成 Danbooru 標籤，供獨立打標或 SAM3 場景圖流程使用。", "Generate Danbooru tags for standalone tagging or SAM3 scene graphs."],
    "检测物件框线。搭配关系去重模型和视觉 API 生成场景图。": ["偵測物件框線，搭配關係去重模型和視覺 API 生成場景圖。", "Detect object boxes. Combine with MiniLM and a vision API to create scene graphs."],
    "合并场景图中的相似对象与关系，供 KohakuGBC 使用。": ["合併場景圖中的相似物件與關係，供 KohakuGBC 使用。", "Merge similar objects and relationships in KohakuGBC scene graphs."],
    "未安装": ["未安裝", "Not installed"], "待继续": ["待繼續", "Partial download"],
    "待校验": ["待校驗", "Needs verification"], "可用": ["可用", "Ready"],
    "排队中": ["排隊中", "Queued"], "安装中": ["安裝中", "Installing"],
    "未完成": ["未完成", "Failed"], "已取消": ["已取消", "Canceled"],
    "路径不可用": ["路徑不可用", "Path unavailable"], "处理中": ["處理中", "Working"],
    "文件校验和本机推理自检通过": ["檔案校驗和本機推理自檢通過", "File verification and local inference check passed"],
    "文件校验通过，已接入打标工作器": ["檔案校驗通過，已接入打標工作器", "Files verified and connected to the caption worker"],
    "未安装，用到时再装即可": ["未安裝，用到時再裝即可", "Install when you need this feature"],
    "发现已有文件，需校验并进行本机自检": ["發現已有檔案，請校驗後啟用", "Existing files found. Verify to enable."],
    "来源、文件与安装位置": ["來源、檔案與安裝位置", "Source, files and location"],
    "查看模型来源与许可": ["查看模型來源與授權", "Model source and license"],
    "下载并安装": ["下載並安裝", "Download and install"], "校验并启用": ["校驗並啟用", "Verify and enable"],
    "重试 / 继续安装": ["重試／繼續安裝", "Retry / Resume"], "已安装": ["已安裝", "Installed"],
    "取消安装": ["取消安裝", "Cancel installation"], "正在取消…": ["正在取消…", "Canceling…"],
    "安装到 {host} 服务所在设备": ["安裝到 {host} 服務所在裝置", "Install on the {host} server"],
    "已选 {count} 项 · {size}": ["已選 {count} 項 · {size}", "{count} selected · {size}"],
    "请选择需要的模型。": ["請選擇需要的模型。", "Choose the models you need."],
    "正在读取模型状态…": ["正在讀取模型狀態…", "Loading model status…"],
    "当前功能需要此模型。勾选后下载，或稍后安装。": ["目前功能需要此模型，勾選後下載，或稍後安裝。", "This feature needs this model. Select it to download or install later."],
    "部分功能需要完整的打标运行依赖，可使用 Windows 1.3 完整安装包，或在设置中指定已有工作器。": ["部分功能需要完整的打標執行依賴，可使用 Windows 1.3 完整安裝包，或在設定中指定已有工作器。", "Some features need the captioning dependencies. Use the Windows 1.3 full installer or configure an existing worker in Settings."],
    "下载任务已加入队列，可以关闭窗口继续工作。": ["下載任務已加入佇列，可以關閉視窗繼續工作。", "Downloads queued. You can close this window and continue working."],
    "取消请求已发送，下载断点会保留。": ["取消請求已傳送，下載斷點會保留。", "Cancellation requested. Download progress will be kept."],
    "无法读取安装状态，请稍后重试。": ["無法讀取安裝狀態，請稍後重試。", "Unable to load installation status. Please retry."],
    "操作失败，请重试。": ["操作失敗，請重試。", "The action failed. Please retry."],
    "下载进度": ["下載進度", "Download progress"],
  };
  function t(value, params = {}) {
    const locale = window.promptHubI18n?.getLocale?.() || "zh-CN";
    const text = locale === "zh-CN" ? value : messages[value]?.[locale === "en" ? 1 : 0] || value;
    return text.replace(/\{(\w+)\}/g, (_, key) => String(params[key] ?? ""));
  }
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const size = bytes => `${(Number(bytes || 0) / (Number(bytes) >= 1e9 ? 1e9 : 1e6)).toFixed(1)} ${Number(bytes) >= 1e9 ? "GB" : "MB"}`;
  async function request(url, options = {}) {
    const response = await fetch(url, {signal: AbortSignal.timeout(10000), ...options});
    const body = await response.json();
    if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : String(response.status));
    return body;
  }
  const post = (url, body) => request(url, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body || {})});
  function message(text, error = false) { notice.textContent = text; notice.dataset.error = String(error); }
  function available(model) { return model.state !== "ready" && model.state !== "blocked" && !["queued","running"].includes(model.job?.status); }
  function selectionSummary() {
    const models = (data?.models || []).filter(model => selected.has(model.id) && available(model));
    document.querySelector("#optionalModelsSelection").textContent = t("已选 {count} 项 · {size}", {count:models.length, size:size(models.reduce((total, model) => total + model.size_bytes, 0))});
    document.querySelector("#optionalModelsInstall").disabled = !models.length || submitting;
  }
  function render() {
    if (!data) return;
    const signature = JSON.stringify([data, [...pending], [...selected], highlighted, submitting]);
    selectionSummary();
    if (signature === rendered) return;
    rendered = signature;
    dialog.querySelectorAll("[data-model-text]").forEach(element => { element.textContent = t(element.dataset.modelText); });
    document.querySelector("#optionalModelsHost").textContent = t("安装到 {host} 服务所在设备", {host:data.host});
    document.querySelector("#optionalModelsRoot").textContent = data.models_root;
    const runtime = document.querySelector("#optionalModelsRuntime");
    runtime.hidden = data.caption_runtime_available;
    runtime.textContent = t("部分功能需要完整的打标运行依赖，可使用 Windows 1.3 完整安装包，或在设置中指定已有工作器。");
    const focus = document.activeElement?.id;
    const expanded = new Set([...list.querySelectorAll("details[open]")].map(item => item.dataset.modelDetails));
    list.innerHTML = data.models.map(model => {
      const job = model.job, active = job && ["queued","running"].includes(job.status);
      const stage = pending.has(model.id) ? "pending" : active ? job.status : model.state === "ready" ? "ready" : job?.status === "failed" ? "failed" : job?.status === "canceled" ? "canceled" : model.state;
      const labels = {missing:"未安装",partial:"待继续",unverified:"待校验",ready:"可用",queued:"排队中",running:"安装中",failed:"未完成",canceled:"已取消",blocked:"路径不可用",pending:"处理中"};
      const detail = pending.get(model.id) || (active ? job.progress_message || labels[stage] : stage === "failed" ? job.error : model.reason);
      const total = Number(job?.progress_total) || model.size_bytes;
      const current = Math.min(total, Math.max(0, Number(job?.progress_current) || 0));
      const progress = active && job.status === "running" ? `<progress class="model-install-progress" aria-label="${escape(t("下载进度"))}" value="${current}" max="${total}"></progress><p>${size(current)} / ${size(total)} · ${Math.floor(current / total * 100)}%</p>` : "";
      const action = active ? "cancel" : "install";
      const text = active ? (job.cancel_requested ? "正在取消…" : "取消安装") : stage === "ready" ? "已安装" : stage === "unverified" ? "校验并启用" : ["failed","canceled","partial"].includes(stage) ? "重试 / 继续安装" : "下载并安装";
      const disabled = submitting || pending.has(model.id) || stage === "ready" || stage === "blocked" || Boolean(active && job.cancel_requested);
      const title = escape(t(model.title));
      return `<article class="model-install-card" data-state="${stage}" data-highlight="${model.id === highlighted}">
        <input id="model-select-${escape(model.id)}" class="model-install-check" type="checkbox" data-model-select="${escape(model.id)}" aria-label="${title}" ${selected.has(model.id) ? "checked" : ""} ${!available(model) || submitting ? "disabled" : ""}>
        <div><div class="model-install-heading"><h3><label for="model-select-${escape(model.id)}">${title}</label></h3><span class="model-install-badge">${escape(t(labels[stage] || stage))}</span></div><p class="model-install-purpose">${escape(t(model.purpose))}</p>
        ${stage === "missing" ? "" : `<div class="model-install-feedback" role="status"><p>${escape(t(detail))}</p>${progress}</div>`}
        <details data-model-details="${escape(model.id)}" ${expanded.has(model.id) ? "open" : ""}><summary>${escape(t("来源、文件与安装位置"))}</summary><a href="${escape(model.source_url)}" target="_blank" rel="noopener noreferrer">${escape(t("查看模型来源与许可"))}</a><code>${escape(model.path)}</code><code>${escape(model.files.join(" + "))}</code></details></div>
        <div class="model-install-actions"><span class="model-install-size">${size(model.size_bytes)}</span><button id="optional-action-${escape(model.id)}" type="button" data-model-action="${action}" data-model-id="${escape(model.id)}" ${disabled ? "disabled" : ""}>${escape(t(text))}</button></div></article>`;
    }).join("");
    if (focus?.startsWith("optional-action-") || focus?.startsWith("model-select-")) document.getElementById(focus)?.focus({preventScroll:true});
  }
  async function refresh() {
    if (fetching || !dialog.open) return;
    fetching = true;
    try {
      data = await request("/api/optional-models");
      if (!restoredSelection) {
        restoredSelection = true;
        try {
          const saved = JSON.parse(sessionStorage.getItem("optional-model-selection-" + data.models_root) || "[]");
          saved.filter(id => data.models.some(model => model.id === id)).forEach(id => selected.add(id));
        } catch {}
      }
      if (dialog.open) render();
    } catch { message(t("无法读取安装状态，请稍后重试。"), true); }
    finally {
      fetching = false;
      clearTimeout(timer);
      if (dialog.open) timer = setTimeout(refresh, 1500);
    }
  }
  async function acknowledge() {
    await post("/api/optional-models/onboarding", {selected:[...selected]});
    firstRun = false;
  }
  window.openOptionalModels = async (modelId = "") => {
    highlighted = typeof modelId === "string" ? modelId : "";
    if (highlighted) selected.add(highlighted);
    if (!dialog.open) { returnFocus = document.activeElement; dialog.showModal(); }
    dialog.querySelectorAll("[data-model-text]").forEach(element => { element.textContent = t(element.dataset.modelText); });
    message(t(highlighted ? "当前功能需要此模型。勾选后下载，或稍后安装。" : "请选择需要的模型。"));
    await refresh();
  };
  window.ensureLocalTagger = async modelId => {
    const config = await request("/api/tagger-config");
    const selectedModel = modelId || config.id;
    if (config.models.some(model => model.id === selectedModel && model.available)) return true;
    await window.openOptionalModels(selectedModel);
    return false;
  };
  window.ensureCaptionModels = async method => {
    const required = {pixai:["pixai_model"],gbc:["detector_model","embedder_model"],pixai_gbc:["pixai_model","detector_model","embedder_model"]}[method];
    if (!required) return method === "wd14" ? window.ensureLocalTagger() : true;
    const status = await request("/api/optional-models");
    const worker = await request("/api/studio/settings");
    const missing = status.models.filter(model => required.includes(model.caption_key) && model.state !== "ready" && !worker.caption_worker?.[model.caption_key]);
    if (!status.caption_runtime_available && !worker.caption_worker?.python) {
      await window.openOptionalModels();
      return false;
    }
    if (!missing.length) return true;
    missing.forEach(model => selected.add(model.id));
    await window.openOptionalModels(missing[0].id);
    return false;
  };
  list.addEventListener("change", event => {
    const id = event.target.dataset.modelSelect;
    if (!id) return;
    if (event.target.checked) {
      selected.add(id);
      if (id === "sam3-litetext-l") selected.add("all-MiniLM-L6-v2");
    } else selected.delete(id);
    try { sessionStorage.setItem("optional-model-selection-" + data.models_root, JSON.stringify([...selected])); } catch {}
    render();
  });
  async function operate(model, cancel) {
    pending.set(model.id, t("处理中")); render();
    try {
      await post(cancel ? `/api/jobs/${encodeURIComponent(model.job.job_id)}/cancel` : `/api/optional-models/${encodeURIComponent(model.id)}/install`);
    } finally { pending.delete(model.id); }
  }
  list.addEventListener("click", async event => {
    const button = event.target.closest("[data-model-action]");
    if (!button || button.disabled) return;
    const model = data?.models.find(item => item.id === button.dataset.modelId);
    if (!model || pending.has(model.id)) return;
    try {
      const cancel = button.dataset.modelAction === "cancel";
      await operate(model, cancel);
      if (!cancel && firstRun) await acknowledge();
      message(t(cancel ? "取消请求已发送，下载断点会保留。" : "下载任务已加入队列，可以关闭窗口继续工作。"));
    } catch (error) { message(`${t("操作失败，请重试。")} ${error.message}`, true); }
    finally { rendered = ""; await refresh(); }
  });
  document.querySelector("#optionalModelsInstall").addEventListener("click", async () => {
    if (submitting) return;
    submitting = true; render();
    try {
      const models = data.models.filter(model => selected.has(model.id) && available(model));
      for (const model of models) await operate(model, false);
      await acknowledge();
      message(t("下载任务已加入队列，可以关闭窗口继续工作。"));
    } catch (error) { message(`${t("操作失败，请重试。")} ${error.message}`, true); }
    finally { submitting = false; rendered = ""; await refresh(); }
  });
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-open-optional-models]");
    if (button) window.openOptionalModels(button.dataset.openOptionalModels);
  });
  async function close() {
    try { if (firstRun) await acknowledge(); dialog.close(); }
    catch { message(t("操作失败，请重试。"), true); }
  }
  document.querySelector("#optionalModelsClose").addEventListener("click", close);
  document.querySelector("#optionalModelsSkip").addEventListener("click", close);
  dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
  dialog.addEventListener("close", () => {
    clearTimeout(timer);
    if (returnFocus?.isConnected) returnFocus.focus({preventScroll:true});
    window.dispatchEvent(new Event("optional-models-changed"));
  });
  document.querySelector("#optionalModelsServices").addEventListener("click", async () => { await close(); window.openModelEndpoints?.(); });
  async function offerModels() {
    if (attempted) return;
    attempted = true;
    try {
      const status = await request("/api/optional-models");
      if (status.onboarding.completed) return;
      firstRun = true;
      (status.onboarding.selected || []).forEach(id => selected.add(id));
      try {
        const saved = JSON.parse(sessionStorage.getItem("optional-model-selection-" + status.models_root) || "[]");
        saved.filter(id => status.models.some(model => model.id === id)).forEach(id => selected.add(id));
      } catch {}
      if (document.querySelector("dialog[open]")) { attempted = false; setTimeout(offerModels, 1500); return; }
      await window.openOptionalModels();
    } catch { attempted = false; }
  }
  window.addEventListener("prompt-hub-language-ready", () => setTimeout(offerModels, 250), {once:true});
  if (document.readyState !== "loading") setTimeout(offerModels, 500);
  else document.addEventListener("DOMContentLoaded", () => setTimeout(offerModels, 500), {once:true});
})();
