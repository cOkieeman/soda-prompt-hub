(() => {
  "use strict";
  const host = document.querySelector("#archiveWorkspace");
  const grid = document.querySelector("#results");
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const key = item => item.source_id + "/" + item.external_id;
  let selection = [];
  let results = [];
  let inspected = null;
  let visualIndex = 0;
  let dragged = "";
  try { selection = JSON.parse(localStorage.getItem("soda-library-selection-v1") || "[]"); }
  catch { selection = []; }
  const toolbar = document.createElement("div");
  toolbar.className = "library-toolbar";
  toolbar.innerHTML = '<label>卡片密度<select id="libraryDensity"><option value="compact">紧凑</option><option value="regular">适中</option></select></label><button type="button" id="libraryRefreshLocal">同步本地画风预览</button><span id="libraryLocalStatus" role="status"></span>';
  host.querySelector("main").prepend(toolbar);
  const tabs = document.createElement("div");
  tabs.className = "library-tabs";
  tabs.innerHTML = '<button type="button" data-library-kind="" aria-pressed="true">全部</button><button type="button" data-library-kind="style">画风</button><button type="button" data-library-kind="character_reference">角色</button><button type="button" data-library-kind="tag">服饰与标签</button><button type="button" data-library-kind="prompt">完整提示词</button><button type="button" data-library-kind="modifier">修饰词</button>';
  host.querySelector("main").prepend(tabs);
  const side = document.createElement("aside");
  side.className = "library-selection";
  side.innerHTML = '<h2>当前组合 <span id="librarySelectionCount"></span></h2><div id="librarySelectionList"></div><section id="libraryDetail" class="library-detail" hidden></section><section class="library-compose"><h3>合并预览</h3><label>目标语法<select id="librarySyntax"><option value="plain">原文</option><option value="novelai">NovelAI 权重</option><option value="sd">SD 权重</option></select></label><textarea id="libraryCombined" rows="5" aria-label="组合提示词" readonly></textarea><label>插入字段<select id="librarySlot"><option value="prefix">主题／风格</option><option value="body">正文</option><option value="negative">负面</option><option value="suffix">后缀／署名</option></select></label><button type="button" id="libraryApply" class="library-apply">应用到创作台</button><p id="libraryStatus" role="status" aria-live="polite"></p></section>';
  host.appendChild(side);
  const dialog = document.createElement("dialog");
  dialog.className = "library-image-dialog";
  dialog.innerHTML = '<header><strong id="libraryImageTitle"></strong><button type="button" id="libraryImageClose">关闭</button></header><img id="libraryLargeImage" alt="">';
  document.body.appendChild(dialog);
  const find = selector => side.querySelector(selector);
  const notice = text => { find("#libraryStatus").textContent = text; };
  function save() {
    try { localStorage.setItem("soda-library-selection-v1", JSON.stringify(selection)); }
    catch { notice("组合暂存空间已满，请先复制提示词。"); }
  }
  function combined() {
    const syntax = find("#librarySyntax").value;
    return selection.map(item => {
      const weight = Number(item.weight ?? 1);
      if (weight === 1 || syntax === "plain") return item.content;
      return syntax === "novelai" ? weight + "::" + item.content + "::" : "(" + item.content + ":" + weight + ")";
    }).join("\n\n");
  }
  function renderSelection() {
    find("#librarySelectionCount").textContent = String(selection.length);
    find("#librarySelectionList").innerHTML = selection.map((item,index) => '<div class="library-selection-row" data-selection-key="' + escape(key(item)) + '"><button type="button" class="library-drag" draggable="true" aria-label="拖动排序">⋮⋮</button><span>' + escape(item.title) + '</span><input type="number" min="0" max="20" step="0.05" value="' + Number(item.weight ?? 1) + '" data-library-weight aria-label="' + escape(item.title) + ' 权重"' + (find("#librarySyntax").value === "plain" ? ' disabled' : '') + '><button type="button" data-library-move="-1" aria-label="上移"' + (!index ? ' disabled' : '') + '>↑</button><button type="button" data-library-remove aria-label="移除">×</button></div>').join("") || "<p>点击素材卡片加入组合，可以选择多项。</p>";
    find("#libraryCombined").value = combined();
    find("#libraryApply").disabled = !selection.length;
    grid.querySelectorAll("[data-library-key]").forEach(card => card.setAttribute("aria-pressed", String(selection.some(item => key(item) === card.dataset.libraryKey))));
    save();
  }
  function inspect(item) {
    if (inspected !== item) visualIndex=0;
    inspected = item;
    const detail = find("#libraryDetail");
    detail.hidden = false;
    const visual = item.visuals?.[visualIndex];
    detail.innerHTML = '<h3>' + escape(item.title) + '</h3>' + (visual ? '<img src="' + escape(visual.thumbnail_url) + '" alt="' + escape(item.title) + '"><button type="button" data-library-enlarge>查看大图</button>' : '<p>此条目暂未提供预览。</p>') + '<p>' + escape(item.source_name || item.source_id) + ' · ' + escape(item.model_family || "未标注模型") + '</p><pre>' + escape(item.content) + '</pre><details><summary>负面与来源记录</summary><pre>' + escape(item.negative_content || "") + '</pre><p>' + escape(item.category || "") + '</p>' + (item.source_url ? '<a href="' + escape(item.source_url) + '" target="_blank" rel="noreferrer">查看来源</a>' : '') + '</details><div class="library-toolbar"><button type="button" data-library-favorite>' + (item.favorite ? "已收藏" : "收藏") + '</button><button type="button" data-library-copy>复制原文</button></div><label>备注<textarea id="libraryNote" maxlength="1200" rows="3"></textarea></label><button type="button" data-library-note>保存备注</button>';
    find("#libraryNote").value = item.user_note || "";
    if(item.visuals?.length>1){const controls=document.createElement("div");controls.className="library-toolbar";controls.innerHTML='<button type="button" data-library-shot="-1">上一張</button><span>'+String(visualIndex+1)+' / '+item.visuals.length+'</span><button type="button" data-library-shot="1">下一張</button>';detail.querySelector("img").after(controls);}
  }
  async function request(path, values) {
    const response = await fetch(path, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(values || {})});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "请求失败");
    return data;
  }
  function enlarge() {
    if (!inspected?.visuals?.length) return;
    dialog.querySelector("#libraryImageTitle").textContent = inspected.title;
    const image = dialog.querySelector("#libraryLargeImage");
    image.src = inspected.visuals[visualIndex].original_url;
    image.alt = inspected.title;
    dialog.showModal();
  }
  function render(items) {
    results = items;
    grid.innerHTML = items.map((item,index) => {
      const visual = item.visuals?.[0];
      return '<article class="library-card" data-library-key="' + escape(key(item)) + '" aria-pressed="' + selection.some(selected => key(selected) === key(item)) + '"><button type="button" class="library-card-select" data-library-index="' + index + '">' + (visual ? '<img src="' + escape(visual.thumbnail_url) + '" alt="' + escape(item.title) + '" loading="lazy" decoding="async">' : '<span class="library-no-image">暂无预览</span>') + '<strong>' + escape(item.title) + '</strong><small>' + escape(item.model_family || item.kind) + ' · ' + escape(item.source_name || item.source_id) + '</small></button><button type="button" class="library-inspect" data-library-inspect="' + index + '">查看详情</button></article>';
    }).join("");
    tabs.querySelectorAll("[data-library-kind]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.libraryKind === document.querySelector("#kind").value)));
    selection = selection.map(selected => ({...selected,...(items.find(item => key(item) === key(selected)) || {})}));
    renderSelection();
  }
  grid.addEventListener("click", event => {
    const button = event.target.closest("[data-library-index],[data-library-inspect]");
    if (!button) return;
    const item = results[Number(button.dataset.libraryIndex ?? button.dataset.libraryInspect)];
    inspect(item);
    if (button.hasAttribute("data-library-index")) {
      const index = selection.findIndex(selected => key(selected) === key(item));
      if (index < 0) selection.push({...item,weight:1});
      else selection.splice(index,1);
      renderSelection();
    }
  });
  tabs.addEventListener("click", event => {
    const button = event.target.closest("[data-library-kind]");
    if (button) { document.querySelector("#kind").value = button.dataset.libraryKind; document.querySelector("#searchButton").click(); }
  });
  side.addEventListener("change", event => {
    if (event.target.id === "librarySyntax") renderSelection();
    if (event.target.matches("[data-library-weight]") && event.target.validity.valid) {
      const item = selection.find(item => key(item) === event.target.closest("[data-selection-key]").dataset.selectionKey);
      item.weight = Number(event.target.value);
      find("#libraryCombined").value = combined();
      save();
    }
  });
  side.addEventListener("click", async event => {
    const button = event.target.closest("button");
    if (!button) return;
    const row = button.closest("[data-selection-key]");
    if (row) {
      const index = selection.findIndex(item => key(item) === row.dataset.selectionKey);
      if (button.hasAttribute("data-library-remove")) selection.splice(index,1);
      if (button.hasAttribute("data-library-move") && index > 0) selection.splice(index-1,0,selection.splice(index,1)[0]);
      renderSelection();
    }
    if (button.hasAttribute("data-library-enlarge")) enlarge();
    if (button.hasAttribute("data-library-shot")) {visualIndex=(visualIndex+Number(button.dataset.libraryShot)+inspected.visuals.length)%inspected.visuals.length;inspect(inspected);}
    if (button.hasAttribute("data-library-copy")) navigator.clipboard.writeText(inspected.content).catch(error => notice(error.message));
    if (button.hasAttribute("data-library-favorite") || button.hasAttribute("data-library-note")) {
      const values = {source_id:inspected.source_id,external_id:inspected.external_id,favorite:Boolean(inspected.favorite),note:inspected.user_note || "",rating:inspected.user_rating || null};
      if (button.hasAttribute("data-library-favorite")) values.favorite = !inspected.favorite;
      else values.note = find("#libraryNote").value;
      try {
        const response = await fetch("/api/marks",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(values)});
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "保存失败");
        inspected.favorite = values.favorite;
        inspected.user_note = values.note;
        inspect(inspected); notice("已保存");
      } catch(error) { notice(error.message); }
    }
    if (button.id === "libraryApply") {
      if (window.SodaWorkbench) await window.SodaWorkbench.applySlots({[find("#librarySlot").value]:combined()});
      else notice("创作台正在载入，请稍后重试。");
    }
  });
  side.addEventListener("dragstart", event => {
    if (!event.target.matches(".library-drag")) return;
    dragged = event.target.closest("[data-selection-key]").dataset.selectionKey;
    event.dataTransfer.setData("text/plain",dragged);
  });
  side.addEventListener("dragover", event => { if (dragged && event.target.closest("[data-selection-key]")) event.preventDefault(); });
  side.addEventListener("drop", event => {
    const row = event.target.closest("[data-selection-key]");
    if (!row || !dragged) return;
    event.preventDefault();
    const from = selection.findIndex(item => key(item) === dragged);
    const to = selection.findIndex(item => key(item) === row.dataset.selectionKey);
    if (from >= 0 && to >= 0) selection.splice(to,0,selection.splice(from,1)[0]);
    dragged = ""; renderSelection();
  });
  side.addEventListener("dragend", () => { dragged = ""; });
  dialog.querySelector("#libraryImageClose").addEventListener("click", () => dialog.close());
  toolbar.querySelector("#libraryDensity").addEventListener("change", event => { grid.dataset.density = event.target.value; localStorage.setItem("soda-library-density",event.target.value); });
  grid.dataset.density = localStorage.getItem("soda-library-density") || "compact";
  toolbar.querySelector("#libraryDensity").value = grid.dataset.density;
  toolbar.querySelector("#libraryRefreshLocal").addEventListener("click", async event => {
    const button = event.currentTarget;
    button.disabled = true;
    try { const result = await request("/api/local-styles/sync"); toolbar.querySelector("#libraryLocalStatus").textContent = "已同步 " + result.entries + " 条"; await window.loadPromptHubStats(); document.querySelector("#searchButton").click(); }
    catch(error) { toolbar.querySelector("#libraryLocalStatus").textContent = error.message; }
    finally { button.disabled = false; }
  });
  renderSelection();
  window.SodaPromptLibrary = {render};
})();
