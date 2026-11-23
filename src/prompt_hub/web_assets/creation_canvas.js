/* Layout follows NAI Launcher v4.3.1 WebLeftPanel and GenerationControls.
   Existing Studio controls retain their IDs, event handlers and stored recipes. */
(() => {
  "use strict";

  const $ = selector => document.querySelector(selector);
  const editor = $("#studioPage .studio-editor");
  const layout = editor.closest(".studio-generation-layout");
  const legacy = document.createElement("div");
  legacy.hidden = true;
  legacy.append(...editor.childNodes);
  editor.append($("#creationCanvasTemplate").content.cloneNode(true));
  $("#creationLegacyControls").append(legacy);
  const collapseButton = $("#creationCollapse");
  const parameters = $("#creationParameters");
  const parameterShortcut = $("#creationParameterShortcut");
  const referenceInputs = [...editor.querySelectorAll("[data-canvas-reference]")];
  const paths = {
    brush: "m14 5 5-3 3 3-3 5-5 5-5-5 5-5ZM9 10l5 5M8 14c-5 0-1 7-6 7 7 2 10-2 10-4",
    "chevron-left": "m14 6-6 6 6 6", "chevron-down": "m6 9 6 6 6-6", "chevron-up": "m6 15 6-6 6 6",
    swap: "M3 7h17m-4-4 4 4-4 4M21 17H4m4-4-4 4 4 4",
    unlock: "M8 10V7a4 4 0 0 1 8 0M6 10h12v11H6ZM12 14v3",
    lock: "M8 10V7a4 4 0 0 1 8 0v3M6 10h12v11H6ZM12 14v3",
    sparkles: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3ZM20 2v4m-2-2h4",
    ban: "M4 4 20 20M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
    pin: "m9 3 8 0-1 6 3 3v2h-6v7l-2-3v-4H5v-2l3-3 1-6Z",
    tag: "M3 3h8l10 10-8 8L3 11V3Zm4 4h.01",
    x: "m6 6 12 12M18 6 6 18",
    settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3Z",
    dice: "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM7 7h.01M17 7h.01M12 12h.01M7 17h.01M17 17h.01",
    user: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 21v-2a8 8 0 0 1 16 0v2H4Z",
    scan: "M3 8V3h5m8 0h5v5m0 8v5h-5M8 21H3v-5M8 8h8M8 12h5M8 16h8",
    image: "M3 3h18v18H3V3Zm0 13 6-6 5 5 3-3 4 4M16 7h.01",
    wand: "m4 20 13-13 3 3L7 23 4 20ZM15 3V1m-4 5H9m12-3 2-2m-2 12h2",
    target: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0ZM16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 3v3m0 12v3M3 12h3m12 0h3",
    workflow: "M3 3h6v6H3V3Zm12 12h6v6h-6v-6ZM6 9v9h9m3-3V6H9",
    check: "m5 12 4 4L19 6",
  };
  const icon = name => `<svg class="canvas-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"></path></svg>`;
  document.querySelectorAll("[data-canvas-icon]").forEach(element => { element.innerHTML = icon(element.dataset.canvasIcon); });
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[character]);
  const current = () => window.SodaStudio.current();
  const recipe = () => current().project?.studio;
  const translate = value => window.promptHubI18n?.t(value) || value;
  const state = {engine: "", tab: "positive", highlighted: true, cleared: null, reverseSerial: 0, referenceImporting: false};

  function move(selector, mount) { $(mount).append($(selector)); }
  function moveLabel(name, mount) { $(mount).append($(`[data-recipe="${name}"]`).closest("label")); }
  function detailFor(selector, mount) { $(mount).append($(selector).closest("details")); }

  ["width", "height"].forEach(name => {
    const label = $(`[data-recipe="${name}"]`).closest("label");
    const text = label.firstChild;
    const title = document.createElement("span");
    title.className = "creation-dimension-label";
    title.textContent = text.textContent;
    text.replaceWith(title);
    $(name === "width" ? "#creationWidth" : "#creationHeight").append(label);
  });
  move("#studioBody", "#creationPositive");
  move("#studioNegative", "#creationNegative");
  ["prefix", "suffix"].forEach(name => {
    $("#creationFixed").append($(`[data-recipe="${name}"]`).closest(".studio-prompt-field"));
  });
  $("#creationPositive").append($("#studioBody"));
  $("#studioBody").setAttribute("aria-label", "正文");
  $("#studioNegative").setAttribute("aria-label", "負面詞");
  ["#studioBody", "#studioNegative"].forEach(selector => {
    const textarea = $(selector);
    const wrapper = document.createElement("div");
    wrapper.className = "creation-highlight-editor";
    wrapper.dataset.highlight = "true";
    const highlight = document.createElement("div");
    highlight.className = "creation-highlight-text";
    highlight.setAttribute("aria-hidden", "true");
    textarea.before(wrapper);
    wrapper.append(highlight, textarea);
    textarea.spellcheck = false;
    textarea.addEventListener("scroll", () => { highlight.scrollTop = textarea.scrollTop; highlight.scrollLeft = textarea.scrollLeft; });
  });

  // The textarea has moved; the remaining original body controls keep their handlers.
  const originalBody = legacy.querySelector(".studio-prompt-field:has([data-recipe='text_mode'])");
  const originalNegative = legacy.querySelector(".studio-prompt-field:has(label[for='studioNegative'])");
  const prefixField = $("#studioPrefix").closest(".studio-prompt-field");
  const suffixField = $("#studioSuffix").closest(".studio-prompt-field");
  const bodyLock = originalBody.querySelector(".studio-lock");
  $("#creationRandomContent").append(originalBody.querySelector(".studio-control-row"));
  move("#studioWildcardV2", "#creationRandomContent");
  $("#creationRandomContent").append(originalBody.querySelector(".studio-lock"));
  move("#studioOpenWordlists", "#creationRandomContent");
  move("#studioLockDraw", "#creationRandomContent");
  detailFor("#studioRaffleSettings", "#creationRandomContent");
  ["text_seed", "text_seed_mode", "batch_mode"].forEach(name => moveLabel(name, "#creationRandomContent"));
  moveLabel("seed_mode", "#creationRandomContent");
  $('[data-recipe="seed_mode"]').closest("label").firstChild.textContent = "出圖種子變化";
  move("#studioDrawOnce", "#creationDraw");
  $("#studioDrawOnce").innerHTML = icon("dice");
  $("#studioDrawOnce").setAttribute("aria-label", "抽一次");
  move("#studioPreviewBatch", "#creationPreview");
  $("#studioPreviewBatch").innerHTML = icon("scan");
  $("#studioPreviewBatch").setAttribute("aria-label", "預覽本批提示詞");
  move("#studioQueueBatch", "#creationGenerate");
  $("#studioQueueBatch").innerHTML = icon("sparkles") + "<span>生成</span>";
  moveLabel("count", "#creationCount");
  const countLabel = $("#creationCount label");
  const countText = document.createElement("span");
  countText.textContent = countLabel.firstChild.textContent;
  countLabel.firstChild.replaceWith(countText);

  move("#studioProviderField", "#creationConnection");
  move("#studioWorkflowField", "#creationComfyContent");
  move("#studioImportWorkflow", "#creationComfyContent");
  move("#studioComfyUrlField", "#creationComfyContent");
  ["#studioReferenceBindings", "#studioPostprocess"].forEach(selector => detailFor(selector, "#creationComfyContent"));
  move(".workbench-references", "#creationComfyContent");
  move("#naiModel", "#creationModel");
  const modelInput = $("#naiModel");
  const modelLabel = document.createElement("label");
  modelLabel.textContent = "模型";
  modelInput.before(modelLabel);
  modelLabel.append(modelInput);
  const modelSelect = document.createElement("select");
  modelSelect.id = "naiModel";
  modelSelect.dataset.recipe = "model";
  modelSelect.innerHTML = '<option value="">使用連線預設模型</option>' + [...$("#naiModels").options].map(option => `<option value="${escape(option.value)}">${escape(displayModelName(option.value))}</option>`).join("");
  modelInput.replaceWith(modelSelect);
  $("#naiModels").remove();
  $("#naiModel").setAttribute("aria-label", "模型");
  $("#creationSampler").append($('[data-recipe="sampler"]').closest(".studio-control-row"));
  ["steps", "cfg"].forEach(name => moveLabel(name, "#creationSamplingValues"));
  $("#creationAdvanced").append($('[data-nai-check="smea"]').closest(".studio-checks"));
  move("#naiCapabilities", "#creationAdvanced");
  $("#creationCharactersContent").append($("#naiCharacters").parentElement, $("#studioCharacters").closest("details"));
  ["strength", "noise"].forEach(name => moveLabel(name, "#creationImg2imgParameters"));
  move("#naiDrawMask", "#creationImg2imgParameters");
  move("#naiOutpaint", "#creationImg2imgParameters");
  const imageMode = document.createElement("label");
  imageMode.innerHTML = '操作<select id="creationImageMode"><option value="img2img">圖生圖</option><option value="infill">局部重繪</option><option value="outpaint">擴圖</option></select>';
  $("#creationImg2imgParameters").prepend(imageMode);
  const comfyFields = document.createElement("div");
  comfyFields.id = "creationComfyFields";
  comfyFields.hidden = true;
  $(".creation-seed-section").after(comfyFields);
  const workflowTop = document.createElement("div");
  workflowTop.id = "creationWorkflowTop";
  workflowTop.hidden = true;
  $("#creationScroll").prepend(workflowTop);
  const importAlias = document.createElement("button");
  importAlias.type = "button";
  importAlias.textContent = "匯入工作流";
  importAlias.addEventListener("click", () => $("#studioImportWorkflow").click());
  workflowTop.append(importAlias);
  const footer = $(".creation-footer");
  const bodyActions = document.createElement("div");
  bodyActions.className = "creation-comfy-prompt-actions";
  bodyActions.innerHTML = '<button type="button" data-comfy-prompt-action="material">選詞</button><button type="button" data-comfy-prompt-action="draw">抽詞</button><button type="button" data-comfy-prompt-action="lock">鎖定抽取結果</button>';
  const comfyMaterial = bodyActions.querySelector('[data-comfy-prompt-action="material"]');
  comfyMaterial.addEventListener("click", () => $("#studioChooseMaterial").click());
  const prefixActions = document.createElement("div");
  prefixActions.className = "creation-comfy-field-actions";
  prefixActions.append(comfyMaterial, prefixField.querySelector(".studio-lock"));
  prefixField.querySelector("header").append(prefixActions);
  const bodyLockButton = bodyActions.querySelector('[data-comfy-prompt-action="lock"]');
  function renderBodyLock() {
    const locked = bodyLock.querySelector("input").checked;
    bodyLockButton.setAttribute("aria-pressed", String(locked));
    bodyLockButton.textContent = translate(locked ? "已鎖定" : "鎖定");
  }
  bodyActions.addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.comfyPromptAction === "lock") { bodyLock.querySelector("input").click(); renderBodyLock(); }
    else $("#studioDrawOnce").click();
  });
  originalBody.querySelector("header").append(bodyActions);

  const results = $("#studioPage .studio-results");
  const canvas = $(".workbench-canvas");
  canvas.append(results);
  const resultDetails = document.createElement("details");
  resultDetails.className = "creation-result-details";
  resultDetails.innerHTML = "<summary>提示詞預覽與任務</summary>";
  results.before(resultDetails);
  resultDetails.append(results);
  const compactComfy = matchMedia("(max-width: 1100px)");
  const headings = [...results.querySelectorAll(":scope > h2")];
  headings[2].textContent = "歷史";
  results.prepend(headings[2], $("#studioRecentImages"));
  headings[1].textContent = "佇列";

  function arrangeEngine(isComfy) {
    const bodyEditor = $("#studioBody").closest(".creation-highlight-editor");
    const negativeEditor = $("#studioNegative").closest(".creation-highlight-editor");
    comfyFields.hidden = !isComfy;
    workflowTop.hidden = !isComfy;
    bodyActions.hidden = !isComfy;
    comfyMaterial.hidden = !isComfy;
    $(".creation-prompts").hidden = isComfy;
    $(".creation-panel-header").hidden = isComfy;
    if (isComfy) {
      setCanvasCollapsed(false);
      $("#studioBody").style.height = "105px";
      $("#studioNegative").style.height = "52px";
      originalBody.append(bodyEditor);
      originalBody.querySelector("header").append(bodyLock);
      bodyLock.hidden = true;
      originalNegative.append(negativeEditor);
      comfyFields.append(prefixField, originalBody, originalNegative, suffixField);
      $("#creationRandomContent").append($("#studioToggleRows"));
      workflowTop.prepend($("#studioWorkflowField"));
      if (compactComfy.matches) resultDetails.append(results);
      else layout.append(results);
      layout.append(footer);
      workflowTop.append($("#studioWorkflowControls"));
    } else {
      $("#creationPositive").append(bodyEditor);
      $("#creationNegative").append(negativeEditor);
      $("#creationFixed").append(prefixField, suffixField);
      $("#creationRandomContent").append(bodyLock);
      bodyLock.hidden = false;
      prefixField.insertBefore($("#studioToggleRows"), $("#studioPrefixRows"));
      $("#creationComfyContent").prepend($("#studioWorkflowField"));
      $("#creationComfyContent").append($("#studioWorkflowControls"));
      resultDetails.append(results);
      editor.append(footer);
    }
  }

  function promptValue() {
    const value = recipe();
    if (!value) return "";
    return state.tab === "negative" ? value.negative : state.tab === "fixed" ? [value.prefix, value.suffix].filter(Boolean).join("\n") : value.body;
  }

  function renderHighlight(textarea) {
    const highlight = textarea.previousElementSibling;
    highlight.innerHTML = window.SodaPromptEditor.markup(textarea.value);
    highlight.scrollTop = textarea.scrollTop;
    if (state.engine === "novelai") {
      textarea.style.height = "auto";
      textarea.style.height = Math.min(480, Math.max(190, textarea.scrollHeight + 2)) + "px";
    }
  }

  function updateTextState() {
    if (!recipe()) return;
    const count = text => text.split(/[,\n]+/).filter(value => value.trim()).length;
    $("#creationPositiveCount").textContent = count(recipe().body);
    $("#creationNegativeCount").textContent = count(recipe().negative);
    $("#creationCharCount").textContent = promptValue().length + " " + translate("字元");
    $("#creationTransparent").setAttribute("aria-pressed", String(recipe().suffix.split(",").some(tag => tag.trim() === "transparent background")));
    ["#studioBody", "#studioNegative"].forEach(selector => renderHighlight($(selector)));
  }

  function selectTab(tab) {
    state.tab = tab;
    document.querySelectorAll("[data-canvas-tab]").forEach(button => {
      const active = button.dataset.canvasTab === tab;
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
      document.getElementById(button.getAttribute("aria-controls")).hidden = !active;
    });
    localStorage.setItem("soda-canvas-tab-" + state.engine, tab);
    updateTextState();
    renderBodyLock();
  }

  function setFields(fields) { window.SodaStudio.setFields(fields); }
  function setPrompt(value) {
    const field = state.tab === "negative" ? "negative" : state.tab === "fixed" ? "prefix" : "body";
    setFields({[field]: value});
    updateTextState();
  }

  function fitHeight() {
    if (layout.getBoundingClientRect().height && !$("#workbenchCreation").hidden) {
      layout.style.setProperty("--creation-height", Math.max(260, innerHeight - layout.getBoundingClientRect().top - 12) + "px");
    }
  }

  function modelName() {
    const value = recipe();
    const provider = current().bootstrap?.connections.providers.find(item => item.id === value?.provider_id);
    return value?.model || provider?.model || "";
  }

  function displayModelName(model) {
    if (model === "nai-diffusion-furry-3") return "NAI Diffusion Furry V3";
    return model.replace(/^nai-diffusion-4-5/, "NAI Diffusion V4.5").replace(/^nai-diffusion-([345])/, "NAI Diffusion V$1").replaceAll("-", " ").replace(/\bfull\b/, "Full").replace(/\bcurated\b/, "Curated");
  }

  function updatePresets() {
    const value = recipe();
    const preset = window.SodaNaiPresets;
    if (!value || !preset) return;
    const changes = {};
    if (value.nai_quality && value.nai_quality !== "none") {
      const quality = preset.quality(modelName(), value.nai_quality);
      if (quality !== value.nai_quality_text) {
        changes.suffix = preset.replace(value.suffix, value.nai_quality_text, quality, false);
        changes.nai_quality_text = quality;
      }
    }
    if (value.nai_uc && value.nai_uc !== "none") {
      const negative = preset.negative(modelName(), value.nai_uc);
      if (negative !== value.nai_uc_text) {
        changes.negative = preset.replace(value.negative, value.nai_uc_text, negative, true);
        changes.nai_uc_text = negative;
      }
    }
    if (Object.keys(changes).length) setFields(changes);
  }

  function syncSizePreset(value) {
    const size = `${value.width}x${value.height}`;
    const select = $("#creationSizePreset");
    select.value = [...select.options].some(option => option.value === size) ? size : "custom";
  }

  function renderRecipe() {
    const value = recipe();
    if (!value) return;
    const changed = state.engine !== value.backend;
    state.engine = value.backend;
    layout.dataset.engine = value.backend;
    document.querySelectorAll("[data-novelai-only]").forEach(element => { element.hidden = value.backend !== "novelai"; });
    document.querySelectorAll("[data-comfy-only]").forEach(element => { element.hidden = value.backend !== "comfyui"; });
    $("#creationModel").hidden = value.backend !== "novelai";
    $("#creationSampler").hidden = value.backend !== "novelai";
    $("#creationAdvanced").hidden = value.backend !== "novelai";
    $(".creation-prompt-presets").hidden = value.backend !== "novelai";
    $("#creationSeed").value = value.seed_mode === "random" ? "" : String(value.seed);
    $("#creationSeedLock").setAttribute("aria-pressed", String(value.seed_mode === "fixed"));
    $("#creationSeedLock").innerHTML = icon(value.seed_mode === "fixed" ? "lock" : "unlock");
    syncSizePreset(value);
    $("#creationImageMode").value = ["img2img", "infill", "outpaint"].includes(value.novelai_mode) ? value.novelai_mode : "img2img";
    if (value.model && ![...modelSelect.options].some(option => option.value === value.model)) {
      const option = document.createElement("option");
      option.value = value.model;
      option.textContent = value.model;
      modelSelect.append(option);
    }
    modelSelect.value = value.model;
    $("#creationQuality").value = value.nai_quality || "";
    $("#creationUc").value = value.nai_uc || "none";
    $("#creationModelLabel").textContent = value.backend === "comfyui" ? "ComfyUI" : displayModelName(modelName()) || translate("連線預設模型");
    if (changed) {
      arrangeEngine(value.backend === "comfyui");
      editor.querySelectorAll(".creation-reference-status").forEach(status => { status.hidden = true; });
      state.cleared = null;
      $("#creationUndoClear").hidden = true;
      const tab = localStorage.getItem("soda-canvas-tab-" + state.engine) || "positive";
      selectTab(["positive", "negative", "fixed"].includes(tab) ? tab : "positive");
      document.querySelectorAll(".creation-section, #creationParameters").forEach(details => {
        details.open = localStorage.getItem("soda-canvas-open-" + state.engine + "-" + details.id) === "true";
      });
      $("#creationScroll").scrollTop = Number(sessionStorage.getItem("soda-canvas-scroll-" + state.engine) || 0);
    }
    updateTextState();
    renderReferences();
    updatePresets();
    requestAnimationFrame(fitHeight);
  }

  function referenceKind(image) {
    const value = recipe();
    if (image.role === "mask" || ["img2img", "infill", "outpaint"].includes(value.novelai_mode)) return "img2img";
    return value.reference_modes[image.item_id]?.mode || (value.novelai_mode === "precise" ? "precise" : "vibe");
  }

  function renderReferences() {
    const value = recipe();
    if (!value) return;
    const images = current().images.filter(image => image.kind === "reference");
    const selectedReverse = $("#creationReverseImage").value;
    $("#creationReverseImage").innerHTML = '<option value="">選擇圖片</option>' + images.map(image => `<option value="${escape(image.item_id)}">${escape(image.title)}</option>`).join("");
    if (images.some(image => image.item_id === selectedReverse)) $("#creationReverseImage").value = selectedReverse;
    const models = current().bootstrap?.vision_models || [];
    const selectedModel = $("#creationReverseModel").value;
    $("#creationReverseModel").innerHTML = '<option value="">選擇視覺模型</option>' + models.map(model => `<option value="${escape(model.id || model.value)}">${escape(model.label || model.name || model.model)}</option>`).join("");
    if (selectedModel) $("#creationReverseModel").value = selectedModel;
    $("#creationReverseRun").disabled = !images.length || !models.length;
    for (const kind of ["img2img", "vibe", "precise"]) {
      const rows = images.filter(image => image.review !== "excluded" && referenceKind(image) === kind);
      $(`[data-reference-count="${kind}"]`).textContent = rows.length || "";
      $(`[data-reference-mount="${kind}"]`).innerHTML = rows.map(image => {
        const options = value.reference_modes[image.item_id] || {};
        return `<article class="creation-reference-card"><img src="${escape(image.thumbnail_url || image.image_url)}" alt="${escape(image.title)}"><div><span>${escape(image.title)}</span><button type="button" data-canvas-remove-reference="${escape(image.item_id)}" aria-label="移除參考圖">${icon("x")}</button></div>${kind === "img2img" ? "" : `<label>${kind === "precise" ? "保真度" : "強度"}<input type="range" min="0" max="1" step="0.05" value="${Number(options[kind === "precise" ? "fidelity" : "strength"] ?? .6)}" data-canvas-ref="${escape(image.item_id)}" data-canvas-ref-field="${kind === "precise" ? "fidelity" : "strength"}"></label>`}</article>`;
      }).join("");
    }
    updateReferenceInputs();
  }

  function updateReferenceInputs() {
    const unsupported = modelName().startsWith("nai-diffusion-5");
    for (const input of referenceInputs) {
      const kind = input.dataset.canvasReference;
      const note = $(`[data-reference-capability="${kind}"]`);
      if (note) {
        note.hidden = !unsupported;
        note.textContent = translate("目前模型不支援此參考方式，請在參數中選擇 V4.5。");
      }
      input.disabled = state.referenceImporting || Boolean(note && unsupported);
    }
  }

  async function api(path, options = {}) {
    const response = await fetch(path, options);
    const result = await response.json();
    if (!response.ok) throw Error(result.detail || translate("請求失敗"));
    return result;
  }

  function showError(error) {
    $("#studioStatus").textContent = error.message;
    $("#studioStatus").dataset.error = "true";
  }

  async function importReference(input, status) {
    const kind = input.dataset.canvasReference;
    const files = [...input.files];
    input.value = "";
    const project = current().project;
    if (!files.length || !project || state.referenceImporting) return;
    const projectId = project.project_id;
    const role = {vibe: "style", precise: "identity", img2img: "composition", reverse: "identity"}[kind];
    const mode = kind === "img2img" ? $("#creationImageMode").value : "mixed";
    const knownImages = new Set(current().images.map(image => image.item_id));
    const imported = {};
    let reverseImage = "";
    let uploadError;
    state.referenceImporting = true;
    status.hidden = false;
    status.dataset.error = "false";
    status.textContent = translate("正在加入圖片…");
    updateReferenceInputs();
    try {
      await window.SodaStudio.save();
      for (const file of files) {
        if (current().project !== project) return;
        try {
          const image = await api(`/api/studio/projects/${projectId}/images?kind=reference&role=${role}&filename=${encodeURIComponent(file.name)}`, {method: "POST", headers: {"Content-Type": file.type}, body: file});
          const changes = {};
          if (kind === "reverse") {
            if (!knownImages.has(image.item_id)) changes.review = "excluded";
          } else {
            if (image.review === "excluded") changes.review = "pending";
            if (image.role !== role) changes.role = role;
          }
          if (Object.keys(changes).length) {
            await api(`/api/studio/projects/${projectId}/images/${image.item_id}`, {
              method: "PUT",
              headers: {"Content-Type": "application/json"},
              body: JSON.stringify({...changes, expected_updated_at: image.updated_at}),
            });
          }
          if (kind === "reverse") reverseImage = image.item_id;
          else imported[image.item_id] = {mode: kind === "precise" ? "precise" : "vibe", strength: .6, information: 1, fidelity: .6};
        } catch (error) {
          uploadError = error;
          break;
        }
      }
      if (current().project !== project) return;
      if (Object.keys(imported).length) {
        setFields({reference_modes: {...recipe().reference_modes, ...imported}, novelai_mode: mode});
        await window.SodaStudio.refresh();
        await window.SodaStudio.save();
      }
      if (reverseImage) {
        await window.SodaStudio.refresh();
        if (current().project === project) $("#creationReverseImage").value = reverseImage;
      }
      if (uploadError) throw uploadError;
      status.textContent = translate("已加入圖片");
    } catch (error) {
      status.dataset.error = "true";
      status.textContent = translate("加入圖片失敗") + " · " + error.message;
    } finally {
      if (current().project !== project) status.hidden = true;
      state.referenceImporting = false;
      updateReferenceInputs();
    }
  }

  async function reversePrompt() {
    const button = $("#creationReverseRun");
    const model = $("#creationReverseModel").value;
    const item = $("#creationReverseImage").value;
    if (!model || !item) { $("#creationReverseStatus").textContent = translate("請選擇圖片與視覺模型"); return; }
    const projectId = current().project.project_id;
    const serial = ++state.reverseSerial;
    button.disabled = true;
    $("#creationReverseStatus").textContent = translate("正在反推提示詞…");
    try {
      const job = await api(`/api/studio/projects/${projectId}/caption`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({item_ids: [item], model, method: "vision"})});
      const poll = async () => {
        if (serial !== state.reverseSerial || current().project?.project_id !== projectId) return;
        try {
          const result = await api("/api/jobs/" + job.job_id);
          if (["queued", "running"].includes(result.status)) { setTimeout(poll, 1200); return; }
          if (result.status !== "completed") throw Error(result.error || translate("反推失敗"));
          const project = await api(`/api/studio/projects/${projectId}`);
          const caption = project.images.find(image => image.item_id === item)?.caption;
          $("#creationReverseResult").value = caption?.tags?.length ? caption.tags.join(", ") : caption?.long || "";
          $("#creationReverseResult").hidden = false;
          $("#creationReverseApply").hidden = false;
          $("#creationReverseStatus").textContent = translate("反推完成");
          button.disabled = false;
        } catch (error) { $("#creationReverseStatus").textContent = error.message; button.disabled = false; }
      };
      await poll();
    } catch (error) { $("#creationReverseStatus").textContent = error.message; button.disabled = false; }
  }

  document.querySelectorAll("[data-canvas-tab]").forEach(button => {
    button.addEventListener("click", () => selectTab(button.dataset.canvasTab));
    button.addEventListener("keydown", event => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const tabs = ["positive", "negative", "fixed"];
      const index = event.key === "Home" ? 0 : event.key === "End" ? 2 : (tabs.indexOf(state.tab) + (event.key === "ArrowLeft" ? 2 : 1)) % 3;
      selectTab(tabs[index]);
      $(`[data-canvas-tab="${tabs[index]}"]`).focus();
    });
  });
  $("#creationSizePreset").addEventListener("change", event => {
    if (event.target.value !== "custom") { const [width, height] = event.target.value.split("x").map(Number); setFields({width, height}); }
  });
  $("#creationSwapSize").addEventListener("click", () => setFields({width: recipe().height, height: recipe().width}));
  function updateSeed(event) {
    const value = event.target.value.trim();
    const number = Number(value);
    const random = !value || value === "-1" || /^(random|隨機|随机)$/i.test(value);
    const valid = /^\d+$/.test(value) && Number.isSafeInteger(number) && number < (state.engine === "novelai" ? 2 ** 32 : 2 ** 53);
    if (!random && !valid) {
      if (event.type === "change") { event.target.value = recipe().seed; showError(Error(translate("種子超出範圍"))); }
      return;
    }
    if (valid) {
      const seed = $('[data-recipe="seed"]');
      seed.value = number;
      seed.dispatchEvent(new Event("input", {bubbles: true}));
    }
    const mode = $('[data-recipe="seed_mode"]');
    mode.value = random ? "random" : "fixed";
    mode.dispatchEvent(new Event("input", {bubbles: true}));
    $("#creationSeedLock").setAttribute("aria-pressed", String(!random));
    $("#creationSeedLock").innerHTML = icon(random ? "unlock" : "lock");
  }
  $("#creationSeed").addEventListener("input", updateSeed);
  $("#creationSeed").addEventListener("change", updateSeed);
  $("#creationSeedLock").addEventListener("click", () => setFields({seed_mode: recipe().seed_mode === "fixed" ? "random" : "fixed"}));
  function setCanvasCollapsed(collapsed) {
    layout.classList.toggle("creation-collapsed", collapsed);
    const label = translate(collapsed ? "展開畫布面板" : "收起畫布面板");
    collapseButton.setAttribute("aria-expanded", String(!collapsed));
    collapseButton.setAttribute("aria-label", label);
    collapseButton.title = label;
    if (collapsed) parameters.open = false;
  }
  collapseButton.addEventListener("click", () => setCanvasCollapsed(!layout.classList.contains("creation-collapsed")));
  $("#creationHighlight").addEventListener("click", () => {
    state.highlighted = !state.highlighted;
    $("#creationHighlight").setAttribute("aria-pressed", String(state.highlighted));
    document.querySelectorAll(".creation-highlight-editor").forEach(element => { element.dataset.highlight = String(state.highlighted); });
  });
  $("#creationTransparent").addEventListener("click", () => {
    const tags = recipe().suffix.split(",").map(tag => tag.trim()).filter(Boolean);
    setFields({suffix: (tags.includes("transparent background") ? tags.filter(tag => tag !== "transparent background") : ["transparent background", ...tags]).join(", ")});
  });
  $("#creationClear").addEventListener("click", () => { state.cleared = {tab: state.tab, prefix: recipe().prefix, body: recipe().body, negative: recipe().negative, suffix: recipe().suffix}; if (state.tab === "fixed") setFields({prefix: "", suffix: ""}); else setPrompt(""); $("#creationUndoClear").hidden = false; });
  $("#creationUndoClear").addEventListener("click", () => { if (!state.cleared) return; const {tab, ...fields} = state.cleared; setFields(fields); selectTab(tab); state.cleared = null; $("#creationUndoClear").hidden = true; });
  $("#creationRandomSettings").addEventListener("click", () => { const section = $("#creationRandom"); section.open = !section.open; $("#creationRandomSettings").setAttribute("aria-expanded", String(section.open)); });
  $("#studioWildcardV2Edit").addEventListener("click", () => {
    $("#creationRandom").open = true;
    $("#creationRandomSettings").setAttribute("aria-expanded", "true");
    $("#studioWildcardV2").scrollIntoView({block:"nearest"});
    $("#studioWildcardV2 [data-v2-setting='enabled']").focus({preventScroll:true});
  });
  $("#creationMaterial").addEventListener("click", () => $("#studioChooseMaterial").click());
  $("#creationQuality").addEventListener("change", event => {
    const value = event.target.value;
    const text = value === "none" ? "" : window.SodaNaiPresets.quality(modelName(), value);
    setFields({nai_quality: value, nai_quality_text: text, suffix: window.SodaNaiPresets.replace(recipe().suffix, recipe().nai_quality_text, text, false)});
  });
  $("#creationUc").addEventListener("change", event => {
    const value = event.target.value;
    const text = value === "none" ? "" : window.SodaNaiPresets.negative(modelName(), value);
    setFields({nai_uc: value, nai_uc_text: text, negative: window.SodaNaiPresets.replace(recipe().negative, recipe().nai_uc_text, text, true)});
  });
  $("#creationImageMode").addEventListener("change", event => setFields({novelai_mode: event.target.value}));
  const parameterBackdrop = document.createElement("div");
  parameterBackdrop.className = "creation-parameter-backdrop";
  parameterBackdrop.setAttribute("aria-hidden", "true");
  parameterBackdrop.hidden = true;
  editor.append(parameterBackdrop);
  parameterShortcut.addEventListener("click", () => {
    setCanvasCollapsed(false);
    parameters.open = !parameters.open;
    if (parameters.open) parameters.querySelector("summary").focus({preventScroll: true});
  });
  parameterBackdrop.addEventListener("click", () => { parameters.open = false; });
  parameters.addEventListener("toggle", () => {
    parameterBackdrop.hidden = !parameters.open;
    parameterShortcut.setAttribute("aria-expanded", String(parameters.open));
  });
  $("#studioPage").addEventListener("keydown", event => {
    if (event.key === "Escape" && parameters.open) {
      event.preventDefault();
      event.stopPropagation();
      parameters.open = false;
      if (parameters.contains(document.activeElement)) parameters.querySelector("summary").focus({preventScroll: true});
    }
  });
  for (const input of referenceInputs) {
    const status = document.createElement("p");
    status.id = "creationReferenceStatus-" + input.dataset.canvasReference;
    status.className = "creation-reference-status";
    status.setAttribute("role", "status");
    status.hidden = true;
    input.setAttribute("aria-describedby", status.id);
    input.closest("label").after(status);
    input.addEventListener("change", () => importReference(input, status));
  }
  editor.addEventListener("change", event => {
    const input = event.target;
    if (!input.dataset.canvasRef) return;
    const referenceModes = structuredClone(recipe().reference_modes);
    referenceModes[input.dataset.canvasRef] = {...referenceModes[input.dataset.canvasRef], [input.dataset.canvasRefField]: Number(input.value)};
    setFields({reference_modes: referenceModes});
  });
  editor.addEventListener("click", async event => {
    const button = event.target.closest("[data-canvas-remove-reference]");
    if (!button) return;
    button.disabled = true;
    try {
      await api(`/api/studio/projects/${current().project.project_id}/images/${button.dataset.canvasRemoveReference}`, {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({review: "excluded"})});
      button.closest(".creation-section").querySelector(".creation-reference-status").hidden = true;
      await window.SodaStudio.refresh();
    }
    catch (error) { showError(error); button.disabled = false; }
  });
  $("#creationReverseRun").addEventListener("click", reversePrompt);
  $("#creationReverseApply").addEventListener("click", () => { setFields({body: $("#creationReverseResult").value}); selectTab("positive"); });
  document.querySelectorAll(".creation-section, #creationParameters").forEach(details => details.addEventListener("toggle", () => { if (state.engine) localStorage.setItem("soda-canvas-open-" + state.engine + "-" + details.id, String(details.open)); }));
  $("#creationScroll").addEventListener("scroll", () => { if (state.engine) sessionStorage.setItem("soda-canvas-scroll-" + state.engine, $("#creationScroll").scrollTop); });
  $("#studioPage").addEventListener("input", event => queueMicrotask(() => {
    if (["width", "height"].includes(event.target.dataset.recipe) && recipe()) syncSizePreset(recipe());
    updateTextState();
  }));
  $("#studioPage").addEventListener("change", event => { if (event.target.matches("#naiModel,#studioProvider")) { updatePresets(); renderRecipe(); } });
  window.addEventListener("soda-studio-populated", renderRecipe);
  window.addEventListener("soda-studio-populated", () => {
    const project = current().project;
    if (!project) return;
    ["studioBody", "studioNegative"].forEach(id => window.SodaPromptEditor.attach($("#" + id), project.project_id + "-" + id));
  });
  window.addEventListener("soda-studio-images", renderReferences);
  window.addEventListener("resize", fitHeight);
  compactComfy.addEventListener("change", () => { if (recipe()?.backend === "comfyui") arrangeEngine(true); requestAnimationFrame(fitHeight); });
  new ResizeObserver(fitHeight).observe($(".app-nav"));
  new MutationObserver(() => { $("#creationSaveState").textContent = $("#studioSaveState").textContent || translate("自動保存"); }).observe($("#studioSaveState"), {childList: true, characterData: true, subtree: true});
})();
