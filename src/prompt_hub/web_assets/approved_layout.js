(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const agentLayout = $(".agent-layout");
  const panel = document.createElement("aside");
  panel.className = "agent-right-panel";
  panel.innerHTML = '<h2>本次使用</h2><div id="agentCurrentTools"></div><details class="agent-tool-log"><summary>工具執行記錄</summary><pre id="agentToolLog"></pre></details>';
  agentLayout.append(panel);
  const tools = panel.querySelector("#agentCurrentTools");
  tools.append($(".agent-sidebar > details"));
  tools.append($("#agentImageProvider").closest("label"), $("#agentConnections"));
  $(".agent-sidebar .workbench-heading").prepend($("#agentNewChat"));
  $(".agent-sidebar h2").textContent = "會話";
  const label = $("#agentComposer > label");
  label.classList.remove("sr-only");
  label.textContent = "訊息與參考圖";
  new MutationObserver(() => {
    const jobs = [...$("#agentMessages").querySelectorAll("[data-agent-job], [data-agent-tool-result]")].map(element => element.textContent).filter(Boolean);
    $("#agentToolLog").textContent = jobs.join("\n\n") || (window.promptHubI18n?.t("目前沒有工具執行記錄") || "目前沒有工具執行記錄");
  }).observe($("#agentMessages"), {childList: true, subtree: true, characterData: true});

  const form = $("#onlineGalleryForm");
  const feed = $("#onlineFeed");
  feed.closest("label").hidden = true;
  const modes = document.createElement("div");
  modes.className = "online-feed-buttons";
  modes.setAttribute("aria-label", "畫廊瀏覽方式");
  modes.innerHTML = '<button type="button" data-online-feed="search">搜尋</button><button type="button" data-online-feed="popular">熱門</button><button type="button" data-online-feed="favorites">本地收藏</button><button type="button" data-online-feed="remote_favorites">遠端收藏</button>';
  form.insertBefore(modes, $("#onlineQuery").closest("label"));
  const random = document.createElement("button");
  random.type = "button";
  random.id = "onlineRandomBrowse";
  random.textContent = "隨機瀏覽";
  modes.after(random);
  $("#onlineQuery").closest("label").classList.add("online-query-field");
  const submit = form.querySelector('button[type="submit"]');
  submit.textContent = "篩選";
  function updateModes() {
    modes.querySelectorAll("button").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.onlineFeed === feed.value));
      button.disabled = feed.querySelector(`option[value="${button.dataset.onlineFeed}"]`).disabled;
    });
    random.setAttribute("aria-pressed", String(feed.value === "random"));
  }
  modes.addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button) return;
    feed.value = button.dataset.onlineFeed;
    feed.dispatchEvent(new Event("change", {bubbles: true}));
    updateModes();
  });
  random.addEventListener("click", () => { feed.value = "random"; form.requestSubmit(); updateModes(); });
  $("#onlineSource").addEventListener("change", updateModes);
  updateModes();
})();
