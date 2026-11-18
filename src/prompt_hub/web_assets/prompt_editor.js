(() => {
  "use strict";
  const escape = value => String(value).replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
  const t = value => window.promptHubI18n?.t(value) || value;
  const attached = new WeakMap();
  let active = null;
  let requestSerial = 0;
  let installTarget = null;
  const suggestions = document.createElement("div");
  suggestions.id = "studioPromptSuggestions";
  suggestions.className = "studio-prompt-suggestions";
  suggestions.setAttribute("role", "listbox");
  suggestions.hidden = true;
  document.body.append(suggestions);

  function history(key) {
    try { return JSON.parse(localStorage.getItem("soda-prompt-history-" + key) || "[]"); }
    catch { return []; }
  }

  function remember(key, text) {
    if (!text.trim()) return;
    const entries = history(key);
    if (entries[0]?.text === text) return;
    try {
      localStorage.setItem("soda-prompt-history-" + key, JSON.stringify([
        {text, at: new Date().toISOString()}, ...entries.filter(entry => entry.text !== text),
      ].slice(0, 30)));
    } catch {
      const status = document.querySelector("#studioStatus");
      if (status) status.textContent = t("提示詞歷史空間不足，請確認目前內容已保存。");
    }
  }

  function markup(text) {
    return String(text).split(/(artist:[^,\n]+|[-+]?\d+(?:\.\d+)?::|[{}\[\]]|\b(?:masterpiece|very aesthetic|best quality|amazing quality|no text)\b)/g).map(part => {
      const kind = part.startsWith("artist:") ? "artist"
        : /^[-+]?\d+(?:\.\d+)?::$/.test(part) || /^[{}\[\]]$/.test(part) ? "weight"
        : /^(masterpiece|very aesthetic|best quality|amazing quality|no text)$/.test(part) ? "quality" : "";
      return kind ? `<span class="canvas-token-${kind}">${escape(part)}</span>` : escape(part);
    }).join("") + "\n";
  }

  function highlight(textarea) {
    const layer = textarea.parentElement.querySelector(".creation-highlight-text");
    if (!layer) return;
    layer.innerHTML = markup(textarea.value);
    layer.scrollTop = textarea.scrollTop;
    layer.scrollLeft = textarea.scrollLeft;
  }

  function tokenAt(textarea) {
    const cursor = textarea.selectionStart;
    const text = textarea.value;
    const boundary = Math.max(text.lastIndexOf(",", cursor - 1), text.lastIndexOf("\n", cursor - 1));
    const token = text.slice(boundary + 1, cursor);
    const prefix = /^\s*(?:[-+]?\d+(?:\.\d+)?::)?(?:artist:)?/.exec(token)[0];
    const query = token.slice(prefix.length).trim();
    if (query.length < 2 || query.length > 100) return null;
    const remaining = text.slice(cursor).search(/[,\n]|::/);
    return {query, start: boundary + 1 + prefix.length, end: remaining < 0 ? text.length : cursor + remaining};
  }

  function closeSuggestions() {
    requestSerial++;
    active = null;
    installTarget = null;
    suggestions.hidden = true;
  }

  function choose(index) {
    if (!active || !active.textarea.isConnected) return;
    const {textarea, token, items} = active;
    if (!items[index]) return;
    const suffix = textarea.value.slice(token.end);
    const separator = suffix.startsWith(",") || suffix.startsWith("::") ? "" : ", ";
    textarea.setRangeText(items[index].tag + separator, token.start, token.end, "end");
    closeSuggestions();
    textarea.dispatchEvent(new Event("input", {bubbles: true}));
    textarea.focus({preventScroll: true});
  }

  async function complete(textarea) {
    const token = tokenAt(textarea);
    closeSuggestions();
    if (!token || textarea !== document.activeElement) return;
    const serial = requestSerial;
    try {
      const response = await fetch("/api/tag-completions?q=" + encodeURIComponent(token.query) + "&limit=12");
      if (!response.ok) return;
      const data = await response.json();
      if (serial !== requestSerial || !textarea.isConnected || textarea !== document.activeElement) return;
      const rect = textarea.getBoundingClientRect();
      suggestions.style.left = Math.max(8, Math.min(rect.left, innerWidth - 288)) + "px";
      suggestions.style.width = Math.min(Math.max(280, rect.width), innerWidth - 16) + "px";
      suggestions.style.top = Math.min(rect.bottom, innerHeight - 200) + "px";
      if (!data.installed) {
        installTarget = textarea;
        suggestions.innerHTML = `<button type="button" data-install-prompt-tags>${t("安裝標籤庫以啟用補全")}</button>`;
        suggestions.hidden = false;
        return;
      }
      if (!data.results?.length) return;
      active = {textarea, token, items: data.results, selected: 0};
      suggestions.innerHTML = data.results.map((item, index) => `<button type="button" role="option" data-prompt-suggestion="${index}" aria-selected="${index === 0}"><span data-i18n-ignore>${escape(item.tag)}</span><small data-i18n-ignore>${escape(item.translation_zh || "")}</small></button>`).join("");
      suggestions.hidden = false;
    } catch { if (serial === requestSerial) closeSuggestions(); }
  }

  function attach(textarea, key, withHighlight = false) {
    const existing = attached.get(textarea);
    if (existing) { existing.key = key; highlight(textarea); return; }
    const binding = {key, timer: null};
    attached.set(textarea, binding);
    if (withHighlight && !textarea.closest(".creation-highlight-editor")) {
      const wrapper = document.createElement("div");
      wrapper.className = "creation-highlight-editor";
      wrapper.dataset.highlight = "true";
      const layer = document.createElement("div");
      layer.className = "creation-highlight-text";
      layer.setAttribute("aria-hidden", "true");
      textarea.before(wrapper);
      wrapper.append(layer, textarea);
    }
    const save = () => { clearTimeout(binding.timer); remember(binding.key, textarea.value); };
    textarea.addEventListener("input", event => {
      highlight(textarea);
      clearTimeout(binding.timer);
      binding.timer = setTimeout(save, 900);
      if (!event.isComposing) complete(textarea);
    });
    textarea.addEventListener("blur", () => { save(); setTimeout(() => {if (active?.textarea === textarea) closeSuggestions();}, 0); });
    textarea.addEventListener("scroll", () => { highlight(textarea); closeSuggestions(); });
    textarea.addEventListener("keydown", event => {
      if (event.isComposing || active?.textarea !== textarea) return;
      if (event.key === "Escape") { event.preventDefault(); closeSuggestions(); }
      if (["ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        active.selected = (active.selected + (event.key === "ArrowDown" ? 1 : -1) + active.items.length) % active.items.length;
        [...suggestions.children].forEach((button, index) => button.setAttribute("aria-selected", String(index === active.selected)));
        suggestions.children[active.selected].scrollIntoView({block: "nearest"});
      }
      if (["Enter", "Tab"].includes(event.key)) { event.preventDefault(); choose(active.selected); }
    });
    remember(key, textarea.value);
    highlight(textarea);
  }

  function showHistory(textarea, key) {
    const entries = history(key);
    const dialog = document.createElement("dialog");
    dialog.className = "studio-dialog studio-prompt-history";
    dialog.innerHTML = `<header><h2>${t("提示詞歷史")}</h2><button type="button" data-history-close>${t("關閉")}</button></header><div>${entries.length ? entries.map((entry, index) => `<button type="button" data-history-entry="${index}"><time>${escape(new Date(entry.at).toLocaleString())}</time><span data-i18n-ignore>${escape(entry.text)}</span></button>`).join("") : `<p>${t("尚無歷史記錄")}</p>`}</div>`;
    dialog.addEventListener("click", event => {
      if (event.target.closest("[data-history-close]")) dialog.close();
      const button = event.target.closest("[data-history-entry]");
      if (!button || !textarea.isConnected) return;
      remember(key, textarea.value);
      textarea.value = entries[Number(button.dataset.historyEntry)].text;
      textarea.dispatchEvent(new Event("input", {bubbles: true}));
      dialog.close();
      textarea.focus({preventScroll: true});
    });
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog);
    dialog.showModal();
  }

  suggestions.addEventListener("mousedown", event => {
    if (event.target.closest("[data-install-prompt-tags]")) event.preventDefault();
    const button = event.target.closest("[data-prompt-suggestion]");
    if (button) { event.preventDefault(); choose(Number(button.dataset.promptSuggestion)); }
  });
  suggestions.addEventListener("click", async event => {
    const button = event.target.closest("[data-install-prompt-tags]");
    if (!button || button.disabled) return;
    const target = installTarget;
    button.disabled = true;
    button.textContent = t("正在安裝標籤庫…");
    try {
      const response = await fetch("/api/tag-completions/download", {method: "POST"});
      const result = await response.json();
      if (!response.ok) throw Error(result.detail || t("安裝失敗"));
      async function poll() {
        const response = await fetch("/api/jobs/" + result.job.job_id);
        const job = await response.json();
        if (job.status === "completed") {
          if (target?.isConnected) { target.focus({preventScroll: true}); await complete(target); }
          return;
        }
        if (["failed", "canceled"].includes(job.status)) {
          button.textContent = job.error || t("安裝失敗");
          button.disabled = false;
          return;
        }
        setTimeout(() => poll().catch(error => {button.textContent = error.message; button.disabled = false;}), 1500);
      }
      await poll();
    } catch (error) { button.textContent = error.message; button.disabled = false; }
  });
  window.addEventListener("resize", closeSuggestions);
  window.addEventListener("scroll", event => {
    if (!(event.target instanceof Node) || !suggestions.contains(event.target)) closeSuggestions();
  }, true);
  window.SodaPromptEditor = {attach, markup, highlight, remember, history, showHistory, tokenAt};
})();
