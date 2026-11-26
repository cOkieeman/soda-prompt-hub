(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character =>
    ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[character]);
  const targets = {moss:"MOSS", anima:"Anima", krea2:"Krea 2", h3:"MiniMax H3 Image"};
  const stepLabels = {references:"參考素材", generate:"生圖", review:"挑圖", caption:"打標", export:"匯出"};
  const roles = {identity:"角色外觀", outfit:"服裝", style:"畫風", pose:"姿勢", depth:"深度", composition:"構圖", mask:"遮罩"};
  const wildcardV2Active = recipe => recipe?.backend === "comfyui" && recipe.text_mode === "wildcard" && Boolean(recipe.wildcard_v2?.enabled);
  const v2SamplingFields = new Set(["width", "height", "steps", "cfg", "negative"]);
  const v2NoneMode = ["none", "省略"];
  const v2RandomModes = [["random", "隨機"], ["fixed", "固定"], v2NoneMode];
  const v2Slots = [
    ["layout", "構圖版式", v2RandomModes],
    ["style", "畫風", [["preset", "預設"], ["fixed", "固定"], ["wildcard", "詞庫", "從詞庫隨機抽取"], v2NoneMode]],
    ["character", "角色", v2RandomModes],
    ["outfit", "服裝", v2RandomModes],
    ["action", "動作", v2RandomModes],
    ["scene_light", "場景與光影", v2RandomModes],
    ["lighting", "光線", v2RandomModes],
  ];
  const v2TestLightingSlot = [["test_lighting", "光線", [v2NoneMode, ...v2RandomModes.slice(0, 2)]]];
  const v2BundledSlots = new Set(["style", "character", "lighting"]);
  const v2PairedPoolLists = {layout:"studioWildcardV2LayoutPools", scene_light:"studioWildcardV2SceneLightPools"};
  const v2TestLightActive = settings => settings.layout === "independent" && ["random", "fixed"].includes(settings.test_lighting_mode);
  const v2TagGroups = [["style", "畫風"], ["line", "線條"], ["clothing", "服裝"]];
  const state = {bootstrap:null, project:null, images:[], jobs:[], generationJobIds:[], preview:null, lastDraw:null, selectedImage:"", captionSelection:new Set(),
    v2Editor:"", v2CharacterEditing:false, v2PoolsRequest:null, v2PoolData:null,
    step:"generate", saving:null, dirty:false, saveTimer:null, uploadBusy:false,
    providerFormRun:0, providerDiscoveryRun:0, providerDiscoveryController:null, deletingProviderId:"", graphSelection:"", graphZoom:100,
    graphFilter:"all", graphMinConfidence:0, graphKinds:{entity:true,group:true,relation:true,image:true}, graphDrawMode:false, graphCaptionMode:"detail",
    graphIncludeUnscored:true, graphObjectSearch:""};
  const draftKey = id => "soda-studio-draft-" + id;
  const previewKey = id => "soda-studio-preview-" + id;
  const captionKey = id => "soda-studio-caption-" + state.project.project_id + "-" + id;

  async function api(path, options = {}) {
    const headers = {...options.headers};
    if (options.body && !(options.body instanceof File) && typeof options.body !== "string") {
      options.body = JSON.stringify(options.body);
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch("/api/studio" + path, {...options, headers});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : `請求失敗 ${response.status}`);
    return data;
  }

  function notice(message, error = false, selector = "#studioStatus") {
    const element = $(selector);
    element.textContent = message;
    element.dataset.error = String(error);
  }

  async function action(button, callback) {
    if (button.disabled) return;
    button.disabled = true;
    try { await callback(); }
    catch (error) { notice(error.message, true, button.closest("#studioSettingsPage") ? "#studioSettingsStatus" : button.closest("#studioProjectsPage") ? "#studioHomeStatus" : "#studioStatus"); }
    finally { button.disabled = false; }
  }

  function persistDraft() {
    if (!state.project) return;
    try {
      localStorage.setItem(draftKey(state.project.project_id), JSON.stringify({
        revision: state.project.revision, studio: state.project.studio, step: state.step,
      }));
    } catch { notice("瀏覽器草稿空間已滿，請使用保存狀態確認資料已寫入本機。", true); }
  }

  function markChanged() {
    state.preview = null;
    if (state.project) localStorage.removeItem(previewKey(state.project.project_id));
    renderPreview();
    state.dirty = true;
    persistDraft();
    $("#studioSaveState").textContent = "正在保存";
    clearTimeout(state.saveTimer);
    state.saveTimer = setTimeout(() => saveCurrent().catch(error => {
      $("#studioSaveState").textContent = "保存失敗，本機草稿已保留";
      notice(error.message, true);
    }), 450);
  }

  async function saveCurrent() {
    clearTimeout(state.saveTimer);
    if (state.saving) {
      await state.saving;
      if (state.dirty) return saveCurrent();
      return;
    }
    if (!state.project || !state.dirty) return;
    const project = state.project;
    const snapshot = structuredClone(project.studio);
    const serialized = JSON.stringify(snapshot);
    state.dirty = false;
    state.saving = api(`/projects/${encodeURIComponent(project.project_id)}`, {
      method:"PUT", body:{expected_revision:project.revision, studio:snapshot, step:state.step},
    }).then(saved => {
      project.revision = saved.revision;
      if (JSON.stringify(project.studio) === serialized) localStorage.removeItem(draftKey(project.project_id));
      else persistDraft();
      if (state.project === project) $("#studioSaveState").textContent = "已保存";
    }).catch(error => {
      state.dirty = true;
      throw error;
    }).finally(() => { state.saving = null; });
    await state.saving;
    if (state.dirty) return saveCurrent();
  }

  async function bootstrap() {
    state.bootstrap = await api("/bootstrap");
    return state.bootstrap;
  }

  function openProject(projectId, step) {
    return window.setPromptHubView("studio", {
      route:{view:"studio", project:projectId, step:step || "generate"},
    });
  }

  function renderHome() {
    const projects = state.bootstrap.projects;
    $("#studioProjectList").innerHTML = projects.length ? projects.map(project => `
      <article class="studio-project-row">
        <div><h2>${escape(project.title)}</h2><p>${escape(targets[project.target_profile] || project.target_profile)} · ${project.image_count} 張圖片 · ${project.approved_count} 張已採用</p></div>
        <span>${escape(stepLabels[project.last_step] || "生圖")}</span>
        <time datetime="${escape(project.updated_at)}">${escape(new Date(project.updated_at).toLocaleDateString(window.promptHubI18n?.getLocale() || "zh-CN"))}</time>
        <button type="button" data-studio-project="${escape(project.project_id)}" data-project-step="${escape(project.last_step)}">繼續處理</button>
      </article>`).join("") : '<p class="studio-empty">建立第一個資料集，可以從已有圖片或參考素材開始。</p>';
  }

  window.ensureStudioHome = async () => {
    await bootstrap();
    renderHome();
  };

  function mountWildcardV2Slots(container, slots = v2Slots) {
    container.innerHTML = slots.map(([key, label, modes]) => {
      const nameId = `studioV2-${key}-label`;
      const editorId = `studioV2-${key}-editor`;
      const textKey = key === "layout" ? "layout_text" : key;
      const poolList = v2PairedPoolLists[key] || "studioWildcardV2Pools";
      const theme = key === "lighting" ?
        '<div class="studio-wildcard-v2-theme" data-v2-theme><span>主題包 · 服裝、動作、場景</span><span>整組隨機</span></div>' : "";
      return `${theme}<div class="studio-wildcard-v2-slot" data-v2-category="${key}">
        <span class="studio-wildcard-v2-name" id="${nameId}">${label}</span>
        <div class="studio-wildcard-v2-entry">
          <input type="text" data-v2-setting="${textKey}" data-v2-short maxlength="4000" spellcheck="false" autocomplete="off" aria-labelledby="${nameId}" hidden>
          <span data-v2-summary hidden></span>
          <input type="text" data-v2-setting="${key}_pool" data-v2-pool list="${poolList}" maxlength="4000" spellcheck="false" autocomplete="off" aria-labelledby="${nameId}" hidden>
          <span data-v2-workflow hidden>沿用工作流</span>
          <button type="button" data-v2-expand="${key}" aria-controls="${editorId}" aria-expanded="false" hidden>展開</button>
        </div>
        <div class="studio-wildcard-v2-modes" role="group" aria-labelledby="${nameId}">
          ${modes.map(([value, text, tip]) => `<button type="button" data-v2-mode="${value}" aria-label="${tip || text}" aria-pressed="false">${text}</button>`).join("")}
        </div>
        <div id="${editorId}" class="studio-wildcard-v2-editor" hidden>
          <textarea rows="5" data-v2-setting="${textKey}" data-v2-long maxlength="4000" spellcheck="false" aria-labelledby="${nameId}"></textarea>
          <span data-v2-length aria-hidden="true"></span>
        </div>
      </div>`;
    }).join("");
  }

  function renderWildcardV2Slot(slot, settings, defaults) {
    const key = slot.dataset.v2Category;
    const mode = settings[`${key}_mode`] ?? (key === "style" ? "none" : slot.querySelector("[data-v2-mode]").dataset.v2Mode);
    const editingCharacter = key === "character" && state.v2CharacterEditing;
    const fixed = mode === "fixed" || editingCharacter;
    const text = settings[key === "layout" ? "layout_text" : key] || "";
    const expanded = fixed && state.v2Editor === key;
    const short = slot.querySelector("[data-v2-short]");
    const editor = slot.querySelector("[data-v2-long]");
    const summary = slot.querySelector("[data-v2-summary]");
    const expand = slot.querySelector("[data-v2-expand]");
    const pool = slot.querySelector("[data-v2-pool]");
    const long = /[\r\n]/.test(text) || text.length > 50;
    const showSummary = expanded || (long && document.activeElement !== short);

    slot.querySelectorAll("[data-v2-mode]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.v2Mode === mode));
    });
    short.hidden = !fixed || showSummary;
    short.placeholder = translated(key === "character" ? "輸入角色名或 OC 觸發詞" : "輸入固定詞");
    if (!showSummary && short.value !== text) short.value = text;
    summary.hidden = !fixed || !showSummary;
    summary.textContent = expanded ? translated("編輯中") : text;
    pool.hidden = fixed || !["random", "wildcard"].includes(mode);
    const defaultPools = defaults[key] || [];
    pool.placeholder = defaultPools.length === 1 ? defaultPools[0].split("/").at(-1).replace(/__$/, "") :
      translated(key === "style" ? "選擇詞池" : "預設詞池");
    const poolText = settings[`${key}_pool`] ?? (key === "style" && mode === "wildcard" ? settings.style : "") ?? "";
    if (pool.value !== poolText) pool.value = poolText;
    pool.title = poolText || defaultPools.join("\n");
    const omitted = slot.querySelector("[data-v2-workflow]");
    omitted.hidden = mode !== "none" && mode !== "preset";
    omitted.textContent = mode === "preset" ? selectedWorkflow()?.label || translated("沿用工作流") : translated("留空");
    omitted.title = omitted.textContent;
    expand.hidden = !fixed || (!long && !expanded);
    expand.textContent = translated(expanded ? "收起" : "展開");
    expand.setAttribute("aria-expanded", String(expanded));
    editor.parentElement.hidden = !expanded;
    if (editor.value !== text) editor.value = text;
    slot.querySelector("[data-v2-length]").textContent = `${text.length} ${translated("字元")}`;
  }

  function renderWildcardV2PairOptions(familyDefaults) {
    for (const [slot, listId] of Object.entries(v2PairedPoolLists)) {
      const pools = [...new Set(["design", "world"].flatMap(preset => familyDefaults[preset]?.[slot] || []))];
      replaceWildcardV2PoolOptions($("#" + listId), pools);
    }
  }

  function renderWildcardV2(recipe) {
    const panel = $("#studioWildcardV2");
    if (!panel) return;
    const settings = recipe.wildcard_v2 || {};
    const active = wildcardV2Active(recipe);
    panel.hidden = recipe.backend !== "comfyui" || recipe.text_mode !== "wildcard";
    $("#studioPage").dataset.v2Active = String(active);
    $("#studioWildcardV2Fields").hidden = !active;
    $("#studioWildcardV2Edit").hidden = !active;
    const queueLabel = $("#studioQueueBatch").querySelector("span");
    if (queueLabel) queueLabel.textContent = translated(active ? "隨機出圖" : "生成");
    panel.querySelector('[data-v2-setting="enabled"]').checked = Boolean(settings.enabled);
    panel.querySelector('[data-v2-setting="family"]').value = settings.family || "anima";
    const slots = $("#studioWildcardV2Slots");
    if (!slots.childElementCount) mountWildcardV2Slots(slots);
    const bundled = settings.layout !== "independent";
    const preset = bundled ? "bundled" : settings.scene_preset || "design";
    const familyDefaults = state.bootstrap.wildcard_v2_default_pools?.[settings.family || "anima"] || {};
    const defaults = familyDefaults[preset] || {};
    if (!bundled) renderWildcardV2PairOptions(familyDefaults);
    panel.querySelectorAll("[data-v2-preset]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.v2Preset === preset));
    });
    panel.querySelector("[data-v2-theme]").hidden = !bundled;
    slots.querySelectorAll("[data-v2-category]").forEach(slot => {
      const key = slot.dataset.v2Category;
      slot.hidden = bundled ? !v2BundledSlots.has(key) : key === "lighting";
      renderWildcardV2Slot(slot, settings, defaults);
      if (key === "scene_light") {
        const paused = v2TestLightActive(settings);
        slot.setAttribute("aria-disabled", String(paused));
        slot.querySelectorAll("input, textarea, button").forEach(control => { control.disabled = paused; });
      }
    });
    $("#studioWildcardV2TestLight").hidden = bundled;
    const testLight = $("#studioWildcardV2TestLightSlot");
    if (!testLight.childElementCount) mountWildcardV2Slots(testLight, v2TestLightingSlot);
    renderWildcardV2Slot(testLight.firstElementChild, settings, defaults);
    renderWildcardV2TagFilters(settings, preset, defaults);
  }

  function applyWildcardV2SamplingPreset(recipe) {
    const family = recipe.wildcard_v2.family || "anima";
    const preset = state.bootstrap.wildcard_v2_sampling_presets?.[family];
    if (!preset) return false;
    Object.assign(recipe, preset, {wildcard_v2_sampling_family:family});
    delete recipe.locked_values?.negative;
    return true;
  }

  function hasSpecificWildcardV2Character(text) {
    const genericTags = state.bootstrap.wildcard_v2_generic_character_tags || [];
    return (text || "").toLowerCase().split(/[,，.。\r\n]+/).some(part => {
      const tag = part.replace(/_/g, " ").replace(/\s+/g, " ").trim();
      return tag && !genericTags.includes(tag);
    });
  }

  function setWildcardV2Preset(preset) {
    const recipe = state.project.studio;
    const settings = recipe.wildcard_v2;
    if (preset === "bundled") {
      setWildcardV2Value("layout", "bundled");
      return;
    }
    recipe.wildcard_v2 = {...settings, layout:"independent", scene_preset:preset,
      layout_mode:"random", layout_pool:"", scene_light_mode:"random", scene_light_pool:""};
    state.lastDraw = null;
    state.v2Editor = "";
    renderWildcardV2(recipe);
    markChanged();
  }

  function wildcardV2TagChoices(settings, preset, tagsByPool, defaults) {
    const pools = [...(defaults.theme || [])];
    for (const slot of [...v2Slots, ...v2TestLightingSlot]) {
      const [key] = slot;
      if (preset === "bundled" ? !v2BundledSlots.has(key) : key === "lighting") continue;
      if (key === "scene_light" && v2TestLightActive(settings)) continue;
      const mode = settings[`${key}_mode`] ?? slot[2][0][0];
      if (mode !== "random" && mode !== "wildcard") continue;
      const pool = (settings[`${key}_pool`] || "").trim();
      pools.push(...(pool ? [pool] : defaults[key] || []));
    }
    return Object.fromEntries(v2TagGroups.map(([key]) => {
      const tags = new Set(settings.tag_filters?.[key] || []);
      for (const pool of pools) {
        for (const tag of tagsByPool[pool]?.[key] || []) tags.add(tag);
      }
      return [key, [...tags].sort()];
    }));
  }

  function renderWildcardV2TagFilters(settings, preset, defaults) {
    const container = $("#studioWildcardV2TagFilters");
    container.hidden = !state.v2PoolData;
    if (container.hidden) return;
    const groups = wildcardV2TagChoices(settings, preset, state.v2PoolData.tags_by_pool || {}, defaults);
    const catalogue = JSON.stringify(groups);
    if (container.dataset.v2Catalogue !== catalogue) {
      container.dataset.v2Catalogue = catalogue;
      const controls = v2TagGroups.filter(([key]) => groups[key].length).map(([key, label]) =>
        `<div class="studio-wildcard-v2-tag-group" role="group" aria-label="${escape(translated(label))}">
          <span>${escape(translated(label))}</span>
          ${groups[key].map(tag => `<button type="button" data-v2-tag-group="${key}" data-v2-tag="${escape(tag)}" aria-pressed="false">${escape(tag)}</button>`).join("")}
        </div>`).join("");
      container.innerHTML = `<h4>${escape(translated("詞庫標籤"))}</h4>${controls || `<p>${escape(translated("目前詞池沒有可用標籤。"))}</p>`}`;
    }
    container.querySelectorAll("[data-v2-tag]").forEach(button => {
      const selected = settings.tag_filters?.[button.dataset.v2TagGroup] || [];
      button.setAttribute("aria-pressed", String(selected.includes(button.dataset.v2Tag)));
    });
  }

  function setWildcardV2Value(key, value) {
    const recipe = state.project.studio;
    const settings = recipe.wildcard_v2 || {};
    const next = {...settings, [key]:value};
    if (key === "character_mode") state.v2CharacterEditing = value === "fixed";
    if (key === "character" || (key === "character_mode" && state.v2CharacterEditing)) {
      state.v2CharacterEditing = true;
      next.character_mode = hasSpecificWildcardV2Character(next.character) ? "fixed" : "random";
    }
    if (next[key] === settings[key] && next.character_mode === settings.character_mode) {
      if (key === "character_mode") renderWildcardV2(recipe);
      return;
    }
    recipe.wildcard_v2 = next;
    if (["enabled", "family", "layout"].includes(key)) {
      state.lastDraw = null;
      state.v2Editor = "";
    }
    if (key === "enabled" && !value) state.v2CharacterEditing = false;
    if (["enabled", "family"].includes(key) && wildcardV2Active(recipe) && applyWildcardV2SamplingPreset(recipe)) {
      populateRecipe();
    } else renderWildcardV2(recipe);
    markChanged();
  }

  function replaceWildcardV2PoolOptions(list, pools) {
    if (list.options.length === pools.length && pools.every((value, index) => list.options[index].value === value)) return;
    list.replaceChildren(...pools.map(value => {
      const option = document.createElement("option");
      option.value = value;
      return option;
    }));
  }

  async function loadWildcardV2Pools() {
    if (state.v2PoolsRequest) return state.v2PoolsRequest;
    const status = $("#studioWildcardV2PoolStatus");
    status.hidden = true;
    state.v2PoolsRequest = api("/wildcard-v2/pools").then(data => {
      const {scene_pools} = data;
      replaceWildcardV2PoolOptions($("#studioWildcardV2Pools"), scene_pools);
      state.v2PoolData = data;
      if (state.project && wildcardV2Active(state.project.studio)) renderWildcardV2(state.project.studio);
    }).catch(() => {
      state.v2PoolsRequest = null;
      status.textContent = translated("詞池清單暫時無法載入，可直接輸入已知的 Wildcard 引用。");
      status.hidden = false;
    });
    return state.v2PoolsRequest;
  }

  function populateRecipe() {
    const recipe = state.project.studio;
    document.querySelectorAll("#studioPage [data-recipe]").forEach(element => {
      element.value = recipe[element.dataset.recipe] ?? "";
    });
    document.querySelectorAll("#studioPage [data-lock]").forEach(element => {
      element.checked = Boolean(recipe.locks[element.dataset.lock]);
    });
    document.querySelectorAll("#studioPage [data-raffle]").forEach(element => {
      const value = recipe.raffle[element.dataset.raffle];
      if (element.type === "checkbox") element.checked = Boolean(value);
      else element.value = value || "";
    });
    $("#studioWorkflow").innerHTML = '<option value="">請匯入工作流</option>' +
      state.bootstrap.workflows.map(workflow =>
        `<option value="${escape(workflow.profile_id)}">${escape(workflow.label)}</option>`).join("");
    $("#studioWorkflow").value = recipe.workflow_id;
    populateProviders();
    renderWordlists();
    renderWorkflow();
    renderPrefixRows();
    $("#studioRaffleSettings").hidden = recipe.text_mode !== "raffle";
    renderWildcardV2(recipe);
    if (wildcardV2Active(recipe)) void loadWildcardV2Pools();
    window.dispatchEvent(new Event("soda-studio-populated"));
  }

  function populateProviders() {
    const recipe = state.project.studio;
    const isComfy = recipe.backend === "comfyui";
    $("#studioWorkflowField").hidden = !isComfy;
    $("#studioComfyUrlField").hidden = !isComfy && recipe.text_mode !== "raffle";
    $("#studioImportWorkflow").hidden = !isComfy;
    $("#studioWorkflowControls").hidden = !isComfy;
    ["#studioReferenceBindings","#studioPostprocess"].forEach(selector => {
      $(selector).closest("details").hidden = !isComfy;
    });
    ["steps","cfg"].forEach(name => {
      document.querySelector(`[data-recipe="${name}"]`).closest("label").hidden = recipe.backend === "openai";
    });
    $("#studioProviderField").hidden = isComfy;
    const providers = state.bootstrap.connections.providers.filter(provider => provider.kind === recipe.backend);
    $("#studioProvider").innerHTML = '<option value="">請選擇圖片連線</option>' +
      providers.map(provider => `<option value="${escape(provider.id)}">${escape(provider.label)} · ${escape(provider.model)}</option>`).join("");
    $("#studioProvider").value = recipe.provider_id;
    $("#studioNovelaiSettings").hidden = recipe.backend !== "novelai";
    $("#studioSeedNote").textContent = recipe.backend === "openai" ? "GPT 圖片 API 依服務能力生成，出圖種子不會送出。" : "";
    document.querySelectorAll('[data-recipe="seed"],[data-recipe="seed_mode"]').forEach(element => { element.disabled = recipe.backend === "openai"; });
    $("#studioCharacters").value = JSON.stringify(recipe.characters, null, 2);
  }

  function renderWordlists() {
    const options = state.bootstrap.wordlists.map(item =>
      `<option value="${escape(item.name)}">${escape(item.name)} · ${item.count} 條</option>`).join("");
    $("#studioWordlistInsert").innerHTML = '<option value="">選擇詞庫</option>' + options;
    $("#studioWordlistSelect").innerHTML = '<option value="">建立新詞庫</option>' + options;
  }

  function selectedWorkflow() {
    return state.bootstrap.workflows.find(item => item.profile_id === state.project.studio.workflow_id);
  }

  function bindStudioWorkflow(recipe, workflow) {
    recipe.workflow_id = workflow.profile_id;
    recipe.bindings = structuredClone(workflow.bindings);
    recipe.overrides = {};
    recipe.branches = {};
    const v2 = wildcardV2Active(recipe);
    for (const [name, value] of Object.entries(workflow.source_values || {})) {
      if (v2 && v2SamplingFields.has(name)) continue;
      if (recipe[name] === "" || (name !== "negative" && v2SamplingFields.has(name))) recipe[name] = value;
    }
  }

  function translated(message) {
    return window.t?.(message) || message;
  }

  function workflowControlLabel(field) {
    const control = field.control || {};
    const storedLabel = String(control.label || "").trim();
    if (storedLabel && !/^value[_\s-]?\d+$/i.test(storedLabel)) return storedLabel;

    const targets = control.targets || [];
    const branch = targets.find(target => target.class_type === "ComfySwitchNode" &&
      ["on_true", "on_false"].includes(target.input));
    if (branch) {
      const metric = /cfg/i.test(branch.title) ? translated("CFG") :
        /steps|步數|步数/i.test(branch.title) ? translated("步數") : translated("工作流參數");
      const mode = branch.mode === "turbo" ?
        (branch.input === "on_true" ? translated("Turbo") : translated("標準")) :
        (branch.input === "on_true" ? translated("模式開啟") : translated("模式關閉"));
      return `${mode} · ${metric}`;
    }

    if (control.kind === "toggle") {
      return targets.some(target => /turbo/i.test(target.title)) ?
        translated("Turbo 模式") : translated("工作流模式");
    }
    if (control.kind === "combo") {
      if (targets.some(target => target.input === "sampler_name")) return translated("採樣器");
      if (targets.some(target => target.input === "scheduler")) return translated("調度器");
    }
    return storedLabel || `${translated("工作流控制項")} ${String(field.input).replace("value_", "")}`;
  }

  function workflowFieldLabel(field) {
    return field.control ? workflowControlLabel(field) : `${field.title} / ${field.input}`;
  }

  function renderWorkflowControl(field, recipe) {
    const control = field.control || {};
    const label = workflowControlLabel(field);
    const safeLabel = escape(label);
    const key = escape(field.key);
    const value = Object.hasOwn(recipe.overrides, field.key) ? recipe.overrides[field.key] : field.value;

    if (control.kind === "toggle" || field.type === "boolean") {
      const enabled = typeof value === "boolean" ? value : Number(value) !== 0;
      const turbo = /turbo/i.test(label);
      const onLabel = control.on_label || translated(turbo ? "Turbo" : "開啟");
      const offLabel = control.off_label || translated(turbo ? "標準" : "關閉");
      return `<div class="studio-workflow-param" data-workflow-control><span class="studio-workflow-param-label" data-i18n-ignore>${safeLabel}</span><div class="studio-workflow-choice" role="group" aria-label="${safeLabel}"><button type="button" data-override-choice="${key}" data-value="false" aria-pressed="${!enabled}">${escape(offLabel)}</button><button type="button" data-override-choice="${key}" data-value="true" aria-pressed="${enabled}">${escape(onLabel)}</button></div></div>`;
    }

    if (control.kind === "combo" && Array.isArray(control.options) && control.options.length) {
      const options = [...control.options];
      if (typeof value === "string" && !options.includes(value)) options.unshift(value);
      return `<label class="studio-workflow-param" data-workflow-control><span class="studio-workflow-param-label" data-i18n-ignore>${safeLabel}</span><select data-override="${key}">${options.map(option => `<option value="${escape(option)}"${option === value ? " selected" : ""}>${escape(option)}</option>`).join("")}</select></label>`;
    }

    const minimum = Number(control.min);
    const maximum = Number(control.max);
    const increment = Number(control.step);
    const hasRange = ["int", "float"].includes(control.kind) &&
      Number.isFinite(minimum) && Number.isFinite(maximum) && maximum > minimum &&
      Number.isFinite(increment) && increment > 0;
    if (hasRange) {
      const numericValue = Number(value);
      const safeValue = Number.isFinite(numericValue) ? numericValue : minimum;
      const numberStep = control.kind === "int" ? "1" : String(increment);
      return `<div class="studio-workflow-param" data-workflow-control><span class="studio-workflow-param-label" data-i18n-ignore>${safeLabel}</span><div class="studio-workflow-range"><input type="range" data-override="${key}" min="${minimum}" max="${maximum}" step="${increment}" value="${safeValue}" aria-label="${safeLabel}"><input type="number" data-override="${key}" min="${minimum}" max="${maximum}" step="${numberStep}" value="${safeValue}" aria-label="${escape(translated("數值"))} ${safeLabel}"></div></div>`;
    }

    const inputType = field.type === "number" ? "number" : "text";
    const step = inputType === "number" ? ' step="any"' : "";
    return `<label class="studio-workflow-param" data-workflow-control><span class="studio-workflow-param-label" data-i18n-ignore>${safeLabel}</span><input data-override="${key}" type="${inputType}"${step} value="${escape(value)}"></label>`;
  }

  function renderWorkflow() {
    const recipe = state.project.studio;
    const workflow = selectedWorkflow();
    const fields = workflow?.fields || [];
    const internalStateNames = new Set(["SeedState", "SizesState", "SlidersState"]);
    const bindingValues = Object.values(recipe.bindings || {}).flatMap(value =>
      Array.isArray(value) ? value : value ? [value] : []);
    const boundKeys = new Set(bindingValues);
    if (wildcardV2Active(recipe)) {
      const samplingKeys = new Set([...v2SamplingFields].flatMap(name =>
        recipe.bindings?.[name] ?? workflow?.bindings?.[name] ?? []));
      for (const field of fields) {
        if (!samplingKeys.has(field.key)) continue;
        boundKeys.add(field.key);
        if (field.source_key) boundKeys.add(field.source_key);
      }
    }
    const connectedControls = fields.filter(field => field.control?.connected && !boundKeys.has(field.key));
    const primaryControls = connectedControls.filter(field =>
      field.control.kind === "toggle");
    const secondaryControls = connectedControls.filter(field =>
      field.control.kind !== "toggle");
    const unconnectedControls = fields.filter(field => field.control && !field.control.connected);
    const imageFields = fields.filter(field => field.type === "text" && /image|file|path/i.test(field.input));
    const fieldOptions = '<option value="">使用原工作流設定</option>' + imageFields.map(field =>
      `<option value="${escape(field.key)}">${escape(workflowFieldLabel(field))}</option>`).join("");
    const names = {prefix:"主題與風格", body:"正文", positive:"完整正向", negative:"負面詞", suffix:"後綴與簽名", seed:"出圖種子", text_seed:"抽詞種子", width:"寬", height:"高", steps:"步數", cfg:"CFG"};
    $("#studioWorkflowControls").hidden = !workflow;
    const parameterButton = $("#studioWorkflowParametersToggle");
    const parameterPanel = $("#studioWorkflowParameters");
    parameterButton.hidden = !connectedControls.length;
    parameterButton.textContent = `${translated("工作流常用參數")} · ${connectedControls.length}`;
    parameterButton.setAttribute("aria-expanded", "false");
    parameterPanel.hidden = true;
    parameterPanel.innerHTML = connectedControls.length ?
      `<div class="studio-workflow-quick-controls">${primaryControls.map(field => renderWorkflowControl(field, recipe)).join("")}</div>` +
      (secondaryControls.length ? `<details class="studio-workflow-branches"><summary>${escape(translated("其他工作流參數"))} · ${secondaryControls.length}</summary><div class="studio-workflow-quick-controls">${secondaryControls.map(field => renderWorkflowControl(field, recipe)).join("")}</div></details>` : "") : "";

    $("#studioWorkflowBindings").innerHTML = workflow ? Object.entries(names).map(([name, rawLabel]) => {
      const label = translated(rawLabel);
      const current = Array.isArray(recipe.bindings[name]) ? recipe.bindings[name] :
        recipe.bindings[name] ? [recipe.bindings[name]] : [];
      const numeric = ["seed","text_seed","width","height","steps","cfg"].includes(name);
      const choices = fields.filter(field => field.type === (numeric ? "number" : "text") &&
        !internalStateNames.has(field.input));
      const selected = choices.filter(field => current.includes(field.key)).map(workflowFieldLabel);
      const summary = selected.length ?
        `${selected.slice(0, 2).join(" · ")}${selected.length > 2 ? ` +${selected.length - 2}` : ""}` :
        translated("使用工作流預設");
      return `<details class="studio-workflow-binding"><summary><span class="studio-workflow-binding-title">${escape(label)}</span><span class="studio-workflow-binding-summary" data-binding-summary>${escape(summary)}</span></summary><div class="studio-workflow-binding-options">${choices.map(field => `<label class="studio-workflow-binding-option"><input type="checkbox" data-binding-choice="${name}" value="${escape(field.key)}"${current.includes(field.key) ? " checked" : ""}><span data-i18n-ignore>${escape(workflowFieldLabel(field))}</span></label>`).join("") || `<p>${escape(translated("沒有相容的工作流欄位"))}</p>`}</div></details>`;
    }).join("") : "";

    const unboundFields = fields.filter(field => !boundKeys.has(field.key) &&
      !field.control && !internalStateNames.has(field.input));
    $("#studioWorkflowOverrides").innerHTML = unboundFields.length ? unboundFields.map(field => {
      const value = Object.hasOwn(recipe.overrides, field.key) ? recipe.overrides[field.key] : field.value;
      const label = `${field.title} / ${field.input}`;
      if (field.type === "boolean") return `<label class="studio-lock"><input type="checkbox" data-override="${escape(field.key)}"${value ? " checked" : ""}><span data-i18n-ignore>${escape(label)}</span></label>`;
      return `<label><span data-i18n-ignore>${escape(label)}</span><input data-override="${escape(field.key)}" type="${field.type === "number" ? "number" : "text"}"${field.type === "number" ? ' step="any"' : ""} value="${escape(value)}"></label>`;
    }).join("") : `<p class="studio-empty">${escape(translated("沒有其他節點參數"))}</p>`;

    const rawStateFields = fields.filter(field => !boundKeys.has(field.key) &&
      internalStateNames.has(field.input));
    $("#studioWorkflowStateOverrides").innerHTML = rawStateFields.length ? rawStateFields.map(field => {
      const value = Object.hasOwn(recipe.overrides, field.key) ? recipe.overrides[field.key] : field.value;
      const label = `${field.title} / ${field.input}`;
      return `<label><span data-i18n-ignore>${escape(label)}</span><input data-override="${escape(field.key)}" type="text" value="${escape(value)}"></label>`;
    }).join("") : `<p class="studio-empty">${escape(translated("沒有底層狀態資料"))}</p>`;
    $("#studioWorkflowUnconnected").hidden = !unconnectedControls.length;
    $("#studioWorkflowUnconnected").textContent = unconnectedControls.length ?
      `${unconnectedControls.length} ${translated("個未連接控制項已收起，對生成結果沒有影響。")}` : "";

    $("#studioPostprocess").innerHTML = workflow?.postprocess?.length ? workflow.postprocess.map(item =>
      `<label class="studio-lock"><input type="checkbox" data-branch="${escape(item.node_id)}"${recipe.branches[item.node_id] !== false ? " checked" : ""}>${escape(item.label)}</label>`).join("") : '<p>此工作流按匯入時的後處理路徑執行。可以另存工作流變體供切換。</p>';
    $("#studioReferenceBindings").innerHTML = state.images.filter(image => image.kind === "reference").map(image =>
      `<label><span>${escape(roles[image.role])}</span><span data-i18n-ignore>${escape(image.title)}</span><select data-reference-binding="${escape(image.item_id)}">${fieldOptions}</select></label>`).join("") || "<p>在參考素材頁加入圖片後設定輸入。</p>";
    document.querySelectorAll("[data-reference-binding]").forEach(element => {
      element.value = recipe.reference_bindings[element.dataset.referenceBinding] || "";
    });
  }

  function renderPrefixRows() {
    const rows = state.project.studio.prefix_rows || [];
    $("#studioPrefixRows").innerHTML = rows.map((row, index) => `<div class="studio-prefix-row">
      <input type="checkbox" data-row-enabled="${index}" aria-label="啟用第 ${index + 1} 行"${row.enabled !== false ? " checked" : ""}>
      <input type="text" data-row-text="${index}" aria-label="第 ${index + 1} 行前綴" value="${escape(row.text)}">
      <button type="button" data-row-up="${index}" aria-label="上移第 ${index + 1} 行"${index === 0 ? " disabled" : ""}>上移</button>
      <button type="button" data-row-delete="${index}">移除</button></div>`).join("") +
      '<button type="button" id="studioAddPrefixRow">加入一行</button>';
  }

  function imageCard(image, reference = false) {
    return `<article class="studio-image">
      <button type="button" data-image-preview="${escape(image.item_id)}" aria-label="放大 ${escape(image.title)}"><img src="${escape(image.thumbnail_url)}" alt="${escape(image.title)}" loading="lazy" width="300" height="400"></button>
      <p>${escape(image.title)}</p>
      ${reference ? `<label class="studio-lock"><input type="checkbox" data-reference-enabled="${image.item_id}"${image.review !== "excluded" ? " checked" : ""}>參與生成</label><label>用途<select data-image-role="${escape(image.item_id)}">${Object.entries(roles).map(([value,label]) => `<option value="${value}"${image.role === value ? " selected" : ""}>${label}</option>`).join("")}</select></label>` :
        `<div class="studio-image-actions"><button type="button" data-review="approved" data-item="${image.item_id}" aria-pressed="${image.review === "approved"}">採用</button><button type="button" data-review="excluded" data-item="${image.item_id}" aria-pressed="${image.review === "excluded"}">淘汰</button></div><button type="button" data-repair="${image.item_id}">用此圖修正／補圖</button>`}
      </article>`;
  }

  function renderTaggerImageList(images, taggerMode) {
    const filters = $("#taggerImageFilters");
    filters.hidden = !taggerMode;
    const search = $("#taggerImageSearch").value.trim().toLowerCase();
    const captioned = images.filter(image => Boolean(image.caption?.long || image.caption?.graph || image.caption?.tags?.length || image.caption?.regions?.length));
    $("#taggerAllCount").textContent = String(images.length);
    $("#taggerCaptionedCount").textContent = String(captioned.length);
    $("#taggerUncaptionedCount").textContent = String(images.length - captioned.length);
    filters.querySelectorAll("[data-graph-filter]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.graphFilter === state.graphFilter)));
    const visible = images.filter(image => {
      const hasCaption = captioned.includes(image);
      return (!taggerMode || (state.graphFilter === "all" || (state.graphFilter === "captioned") === hasCaption))
        && (!taggerMode || image.title.toLowerCase().includes(search));
    });
    $("#taggerImageCount").textContent = `${visible.length} / ${images.length}`;
    $("#studioCaptionImages").innerHTML = visible.map(image => {
      const button = `<button type="button" data-caption-image="${escape(image.item_id)}" aria-pressed="${state.selectedImage === image.item_id}"><img src="${escape(image.thumbnail_url)}" width="56" height="72" alt=""><span><span data-i18n-ignore>${escape(image.title)}</span><br><span>${image.caption_confirmed ? "已確認" : "待審核"}</span></span></button>`;
      return taggerMode ? `<label class="studio-caption-select"><input type="checkbox" data-caption-select="${escape(image.item_id)}" aria-label="選擇此圖片"${state.captionSelection.has(image.item_id) ? " checked" : ""}${image.caption_confirmed ? " disabled" : ""}>${button}</label>` : button;
    }).join("") || `<p class="studio-empty">${taggerMode ? "先導入圖片或從畫廊加入。" : "在挑圖頁採用圖片後開始標注。"}</p>`;
  }

  function renderImages() {
    const candidates = state.images.filter(image => image.kind === "candidate");
    const approved = candidates.filter(image => image.review === "approved");
    const taggerMode = document.body.dataset.appView === "tagger";
    const captionImages = taggerMode ? candidates.filter(image => image.review !== "excluded") : approved;
    $("#studioReferences").innerHTML = state.images.filter(image => image.kind === "reference").map(image => imageCard(image, true)).join("") || '<p class="studio-empty">加入角色、服裝或畫風參考圖。</p>';
    $("#studioRecentImages").innerHTML = candidates.slice(-6).reverse().map(image => imageCard(image)).join("") || '<p class="studio-empty">生成圖片會出現在這裡。</p>';
    const filter = $("#studioReviewFilter").value;
    $("#studioCandidates").innerHTML = candidates.filter(image => filter === "all" || image.review === filter).map(image => imageCard(image)).join("") || '<p class="studio-empty">目前沒有符合條件的圖片。</p>';
    $("#studioImageCounts").textContent = `${candidates.length} 張圖片，${approved.length} 張已採用。`;
    renderTaggerImageList(captionImages, taggerMode);
    const annotatable = captionImages.filter(image => !image.caption_confirmed);
    $("#studioCaptionBatch").textContent = taggerMode ? "為可打標圖片生成草稿" : "為已採用圖片生成草稿";
    $("#studioCaptionBatch").disabled = annotatable.length === 0;
    const confirmed = approved.filter(image => image.caption_confirmed && image.caption.long?.trim()).length;
    $("#studioExportCounts").textContent = `已採用 ${approved.length} 張，其中 ${confirmed} 張標注已確認。`;
    $("#studioExportTarget").textContent = `訓練目標 ${targets[state.project.target_profile]}`;
    $("#studioNativeExportNote").textContent = state.project.target_profile === "moss" ? "原生 GBC 包含 KohakuMossTrainer 資料集及相對路徑設定檔，建立時會回讀核對圖片與描述。" : "";
    if (state.selectedImage && !captionImages.some(image => image.item_id === state.selectedImage)) {
      state.selectedImage = "";
      $("#studioCaptionEditor").innerHTML = `<p class="studio-empty">${taggerMode ? "先選擇一張圖片。" : "先選擇一張已採用的圖片。"}</p>`;
    }
    if (!state.selectedImage) {
      $("#studioCaptionEditor").innerHTML = `<p class="studio-empty">${taggerMode ? "選擇一張可打標圖片。" : "先選擇一張已採用的圖片。"}</p>`;
    }
    window.dispatchEvent(new Event("soda-studio-images"));
  }

  function renderJobs() {
    const labels = {queued:"等待執行", running:"執行中", completed:"已完成", failed:"執行失敗", canceled:"已取消"};
    $("#studioJobs").innerHTML = state.jobs.slice(0, 20).map(job => `<article class="studio-job">
      <strong>${escape(labels[job.status] || job.status)}</strong><p>${escape(job.progress_message || "")}</p>
      ${job.job_type === "studio_caption" && job.status === "running" ? `<progress aria-label="標注任務進度" max="${Math.max(1,Number(job.progress_total) || 1)}"${job.progress_total ? ` value="${Math.max(0,Number(job.progress_current) || 0)}"` : ""}></progress>` : ""}
      ${job.error ? `<p class="studio-job-error">${escape(job.error)}</p>` : ""}
      ${["queued","running"].includes(job.status) ? `<button type="button" data-job-cancel="${job.job_id}">${job.status === "running" ? "停止等待" : "取消排隊"}</button>` : ""}
      ${job.status === "canceled" && job.job_type === "studio_generate" ? "<p>服務端已開始的任務可在重試時接收結果。</p>" : ""}
      ${["failed","canceled"].includes(job.status) ? `<button type="button" data-job-retry="${job.job_id}">重試</button>` : ""}
      </article>`).join("") || '<p class="studio-empty">目前沒有生成或標注任務。</p>';
    renderGenerationProgress();
  }

  function generationProgress(jobs) {
    if (!jobs.length) return null;
    const total = jobs.length;
    const completed = jobs.filter(job => job.status === "completed").length;
    const failed = jobs.filter(job => job.status === "failed").length;
    const canceled = jobs.filter(job => job.status === "canceled").length;
    const running = jobs.find(job => job.status === "running");
    const queued = jobs.some(job => job.status === "queued");

    if (running || queued) {
      const label = running ? "正在出圖" : "排隊中，尚未出圖";
      const value = completed > 0 ? Math.round(completed / total * 100) : running ? null : 0;
      const message = running?.progress_message || (running ? "等待圖片服務回傳" : `${completed} / ${total}`);
      return {state: running ? "running" : "queued", label, value, message};
    }
    if (failed || canceled) {
      const stateName = failed ? "failed" : "canceled";
      const label = failed ? "出圖失敗" : "生成已取消";
      const message = jobs.find(job => job.error)?.error || `${completed} / ${total}`;
      return {state: stateName, label, value: Math.round(completed / total * 100), message};
    }
    return {state: "completed", label: "已出圖，圖片已加入畫廊", value: 100, message: `${completed} / ${total}`};
  }

  function renderGenerationProgress() {
    const container = $("#creationGenerationProgress");
    if (!container) return;
    const generated = state.jobs.filter(job => job.job_type === "studio_generate");
    const selected = state.generationJobIds.map(id => generated.find(job => job.job_id === id)).filter(Boolean);
    const active = generated.filter(job => ["queued", "running"].includes(job.status));
    const jobs = selected.length ? selected : active.length ? active : generated.slice(0, 1);
    const progress = generationProgress(jobs);
    container.hidden = !progress;
    if (!progress) return;
    container.dataset.state = progress.state;
    const bar = $("#creationGenerationBar");
    if (progress.value === null) bar.removeAttribute("value");
    else bar.value = progress.value;
    bar.setAttribute("aria-valuetext", progress.label);
    const locale = window.promptHubI18n?.getLocale?.() || "zh-CN";
    $("#creationGenerationLabel").textContent = window.promptHubStudioI18n?.translate(progress.label, locale) || progress.label;
    $("#creationGenerationMessage").textContent = progress.message;
  }

  async function refreshImages() {
    if (!state.project) return;
    const id = state.project.project_id;
    const result = await api(`/projects/${id}`);
    if (state.project?.project_id !== id) return;
    state.images = result.images;
    state.jobs = result.jobs;
    renderImages();
    renderJobs();
  }

  window.ensureDatasetStudio = async route => {
    if (!route.project) return window.setPromptHubView("projects");
    if (state.project?.project_id !== route.project) {
      await saveCurrent();
      state.captionSelection.clear();
      const [result] = await Promise.all([api(`/projects/${encodeURIComponent(route.project)}`), bootstrap()]);
      if (window.PromptHubNavigation.current()?.project !== route.project) return;
      state.project = result.project;
      state.images = result.images;
      state.jobs = result.jobs;
      state.graphSelection = "";
      state.graphDrawMode = false;
      state.graphObjectSearch = "";
      try {
        const savedJobIds = JSON.parse(sessionStorage.getItem("studio-generation-jobs-" + route.project) || "[]");
        state.generationJobIds = Array.isArray(savedJobIds) ? savedJobIds.filter(id => typeof id === "string") : [];
      } catch { state.generationJobIds = []; }
      state.preview = null;
      state.lastDraw = null;
      state.v2Editor = "";
      state.v2CharacterEditing = false;
      state.dirty = false;
      state.pendingDraft = null;
      $("#studioDraftRecovery").hidden = true;
      try {
        const draft = JSON.parse(localStorage.getItem(draftKey(route.project)) || "null");
        if (draft && draft.revision === state.project.revision) {
          state.project.studio = draft.studio;
          state.dirty = true;
        } else if (draft && JSON.stringify(draft.studio) !== JSON.stringify(state.project.studio)) {
          state.pendingDraft = draft;
          $("#studioDraftRecovery").hidden = false;
        }
      } catch { }
      try {
        const preview = JSON.parse(localStorage.getItem(previewKey(route.project)) || "null");
        if (preview && preview.recipe === JSON.stringify(state.project.studio)) {
          usePreview(preview.value);
        }
      } catch { }
      state.selectedImage = sessionStorage.getItem("studio-selected-" + route.project) || "";
      $("#studioProjectTitle").textContent = state.project.title;
      $("#studioTargetLabel").textContent = targets[state.project.target_profile];
      $("#studioSaveState").textContent = state.dirty ? "已恢復本機草稿" : "已保存";
      populateRecipe();
      renderImages();
      renderJobs();
      renderPreview();
      renderExports(result.exports || []);
      const models = state.bootstrap.vision_models;
      $("#studioCaptionModel").innerHTML = models.length ? models.map(model => `<option value="${escape(model.id)}">${escape(model.name)}</option>`).join("") : '<option value="">請先接入視覺模型</option>';
      const nativeOption = $("#studioExportFormat option[value='gbc']");
      nativeOption.hidden = state.project.target_profile !== "moss";
      $("#studioExportFormat").value = state.project.target_profile === "moss" ? "gbc" : "both";
      try {
        const options = JSON.parse(localStorage.getItem("studio-caption-options-" + route.project) || "{}");
        if (options.method) $("#studioCaptionMethod").value = options.method;
        else if (document.body.dataset.appView === "tagger") $("#studioCaptionMethod").value = "pixai_gbc";
        if (options.model) $("#studioCaptionModel").value = options.model;
      } catch { }
      $("#studioCaptionModelField").hidden = ["wd14","pixai"].includes($("#studioCaptionMethod").value);
    }
    await saveCurrent();
    if (window.PromptHubNavigation.current()?.project !== route.project) return;
    state.step = route.step;
    renderImages();
    if (route.step === "caption") {
      const selectedId = state.selectedImage || sessionStorage.getItem("studio-selected-" + route.project);
      const taggerMode = document.body.dataset.appView === "tagger";
      const selected = state.images.find(image => image.item_id === selectedId && image.kind === "candidate"
        && (taggerMode ? image.review !== "excluded" : image.review === "approved"));
      if (selected) renderCaptionEditor(selected.item_id);
    }
    document.querySelectorAll("[data-studio-panel]").forEach(element => { element.hidden = element.dataset.studioPanel !== route.step; });
    document.querySelectorAll("[data-studio-step]").forEach(element => { element.setAttribute("aria-current", element.dataset.studioStep === route.step ? "step" : "false"); });
    if (state.project.generation.studio_step !== route.step) {
      state.project.generation.studio_step = route.step;
      state.dirty = true;
      persistDraft();
      await saveCurrent();
    }
  };

  function renderPreview() {
    const rows = state.preview?.rows || [];
    $("#studioPromptPreview").innerHTML = rows.length ? rows.slice(0, 12).map((row, index) => `<article class="studio-prompt-preview"><strong>第 ${index + 1} 張</strong><p>${escape(row.positive)}</p><small>抽詞種子 ${row.text_seed}${state.project.studio.backend === "openai" ? "" : `　出圖種子 ${row.seed}`}</small>${row.debug ? `<details><summary>Raffle 抽取紀錄</summary><p>${escape(row.debug)}</p></details>` : ""}</article>`).join("") + (rows.length > 12 ? `<p>本批共 ${rows.length} 張，顯示前 12 組。</p>` : "") : '<p class="studio-empty">填好提示詞後，預覽抽取結果。</p>';
  }

  function usePreview(preview) {
    state.preview = preview;
    state.lastDraw = wildcardV2Active(state.project.studio) ? preview.rows.at(-1) : preview.rows[0];
  }

  async function previewBatch(count) {
    const project = state.project;
    const v2 = wildcardV2Active(project.studio);
    if (state.lastDraw && (v2 || (count === 1 && project.studio.text_seed_mode === "increment"))) {
      project.studio.text_seed = (state.lastDraw.text_seed + 1) % (2 ** 53);
      const input = document.querySelector('[data-recipe="text_seed"]');
      input.value = project.studio.text_seed;
      markChanged();
    }
    const snapshot = JSON.stringify(project.studio);
    await saveCurrent();
    const result = await api(`/projects/${project.project_id}/preview`, {
      method:"POST", body:count === 1 ? {count:1} : {},
    });
    if (project !== state.project || snapshot !== JSON.stringify(project.studio)) {
      throw new Error(translated("抽詞設定已變更，請重新抽詞。"));
    }
    usePreview(result);
    try { localStorage.setItem(previewKey(state.project.project_id), JSON.stringify({recipe:JSON.stringify(state.project.studio),value:result})); } catch { }
    renderPreview();
    notice(`已準備 ${result.rows.length} 組提示詞。`);
  }

  async function queueBatch() {
    const project = state.project;
    await saveCurrent();
    if (state.project !== project) return;
    const v2 = wildcardV2Active(project.studio);
    if (!state.preview || state.preview.rows.length !== project.studio.count || (v2 && state.preview.queued)) {
      await previewBatch();
    }
    const preview = state.preview;
    const projectId = project.project_id;
    const result = await api(`/projects/${projectId}/generate`, {method:"POST",body:{preview_id:preview.preview_id}});
    if (v2) {
      if (state.preview?.preview_id === preview.preview_id) state.preview.queued = true;
      try {
        const key = previewKey(projectId);
        const saved = JSON.parse(localStorage.getItem(key));
        if (saved?.value?.preview_id === preview.preview_id) {
          saved.value.queued = true;
          localStorage.setItem(key, JSON.stringify(saved));
        }
      } catch { }
    }
    sessionStorage.setItem("studio-generation-jobs-" + projectId, JSON.stringify(result.job_ids));
    if (state.project !== project) return;
    state.generationJobIds = result.job_ids;
    notice(`已加入 ${result.job_ids.length} 個任務。`);
    await refreshImages();
  }

  async function importFiles(files, kind) {
    if (state.uploadBusy || !files.length) return;
    state.uploadBusy = true;
    const projectId = state.project.project_id;
    try {
      for (let index = 0; index < files.length; index++) {
        notice(`正在匯入 ${index + 1} / ${files.length}`);
        const query = new URLSearchParams({filename:files[index].name, kind, role:"identity"});
        await api(`/projects/${projectId}/images?${query}`, {method:"POST", body:files[index]});
      }
      await refreshImages();
      renderWorkflow();
      notice(`已匯入 ${files.length} 張圖片，相同檔案會合併。`);
    } finally { state.uploadBusy = false; }
  }

  function renderCaptionEditor(itemId) {
    const image = state.images.find(item => item.item_id === itemId);
    if (!image) return;
    state.selectedImage = itemId;
    sessionStorage.setItem("studio-selected-" + state.project.project_id, itemId);
    if (document.body.dataset.appView === "tagger") {
      renderGraphEditor(image);
      return;
    }
    $("#studioCaptionEditor").innerHTML = `<form id="studioCaptionForm" class="studio-caption-form">
      <img src="${escape(image.image_url)}" alt="${escape(image.title)}">
      <div class="studio-caption-fields"><h2>${escape(image.title)}</h2>
      <label>完整描述<textarea name="long" rows="8" required>${escape(image.caption.long || "")}</textarea></label>
      <label>中等長度描述<textarea name="medium" rows="3">${escape(image.caption.medium || "")}</textarea></label>
      <label>簡短描述<textarea name="short" rows="2">${escape(image.caption.short || "")}</textarea></label>
      <details><summary>完整 JSON 與區域資料</summary><label>結構化標注<textarea name="json" rows="10">${escape(JSON.stringify(image.caption, null, 2))}</textarea></label><button type="button" id="studioApplyCaptionJson">將 JSON 描述填入欄位</button></details>
      <label class="studio-lock"><input type="checkbox" name="confirmed"${image.caption_confirmed ? " checked" : ""}>已逐圖審核並確認</label>
      <button type="submit" class="studio-primary">保存標注</button><p id="studioCaptionSaveState" role="status"></p></div></form>`;
    try {
      const draft = JSON.parse(localStorage.getItem(captionKey(itemId)) || "null");
      if (draft) {
        const form = $("#studioCaptionForm");
        ["long","medium","short","json"].forEach(name => { form.elements[name].value = draft[name] || ""; });
        form.elements.confirmed.checked = Boolean(draft.confirmed);
        $("#studioCaptionSaveState").textContent = draft.updated_at === image.updated_at ? "已恢復未保存的標注草稿" : "已恢復本機草稿，服務端標注另有更新，請核對後保存";
      }
    } catch { }
    document.querySelectorAll("[data-caption-image]").forEach(element => element.setAttribute("aria-pressed", String(element.dataset.captionImage === itemId)));
  }

  let graphCanvasObserver;

  function resizeGraphCanvas() {
    const canvas = $(".tagger-canvas-scroll");
    const image = canvas?.querySelector("img");
    if (!image) return;
    const style = getComputedStyle(canvas);
    const height = canvas.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
    image.style.maxHeight = `${Math.max(1, height) * state.graphZoom / 100}px`;
  }

  function renderGraphEditor(image) {
    let draft = null;
    try { draft = JSON.parse(localStorage.getItem(captionKey(image.item_id)) || "null"); } catch { }
    let caption = image.caption || {};
    try { if (draft?.json) caption = JSON.parse(draft.json); } catch { }
    const graph = caption.graph || {};
    const allVertices = graph.vertices || [];
    const vertices = allVertices.filter(vertex => vertex.label !== "image" && vertex.bbox);
    const root = allVertices.find(vertex => vertex.label === "image");
    const colors = ["#59a8df", "#a68ad5", "#49b494", "#e59c55", "#e67699", "#53b4bc"];
    const label = vertex => (vertex.in_edges || [])[0]?.text || vertex.vertex_id || "物件";
    const edgeCount = allVertices.reduce((sum, vertex) => sum + (vertex.out_edges || []).length, 0);
    const descriptions = allVertices.reduce((sum, vertex) => sum + (vertex.descs || []).length, 0);
    const tags = Array.isArray(caption.tags) ? caption.tags : Object.keys(root?.tags || {});
    const edgeLines = vertices.flatMap(source => (source.out_edges || []).map(edge => {
      const target = vertices.find(vertex => vertex.vertex_id === edge.target);
      if (!target || !source.bbox || !target.bbox) return "";
      const x1 = (source.bbox.left + source.bbox.right) * 500;
      const y1 = (source.bbox.top + source.bbox.bottom) * 500;
      const x2 = (target.bbox.left + target.bbox.right) * 500;
      const y2 = (target.bbox.top + target.bbox.bottom) * 500;
      return `<g><path d="M ${x1} ${y1} L ${x2} ${y2}"/><text x="${(x1+x2)/2}" y="${(y1+y2)/2}">${escape(edge.text || "")}</text></g>`;
    })).join("");
    const boxes = vertices.map((vertex, index) => {
      const box = vertex.bbox;
      return `<button type="button" class="tagger-box" data-graph-vertex="${escape(vertex.vertex_id)}" aria-label="${escape(label(vertex))}" style="--box-color:${colors[index % colors.length]};left:${box.left * 100}%;top:${box.top * 100}%;width:${(box.right - box.left) * 100}%;height:${(box.bottom - box.top) * 100}%"><span>${escape(label(vertex))}</span><i class="tagger-resize-handle" data-graph-resize></i></button>`;
    }).join("");
    const kinds = ["entity", "group", "relation"];
    const visibleVertices = vertices.filter(vertex => state.graphKinds[vertex.label] !== false
      && (state.graphIncludeUnscored || vertex.bbox.confidence != null)
      && (vertex.bbox.confidence == null || vertex.bbox.confidence * 100 >= state.graphMinConfidence)
      && label(vertex).toLowerCase().includes(state.graphObjectSearch || ""));
    const visibleEdges = vertices.flatMap(source => (source.out_edges || []).map(edge => ({source, edge})))
      .filter(({edge}) => (state.graphKinds.relation !== false)
        && `${label(vertices.find(vertex => vertex.vertex_id === edge.target) || {})} ${edge.text || ""}`.toLowerCase().includes(state.graphObjectSearch || ""));
    const captionMode = state.graphCaptionMode;
    const linkOptions = vertices.filter(vertex => vertex.vertex_id !== state.graphSelection)
      .map(vertex => `<option value="${escape(vertex.vertex_id)}">${escape(label(vertex))}</option>`).join("");
    $("#studioCaptionEditor").innerHTML = `<form id="studioCaptionForm" class="tagger-graph-form">
      <div class="tagger-canvas-column"><div class="tagger-canvas-toolbar">
        <button type="button" data-graph-zoom="-10" aria-label="縮小">−</button><span id="taggerZoomValue">${state.graphZoom}%</span><button type="button" data-graph-zoom="10" aria-label="放大">+</button>
        <button type="button" id="taggerFitCanvas">適合視窗</button><button type="button" id="taggerAddBox" aria-pressed="${state.graphDrawMode}">新增框線</button><button type="button" id="taggerExportPng">匯出標註 PNG</button>
        <label><input type="checkbox" id="taggerShowBoxes" checked>框線</label><label><input type="checkbox" id="taggerShowNames" checked>名稱</label>
      </div><div class="tagger-canvas-scroll"><div class="tagger-image-wrap"><img style="max-height:${state.graphZoom * 0.70}vh" src="${escape(image.image_url)}" alt="${escape(image.title)}"><div class="tagger-box-layer"><svg class="tagger-edge-layer" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true">${edgeLines}</svg>${boxes}</div></div></div></div>
      <aside class="tagger-inspector"><h2>SCENE GRAPH</h2><div class="tagger-metrics"><span><strong>${vertices.length}</strong>物件</span><span><strong>${edgeCount}</strong>連線</span><span><strong>${descriptions}</strong>描述</span></div>
        <section class="tagger-caption-section"${state.graphKinds.image === false ? " hidden" : ""}><div class="tagger-section-heading"><h3>全圖描述</h3><div class="tagger-segmented"><button type="button" data-caption-mode="detail" aria-pressed="${captionMode === "detail"}">詳細描述</button><button type="button" data-caption-mode="simple" aria-pressed="${captionMode === "simple"}">簡短描述</button></div></div>
          <label class="tagger-caption-editor-label" data-caption-field="detail"${captionMode === "detail" ? "" : " hidden"}><span>詳細描述</span><textarea name="long" data-graph-caption rows="5" required>${escape(draft?.long ?? caption.long ?? "")}</textarea></label>
          <label class="tagger-caption-editor-label" data-caption-field="simple"${captionMode === "simple" ? "" : " hidden"}><span>簡短描述</span><textarea name="short" data-graph-caption rows="3">${escape(draft?.short ?? caption.short ?? "")}</textarea></label>
          <details><summary>中等描述與完整資料</summary><label>中等描述<textarea name="medium" rows="3">${escape(draft?.medium ?? caption.medium ?? "")}</textarea></label><label>結構化標注<textarea name="json" rows="10">${escape(draft?.json ?? JSON.stringify(caption, null, 2))}</textarea></label><button type="button" id="studioApplyCaptionJson">套用 JSON 描述</button></details>
        </section>
        <section class="tagger-tags-section"><h3>全圖 tags (${tags.length})</h3><div class="tagger-tags">${tags.map(tag => `<button type="button" data-graph-remove-tag="${escape(tag)}">${escape(tag)} <span aria-hidden="true">×</span></button>`).join("")}</div><div class="tagger-add-tag"><input id="taggerNewTag" type="text" placeholder="新增 tag"><button type="button" id="taggerAddTag">新增</button></div></section>
        <label class="studio-lock tagger-confirm"><input type="checkbox" name="confirmed"${(draft ? draft.confirmed : image.caption_confirmed) ? " checked" : ""}>已逐圖審核並確認</label><button type="submit" class="studio-primary">保存標注</button><p id="studioCaptionSaveState" role="status"></p>
        <section class="tagger-objects-section"><div class="tagger-section-heading"><h3>物件與關係</h3><span>${vertices.length} 個物件</span></div>
          <input id="taggerObjectSearch" type="search" placeholder="搜尋名稱或關係" value="${escape(state.graphObjectSearch || "")}">
          <div class="tagger-graph-filters">${kinds.map(kind => `<label><input type="checkbox" data-graph-kind="${kind}"${state.graphKinds[kind] !== false ? " checked" : ""}>${kind === "entity" ? "物件" : kind === "group" ? "組合" : "關係"}</label>`).join("")}<label><input type="checkbox" data-graph-kind="image"${state.graphKinds.image !== false ? " checked" : ""}>全圖</label></div>
          <label class="tagger-confidence">最低信心值 <output id="taggerConfidenceValue">${state.graphMinConfidence}%</output><input id="taggerConfidence" type="range" min="0" max="100" step="1" value="${state.graphMinConfidence}"></label><label class="tagger-include-unscored"><input type="checkbox" id="taggerIncludeUnscored"${state.graphIncludeUnscored ? " checked" : ""}>含未提供信心值</label>
          <div id="taggerGraphObjects" class="tagger-object-list">${visibleVertices.map((vertex, index) => `<button type="button" data-graph-vertex="${escape(vertex.vertex_id)}" aria-pressed="${state.graphSelection === vertex.vertex_id}"><i style="background:${colors[index % colors.length]}"></i><span>${escape(label(vertex))}</span><small>${vertex.bbox.confidence == null ? "未提供" : `${Math.round(vertex.bbox.confidence * 100)}%`}</small></button>`).join("") || '<p>此圖片尚無符合條件的物件。</p>'}</div>
          <h4>關係</h4><div id="taggerGraphRelations" class="tagger-relation-list">${visibleEdges.map(({source,edge}) => `<button type="button" data-graph-vertex="${escape(source.vertex_id)}"><span>${escape(edge.text || "關係")}</span><small>${escape(label(vertices.find(vertex => vertex.vertex_id === edge.target) || {vertex_id:edge.target}))}</small></button>`).join("") || '<p>尚無關係連線。</p>'}</div><div id="taggerVertexDetails"></div>
        </section>
      </aside></form>`;
    document.querySelectorAll("[data-caption-image]").forEach(element => element.setAttribute("aria-pressed", String(element.dataset.captionImage === image.item_id)));
    if (draft) $("#studioCaptionSaveState").textContent = "已恢復未保存的標注草稿";
    if (state.graphSelection) selectGraphVertex(state.graphSelection);
    graphCanvasObserver?.disconnect();
    graphCanvasObserver = new ResizeObserver(resizeGraphCanvas);
    graphCanvasObserver.observe($(".tagger-canvas-scroll"));
    resizeGraphCanvas();
  }

  function selectGraphVertex(id) {
    const form = $("#studioCaptionForm");
    let caption;
    try { caption = JSON.parse(form.elements.json.value); } catch { return; }
    const label = item => (item.in_edges || [])[0]?.text || item.vertex_id || "物件";
    const vertex = caption.graph?.vertices?.find(item => item.vertex_id === id);
    if (!vertex?.bbox) return;
    state.graphSelection = id;
    form.querySelectorAll("[data-graph-vertex]").forEach(element => {
      element.classList.toggle("selected", element.dataset.graphVertex === id);
      if (element.matches("button[data-graph-vertex]")) element.setAttribute("aria-pressed", String(element.dataset.graphVertex === id));
    });
    const box = vertex.bbox;
    const parent = (vertex.in_edges || [])[0];
    const detail = (vertex.descs || []).find(item => item.label === "detail")?.text || "";
    const targets = (caption.graph.vertices || []).filter(item => item.label !== "image" && item.vertex_id !== id);
    $("#taggerVertexDetails").innerHTML = `<h4>${escape(parent?.text || id)}</h4><label>物件名稱<input type="text" data-graph-edge-text data-edge-source="${escape(parent?.source || "")}" data-edge-target="${escape(id)}" value="${escape(parent?.text || id)}"></label><label>區域描述<textarea data-graph-description rows="3">${escape(detail)}</textarea></label><div class="tagger-box-fields">${["left","top","right","bottom"].map(key => `<label>${key}<input type="number" data-graph-coordinate="${key}" min="0" max="1" step="any" value="${box[key]}"></label>`).join("")}</div>
      <div class="tagger-link-editor"><label>新增關係<select id="taggerRelationTarget"><option value="">選擇物件</option>${targets.map(target => `<option value="${escape(target.vertex_id)}">${escape(label(target))}</option>`).join("")}</select></label><input id="taggerRelationText" type="text" placeholder="關係描述"><button type="button" id="taggerAddRelation">新增關係</button></div>
      <div class="tagger-outgoing-relations">${(vertex.out_edges || []).map(edge => `<div><span>${escape(edge.text || "關係")}</span><small>${escape(label(targets.find(item => item.vertex_id === edge.target) || {vertex_id:edge.target}))}</small><button type="button" data-delete-relation-source="${escape(id)}" data-delete-relation-target="${escape(edge.target)}" aria-label="刪除關係">×</button></div>`).join("")}</div>
      <button type="button" class="tagger-delete-object" data-delete-vertex="${escape(id)}">刪除此物件</button>`;
  }

  function updateGraphBox(id, box) {
    const form = $("#studioCaptionForm");
    const caption = JSON.parse(form.elements.json.value);
    const vertex = caption.graph.vertices.find(item => item.vertex_id === id);
    vertex.bbox = {...vertex.bbox, ...box};
    const region = (caption.regions || []).find(item => item.name === id);
    if (region) region.bbox = [box.left, box.top, box.right, box.bottom];
    form.elements.json.value = JSON.stringify(caption, null, 2);
    const overlay = Array.from(form.querySelectorAll(".tagger-box")).find(item => item.dataset.graphVertex === id);
    if (overlay) Object.assign(overlay.style, {left:`${box.left * 100}%`,top:`${box.top * 100}%`,width:`${(box.right-box.left) * 100}%`,height:`${(box.bottom-box.top) * 100}%`});
    persistCaptionDraft();
  }

  function saveGraphCaption(caption) {
    $("#studioCaptionForm").elements.json.value = JSON.stringify(caption, null, 2);
    persistCaptionDraft();
  }

  function setGraphEdgeText(caption, sourceId, targetId, text) {
    const source = caption.graph.vertices.find(vertex => vertex.vertex_id === sourceId);
    const target = caption.graph.vertices.find(vertex => vertex.vertex_id === targetId);
    source?.out_edges?.filter(edge => edge.target === targetId).forEach(edge => { edge.text = text; });
    target?.in_edges?.filter(edge => edge.source === sourceId).forEach(edge => { edge.text = text; });
  }

  function addGraphVertex(box) {
    const form = $("#studioCaptionForm");
    const caption = JSON.parse(form.elements.json.value || "{}");
    const image = state.images.find(item => item.item_id === state.selectedImage);
    if (!caption.graph) {
      const long = form.elements.long.value;
      const short = form.elements.short.value;
      caption.graph = {vertices:[
        {vertex_id:"",label:"image",bbox:{left:0,top:0,right:1,bottom:1,confidence:null},descs:[{text:long,label:"detail",full_label:"detail-image"},{text:short,label:"short",full_label:"short-image"}],in_edges:[],out_edges:[],sub_masks:[],super_masks:[],tags:{}},
      ],detail_caption:long,short_caption:short,img_path:image.title,img_size:[],mask_inside_threshold:0.85};
    }
    const graph = caption.graph;
    const root = graph.vertices.find(vertex => vertex.label === "image");
    let number = graph.vertices.length;
    while (graph.vertices.some(vertex => vertex.vertex_id === `region_${number}`)) number += 1;
    const id = `region_${number}`;
    const edge = {source:root.vertex_id || "",target:id,text:"object"};
    root.out_edges ||= [];
    root.sub_masks ||= [];
    root.out_edges.push(edge);
    root.sub_masks.push(id);
    graph.vertices.push({vertex_id:id,label:"entity",bbox:{...box,confidence:null},descs:[{text:"",label:"detail",full_label:"detail-entity"}],in_edges:[{...edge}],out_edges:[],sub_masks:[],super_masks:[root.vertex_id || ""]});
    caption.regions ||= [];
    caption.regions.push({name:id,caption:"",bbox:[box.left,box.top,box.right,box.bottom]});
    saveGraphCaption(caption);
    state.graphSelection = id;
    renderGraphEditor(image);
    selectGraphVertex(id);
  }

  function addGraphRelation() {
    const targetId = $("#taggerRelationTarget").value;
    const text = $("#taggerRelationText").value.trim();
    if (!state.graphSelection || !targetId || !text) return notice("選擇關聯物件並填寫關係描述。", true);
    const form = $("#studioCaptionForm");
    const caption = JSON.parse(form.elements.json.value);
    const source = caption.graph.vertices.find(vertex => vertex.vertex_id === state.graphSelection);
    const target = caption.graph.vertices.find(vertex => vertex.vertex_id === targetId);
    if (!source || !target || source.out_edges.some(edge => edge.target === targetId && edge.text === text)) return;
    const edge = {source:source.vertex_id,target:target.vertex_id,text};
    source.out_edges ||= [];
    target.in_edges ||= [];
    source.out_edges.push(edge);
    target.in_edges.push({...edge});
    saveGraphCaption(caption);
    const image = state.images.find(item => item.item_id === state.selectedImage);
    renderGraphEditor(image);
    selectGraphVertex(state.graphSelection);
  }

  function removeGraphRelation(sourceId, targetId) {
    const form = $("#studioCaptionForm");
    const caption = JSON.parse(form.elements.json.value);
    const source = caption.graph.vertices.find(vertex => vertex.vertex_id === sourceId);
    const target = caption.graph.vertices.find(vertex => vertex.vertex_id === targetId);
    source.out_edges = (source.out_edges || []).filter(edge => edge.target !== targetId);
    target.in_edges = (target.in_edges || []).filter(edge => edge.source !== sourceId);
    saveGraphCaption(caption);
    const image = state.images.find(item => item.item_id === state.selectedImage);
    renderGraphEditor(image);
    selectGraphVertex(sourceId);
  }

  function removeGraphVertex(id) {
    const form = $("#studioCaptionForm");
    const caption = JSON.parse(form.elements.json.value);
    const graph = caption.graph;
    graph.vertices = graph.vertices.filter(vertex => vertex.vertex_id !== id);
    graph.vertices.forEach(vertex => {
      vertex.out_edges = (vertex.out_edges || []).filter(edge => edge.target !== id);
      vertex.in_edges = (vertex.in_edges || []).filter(edge => edge.source !== id);
      vertex.sub_masks = (vertex.sub_masks || []).filter(child => child !== id);
      vertex.super_masks = (vertex.super_masks || []).filter(parent => parent !== id);
    });
    caption.regions = (caption.regions || []).filter(region => region.name !== id);
    state.graphSelection = "";
    saveGraphCaption(caption);
    renderGraphEditor(state.images.find(item => item.item_id === state.selectedImage));
  }

  function updateGraphTags(transform) {
    const form = $("#studioCaptionForm");
    const caption = JSON.parse(form.elements.json.value || "{}");
    const root = caption.graph?.vertices?.find(vertex => vertex.label === "image");
    const scores = root?.tags && !Array.isArray(root.tags) ? root.tags : {};
    const tags = Array.isArray(caption.tags) ? [...caption.tags] : Object.keys(scores);
    caption.tags = transform(tags);
    if (root) root.tags = Object.fromEntries(caption.tags.map(tag => [tag, scores[tag] ?? 1]));
    saveGraphCaption(caption);
    renderGraphEditor(state.images.find(item => item.item_id === state.selectedImage));
  }

  async function exportGraphPng() {
    const form = $("#studioCaptionForm");
    const caption = JSON.parse(form.elements.json.value || "{}");
    const imageElement = form.querySelector(".tagger-image-wrap img");
    await imageElement.decode();
    const canvas = document.createElement("canvas");
    canvas.width = imageElement.naturalWidth;
    canvas.height = imageElement.naturalHeight;
    const context = canvas.getContext("2d");
    context.drawImage(imageElement, 0, 0);
    const vertices = (caption.graph?.vertices || []).filter(vertex => vertex.label !== "image" && vertex.bbox);
    vertices.forEach((vertex, index) => {
      const box = vertex.bbox;
      const left = box.left * canvas.width, top = box.top * canvas.height;
      const width = (box.right - box.left) * canvas.width, height = (box.bottom - box.top) * canvas.height;
      const color = ["#59a8df", "#a68ad5", "#49b494", "#e59c55", "#e67699", "#53b4bc"][index % 6];
      context.strokeStyle = color;
      context.lineWidth = Math.max(2, canvas.width / 500);
      context.strokeRect(left, top, width, height);
      const text = (vertex.in_edges || [])[0]?.text || vertex.vertex_id;
      context.font = `600 ${Math.max(12, canvas.width / 45)}px sans-serif`;
      const labelWidth = context.measureText(text).width + 12;
      context.fillStyle = color;
      context.fillRect(left, Math.max(0, top - canvas.width / 22), labelWidth, canvas.width / 22);
      context.fillStyle = "#101010";
      context.fillText(text, left + 6, Math.max(canvas.width / 50, top - canvas.width / 90));
    });
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
    if (!blob) throw new Error("標註 PNG 匯出失敗。");
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(blob);
    anchor.download = state.images.find(item => item.item_id === state.selectedImage).title + "-annotations.png";
    anchor.click();
    URL.revokeObjectURL(anchor.href);
  }

  function persistCaptionDraft() {
    const form = $("#studioCaptionForm");
    if (!form || !state.selectedImage) return;
    const image = state.images.find(item => item.item_id === state.selectedImage);
    const value = {updated_at:image.updated_at,confirmed:form.elements.confirmed.checked};
    ["long","medium","short","json"].forEach(name => { value[name] = form.elements[name].value; });
    try {
      localStorage.setItem(captionKey(state.selectedImage), JSON.stringify(value));
      $("#studioCaptionSaveState").textContent = "標注草稿已保留，完成審核後點保存";
    } catch { notice("標注草稿空間不足，請點保存標注。", true); }
  }

  function renderExports(exports) {
    $("#studioExports").innerHTML = exports.map(item => `<p><a href="${escape(item.download_url)}" download>下載交付包 · ${item.image_count} 張圖片</a></p>`).join("");
  }

  function renderSettings() {
    const config = state.bootstrap.connections;
    $("#studioConnectionList").innerHTML = config.providers.map(provider => `<div class="studio-connection"><span><strong data-i18n-ignore>${escape(provider.label)}</strong><br><span data-i18n-ignore>${escape(provider.model)}</span> · <span>${provider.has_api_key ? "已保存憑證" : "未填憑證"}</span></span><div class="studio-connection-actions"><button type="button" data-edit-provider="${escape(provider.id)}">編輯</button><button type="button" data-delete-provider="${escape(provider.id)}">刪除</button></div></div>`).join("") || '<p class="studio-empty">加入已有的圖片 API 連線。</p>';
    $("#studioLocalToolsForm").elements.comfy_root.value = config.comfy_root || "";
    const workerForm = $("#studioWorkerForm");
    ["python","pixai_model","detector_model","embedder_model","device"].forEach(name => { workerForm.elements[name].value = config.caption_worker?.[name] || (name === "device" ? "cpu" : ""); });
  }

  function clearProviderModels() {
    state.providerDiscoveryRun++;
    state.providerDiscoveryController?.abort();
    state.providerDiscoveryController = null;
    $("#studioProviderModelSelect").innerHTML = "";
    $("#studioProviderModelSelectField").hidden = true;
    $("#studioDiscoverProviderModels").hidden = $("#studioProviderForm").elements.kind.value !== "openai";
    notice("", false, "#studioProviderModelsStatus");
  }

  window.ensureStudioSettings = async () => {
    await bootstrap();
    renderSettings();
  };

  document.addEventListener("DOMContentLoaded", () => {
    $("#studioNewProject").addEventListener("click", () => {
      $("#studioCreateForm").hidden = false;
      $("#studioCreateForm").elements.title.focus({preventScroll:true});
    });
    $("#studioCancelCreate").addEventListener("click", () => { $("#studioCreateForm").hidden = true; });
    $("#studioCreateForm").addEventListener("submit", event => {
      event.preventDefault();
      const form = event.currentTarget;
      action(event.submitter || form.querySelector('[type="submit"]'), async () => {
        const project = await api("/projects", {method:"POST", body:{title:form.elements.title.value, target:form.elements.target.value}});
        form.reset();
        form.hidden = true;
        await openProject(project.project_id, "references");
      });
    });
    $("#studioProjectList").addEventListener("click", event => {
      const button = event.target.closest("[data-studio-project]");
      if (button) action(button, () => openProject(button.dataset.studioProject, button.dataset.projectStep));
    });
    $("#studioBackProjects").addEventListener("click", event => action(event.currentTarget, async () => { await saveCurrent(); await window.setPromptHubView("projects"); }));
    $("#studioWorkflowParametersToggle").addEventListener("click", event => {
      const button = event.currentTarget;
      const expanded = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", String(expanded));
      $("#studioWorkflowParameters").hidden = !expanded;
    });
    $("#studioWorkflowControls").addEventListener("click", event => {
      const button = event.target.closest("[data-override-choice]");
      if (!button || !state.project) return;
      const value = button.dataset.value === "true";
      const group = button.closest('[role="group"]');
      group.querySelectorAll("[data-override-choice]").forEach(choice =>
        choice.setAttribute("aria-pressed", String(choice.dataset.value === String(value))));
      state.project.studio.overrides[button.dataset.overrideChoice] = value;
      markChanged();
    });
    $("#studioPage").addEventListener("input", event => {
      if (!state.project) return;
      const element = event.target;
      if (element.id === "taggerImageSearch") {
        const images = state.images.filter(image => image.kind === "candidate" && (document.body.dataset.appView === "tagger" ? image.review !== "excluded" : image.review === "approved"));
        renderTaggerImageList(images, document.body.dataset.appView === "tagger");
      }
      if (element.id === "taggerObjectSearch") state.graphObjectSearch = element.value.trim().toLowerCase();
      if (element.closest("#studioCaptionForm")) persistCaptionDraft();
      if (element.matches("[data-graph-edge-text]")) {
        const form = $("#studioCaptionForm");
        const caption = JSON.parse(form.elements.json.value);
        setGraphEdgeText(caption, element.dataset.edgeSource, element.dataset.edgeTarget, element.value);
        form.elements.json.value = JSON.stringify(caption, null, 2);
        const vertexButton = Array.from(form.querySelectorAll("[data-graph-vertex]")).find(node => node.dataset.graphVertex === element.dataset.edgeTarget);
        if (vertexButton) {
          const nameNode = vertexButton.matches(".tagger-box") ? vertexButton.querySelector("span") : vertexButton.querySelector("span");
          if (nameNode) nameNode.textContent = element.value;
        }
        persistCaptionDraft();
      }
      if (element.matches("[data-graph-description]")) {
        const caption = JSON.parse($("#studioCaptionForm").elements.json.value);
        const vertex = caption.graph.vertices.find(item => item.vertex_id === state.graphSelection);
        const detail = vertex.descs.find(item => item.label === "detail");
        if (detail) detail.text = element.value;
        else vertex.descs.push({text:element.value,label:"detail",full_label:"detail-entity"});
        $("#studioCaptionForm").elements.json.value = JSON.stringify(caption, null, 2);
        persistCaptionDraft();
      }
      if (element.matches("[data-recipe]")) {
        const recipe = state.project.studio;
        const field = element.dataset.recipe;
        const wasV2 = wildcardV2Active(recipe);
        recipe[field] = element.type === "number" ? Number(element.value) : element.value;
        if (field === "prefix") recipe.prefix_rows = [];
        if (Object.hasOwn(recipe.locked_values, field)) delete recipe.locked_values[field];
        if (["backend", "text_mode"].includes(field)) {
          const active = wildcardV2Active(recipe);
          if (wasV2 !== active) {
            state.lastDraw = null;
            if (active && recipe.wildcard_v2_sampling_family !== recipe.wildcard_v2.family) applyWildcardV2SamplingPreset(recipe);
            populateRecipe();
          } else renderWildcardV2(recipe);
        }
        if (field === "text_seed" && wasV2) state.lastDraw = null;
        markChanged();
      }
      if (element.matches("[data-v2-setting]")) {
        const key = element.dataset.v2Setting;
        setWildcardV2Value(key, element.type === "checkbox" ? element.checked : element.value);
      }
      if (element.matches("[data-row-text]")) {
        state.project.studio.prefix_rows[Number(element.dataset.rowText)].text = element.value;
        markChanged();
      }
      if (element.matches("[data-override]")) {
        const numeric = element.type === "number" || element.type === "range";
        const value = element.type === "checkbox" ? element.checked : numeric ? Number(element.value) : element.value;
        state.project.studio.overrides[element.dataset.override] = value;
        if (numeric) {
          element.closest("[data-workflow-control]")?.querySelectorAll('input[type="number"],input[type="range"]').forEach(input => {
            if (input !== element) input.value = element.value;
          });
        }
        markChanged();
      }
      if (element.matches("[data-raffle]")) {
        state.project.studio.raffle[element.dataset.raffle] = element.type === "checkbox" ? element.checked : element.value;
        markChanged();
      }
    });
    $("#studioPage").addEventListener("pointerdown", event => {
      const overlay = event.target.closest(".tagger-box");
      const imageWrap = event.target.closest(".tagger-image-wrap");
      if (state.graphDrawMode && imageWrap && !overlay && event.button === 0) {
        const layer = imageWrap.querySelector(".tagger-box-layer");
        const bounds = layer.getBoundingClientRect();
        const startX = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
        const startY = Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height));
        const preview = document.createElement("div");
        preview.className = "tagger-draw-preview";
        layer.append(preview);
        layer.setPointerCapture(event.pointerId);
        const move = current => {
          const x = Math.max(0, Math.min(1, (current.clientX - bounds.left) / bounds.width));
          const y = Math.max(0, Math.min(1, (current.clientY - bounds.top) / bounds.height));
          Object.assign(preview.style, {left:`${Math.min(startX,x)*100}%`,top:`${Math.min(startY,y)*100}%`,width:`${Math.abs(x-startX)*100}%`,height:`${Math.abs(y-startY)*100}%`});
        };
        const finish = current => {
          layer.removeEventListener("pointermove", move);
          layer.removeEventListener("pointerup", finish);
          layer.removeEventListener("pointercancel", cancel);
          const x = Math.max(0, Math.min(1, (current.clientX - bounds.left) / bounds.width));
          const y = Math.max(0, Math.min(1, (current.clientY - bounds.top) / bounds.height));
          preview.remove();
          state.graphDrawMode = false;
          const addButton = $("#taggerAddBox");
          addButton?.setAttribute("aria-pressed", "false");
          if (current.type === "pointerup" && Math.abs(x-startX) > 0.01 && Math.abs(y-startY) > 0.01) {
            addGraphVertex({left:Math.min(startX,x),top:Math.min(startY,y),right:Math.max(startX,x),bottom:Math.max(startY,y)});
          }
        };
        const cancel = current => finish(current);
        layer.addEventListener("pointermove", move);
        layer.addEventListener("pointerup", finish);
        layer.addEventListener("pointercancel", cancel);
        event.preventDefault();
        return;
      }
      if (!overlay || event.button !== 0) return;
      const layer = overlay.parentElement;
      const bounds = layer.getBoundingClientRect();
      const caption = JSON.parse($("#studioCaptionForm").elements.json.value);
      const vertex = caption.graph.vertices.find(item => item.vertex_id === overlay.dataset.graphVertex);
      const original = {...vertex.bbox};
      const startX = event.clientX, startY = event.clientY;
      const resize = Boolean(event.target.closest("[data-graph-resize]"));
      let box = original;
      overlay.setPointerCapture(event.pointerId);
      selectGraphVertex(overlay.dataset.graphVertex);
      const move = current => {
        const dx = (current.clientX - startX) / bounds.width;
        const dy = (current.clientY - startY) / bounds.height;
        if (resize) {
          box = {...original, right:Math.max(original.left + 0.01, Math.min(1, original.right + dx)), bottom:Math.max(original.top + 0.01, Math.min(1, original.bottom + dy))};
        } else {
          const x = Math.max(-original.left, Math.min(1 - original.right, dx));
          const y = Math.max(-original.top, Math.min(1 - original.bottom, dy));
          box = {...original, left:original.left + x, right:original.right + x, top:original.top + y, bottom:original.bottom + y};
        }
        Object.assign(overlay.style, {left:`${box.left * 100}%`,top:`${box.top * 100}%`,width:`${(box.right-box.left) * 100}%`,height:`${(box.bottom-box.top) * 100}%`});
      };
      const finish = current => {
        overlay.removeEventListener("pointermove", move);
        overlay.removeEventListener("pointerup", finish);
        overlay.removeEventListener("pointercancel", cancel);
        const id = overlay.dataset.graphVertex;
        updateGraphBox(id, current.type === "pointerup" ? box : original);
        if (current.type === "pointerup") renderGraphEditor(state.images.find(item => item.item_id === state.selectedImage));
        selectGraphVertex(id);
      };
      const cancel = current => finish(current);
      overlay.addEventListener("pointermove", move);
      overlay.addEventListener("pointerup", finish);
      overlay.addEventListener("pointercancel", cancel);
      event.preventDefault();
    });
    $("#studioPage").addEventListener("change", event => {
      const element = event.target;
      const recipe = state.project?.studio;
      if (!recipe) return;
      if (element.id === "taggerShowBoxes") document.querySelectorAll(".tagger-box-layer").forEach(layer => { layer.hidden = !element.checked; });
      if (element.id === "taggerShowNames") document.querySelectorAll(".tagger-box-layer").forEach(layer => layer.classList.toggle("hide-names", !element.checked));
      if (element.matches("[data-graph-kind]")) {
        state.graphKinds[element.dataset.graphKind] = element.checked;
        if (element.dataset.graphKind === "image") $(".tagger-caption-section").hidden = !element.checked;
        renderGraphEditor(state.images.find(item => item.item_id === state.selectedImage));
      }
      if (element.id === "taggerConfidence") {
        state.graphMinConfidence = Number(element.value);
        $("#taggerConfidenceValue").textContent = `${state.graphMinConfidence}%`;
        renderGraphEditor(state.images.find(item => item.item_id === state.selectedImage));
      }
      if (element.id === "taggerIncludeUnscored") {
        state.graphIncludeUnscored = element.checked;
        renderGraphEditor(state.images.find(item => item.item_id === state.selectedImage));
      }
      if (element.id === "taggerObjectSearch") {
        state.graphObjectSearch = element.value.trim().toLowerCase();
        renderGraphEditor(state.images.find(item => item.item_id === state.selectedImage));
      }
      if (element.matches("[data-graph-coordinate]")) {
        const form = $("#studioCaptionForm");
        try {
          const caption = JSON.parse(form.elements.json.value);
          const vertex = caption.graph.vertices.find(item => item.vertex_id === state.graphSelection);
          const value = Number(element.value);
          if (!Number.isFinite(value) || value < 0 || value > 1) throw new Error("座標必須介於 0 和 1。");
          const box = {...vertex.bbox, [element.dataset.graphCoordinate]:value};
          if (box.left >= box.right || box.top >= box.bottom) throw new Error("框線座標無效。");
          updateGraphBox(state.graphSelection, box);
          renderGraphEditor(state.images.find(item => item.item_id === state.selectedImage));
        } catch (error) { notice(error.message, true); selectGraphVertex(state.graphSelection); }
      }
      if (element.matches("[data-lock]")) {
        const name = element.dataset.lock;
        recipe.locks[name] = element.checked;
        if (element.checked && state.lastDraw) recipe.locked_values[name] = state.lastDraw[name];
        else delete recipe.locked_values[name];
        markChanged();
      }
      if (element.matches("[data-binding-choice]")) {
        const row = element.closest(".studio-workflow-binding");
        const selected = Array.from(row.querySelectorAll("[data-binding-choice]:checked"));
        recipe.bindings[element.dataset.bindingChoice] = selected.map(option => option.value);
        const labels = selected.map(option => option.closest("label").querySelector("span").textContent);
        const summary = row.querySelector("[data-binding-summary]");
        summary.textContent = labels.length ?
          `${labels.slice(0, 2).join(" · ")}${labels.length > 2 ? ` +${labels.length - 2}` : ""}` :
          translated("使用工作流預設");
        markChanged();
      }
      if (element.matches("[data-reference-binding]")) { recipe.reference_bindings[element.dataset.referenceBinding] = element.value; markChanged(); }
      if (element.matches("[data-branch]")) { recipe.branches[element.dataset.branch] = element.checked; markChanged(); }
      if (element.matches("[data-row-enabled]")) { recipe.prefix_rows[Number(element.dataset.rowEnabled)].enabled = element.checked; markChanged(); }
      if (element.id === "studioBackend") {
        if (recipe.backend === "openai" && ![[1024,1024],[1024,1536],[1536,1024]].some(([w,h]) => w === recipe.width && h === recipe.height)) {
          recipe.width = 1024; recipe.height = 1536; populateRecipe(); markChanged();
        }
        populateProviders();
      }
      if (element.id === "studioCharacters") {
        try { recipe.characters = JSON.parse(element.value.trim() || "[]"); markChanged(); }
        catch { notice("角色提示 JSON 有誤，請修正後保存。",true); }
      }
      if (element.dataset.recipe === "text_mode") { $("#studioRaffleSettings").hidden = recipe.text_mode !== "raffle"; populateProviders(); }
      if (element.id === "studioWorkflow") {
        const workflow = selectedWorkflow();
        if (workflow) {
          bindStudioWorkflow(recipe, workflow);
          populateRecipe();
          markChanged();
        }
      }
      if (element.id === "studioWordlistInsert" && element.value) {
        const body = $("#studioBody");
        const insertion = `__${element.value}__`;
        body.setRangeText(insertion, body.selectionStart, body.selectionEnd, "end");
        recipe.body = body.value;
        markChanged();
        element.value = "";
      }
      if (element.id === "studioReferenceFiles" || element.id === "studioCandidateFiles") {
        const files = Array.from(element.files);
        element.value = "";
        importFiles(files, element.id === "studioReferenceFiles" ? "reference" : "candidate").catch(error => notice(error.message, true));
      }
      if (element.id === "studioReviewFilter") renderImages();
      if (element.matches("[data-caption-select]")) {
        if (element.checked) state.captionSelection.add(element.dataset.captionSelect);
        else state.captionSelection.delete(element.dataset.captionSelect);
      }
      if (element.matches("[data-image-role]")) {
        api(`/projects/${state.project.project_id}/images/${element.dataset.imageRole}`, {method:"PUT",body:{role:element.value}}).then(refreshImages).catch(error => notice(error.message,true));
      }
      if (element.matches("[data-reference-enabled]")) {
        api(`/projects/${state.project.project_id}/images/${element.dataset.referenceEnabled}`, {method:"PUT",body:{review:element.checked ? "pending" : "excluded"}}).then(refreshImages).catch(error => notice(error.message,true));
      }
      if (element.id === "studioCaptionMethod" || element.id === "studioCaptionModel") {
        $("#studioCaptionModelField").hidden = ["wd14","pixai"].includes($("#studioCaptionMethod").value);
        localStorage.setItem("studio-caption-options-" + state.project.project_id, JSON.stringify({method:$("#studioCaptionMethod").value,model:$("#studioCaptionModel").value}));
      }
    });
    $("#studioWildcardV2").addEventListener("focusin", event => {
      if (event.target.matches("[data-v2-pool]")) void loadWildcardV2Pools();
    });
    $("#studioWildcardV2").addEventListener("focusout", event => {
      if (event.target.matches("[data-v2-short]")) {
        queueMicrotask(() => { if (state.project) renderWildcardV2(state.project.studio); });
      }
    });
    $("#studioWildcardV2").addEventListener("paste", event => {
      const short = event.target;
      if (!short.matches("[data-v2-short]")) return;
      const text = event.clipboardData?.getData("text/plain").replace(/\r\n?/g, "\n") || "";
      if (!text.includes("\n")) return;
      event.preventDefault();
      const [start, end] = [short.selectionStart, short.selectionEnd];
      const slot = short.closest("[data-v2-category]");
      const editor = slot.querySelector("[data-v2-long]");
      state.v2Editor = slot.dataset.v2Category;
      renderWildcardV2(state.project.studio);
      editor.setRangeText(text.slice(0, editor.maxLength - editor.value.length + end - start), start, end, "end");
      setWildcardV2Value(short.dataset.v2Setting, editor.value);
      editor.focus();
    });
    $("#studioPage").addEventListener("click", event => {
      const button = event.target.closest("button");
      if (!button) return;
      if (button.dataset.v2Preset) {
        setWildcardV2Preset(button.dataset.v2Preset);
        return;
      }
      if (button.dataset.v2Tag) {
        const {v2TagGroup:key, v2Tag:tag} = button.dataset;
        const filters = state.project.studio.wildcard_v2.tag_filters || {};
        const selected = filters[key] || [];
        setWildcardV2Value("tag_filters", {...filters,
          [key]:selected.includes(tag) ? selected.filter(value => value !== tag) : [...selected, tag]});
        return;
      }
      if (button.dataset.v2Mode) {
        const slot = button.closest("[data-v2-category]");
        const key = slot.dataset.v2Category;
        if (button.dataset.v2Mode !== "fixed" && state.v2Editor === key) state.v2Editor = "";
        setWildcardV2Value(`${key}_mode`, button.dataset.v2Mode);
        if (button.dataset.v2Mode === "fixed") {
          const input = slot.querySelector("[data-v2-short]");
          if (!input.hidden && (key === "character" || !input.value)) input.focus();
        } else if (button.dataset.v2Mode === "wildcard") {
          slot.querySelector("[data-v2-pool]").focus();
        }
        return;
      }
      if (button.dataset.v2Expand) {
        const key = button.dataset.v2Expand;
        state.v2Editor = state.v2Editor === key ? "" : key;
        renderWildcardV2(state.project.studio);
        if (state.v2Editor) button.closest("[data-v2-category]").querySelector("[data-v2-long]").focus();
        return;
      }
      if (button.dataset.graphFilter) {
        state.graphFilter = button.dataset.graphFilter;
        renderTaggerImageList(state.images.filter(image => image.kind === "candidate" && image.review !== "excluded"), true);
      }
      if (button.dataset.captionMode) {
        persistCaptionDraft();
        state.graphCaptionMode = button.dataset.captionMode;
        renderGraphEditor(state.images.find(item => item.item_id === state.selectedImage));
      }
      if (button.id === "taggerAddBox") {
        state.graphDrawMode = !state.graphDrawMode;
        button.setAttribute("aria-pressed", String(state.graphDrawMode));
        notice(state.graphDrawMode ? "在圖片上拖曳以新增物件框線。" : "已取消新增框線。");
      }
      if (button.id === "taggerFitCanvas") {
        state.graphZoom = 100;
        resizeGraphCanvas();
        $("#taggerZoomValue").textContent = "100%";
        $(".tagger-canvas-scroll").scrollTo({top:0,left:0,behavior:"smooth"});
      }
      if (button.id === "taggerExportPng") action(button, exportGraphPng);
      if (button.id === "taggerAddTag") {
        const tag = $("#taggerNewTag").value.trim();
        if (tag) updateGraphTags(tags => tags.includes(tag) ? tags : [...tags, tag]);
      }
      if (button.hasAttribute("data-graph-remove-tag")) updateGraphTags(tags => tags.filter(tag => tag !== button.dataset.graphRemoveTag));
      if (button.id === "taggerAddRelation") action(button, async () => addGraphRelation());
      if (button.hasAttribute("data-delete-relation-source")) removeGraphRelation(button.dataset.deleteRelationSource, button.dataset.deleteRelationTarget);
      if (button.hasAttribute("data-delete-vertex")) removeGraphVertex(button.dataset.deleteVertex);
      if (button.dataset.studioStep) return action(button, async () => {
        await saveCurrent();
        await openProject(state.project.project_id, button.dataset.studioStep);
      });
      if (button.dataset.imagePreview) {
        const image = state.images.find(item => item.item_id === button.dataset.imagePreview);
        $("#studioLargeImageMount").innerHTML = `<img src="${escape(image.image_url)}" alt="${escape(image.title)}">`;
        $("#studioImageProvenance").textContent = JSON.stringify(image.provenance, null, 2);
        $("#studioImageDialog").showModal();
      }
      if (button.dataset.review) action(button, async () => {
        await api(`/projects/${state.project.project_id}/images/${button.dataset.item}`, {method:"PUT",body:{review:button.dataset.review}});
        await refreshImages();
      });
      if (button.dataset.repair) action(button, async () => {
        await saveCurrent();
        if(window.SodaWorkbench){const image=state.images.find(item=>item.item_id===button.dataset.repair);await window.SodaWorkbench.repair(image.asset_id);return;}
        await api(`/projects/${state.project.project_id}/images/${button.dataset.repair}/repair`, {method:"POST"});
        const identifier = state.project.project_id;
        state.project = null;
        await openProject(identifier, "generate");
        notice("已將圖片加入參考素材，可修改提示詞並生成修正版。ComfyUI 請設定參考圖輸入。");
      });
      if (button.id === "studioFindDuplicates") action(button, async () => {
        const result = await api(`/projects/${state.project.project_id}/duplicates`, {method:"POST"});
        const imageById = id => state.images.find(item => item.item_id === id);
        $("#studioDuplicateResults").innerHTML = result.groups.length ? result.groups.slice(0,100).map(group => `<article class="studio-duplicate-pair"><p>相似度距離 ${group.distance}，請比較後挑選。</p><div class="studio-image-grid">${[group.left_files[0],group.right_files[0]].map(id => imageCard(imageById(id))).join("")}</div></article>`).join("") : "<p>沒有找到近似圖片。</p>";
      });
      if (button.dataset.captionImage) renderCaptionEditor(button.dataset.captionImage);
      if (button.hasAttribute("data-graph-vertex")) selectGraphVertex(button.dataset.graphVertex);
      if (button.hasAttribute("data-graph-zoom")) {
        state.graphZoom = Math.max(30, Math.min(200, state.graphZoom + Number(button.dataset.graphZoom)));
        resizeGraphCanvas();
        $("#taggerZoomValue").textContent = `${state.graphZoom}%`;
      }
      if (button.dataset.jobCancel) action(button, async () => { await api(`/jobs/${button.dataset.jobCancel}/cancel`, {method:"POST"}); await refreshImages(); });
      if (button.dataset.jobRetry) action(button, async () => { await api(`/jobs/${button.dataset.jobRetry}/retry`, {method:"POST"}); await refreshImages(); });
      if (button.id === "studioPreviewBatch" || button.id === "studioDrawOnce") action(button, () => previewBatch(button.id === "studioDrawOnce" ? 1 : undefined));
      if (button.id === "studioQueueBatch") action(button, queueBatch);
      if (button.id === "studioLockDraw") {
        if (!state.preview?.rows?.length) return notice("先點抽一次，再鎖定抽取結果。", true);
        recipeFieldsFromPreview(state.preview.rows[0]);
      }
      if (button.id === "studioImportWorkflow") $("#studioWorkflowFile").click();
      if (button.id === "studioToggleRows") {
        const container = $("#studioPrefixRows");
        if (!state.project.studio.prefix_rows.length) {
          state.project.studio.prefix_rows = state.project.studio.prefix.split(/\n/).filter(Boolean).map(text => ({text,enabled:true}));
          renderPrefixRows();
          markChanged();
        }
        container.hidden = !container.hidden;
      }
      if (button.id === "studioAddPrefixRow") { state.project.studio.prefix_rows.push({text:"",enabled:true}); renderPrefixRows(); markChanged(); }
      if (button.hasAttribute("data-row-delete")) { state.project.studio.prefix_rows.splice(Number(button.dataset.rowDelete), 1); renderPrefixRows(); markChanged(); }
      if (button.hasAttribute("data-row-up")) {
        const index = Number(button.dataset.rowUp);
        const rows = state.project.studio.prefix_rows;
        if (index > 0) [rows[index - 1],rows[index]] = [rows[index],rows[index - 1]];
        renderPrefixRows(); markChanged();
      }
      if (button.id === "studioOpenWordlists") $("#studioWordlistDialog").showModal();
      if (button.id === "studioChooseMaterial") openMaterialPicker();
      if (button.id === "studioApproveVisible") action(button, async () => {
        const filter = $("#studioReviewFilter").value;
        const images = state.images.filter(image => image.kind === "candidate" && (filter === "all" || image.review === filter));
        for (const image of images) await api(`/projects/${state.project.project_id}/images/${image.item_id}`, {method:"PUT",body:{review:"approved"}});
        await refreshImages();
      });
      if (button.id === "studioApplyCaptionJson") {
        try {
          const form = $("#studioCaptionForm");
          const value = JSON.parse(form.elements.json.value);
          ["long","medium","short"].forEach(name => { form.elements[name].value = value[name] || ""; });
          form.elements.confirmed.checked = false;
          persistCaptionDraft();
        } catch { notice("標注 JSON 格式有誤，請檢查括號與引號。", true); }
      }
      if (button.id === "studioCaptionBatch") action(button, async () => {
        const taggerMode = document.body.dataset.appView === "tagger";
        const items = state.images.filter(image => image.kind === "candidate" && (taggerMode ? image.review !== "excluded" : image.review === "approved") && !image.caption_confirmed && (!taggerMode || !state.captionSelection.size || state.captionSelection.has(image.item_id))).map(image => image.item_id);
        if (!items.length) return notice("目前沒有可打標的圖片。", true);
        if (window.ensureCaptionModels && !await window.ensureCaptionModels($("#studioCaptionMethod").value)) return;
        for (let index=0; index<items.length; index+=200) {
          await api(`/projects/${state.project.project_id}/caption`, {method:"POST",body:{item_ids:items.slice(index,index+200), model:$("#studioCaptionModel").value, method:$("#studioCaptionMethod").value}});
        }
        notice("標注任務已加入佇列。");
        await refreshImages();
      });
      if (button.id === "studioTaggerSelectAll") {
        state.captionSelection = new Set(state.images.filter(image => image.kind === "candidate" && image.review !== "excluded" && !image.caption_confirmed).map(image => image.item_id));
        renderImages();
      }
      if (button.id === "studioTaggerClear") { state.captionSelection.clear(); renderImages(); }
      if (button.id === "studioExport") action(button, async () => {
        await saveCurrent();
        const result = await api(`/projects/${state.project.project_id}/exports`, {method:"POST",body:{format:$("#studioExportFormat").value}});
        const link = document.createElement("a");
        link.href = result.download_url;
        link.textContent = `下載交付包 · ${result.image_count} 張圖片`;
        link.download = "";
        const paragraph = document.createElement("p");
        paragraph.append(link);
        $("#studioExports").prepend(paragraph);
        notice("交付包已建立。");
      });
    });
    $("#studioPage").addEventListener("submit", event => {
      if (event.target.id !== "studioCaptionForm") return;
      event.preventDefault();
      const form = event.target;
      action(event.submitter || form.querySelector('[type="submit"]'), async () => {
        const caption = JSON.parse(form.elements.json.value || "{}");
        ["long","medium","short"].forEach(name => { caption[name] = form.elements[name].value; });
        if (caption.graph) {
          caption.graph.detail_caption = caption.long;
          caption.graph.short_caption = caption.short;
          const root = caption.graph.vertices?.find(vertex => vertex.label === "image");
          if (root) (root.descs || []).forEach(description => {
            if (description.label === "detail") description.text = caption.long;
            if (description.label === "short") description.text = caption.short;
          });
        }
        await api(`/projects/${state.project.project_id}/images/${state.selectedImage}`, {method:"PUT",body:{caption,caption_confirmed:form.elements.confirmed.checked}});
        localStorage.removeItem(captionKey(state.selectedImage));
        $("#studioCaptionSaveState").textContent = "標注已保存";
        await refreshImages();
      });
    });
    $("#studioWorkflowFile").addEventListener("change", event => {
      const file = event.target.files[0];
      event.target.value = "";
      if (!file) return;
      action($("#studioImportWorkflow"), async () => {
        const parameters = new URLSearchParams({filename:file.name,label:file.name.replace(/\.json$/i,""),target:state.project.target_profile});
        const workflow = await api(`/workflows?${parameters}`, {method:"POST",body:file});
        await bootstrap();
        bindStudioWorkflow(state.project.studio, workflow);
        populateRecipe();
        markChanged();
        await saveCurrent();
        notice(`已匯入 ${workflow.node_count} 個節點，可調整欄位對應。`);
      });
    });
    $("#studioAnnotationFiles").addEventListener("change", async event => {
      const files = Array.from(event.target.files);
      event.target.value = "";
      try {
        const records = [];
        for (const file of files) {
          const text = await file.text();
          records.push({filename:file.name,annotation:file.name.toLowerCase().endsWith(".txt") ? {long:text} : JSON.parse(text)});
        }
        const result = await api(`/projects/${state.project.project_id}/annotations/import`, {method:"POST",body:{records}});
        await refreshImages();
        if (state.selectedImage) renderCaptionEditor(state.selectedImage);
        notice(`已匯入 ${result.item_ids.length} 份標注。${result.errors.map(item => item.filename + " " + item.error).join("；")}`, Boolean(result.errors.length));
      } catch(error) { notice(error.message, true); }
    });
    document.addEventListener("click", event => {
      const close = event.target.closest("[data-studio-close]");
      if (close) document.getElementById(close.dataset.studioClose).close();
    });
    $("#studioWordlistSelect").addEventListener("change", event => {
      const item = state.bootstrap.wordlists.find(item => item.name === event.target.value);
      const form = $("#studioWordlistForm");
      form.elements.name.value = item?.name || "";
      form.elements.content.value = item?.content || "";
    });
    $("#studioWordlistForm").addEventListener("submit", event => {
      event.preventDefault();
      const form = event.target;
      action(event.submitter || form.querySelector('[type="submit"]'), async () => {
        await api("/wordlists", {method:"PUT",body:{name:form.elements.name.value,content:form.elements.content.value}});
        await bootstrap();
        renderWordlists();
        $("#studioWordlistStatus").textContent = "詞庫已保存";
      });
    });
    $("#studioMaterialSearch").addEventListener("submit", async event => {
      event.preventDefault();
      const query = event.target.elements.query.value;
      try {
        const response = await fetch("/api/search?" + new URLSearchParams({query,limit:"20"}));
        const result = await response.json();
        if (!response.ok) throw new Error("素材搜尋失敗");
        const items = result.results || result.items || [];
        $("#studioMaterialResults").innerHTML = items.map((item,index) => `<article class="studio-material-result"><strong>${escape(item.title || item.name || "")}</strong><p>${escape(item.prompt || item.text || item.content || "")}</p><button type="button" data-material-index="${index}">${state.materialSelection ? "加入角色" : "加入所選欄位"}</button></article>`).join("") || "<p>沒有找到符合的素材。</p>";
        $("#studioMaterialResults").onclick = click => {
          const button = click.target.closest("[data-material-index]");
          if (!button) return;
          const item = items[Number(button.dataset.materialIndex)];
          if (state.materialSelection) {
            if (state.materialSelection(item) === false) return;
            button.textContent = "已加入";
            button.disabled = true;
            return;
          }
          const name = $("#studioMaterialField").value;
          const text = item.prompt || item.text || item.content || "";
          state.project.studio[name] = [state.project.studio[name],text].filter(Boolean).join("\n");
          populateRecipe();
          markChanged();
          button.textContent = "已加入";
          button.disabled = true;
        };
      } catch (error) { $("#studioMaterialResults").textContent = error.message; }
    });
    $("#studioProviderForm").addEventListener("submit", event => {
      event.preventDefault();
      const form = event.target;
      action(event.submitter || form.querySelector('[type="submit"]'), async () => {
        const run = state.providerFormRun;
        const provider = Object.fromEntries(new FormData(form));
        provider.capabilities = {references:form.elements.references.checked};
        const result = await api("/settings", {method:"PUT",body:{provider}});
        if (run === state.providerFormRun) {
          form.elements.id.value = result.saved_provider_id;
          if (form.elements.api_key.value === provider.api_key) form.elements.api_key.value = "";
        }
        await bootstrap();
        renderSettings();
        if (state.project) populateRecipe();
        if (run !== state.providerFormRun) return;
        notice("圖片連線已保存。", false, "#studioSettingsStatus");
      });
    });
    $("#studioNewProvider").addEventListener("click", () => {
      state.providerFormRun++;
      $("#studioProviderForm").reset();
      $("#studioProviderForm").elements.id.value = "";
      clearProviderModels();
    });
    $("#studioConnectionList").addEventListener("click", event => {
      const button = event.target.closest("[data-edit-provider],[data-delete-provider]");
      if (!button) return;
      const id = button.dataset.editProvider || button.dataset.deleteProvider;
      const provider = state.bootstrap.connections.providers.find(item => item.id === id);
      if (!provider) return;
      if (button.dataset.deleteProvider) {
        state.deletingProviderId = id;
        $("#studioDeleteProviderName").textContent = provider.label;
        $("#studioDeleteProviderDialog").showModal();
        return;
      }
      state.providerFormRun++;
      const form = $("#studioProviderForm");
      ["id","label","kind","base_url","model"].forEach(name => { form.elements[name].value = provider[name]; });
      form.elements.api_key.value = "";
      form.elements.references.checked = provider.capabilities?.references !== false;
      clearProviderModels();
    });
    $("#studioConfirmDeleteProvider").addEventListener("click", event => action(event.currentTarget, async () => {
      const id = state.deletingProviderId;
      if (!id) return;
      await api("/providers/" + encodeURIComponent(id), {method:"DELETE"});
      const form = $("#studioProviderForm");
      if (form.elements.id.value === id) {
        state.providerFormRun++;
        form.reset();
        form.elements.id.value = "";
        clearProviderModels();
      }
      await bootstrap();
      renderSettings();
      if (state.project) populateRecipe();
      if (state.deletingProviderId === id) {
        state.deletingProviderId = "";
        $("#studioDeleteProviderDialog").close();
      }
      notice("圖片連線已刪除。", false, "#studioSettingsStatus");
    }));
    $("#studioProviderForm").addEventListener("input", event => {
      if (["base_url", "api_key"].includes(event.target.name)) clearProviderModels();
    });
    $("#studioProviderForm").elements.kind.addEventListener("change", clearProviderModels);
    $("#studioDiscoverProviderModels").addEventListener("click", event => action(event.currentTarget, async () => {
      const form = $("#studioProviderForm");
      if (!form.elements.base_url.reportValidity()) return;
      clearProviderModels();
      const run = state.providerDiscoveryRun;
      const controller = new AbortController();
      state.providerDiscoveryController = controller;
      notice("正在抓取模型…", false, "#studioProviderModelsStatus");
      try {
        const result = await api("/providers/models", {method:"POST", body:Object.fromEntries(new FormData(form)), signal:controller.signal});
        if (run !== state.providerDiscoveryRun) return;
        const models = result.models;
        $("#studioProviderModelSelect").innerHTML = '<option value="">' + (window.t?.("選擇抓取的模型") || "選擇抓取的模型") + '</option>' + models.map(model => `<option value="${escape(model.id)}" data-i18n-ignore>${escape(model.name)}</option>`).join("");
        $("#studioProviderModelSelect").value = models.some(model => model.id === form.elements.model.value) ? form.elements.model.value : "";
        $("#studioProviderModelSelectField").hidden = !models.length;
        notice(models.length ? (window.t?.("已抓取模型") || "已抓取模型") + " " + models.length : "模型清單為空，可手動填寫。", false, "#studioProviderModelsStatus");
      } catch (error) {
        if (run === state.providerDiscoveryRun) {
          const http = error.message.match(/HTTP (\d+)/);
          const message = http ? (window.t?.("模型清單請求失敗，HTTP") || "模型清單請求失敗，HTTP") + " " + http[1] : (window.t?.(error.message) || error.message);
          notice(message, true, "#studioProviderModelsStatus");
        }
      } finally {
        if (run === state.providerDiscoveryRun) state.providerDiscoveryController = null;
      }
    }));
    $("#studioProviderModelSelect").addEventListener("change", event => {
      if (event.target.value) $("#studioProviderForm").elements.model.value = event.target.value;
    });
    $("#studioManageChatModels").addEventListener("click", () => window.openModelEndpoints());
    $("#studioLocalToolsForm").addEventListener("submit", event => {
      event.preventDefault();
      const form = event.target;
      action(event.submitter || form.querySelector('[type="submit"]'), async () => {
        await api("/settings", {method:"PUT",body:{comfy_root:form.elements.comfy_root.value}});
        notice("本機工具目錄已保存。", false, "#studioSettingsStatus");
      });
    });
    $("#studioWorkerForm").addEventListener("submit", event => {
      event.preventDefault();
      const form = event.target;
      action(event.submitter || form.querySelector('[type="submit"]'), async () => {
        await api("/settings", {method:"PUT",body:{caption_worker:Object.fromEntries(new FormData(form))}});
        notice("標注工作器設定已保存。", false, "#studioSettingsStatus");
      });
    });
    $("#studioOpenModels").addEventListener("click", () => {
      if (window.openOptionalModels) window.openOptionalModels();
      else window.setPromptHubView("creative");
    });
    $("#studioRestoreDraft").addEventListener("click", async () => {
      if (!state.pendingDraft) return;
      state.project.studio = state.pendingDraft.studio;
      state.pendingDraft = null;
      $("#studioDraftRecovery").hidden = true;
      populateRecipe(); markChanged();
    });
    $("#studioDiscardDraft").addEventListener("click", () => {
      localStorage.removeItem(draftKey(state.project.project_id));
      state.pendingDraft = null;
      $("#studioDraftRecovery").hidden = true;
    });
    setInterval(async () => {
      if (!["studio","creative","datasets","tagger"].includes(window.PromptHubNavigation.current()?.view) || !state.project) return;
      try {
        const jobs = await api(`/projects/${state.project.project_id}/jobs`);
        const changed = JSON.stringify(jobs) !== JSON.stringify(state.jobs);
        state.jobs = jobs;
        if (changed) { renderJobs(); await refreshImages(); }
      } catch { }
    }, 4000);
  });

  function openMaterialPicker(onSelect) {
    state.materialSelection = onSelect || null;
    $("#studioMaterialDialog h2").textContent = onSelect ? "從詞庫加入角色" : "從素材庫選詞";
    $("#studioMaterialField").closest("label").hidden = Boolean(onSelect);
    $("#studioMaterialDialog").showModal();
  }

  window.SodaStudio = {
    current: () => state,
    save: saveCurrent,
    chooseMaterial: openMaterialPicker,
    reloadConnections: async () => {
      await bootstrap();
      if (state.project) populateRecipe();
      renderSettings();
    },
    setFields: fields => {
      if (!state.project) return;
      const recipe = state.project.studio;
      const wasV2 = wildcardV2Active(recipe);
      Object.assign(recipe, fields);
      if (!wasV2 && wildcardV2Active(recipe) && recipe.wildcard_v2_sampling_family !== recipe.wildcard_v2.family) {
        applyWildcardV2SamplingPreset(recipe);
      }
      populateRecipe();
      markChanged();
    },
    refresh: refreshImages,
  };

  function recipeFieldsFromPreview(row) {
    const recipe = state.project.studio;
    ["prefix","body","negative","suffix"].forEach(name => { recipe[name] = row[name]; });
    recipe.prefix_rows = [];
    recipe.text_mode = "manual";
    recipe.locks.body = true;
    populateRecipe();
    markChanged();
    notice("已將抽取結果填入欄位並鎖定。");
  }
})();
