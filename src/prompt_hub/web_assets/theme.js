(() => {
  "use strict";
  const key = "soda-prompt-hub-theme-v1";
  const choices = new Set(["dark", "light", "system"]);
  const system = window.matchMedia("(prefers-color-scheme: dark)");
  let preference = "dark";
  try {
    const saved = localStorage.getItem(key);
    if (choices.has(saved)) preference = saved;
  } catch { }

  function apply(value, persist = true) {
    preference = choices.has(value) ? value : "dark";
    document.documentElement.dataset.theme = preference === "system"
      ? (system.matches ? "dark" : "light") : preference;
    document.documentElement.dataset.themePreference = preference;
    if (persist) {
      try { localStorage.setItem(key, preference); } catch { }
    }
    document.querySelectorAll("[data-theme-select]").forEach(select => {
      select.value = preference;
    });
  }

  apply(preference, false);
  document.addEventListener("DOMContentLoaded", () => apply(preference, false), {once:true});
  document.addEventListener("change", event => {
    if (event.target.matches("[data-theme-select]")) apply(event.target.value);
  });
  system.addEventListener("change", () => {
    if (preference === "system") apply(preference, false);
  });
  window.addEventListener("storage", event => {
    if (event.key === key) apply(event.newValue || "dark", false);
  });
})();
