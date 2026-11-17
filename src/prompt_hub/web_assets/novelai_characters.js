/* Character cards and position modes ported from NAI Launcher v4.3.1. */
(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const t = value => window.promptHubI18n?.t(value) || value;
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
  const paths = {
    female: "M16 8a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 12v9m-3-3h6",
    male: "M14 14a5 5 0 1 1-7-7 5 5 0 0 1 7 7Zm0-4 7-7m-6 0h6v6",
    other: "M16 13a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 17v5m-3-2h6M15 10l6-7m-5 0h5v5M9 10 3 4m0 5V4h5",
    library: "M3 4h5v17H3V4Zm7 0h5v17h-5V4Zm7 1 4-1 3 16-4 1-3-16Z",
    check: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Zm-14 0 3 3 7-7",
    circle: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
    more: "M5 12h.01M12 12h.01M19 12h.01",
    position: "M12 2v20M2 12h20M9 5l3-3 3 3M9 19l3 3 3-3M5 9l-3 3 3 3M19 9l3 3-3 3",
    trash: "M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7",
    x: "m6 6 12 12M18 6 6 18",
  };
  const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"></path></svg>`;
  const genderNames = {female: "女性", male: "男性", other: "其他"};
  const section = $("#creationCharacters");
  const content = $("#creationCharactersContent");
  const cards = $("#naiCharacters");
  const jsonDetails = $("#studioCharacters").closest("details");
  const state = {selected: "", tab: "prompt", project: "", drag: null};
  const recipe = () => window.SodaStudio.current().project?.studio;
  const key = (character, index) => character.id || `legacy-${index}`;
  function gender(character) {
    if (Object.hasOwn(genderNames, character.gender)) return character.gender;
    if (/\b(?:1boy|boy|male)\b/i.test(character.prompt)) return "male";
    return /\b(?:1girl|girl|female)\b/i.test(character.prompt) ? "female" : "other";
  }

  section.querySelector(".creation-character-shortcuts").innerHTML =
    ["female", "male", "other"].map(name => `<button type="button" data-character-add="${name}" data-gender="${name}" aria-label="${t("加入角色")} ${t(genderNames[name])}">${icon(name)}<span>${t({female: "女", male: "男", other: "其他"}[name])}</span></button>`).join("") +
    `<button type="button" id="creationCharacterLibrary">${icon("library")}<span>${t("詞庫")}</span></button>`;
  content.innerHTML = `<div class="nai-character-tools" id="naiCharacterTools"><div role="group" aria-label="${t("角色位置模式")}"><button type="button" data-character-mode="ai">${t("AI 選擇")}</button><button type="button" data-character-mode="custom">${t("自訂")}</button><button type="button" id="naiOpenPositions" aria-label="${t("角色位置畫布")}">${icon("position")}</button></div><button type="button" id="naiClearCharacters" aria-label="${t("清空全部角色")}">${icon("trash")}</button></div><div id="naiCharacterCardsMount"></div><p id="naiCharacterStatus" role="status"></p>`;
  $("#naiCharacterCardsMount").append(cards);
  jsonDetails.hidden = true;
  content.append(jsonDetails);
  const positionDialog = document.createElement("dialog");
  positionDialog.id = "naiPositionDialog";
  positionDialog.className = "studio-dialog nai-position-dialog";
  positionDialog.innerHTML = `<header><h2>${t("角色位置畫布")}</h2><button type="button" id="naiClosePositions" aria-label="${t("關閉角色位置畫布")}">${icon("x")}</button></header><div class="nai-position-mode"><button type="button" data-character-mode="ai">${t("AI 選擇")}</button><button type="button" data-character-mode="custom">${t("自訂")}</button></div><div class="nai-composition-guides"><label>${t("構圖參考線")}<select id="naiCompositionGuide"><option value="none">${t("無參考線")}</option><option value="thirds">${t("三分法")}</option><option value="phi">${t("黃金分割")}</option><option value="grid">${t("網格")}</option></select></label><label>${t("網格數量")}<input id="naiCompositionCount" type="number" min="2" max="12" value="3"></label></div><p id="naiPositionHelp"></p><div class="nai-position-stage"><div id="naiPositionBoard"></div></div><div id="naiPositionChips"></div>`;
  document.body.append(positionDialog);
  const clearDialog = document.createElement("dialog");
  clearDialog.id = "naiClearCharactersDialog";
  clearDialog.className = "studio-dialog";
  clearDialog.innerHTML = `<h2>${t("清空全部角色？")}</h2><div class="workbench-actions"><button type="button" id="naiCancelClearCharacters">${t("取消")}</button><button type="button" id="naiConfirmClearCharacters">${t("清空全部角色")}</button></div>`;
  document.body.append(clearDialog);

  function persistCharacters(characters, redraw = true) {
    if (redraw) {
      window.SodaStudio.setFields({characters});
      return;
    }
    $("#studioCharacters").value = JSON.stringify(characters);
    $("#studioCharacters").dispatchEvent(new Event("change", {bubbles: true}));
  }

  function addCharacter(value = {}) {
    if (!recipe() || recipe().characters.length >= 6) {
      $("#naiCharacterStatus").textContent = t("最多加入六個角色");
      return false;
    }
    const character = {
      id: crypto.randomUUID(), name: `Character ${recipe().characters.length + 1}`,
      prompt: "", negative: "", enabled: true, x: .5, y: .5, gender: "other", ...value,
    };
    state.selected = "";
    persistCharacters([...recipe().characters, character]);
    section.open = true;
    return true;
  }

  function historyKey(character, field) {
    return state.project + "-character-" + character.id + "-" + field;
  }

  function editor(character, index) {
    const custom = recipe().character_position_mode === "custom";
    const field = state.tab;
    return `<div class="nai-character-editor"><div class="nai-character-editor-tabs">
      <button type="button" data-character-tab="prompt" aria-pressed="${field === "prompt"}">${t("正面")}</button>
      <button type="button" data-character-tab="negative" aria-pressed="${field === "negative"}">${t("負面")}</button>
      <button type="button" data-character-action="history">${t("歷史")}</button>
      <button type="button" data-character-action="highlight" aria-label="${t("提示詞語法高亮")}">Tt</button>
      <button type="button" class="nai-character-clear" data-character-action="clear" aria-label="${t("清除角色提示詞")}">${icon("x")}</button>
      </div><textarea data-character-field="${field}" data-character-index="${index}" aria-label="${t(field === "prompt" ? "角色正向" : "角色負面")}" placeholder="${t(field === "prompt" ? "填寫角色外觀、服裝與動作" : "填寫此角色的負面提示詞")}" rows="4" spellcheck="false">${escape(character[field] || "")}</textarea>
      <label class="nai-character-thumbnail-upload">${t("角色頭像")}<input type="file" data-character-thumbnail accept="image/png,image/jpeg,image/webp"></label>
      ${custom ? `<div class="nai-character-coordinates"><label>${t("水平位置")}<input type="number" min="0" max="1" step="0.01" data-character-field="x" value="${character.x ?? .5}"></label><label>${t("垂直位置")}<input type="number" min="0" max="1" step="0.01" data-character-field="y" value="${character.y ?? .5}"></label></div>` : ""}</div>`;
  }

  function render() {
    const current = window.SodaStudio.current();
    if (!current.project) return;
    if (state.project !== current.project.project_id) {
      state.project = current.project.project_id;
      state.selected = "";
      positionDialog.close();
      clearDialog.close();
    }
    const values = current.project.studio;
    const provider = current.bootstrap?.connections.providers.find(item => item.id === values.provider_id);
    const model = values.model || provider?.model || "";
    section.hidden = values.backend !== "novelai" || Boolean(model && !/nai-diffusion-[45]/.test(model));
    const characters = values.characters;
    const full = characters.length >= 6;
    section.querySelectorAll("[data-character-add],#creationCharacterLibrary").forEach(button => {
      button.disabled = full;
      button.title = full ? t("最多加入六個角色") : "";
    });
    $("#naiCharacterTools").hidden = !characters.length;
    $("#naiCharacterStatus").textContent = "";
    document.querySelectorAll("[data-character-mode]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.characterMode === (values.character_position_mode || "ai")));
    });
    cards.innerHTML = characters.map((character, index) => {
      const selected = state.selected === key(character, index);
      const kind = gender(character);
      const name = character.name || `Character ${index + 1}`;
      const thumbnail = character.thumbnail_asset_id ? `<img class="nai-character-thumbnail" src="/api/gallery/assets/${escape(character.thumbnail_asset_id)}/media/thumbnail" alt="">` : "";
      const badge = thumbnail + `<span class="nai-character-gender">${icon(kind)}${t(genderNames[kind])}</span>`;
      return `<article class="nai-character" data-character-index="${index}" data-gender="${kind}" data-editing="${selected}" data-enabled="${character.enabled !== false}"><header>${selected ? `${badge}<input class="nai-character-name" data-character-field="name" value="${escape(name)}" aria-label="${t("角色名稱")}">` : `<button type="button" class="nai-character-select" data-character-action="edit">${badge}<strong data-i18n-ignore>${escape(name)}</strong></button>`}<button type="button" class="nai-character-enabled" data-character-action="enabled" aria-label="${t("啟用角色")} ${escape(name)}" aria-pressed="${character.enabled !== false}">${icon(character.enabled !== false ? "check" : "circle")}</button><details class="nai-character-menu"><summary aria-label="${t("角色操作")} ${escape(name)}">${icon("more")}</summary><div><button type="button" data-character-action="up" ${index === 0 ? "disabled" : ""}>${t("上移")}</button><button type="button" data-character-action="down" ${index === characters.length - 1 ? "disabled" : ""}>${t("下移")}</button><button type="button" data-character-action="save">${t("加入詞庫")}</button><button type="button" data-character-action="delete">${t("移除角色")}</button></div></details></header>${selected ? editor(character, index) : `<button type="button" class="nai-character-preview" data-character-action="edit" data-i18n-ignore>${escape(character.prompt || t("點擊編輯角色提示詞"))}</button>`}</article>`;
    }).join("");
    cards.querySelectorAll("textarea[data-character-field]").forEach(textarea => {
      const character = characters[Number(textarea.dataset.characterIndex)];
      window.SodaPromptEditor.attach(textarea, historyKey(character, textarea.dataset.characterField), true);
    });
    if (positionDialog.open) renderPositions();
  }

  function renderPositions() {
    const values = recipe();
    const custom = values.character_position_mode === "custom";
    $("#naiPositionHelp").textContent = t(custom ? "拖曳角色位置，或使用方向鍵微調。" : "AI 會決定角色位置。拖曳位置可切換為自訂。");
    const board = $("#naiPositionBoard");
    board.style.aspectRatio = `${values.width} / ${values.height}`;
    board.style.setProperty("--position-aspect", String(values.width / values.height));
    const enabledCharacters = values.characters.map((character, index) => ({character, index})).filter(({character}) => character.enabled !== false);
    let guide = {mode: "none", count: 3};
    try { guide = {...guide, ...JSON.parse(localStorage.getItem("soda-nai-composition-guide") || "{}")} ; } catch { }
    guide.count = Math.max(2, Math.min(12, Math.round(Number(guide.count) || 3)));
    $("#naiCompositionGuide").value = guide.mode;
    $("#naiCompositionCount").value = guide.count;
    $("#naiCompositionCount").disabled = guide.mode !== "grid";
    const stops = guide.mode === "thirds" ? [1 / 3, 2 / 3] : guide.mode === "phi" ? [.382, .618]
      : guide.mode === "grid" ? Array.from({length: guide.count - 1}, (_, index) => (index + 1) / guide.count) : [];
    const lines = stops.flatMap(stop => ["to right", "to bottom"].map(direction =>
      `linear-gradient(${direction}, transparent calc(${stop * 100}% - .5px), var(--line) calc(${stop * 100}% - .5px), var(--line) calc(${stop * 100}% + .5px), transparent calc(${stop * 100}% + .5px))`));
    board.style.backgroundImage = lines.join(",");
    board.innerHTML = enabledCharacters.map(({character, index}, enabledIndex) => `<button type="button" data-position-character="${index}" data-gender="${gender(character)}" style="left:${(character.x ?? .5) * 100}%;top:${(character.y ?? .5) * 100}%" aria-pressed="${state.selected === key(character, index)}" aria-label="${t("角色位置")} ${escape(character.name || `Character ${index + 1}`)}">${character.thumbnail_asset_id ? `<img src="/api/gallery/assets/${escape(character.thumbnail_asset_id)}/media/thumbnail" alt="">` : ""}<span>${enabledIndex + 1}</span></button>`).join("");
    $("#naiPositionChips").innerHTML = values.characters.map((character, index) => `<button type="button" data-position-select="${index}" data-gender="${gender(character)}" aria-pressed="${state.selected === key(character, index)}" data-i18n-ignore>${escape(character.name || `Character ${index + 1}`)}</button>`).join("");
  }

  async function saveToLibrary(character, button) {
    character.name ||= `Character ${recipe().characters.indexOf(character) + 1}`;
    if (!character.id) {
      character.id = crypto.randomUUID();
      persistCharacters(recipe().characters, false);
    }
    button.disabled = true;
    try {
      const response = await fetch("/api/workbench/characters/library", {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(character),
      });
      const result = await response.json();
      if (!response.ok) throw Error(result.detail || t("保存失敗"));
      $("#naiCharacterStatus").textContent = t("角色已保存至提示詞庫");
    } catch (error) {
      $("#naiCharacterStatus").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  section.addEventListener("click", event => {
    const add = event.target.closest("[data-character-add]");
    if (add) {
      event.preventDefault();
      const kind = add.dataset.characterAdd;
      addCharacter({gender: kind, prompt: {female: "girl,", male: "boy,", other: ""}[kind]});
    }
    if (event.target.closest("#creationCharacterLibrary")) {
      event.preventDefault();
      window.SodaStudio.chooseMaterial(item => addCharacter({
        name: item.title || item.name || "Character", prompt: item.prompt || item.content || item.text || "",
        negative: item.negative_content || "", gender: item.metadata?.gender || "other", thumbnail_asset_id: item.metadata?.thumbnail_asset_id || "",
      }));
    }
    if (event.target.closest("#naiOpenPositions")) {
      renderPositions();
      positionDialog.showModal();
    }
    if (event.target.closest("#naiClearCharacters")) clearDialog.showModal();
  });

  cards.addEventListener("click", event => {
    const card = event.target.closest("[data-character-index]");
    if (!card) return;
    const index = Number(card.dataset.characterIndex);
    const character = recipe().characters[index];
    const tab = event.target.closest("[data-character-tab]");
    if (tab) {
      state.tab = tab.dataset.characterTab;
      render();
      return;
    }
    const button = event.target.closest("[data-character-action]");
    if (!button) return;
    const action = button.dataset.characterAction;
    if (action === "history") {
      window.SodaPromptEditor.showHistory(card.querySelector("textarea"), historyKey(character, state.tab));
      return;
    }
    if (action === "highlight") {
      const wrapper = card.querySelector(".creation-highlight-editor");
      wrapper.dataset.highlight = String(wrapper.dataset.highlight !== "true");
      button.setAttribute("aria-pressed", wrapper.dataset.highlight);
      return;
    }
    if (action === "save") {
      saveToLibrary(character, button);
      return;
    }
    if (action === "edit") {
      if (!character.id) { character.id = crypto.randomUUID(); persistCharacters(recipe().characters, false); }
      state.selected = state.selected === key(character, index) ? "" : key(character, index);
      state.tab = "prompt";
      render();
      return;
    }
    const characters = structuredClone(recipe().characters);
    if (action === "enabled") characters[index].enabled = character.enabled === false;
    if (action === "clear") {
      window.SodaPromptEditor.remember(historyKey(character, state.tab), character[state.tab] || "");
      characters[index][state.tab] = "";
    }
    if (action === "delete") {
      characters.splice(index, 1);
      state.selected = "";
    }
    const target = index + (action === "up" ? -1 : 1);
    if ((action === "up" || action === "down") && target >= 0 && target < characters.length) {
      [characters[index], characters[target]] = [characters[target], characters[index]];
      state.selected = "";
    }
    persistCharacters(characters);
  });

  cards.addEventListener("input", event => {
    const input = event.target.closest("[data-character-field]");
    if (!input) return;
    const index = Number(input.closest("article").dataset.characterIndex);
    const field = input.dataset.characterField;
    let value = input.value;
    if (field === "x" || field === "y") {
      if (!input.validity.valid || value === "") return;
      value = Number(value);
    }
    const characters = structuredClone(recipe().characters);
    characters[index][field] = value;
    persistCharacters(characters, false);
  });

  cards.addEventListener("change", async event => {
    const input = event.target.closest("[data-character-thumbnail]");
    const file = input?.files[0];
    if (!file) return;
    const projectId = state.project;
    const characterId = recipe().characters[Number(input.closest("article").dataset.characterIndex)].id;
    try {
      const response = await fetch("/api/gallery/import?kind=reference&filename=" + encodeURIComponent(file.name), {
        method: "POST", headers: {"Content-Type": "application/octet-stream"}, body: file,
      });
      const asset = await response.json();
      if (!response.ok) throw Error(asset.detail || t("保存失敗"));
      if (state.project !== projectId) return;
      const characters = structuredClone(recipe().characters);
      const character = characters.find(item => item.id === characterId);
      if (!character) return;
      character.thumbnail_asset_id = asset.asset_id;
      persistCharacters(characters);
    } catch (error) { $("#naiCharacterStatus").textContent = error.message; }
  });

  document.addEventListener("click", event => {
    const mode = event.target.closest("[data-character-mode]");
    if (mode) window.SodaStudio.setFields({character_position_mode: mode.dataset.characterMode});
    if (state.selected && !event.composedPath().includes(section) && !event.target.closest("dialog")) {
      state.selected = "";
      render();
    }
    document.querySelectorAll(".nai-character-menu[open]").forEach(menu => {
      if (!menu.contains(event.target)) menu.open = false;
    });
  });
  $("#naiClosePositions").addEventListener("click", () => positionDialog.close());
  $("#naiCancelClearCharacters").addEventListener("click", () => clearDialog.close());
  $("#naiConfirmClearCharacters").addEventListener("click", () => {
    state.selected = "";
    persistCharacters([]);
    clearDialog.close();
  });
  $("#naiPositionChips").addEventListener("click", event => {
    const button = event.target.closest("[data-position-select]");
    if (!button) return;
    const index = Number(button.dataset.positionSelect);
    state.selected = key(recipe().characters[index], index);
    renderPositions();
    $("#naiPositionBoard").querySelector(`[data-position-character="${index}"]`)?.focus({preventScroll: true});
  });
  ["naiCompositionGuide", "naiCompositionCount"].forEach(id => $("#" + id).addEventListener("change", () => {
    const count = Math.max(2, Math.min(12, Number($("#naiCompositionCount").value) || 3));
    localStorage.setItem("soda-nai-composition-guide", JSON.stringify({mode: $("#naiCompositionGuide").value, count}));
    renderPositions();
  }));
  const board = $("#naiPositionBoard");
  board.addEventListener("pointerdown", event => {
    const marker = event.target.closest("[data-position-character]");
    if (!marker) return;
    const index = Number(marker.dataset.positionCharacter);
    state.selected = key(recipe().characters[index], index);
    state.drag = {index, marker, rect: board.getBoundingClientRect()};
    board.setPointerCapture(event.pointerId);
  });
  board.addEventListener("pointermove", event => {
    if (!state.drag) return;
    const drag = state.drag;
    drag.x = Math.max(0, Math.min(1, (event.clientX - drag.rect.left) / drag.rect.width));
    drag.y = Math.max(0, Math.min(1, (event.clientY - drag.rect.top) / drag.rect.height));
    drag.marker.style.left = `${drag.x * 100}%`;
    drag.marker.style.top = `${drag.y * 100}%`;
  });
  board.addEventListener("pointerup", () => {
    const drag = state.drag;
    state.drag = null;
    if (drag?.x === undefined) return;
    const characters = structuredClone(recipe().characters);
    Object.assign(characters[drag.index], {x: Number(drag.x.toFixed(3)), y: Number(drag.y.toFixed(3))});
    window.SodaStudio.setFields({characters, character_position_mode: "custom"});
  });
  board.addEventListener("pointercancel", () => {state.drag = null; renderPositions();});
  board.addEventListener("keydown", event => {
    const marker = event.target.closest("[data-position-character]");
    const moves = {ArrowLeft: [-.01, 0], ArrowRight: [.01, 0], ArrowUp: [0, -.01], ArrowDown: [0, .01]};
    if (!marker || !moves[event.key]) return;
    event.preventDefault();
    const index = Number(marker.dataset.positionCharacter);
    const characters = structuredClone(recipe().characters);
    const multiplier = event.shiftKey ? 5 : 1;
    const [x, y] = moves[event.key].map(value => value * multiplier);
    characters[index].x = Math.max(0, Math.min(1, Number(((characters[index].x ?? .5) + x).toFixed(3))));
    characters[index].y = Math.max(0, Math.min(1, Number(((characters[index].y ?? .5) + y).toFixed(3))));
    window.SodaStudio.setFields({characters, character_position_mode: "custom"});
    board.querySelector(`[data-position-character="${index}"]`).focus({preventScroll: true});
  });
  window.addEventListener("soda-studio-populated", render);
})();
