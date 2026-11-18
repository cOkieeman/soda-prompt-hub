/* Port of NAI Launcher v4.3.1 GalleryDetailDialogView, MediaViewer and InfoPanel. */
(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, character => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[character]);
  const dialog = $("#onlineImage").closest("dialog");
  const nodes = {};
  for (const id of ["onlineTitle", "onlineClose", "onlineImage", "onlineMediaChoices", "onlineSourceLink", "onlinePrompt", "onlineFavorite", "onlineRemoteFavorite", "onlineSendPrompt", "onlineSave", "onlineDataset", "onlineMetadata", "onlineDetailStatus"]) nodes[id] = document.getElementById(id);
  const paths = {
    heart: "M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z",
    external: "M14 3h7v7m0-7L10 14M10 3H3v18h18v-7",
    x: "m6 6 12 12M18 6 6 18", left: "m15 5-7 7 7 7", right: "m9 5 7 7-7 7",
    download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
    save: "M12 3v12m-4-4 4 4 4-4M3 16v5h18v-5",
    scan: "M3 8V3h5m8 0h5v5m0 8v5h-5M8 21H3v-5M8 8h8M8 12h5M8 16h8",
    sparkles: "m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z",
    copy: "M8 8h13v13H8V8ZM16 4V2H2v14h2",
    eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12ZM15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
    user: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 21v-2a8 8 0 0 1 16 0v2",
    zoom: "M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Zm-2 5 6 6M7 10h6m-3-3v6",
  };
  const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"></path></svg>`;
  const mediaUrl = url => "/api/online-gallery/media?url=" + encodeURIComponent(url);
  const translate = text => window.promptHubI18n?.t(text) || text;
  dialog.classList.add("online-gallery-viewer");
  dialog.tabIndex = -1;
  dialog.setAttribute("aria-labelledby", "onlineTitle");
  dialog.innerHTML = `
    <header class="online-viewer-header"><span id="onlineSourceBadge" class="online-source-badge"></span><div class="online-viewer-title"><div id="onlineTitleMount"></div><small id="onlineByline"></small></div><div id="onlineHeaderActions" class="online-header-actions"></div></header>
    <p id="onlineViewerLoading" role="status" hidden></p>
    <div class="online-viewer-layout">
      <section class="online-viewer-media"><div class="online-image-stage" id="onlineImageStage"><div id="onlineImageMount"></div><span id="onlineImageCounter" class="online-image-counter"></span><button type="button" id="onlineMediaPrevious" class="online-image-arrow" aria-label="上一張圖片">${icon("left")}</button><button type="button" id="onlineMediaNext" class="online-image-arrow online-image-next" aria-label="下一張圖片">${icon("right")}</button><div class="online-image-action-rail"><button type="button" id="onlineRailSend" aria-label="送到創作台">${icon("sparkles")}</button><a id="onlineDownload" aria-label="下載原圖" download>${icon("download")}</a><button type="button" id="onlineReverse" aria-label="反推圖片提示詞">${icon("scan")}</button><div id="onlineSaveMount"></div></div><button type="button" id="onlineZoom" class="online-zoom-hint">${icon("zoom")}<span>雙擊縮放</span></button><span id="onlineImageFormat" class="online-image-format"></span><p id="onlineImageError" class="online-image-error" role="status" hidden></p></div><div id="onlineThumbnailsMount" class="online-thumbnails"></div></section>
      <aside class="online-viewer-info"><div class="online-viewer-info-scroll"><div class="online-viewer-stats" id="onlineViewerStats"></div><div class="online-viewer-facts" id="onlineViewerFacts"></div><section id="onlineTagsSection"><h3>標籤</h3><div id="onlineViewerTags" class="online-viewer-tags"></div></section><section class="online-info-card" id="onlineNoteSection"><h3>備註</h3><div id="onlineViewerNote" data-i18n-ignore></div></section><section class="online-info-card" id="onlinePromptSection"><header><h3>正面提示詞</h3><button type="button" id="onlineCopyPrompt" aria-label="複製提示詞">${icon("copy")}</button></header><div id="onlinePromptMount"></div></section><section class="online-info-card" id="onlineNegativeSection" hidden><h3>負面提示詞</h3><pre id="onlineNegative" data-i18n-ignore></pre></section><section class="online-info-card" id="onlineJsonSection"><header><h3>Raw JSON</h3><div><button type="button" id="onlineExpandJson" aria-expanded="false">展開全文</button><button type="button" id="onlineCopyJson" aria-label="複製 JSON">${icon("copy")}</button></div></header><div id="onlineJsonMount"></div></section><p id="onlineViewerAuthor"></p></div><footer class="online-viewer-primary-actions"><div id="onlinePrimarySend"></div><div id="onlinePrimaryDataset"></div><div id="onlineViewerStatus"></div></footer></aside>
    </div>`;
  const mounts = {onlineTitle: "onlineTitleMount", onlineClose: "onlineHeaderActions", onlineSourceLink: "onlineHeaderActions", onlineFavorite: "onlineHeaderActions", onlineRemoteFavorite: "onlinePrimaryDataset", onlineImage: "onlineImageMount", onlineMediaChoices: "onlineThumbnailsMount", onlinePrompt: "onlinePromptMount", onlineSendPrompt: "onlinePrimarySend", onlineSave: "onlineSaveMount", onlineDataset: "onlinePrimaryDataset", onlineMetadata: "onlineJsonMount", onlineDetailStatus: "onlineViewerStatus"};
  for (const [id, mount] of Object.entries(mounts)) document.getElementById(mount).append(nodes[id]);
  $("#onlineHeaderActions").append(nodes.onlineFavorite, nodes.onlineSourceLink, nodes.onlineClose);
  nodes.onlineClose.innerHTML = icon("x");
  nodes.onlineClose.setAttribute("aria-label", "關閉圖片詳情");
  nodes.onlineSourceLink.innerHTML = icon("external");
  nodes.onlineSourceLink.setAttribute("aria-label", "開啟來源");
  nodes.onlineSave.innerHTML = icon("save");
  nodes.onlineSave.setAttribute("aria-label", "保存到畫廊");
  nodes.onlineSendPrompt.innerHTML = icon("sparkles") + "<span>發送到創作台</span>";
  nodes.onlineDataset.innerHTML = "<span>加入資料集</span>";
  const state = {item: null, media: [], index: 0, scale: 1, x: 0, y: 0, pointers: new Map(), pinch: 0};

  function applyZoom() { nodes.onlineImage.style.transform = `translate(${state.x}px, ${state.y}px) scale(${state.scale})`; }
  function resetZoom() { state.scale = 1; state.x = 0; state.y = 0; state.pinch = 0; state.pointers.clear(); applyZoom(); }
  function select(index) {
    if (index < 0 || index >= state.media.length) return;
    $("#onlineMediaChoices").querySelector(`[data-online-media="${index}"]`)?.click();
  }
  function favorite() {
    nodes.onlineFavorite.innerHTML = icon("heart");
    nodes.onlineFavorite.setAttribute("aria-label", translate(state.item?.favorite ? "取消收藏" : "收藏"));
    nodes.onlineFavorite.setAttribute("aria-pressed", String(Boolean(state.item?.favorite)));
  }
  function loading(message = "正在載入詳情…") {
    state.item = null;
    state.media = [];
    dialog.setAttribute("aria-busy", "true");
    dialog.querySelector(".online-viewer-layout").hidden = true;
    $("#onlineViewerLoading").hidden = false;
    $("#onlineViewerLoading").textContent = translate(message);
    $("#onlineByline").textContent = "";
    $("#onlineSourceBadge").textContent = "";
    nodes.onlineFavorite.disabled = true;
    nodes.onlineSourceLink.removeAttribute("href");
  }
  function show(item) {
    dialog.removeAttribute("aria-busy");
    dialog.querySelector(".online-viewer-layout").hidden = false;
    $("#onlineViewerLoading").hidden = true;
    nodes.onlineFavorite.disabled = false;
    state.item = item;
    state.media = item.media?.length ? item.media : item.original_url ? [{url: item.original_url, prompt: item.prompt, negative: item.negative, metadata: item.metadata}] : [];
    state.index = Math.min(item.media_index || 0, Math.max(0, state.media.length - 1));
    const medium = state.media[state.index] || {};
    const metadata = item.metadata || {};
    const work = metadata.work || metadata;
    const imageData = medium.metadata || {};
    const sourceNames = {aitag: "AI TAG", quicktagcloud: "QuickTagCloud", danbooru: "Danbooru", safebooru: "Safebooru", gelbooru: "Gelbooru"};
    $("#onlineSourceBadge").textContent = sourceNames[item.source] || item.source;
    const author = work.userName || work.author_name || work.username || work.author?.name || work.author?.username || work.author || work.user_name || metadata.author?.username || metadata.author?.name || metadata.user?.username || metadata.user?.nickname || metadata.user?.name || imageData.author_name || imageData.author_id || "";
    const authorText = typeof author === "object" ? author.name || author.username || "" : String(author);
    const date = work.create_date || work.created_at || work.uploaded_at || metadata.created_at || "";
    $("#onlineByline").textContent = [authorText, date].filter(Boolean).join(" · ");
    $("#onlineViewerAuthor").innerHTML = authorText ? icon("user") + " " + translate("作者") + " <span data-i18n-ignore>" + escape(authorText) + "</span>" : "";
    $("#onlineViewerStats").innerHTML = [["瀏覽", work.total_view ?? work.view_count ?? work.views, "eye"], ["收藏", work.total_bookmarks ?? work.favorite_count ?? work.favorites_count ?? work.fav_count ?? work.like_count ?? item.score, "heart"]].filter(row => row[1] !== undefined).map(([label, number, glyph]) => `<div>${icon(glyph)}<span><small>${translate(label)}</small><strong>${Number(number).toLocaleString()}</strong></span></div>`).join("");
    const facts = item.source === "quicktagcloud" ? [metadata.codexTitle || "", ...(Array.isArray(metadata.categoryPath) ? metadata.categoryPath : [])] : ["#" + item.id, imageData.image_type || work.ai_type || work.type || "", state.media.length + " " + translate("張圖片")];
    $("#onlineViewerFacts").innerHTML = facts.filter(Boolean).map(value => `<span>${escape(value)}</span>`).join("");
    const tags = Array.isArray(item.tags) ? item.tags : [];
    $("#onlineTagsSection").hidden = !tags.length || item.source === "quicktagcloud";
    $("#onlineViewerTags").innerHTML = tags.map(tag => `<span>${escape(typeof tag === "object" ? tag.name || tag.tag || "" : tag)}</span>`).join("");
    const note = String(work.caption || work.description || work.note || metadata.note || "").replace(/<br\s*\/?\s*>/gi, "\n").replace(/<[^>]*>/g, "");
    $("#onlineNoteSection").hidden = !note;
    $("#onlineViewerNote").textContent = note;
    nodes.onlinePrompt.textContent = medium.prompt || item.prompt || "";
    nodes.onlineSendPrompt.disabled = !nodes.onlinePrompt.textContent.trim();
    $("#onlinePromptSection").hidden = !nodes.onlinePrompt.textContent.trim();
    $("#onlineNegative").textContent = medium.negative || item.negative || "";
    $("#onlineNegativeSection").hidden = !$("#onlineNegative").textContent;
    let raw = imageData.ai_json || medium.metadata || item.metadata;
    if (typeof raw === "string") { try { raw = JSON.parse(raw); } catch { /* Preserve source text. */ } }
    nodes.onlineMetadata.textContent = typeof raw === "string" ? raw : JSON.stringify(raw || {}, null, 2);
    $("#onlineJsonSection").hidden = item.source !== "aitag" || !nodes.onlineMetadata.textContent || nodes.onlineMetadata.textContent === "{}";
    $("#onlineImageCounter").textContent = state.media.length ? `${state.index + 1} / ${state.media.length}` : "";
    $("#onlineMediaPrevious").hidden = state.index === 0;
    $("#onlineMediaNext").hidden = state.index >= state.media.length - 1;
    $("#onlineImageError").hidden = true;
    if (medium.url) {
      nodes.onlineImage.src = mediaUrl(medium.url);
      $("#onlineDownload").href = mediaUrl(medium.url) + "&download=true";
      const extension = new URL(medium.url).pathname.split(".").pop();
      $("#onlineImageFormat").textContent = extension.length < 6 ? extension.toUpperCase() : "";
    }
    $("#onlineRailSend").disabled = nodes.onlineSendPrompt.disabled;
    $("#onlineMediaChoices").innerHTML = state.media.map((media, index) => `<button type="button" data-online-media="${index}" aria-label="第 ${index + 1} 張圖片" aria-pressed="${index === state.index}"><img src="${escape(mediaUrl(media.thumbnail_url || media.url))}" alt="" loading="lazy"></button>`).join("");
    favorite();
    resetZoom();
    dialog.focus({preventScroll: true});
  }
  $("#onlineMediaPrevious").addEventListener("click", () => select(state.index - 1));
  $("#onlineMediaNext").addEventListener("click", () => select(state.index + 1));
  dialog.addEventListener("keydown", event => {
    if (event.target.closest("input,textarea,select")) return;
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); select(state.index + (event.key === "ArrowLeft" ? -1 : 1)); }
  });
  $("#onlineRailSend").addEventListener("click", () => nodes.onlineSendPrompt.click());
  $("#onlineReverse").addEventListener("click", async event => {
    event.currentTarget.disabled = true;
    try { await window.SodaOnlineGallery.reverse(); }
    catch (error) { nodes.onlineDetailStatus.textContent = error.message; }
    finally { $("#onlineReverse").disabled = false; }
  });
  $("#onlineExpandJson").addEventListener("click", event => { const expanded = $("#onlineJsonSection").classList.toggle("online-json-expanded"); event.currentTarget.setAttribute("aria-expanded", String(expanded)); event.currentTarget.textContent = translate(expanded ? "收起全文" : "展開全文"); });
  async function copy(selector) { try { await navigator.clipboard.writeText($(selector).textContent); nodes.onlineDetailStatus.textContent = translate("已複製"); } catch { nodes.onlineDetailStatus.textContent = translate("複製失敗，請選取文字複製"); } }
  $("#onlineCopyJson").addEventListener("click", () => copy("#onlineMetadata"));
  $("#onlineCopyPrompt").addEventListener("click", () => copy("#onlinePrompt"));
  function zoom() { state.scale = state.scale > 1 ? 1 : 2; state.x = 0; state.y = 0; applyZoom(); }
  $("#onlineZoom").addEventListener("click", zoom);
  nodes.onlineImage.addEventListener("dblclick", zoom);
  nodes.onlineImage.draggable = false;
  const stage = $("#onlineImageStage");
  stage.addEventListener("pointerdown", event => {
    if (event.target.closest("button,a")) return;
    state.pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    stage.setPointerCapture(event.pointerId);
    if (state.pointers.size === 2) { const [a, b] = [...state.pointers.values()]; state.pinch = Math.hypot(a.x - b.x, a.y - b.y); }
  });
  stage.addEventListener("pointermove", event => {
    const previous = state.pointers.get(event.pointerId);
    if (!previous) return;
    state.pointers.set(event.pointerId, {x: event.clientX, y: event.clientY});
    if (state.pointers.size === 2) {
      const [a, b] = [...state.pointers.values()];
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      if (state.pinch) state.scale = Math.min(5, Math.max(1, state.scale * distance / state.pinch));
      state.pinch = distance;
    } else if (state.scale > 1) { state.x += event.clientX - previous.x; state.y += event.clientY - previous.y; }
    applyZoom();
  });
  for (const name of ["pointerup", "pointercancel", "lostpointercapture"]) stage.addEventListener(name, event => { state.pointers.delete(event.pointerId); state.pinch = 0; });
  nodes.onlineImage.addEventListener("error", () => { $("#onlineImageError").hidden = false; $("#onlineImageError").textContent = translate("圖片載入失敗，請重新開啟或下載原圖。"); });
  window.SodaOnlineViewer = {show, favorite, loading};
})();
