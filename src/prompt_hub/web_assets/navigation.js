(() => {
  "use strict";
  const views = new Set(["home", "projects", "studio", "settings", "creative", "prompts", "gallery",
    "discover", "characters", "datasets", "tagger", "lora", "comfy", "management", "remote"]);
  const steps = new Set(["references", "generate", "review", "caption", "export"]);
  const storageKey = "soda-prompt-hub-route-v1";
  let current = null;
  let restoring = false;
  let scrollPositions = {};
  try { scrollPositions = JSON.parse(sessionStorage.getItem(storageKey + "-scroll") || "{}"); }
  catch { scrollPositions = {}; }

  function normalize(value) {
    const route = {view: views.has(value.view) ? value.view : "home"};
    if (route.view === "remote" && ["tasks", "loras", "models", "endpoints"].includes(value.tab)) {
      route.tab = value.tab;
    }
    if (["studio", "creative", "datasets", "gallery", "tagger"].includes(route.view)) {
      route.project = String(value.project || "");
      if (route.view === "studio" || route.view === "datasets") route.step = steps.has(value.step) ? value.step : "review";
      if (value.engine) route.engine = ["comfyui", "novelai", "agent"].includes(value.engine) ? value.engine : "comfyui";
      if (value.tab) route.tab = String(value.tab);
      if (value.asset) route.asset = String(value.asset);
    }
    return route;
  }

  function key(route) {
    return [route.view, route.project || "", route.step || "", route.engine || "", route.tab || "", route.asset || ""].join("/");
  }

  function capture() {
    if (!current || restoring) return;
    scrollPositions[key(current)] = Math.max(0, window.scrollY || 0);
    try { sessionStorage.setItem(storageKey + "-scroll", JSON.stringify(scrollPositions)); }
    catch { /* Navigation remains available when browser storage is full. */ }
  }

  function read() {
    const parameters = new URLSearchParams(window.location.search);
    if (parameters.has("view")) return normalize(Object.fromEntries(parameters));
    try { return normalize(JSON.parse(localStorage.getItem(storageKey) || '{"view":"home"}')); }
    catch { return {view: "home"}; }
  }

  function commit(value, mode = "push", options = {}) {
    capture();
    clearTimeout(scrollTimer);
    const route = normalize(value);
    const changed = !current || key(current) !== key(route);
    current = route;
    restoring = true;
    const url = new URL(window.location.href);
    ["view", "project", "step", "engine", "tab", "asset"].forEach(name => url.searchParams.delete(name));
    Object.entries(route).forEach(([name, item]) => url.searchParams.set(name, item));
    url.hash = "";
    if (mode !== "none" && (changed || mode === "replace")) {
      window.history[mode === "replace" ? "replaceState" : "pushState"]({route}, "", url);
    }
    try { localStorage.setItem(storageKey, JSON.stringify(route)); } catch { }
    if(options.preserveScroll){scrollPositions[key(route)]=window.scrollY||0;restoring=false;}
    return route;
  }

  function restore(route) {
    const expected = key(route);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (!current || key(current) !== expected) return;
      window.scrollTo({top: scrollPositions[expected] || 0, behavior: "instant"});
      restoring = false;
    }));
  }

  if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";
  window.addEventListener("pagehide", capture);
  let scrollTimer;
  window.addEventListener("scroll", () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(capture, 120);
  }, {passive: true});
  window.addEventListener("popstate", () => {
    window.setPromptHubView?.(read().view, {route: read(), historyMode: "none"});
  });
  window.PromptHubNavigation = {read, commit, restore, capture, current: () => current};
})();
