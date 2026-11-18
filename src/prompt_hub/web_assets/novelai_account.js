(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const t = value => window.promptHubI18n?.t(value) || value;
  const dialog = $("#naiAccountDialog");
  const form = $("#naiAccountForm");
  const select = $("#naiAccountSelect");
  const state = {mode: "token", busy: false, session: null, run: 0};
  const current = () => window.SodaStudio.current();
  const selectedProvider = () => current().bootstrap?.connections.providers.find(
    provider => provider.id === current().project?.studio.provider_id && provider.kind === "novelai"
  );

  async function api(path, body) {
    const response = await fetch("/api/studio/novelai/" + path, {
      method: body ? "POST" : "GET", headers: {"Content-Type": "application/json"},
      body: body ? JSON.stringify(body) : undefined,
    });
    const result = await response.json();
    if (!response.ok) throw Error(typeof result.detail === "string" ? result.detail : t("請求失敗"));
    return result;
  }

  function status(message, error = false) {
    $("#naiAccountStatus").textContent = t(message);
    $("#naiAccountStatus").dataset.error = String(error);
  }

  function renderButton() {
    const button = $("#naiAccountButton");
    button.hidden = $("[data-generation-engine='novelai']").getAttribute("aria-pressed") !== "true";
    const provider = selectedProvider();
    const invalid = provider?.novelai_account?.authentication_status === "invalid";
    button.textContent = t(invalid ? "重新登入 NovelAI" : provider?.has_api_key ? "NovelAI 帳號" : "登入 NovelAI");
    button.disabled = state.busy;
  }

  function renderAccounts(identifier = current().project?.studio.provider_id || "") {
    select.replaceChildren(new Option(t("加入新帳號"), ""));
    for (const provider of current().bootstrap?.connections.providers || []) {
      if (provider.kind === "novelai" && ["https://image.novelai.net", "https://api.novelai.net"].includes(provider.base_url)) {
        select.add(new Option(provider.label, provider.id));
      }
    }
    select.value = identifier;
    if (select.selectedIndex < 0) select.value = "";
  }

  function renderSession(session) {
    state.session = session;
    const account = session.subscription;
    $("#naiAccountCached").hidden = true;
    $("#naiAccountSummary").hidden = !session.provider?.has_api_key;
    form.elements.label.value = session.provider?.label || "";
    $("#naiSubscriptionTier").textContent = account?.tier || t("尚未驗證");
    $("#naiAnlasBalance").textContent = account ? String(Number(account.fixed_anlas) + Number(account.purchased_anlas)) : "—";
    $("#naiSubscriptionExpiry").textContent = account?.expires_at ? new Date(account.expires_at * 1000).toLocaleDateString(window.promptHubI18n?.getLocale()) : "—";
    $("#naiUsageRow").hidden = !account?.usage;
    $("#naiUsage").textContent = account?.usage ? `${account.usage.isNegative ? "−" : ""}${account.usage.percent}%` : "";
  }

  async function session(refresh = false) {
    const run = ++state.run;
    const identifier = select.value;
    const result = await api(`session?provider_id=${encodeURIComponent(identifier)}&refresh=${refresh}`);
    if (run === state.run && identifier === select.value) {
      renderSession(result);
      if (result.error) status(result.error, true);
    }
    return result;
  }

  async function action(callback) {
    if (state.busy) return;
    state.busy = true;
    dialog.setAttribute("aria-busy", "true");
    dialog.querySelectorAll("button:not(#naiAccountClose),select").forEach(element => {element.disabled = true;});
    try { await callback(); }
    catch (error) {
      status(error.message, true);
      if (state.session?.subscription) $("#naiAccountCached").hidden = false;
    }
    finally {
      state.busy = false;
      dialog.removeAttribute("aria-busy");
      dialog.querySelectorAll("button,select").forEach(element => {element.disabled = false;});
      form.elements.password.value = "";
      form.elements.token.value = "";
      renderButton();
    }
  }

  async function open() {
    if (state.busy) return;
    form.reset();
    setMode("token");
    renderAccounts();
    renderSession({provider: selectedProvider()});
    status("");
    dialog.showModal();
    await action(async () => {
      await session();
      if (state.session?.provider?.has_api_key) {
        status("正在驗證帳號…");
        const result = await session(true);
        await window.SodaStudio.reloadConnections();
        status(result.error || "帳號已驗證", Boolean(result.error));
      }
    });
  }

  function setMode(mode) {
    state.mode = mode;
    status("");
    const credentials = mode === "credentials";
    $("#naiTokenFields").hidden = credentials;
    $("#naiCredentialsFields").hidden = !credentials;
    form.elements.token.disabled = credentials;
    form.elements.token.required = !credentials;
    for (const name of ["email", "password"]) {
      form.elements[name].disabled = !credentials;
      form.elements[name].required = credentials;
    }
    form.elements.password.value = "";
    form.elements.token.value = "";
    $("#naiShowSecret").checked = false;
    form.elements.password.type = "password";
    form.elements.token.type = "password";
    dialog.querySelectorAll("[data-nai-login-mode]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.naiLoginMode === mode));
    });
  }

  $("#naiAccountButton").addEventListener("click", open);
  $("#naiAccountClose").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {form.elements.password.value = ""; form.elements.token.value = ""; state.run++;});
  dialog.querySelectorAll("[data-nai-login-mode]").forEach(button => button.addEventListener("click", () => setMode(button.dataset.naiLoginMode)));
  $("#naiShowSecret").addEventListener("change", event => {
    form.elements.token.type = form.elements.password.type = event.target.checked ? "text" : "password";
  });
  select.addEventListener("change", () => action(async () => {
    status("");
    const provider = current().bootstrap?.connections.providers.find(item => item.id === select.value);
    renderSession({provider});
    if (select.value) window.SodaStudio.setFields({provider_id: select.value});
    await session();
    if (state.session?.provider?.has_api_key) await session(true);
    await window.SodaStudio.reloadConnections();
  }));
  form.addEventListener("submit", event => {
    event.preventDefault();
    const projectId = current().project?.project_id;
    const run = ++state.run;
    action(async () => {
      status("正在驗證帳號…");
      const values = Object.fromEntries(new FormData(form));
      const result = await api("login", {...values, mode: state.mode, provider_id: select.value});
      await window.SodaStudio.reloadConnections();
      if (run !== state.run || current().project?.project_id !== projectId) return;
      window.SodaStudio.setFields({provider_id: result.provider.id});
      await window.SodaStudio.save();
      if (run !== state.run) return;
      renderAccounts(result.provider.id);
      renderSession(result);
      status("登入成功");
    });
  });
  $("#naiAccountRefresh").addEventListener("click", () => action(async () => {
    status("正在驗證帳號…");
    const result = await session(true);
    await window.SodaStudio.reloadConnections();
    status(result.error || "帳號已驗證", Boolean(result.error));
  }));
  $("#naiAccountLogout").addEventListener("click", () => action(async () => {
    await api("logout", {provider_id: select.value});
    await window.SodaStudio.reloadConnections();
    await session();
    status("已登出此帳號");
  }));
  $("#naiThirdPartySettings").addEventListener("click", async () => {
    dialog.close();
    await window.setPromptHubView("settings");
    const providerForm = $("#studioProviderForm");
    providerForm.reset();
    providerForm.elements.id.value = "";
    providerForm.elements.kind.value = "novelai";
    providerForm.elements.model.value = "nai-diffusion-4-5-full";
    providerForm.elements.base_url.focus();
  });
  document.addEventListener("click", event => {
    if (!event.target.closest("#studioQueueBatch") || current().project?.studio.backend !== "novelai") return;
    const provider = selectedProvider();
    const official = !provider || ["https://image.novelai.net", "https://api.novelai.net"].includes(provider.base_url);
    if (official && (!provider?.has_api_key || provider.novelai_account?.authentication_status === "invalid")) {
      event.preventDefault();
      event.stopImmediatePropagation();
      open();
    }
  }, true);
  window.addEventListener("soda-studio-populated", renderButton);
  new MutationObserver(renderButton).observe($("[data-generation-engine='novelai']"), {attributes: true, attributeFilter: ["aria-pressed"]});
  renderButton();
})();
