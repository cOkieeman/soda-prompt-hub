SOURCE_CENTER_STYLES = r"""<style>
  .source-center-grid { display:grid; grid-template-columns:minmax(300px,.72fr) minmax(0,1.28fr); gap:18px; }
  .source-capture-panel,.source-ledger-panel,.source-capture-list-panel { padding:28px; background:var(--paper); box-shadow:var(--shadow); }
  .source-capture-panel { background:var(--ink); color:var(--paper); }
  .source-capture-panel .section-label { color:var(--on-ink-muted); }
  .source-center-heading { margin:8px 0 10px; font:700 34px/1.05 "Iowan Old Style",serif; letter-spacing:-.035em; }
  .source-center-copy { margin:0 0 22px; color:var(--on-ink-faint); font-size:12px; line-height:1.7; }
  .source-policy { display:grid; gap:8px; margin:0 0 22px; }
  .source-policy div { border-top:1px solid rgba(236,232,220,.2); padding:10px 0; }
  .source-policy strong { display:block; color:var(--acid); font:800 10px/1.3 monospace; }
  .source-policy span { display:block; margin-top:5px; color:var(--on-ink-muted); font-size:11px; line-height:1.5; }
  .source-capture-form { display:grid; gap:12px; }
  .source-capture-form label { display:grid; gap:6px; color:var(--on-ink-faint); font:800 9px/1 monospace; letter-spacing:.08em; }
  .source-capture-form input,.source-capture-form textarea,.source-capture-form select { width:100%; border:1px solid rgba(236,232,220,.28); border-radius:0; background:#252622; color:var(--paper); padding:11px 12px; font:13px/1.5 "Avenir Next",sans-serif; }
  .source-capture-form textarea { min-height:84px; resize:vertical; line-height:1.5; }
  .source-form-row { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .source-capture-submit { border:1px solid var(--acid); background:var(--acid); color:var(--ink); padding:13px 15px; cursor:pointer; text-align:left; font:800 10px/1 monospace; letter-spacing:.1em; transition:transform .18s ease, box-shadow .18s ease; }
  .source-capture-submit:hover:not(:disabled) { transform:translate(-2px,-2px); box-shadow:var(--hard-lift); }
  .source-capture-submit:disabled { opacity:.55; cursor:wait; }
  .source-capture-message { min-height:38px; margin:0; padding:10px 12px; border-left:4px solid var(--acid); background:rgba(236,232,220,.08); color:var(--on-ink-muted); font:800 9px/1.55 monospace; }
  .source-ledger-summary { display:flex; flex-wrap:wrap; gap:8px; margin:16px 0; }
  .source-ledger-summary span { padding:7px 9px; background:var(--paper-deep); font:800 9px/1 monospace; }
  .source-ledger { display:grid; border-top:1px solid var(--line); }
  .source-ledger-row { display:grid; grid-template-columns:minmax(160px,1.2fr) repeat(2,minmax(64px,.35fr)) minmax(110px,.65fr) auto; gap:12px; align-items:center; padding:14px 0; border-bottom:1px solid var(--line); }
  .source-ledger-name strong { display:block; font-size:13px; }
  .source-ledger-name span { display:block; margin-top:5px; color:var(--muted); font:700 9px/1.4 monospace; }
  .source-ledger-metric strong { display:block; font:700 22px/1 "Iowan Old Style",serif; }
  .source-ledger-metric span,.source-ledger-license span { color:var(--muted); font:700 8px/1.4 monospace; text-transform:uppercase; }
  .source-ledger-license strong { display:block; margin-bottom:4px; font-size:10px; overflow-wrap:anywhere; }
  .source-ledger-action { display:flex; justify-content:flex-end; align-items:center; }
  .source-delete-btn { padding:6px 10px; border:1px solid rgba(184,51,42,.35); background:transparent; color:var(--signal); font:800 9px/1 monospace; cursor:pointer; letter-spacing:.04em; }
  .source-delete-btn:hover:not(:disabled) { background:var(--signal); color: var(--cream); }
  .source-delete-btn.disabled, .source-delete-btn:disabled { border-color:var(--line); color:var(--muted); opacity:.6; cursor:not-allowed; }
  .source-capture-list-panel { grid-column:1/-1; }
  .source-capture-list { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:16px; }
  .source-capture-card { min-width:0; border:1px solid var(--line); background:var(--paper-wash); padding:14px; }
  .source-capture-visual { display:block; width:100%; aspect-ratio:16/9; object-fit:cover; margin-bottom:12px; background:var(--ink); }
  .source-capture-meta { display:flex; flex-wrap:wrap; gap:5px; margin-bottom:9px; }
  .source-capture-meta span { padding:5px 6px; background:var(--ink); color:var(--paper); font:800 8px/1 monospace; }
  .source-capture-meta .cached { background:var(--acid); color:var(--ink); }
  .source-capture-card h3 { margin:0 0 7px; font:700 20px/1.1 "Iowan Old Style",serif; }
  .source-capture-card p { min-height:34px; margin:0 0 12px; color:var(--ink-soft); font-size:11px; line-height:1.55; white-space:pre-wrap; }
  .source-capture-card a { color:var(--signal); font:900 9px/1 monospace; text-decoration:none; }
  .source-capture-card details { margin-top:12px; border-top:1px dashed var(--line); padding-top:8px; color:var(--muted); font:700 8px/1.6 monospace; overflow-wrap:anywhere; }
  .capture-delete-btn { margin-top:10px; padding:5px 8px; border:1px solid rgba(184,51,42,.35); background:transparent; color:var(--signal); font:800 9px/1 monospace; cursor:pointer; }
  .capture-delete-btn:hover:not(:disabled) { background:var(--signal); color: var(--cream); }
  .capture-delete-btn:disabled { border-color:var(--line); color:var(--muted); opacity:.6; cursor:not-allowed; }
  .source-center-empty { padding:28px; border:1px dashed var(--line); color:var(--muted); font-size:12px; line-height:1.6; }
  @media(max-width:980px){.source-center-grid{grid-template-columns:1fr}.source-capture-list{grid-template-columns:repeat(2,minmax(0,1fr))}.source-ledger-row{grid-template-columns:minmax(160px,1fr) repeat(2,70px) auto}.source-ledger-license{grid-column:1/-1}}
  @media(max-width:620px){.source-capture-panel,.source-ledger-panel,.source-capture-list-panel{padding:22px}.source-form-row,.source-capture-list{grid-template-columns:1fr}.source-ledger-row{grid-template-columns:1fr 1fr}.source-ledger-name,.source-ledger-license,.source-ledger-action{grid-column:1/-1}}
</style>"""

SOURCE_CENTER_HTML = r"""
<section class="source-center-grid" aria-label="本地提示词来源中心">
  <section class="source-capture-panel">
    <p class="section-label">保存网页资料</p>
    <h2 class="source-center-heading">保存网上找到的<br>提示词和模型页面</h2>
    <p class="source-center-copy">粘贴网页地址，再写一句它有什么用。系统会根据站点规则决定能否保存离线副本，同时保留原始网址。</p>
    <div class="source-policy">
      <div><strong>可离线缓存</strong><span>GitHub 页面、raw 文本和直链图片：保存受限副本，断网后仍可检索。</span></div>
      <div><strong>只收藏链接</strong><span>Civitai、OpenArt、PromptHero、Promptomania：保存标题、网址和个人备注，不自动复制站点内容。</span></div>
    </div>
    <form class="source-capture-form" id="sourceCaptureForm">
      <label>网页地址<input id="sourceCaptureUrl" type="url" required placeholder="https://github.com/… 或 https://civitai.com/…"></label>
      <label>资料标题<input id="sourceCaptureTitle" maxlength="300" placeholder="例如：电影感灯光提示词 / 某个 LoRA 的 C 站页面"></label>
      <label>我为什么保存它<textarea id="sourceCaptureNote" maxlength="6000" placeholder="记录适用模型、触发词、构图用途或实测结论"></textarea></label>
      <div class="source-form-row">
        <label>内容分级<select id="sourceCaptureSafety"><option value="sfw">普通</option><option value="suggestive">轻度成人向</option><option value="adult">成人向</option><option value="explicit-adult">明确成人向</option></select></label>
        <label>许可信息<input id="sourceCaptureLicense" maxlength="160" placeholder="例如 MIT、CC-BY；不清楚可以留空"></label>
      </div>
      <button class="source-capture-submit" type="submit">＋ 保存这条网页资料</button>
      <p class="source-capture-message" id="sourceCaptureMessage">保存 Civitai 等链接不会下载作品图；保存 GitHub 资料时会显示是否已经离线缓存。</p>
    </form>
  </section>
  <section class="source-ledger-panel">
    <p class="section-label">资料来源清单</p>
    <h2 class="source-center-heading">这些资料从哪里来</h2>
    <p class="source-center-copy" style="color:#55564f">这里可以确认每个资料库何时更新、包含多少提示词和参考图，以及原始来源在哪里。</p>
    <div class="source-ledger-summary" id="sourceLedgerSummary"></div>
    <div class="source-ledger" id="sourceLedger"><div class="source-center-empty">正在读取本地来源…</div></div>
  </section>
  <section class="source-capture-list-panel">
    <p class="section-label">已经保存的网页资料</p>
    <div class="source-capture-list" id="sourceCaptureList"><div class="source-center-empty">正在读取网页资料…</div></div>
  </section>
</section>
"""

SOURCE_CENTER_SCRIPT = r"""<script>
(()=>{
  const q=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const fmt=v=>new Intl.NumberFormat('zh-CN').format(Number(v)||0);
  const date=v=>{if(!v)return '尚无时间';const d=new Date(v);return Number.isNaN(d.getTime())?v:d.toLocaleString('zh-CN',{dateStyle:'medium',timeStyle:'short'});};
  const safetyLabels={sfw:'普通',suggestive:'轻度成人向',adult:'成人向','explicit-adult':'明确成人向',unrated:'尚未分级'};
  const displayLicense=value=>!value||value==='unknown'?'未确认':value;
  const policyLabels={link_only:'只保存链接',cache_allowed:'允许离线缓存'};
  async function api(url,options){const r=await fetch(url,options),data=await r.json().catch(()=>({}));if(!r.ok)throw new Error(data.detail||`请求失败：${r.status}`);return data;}
  function sourceType(item){return item.source_type==='web_capture'?'网页摘录':item.source_type==='git'?'本地 Git 库':item.source_type==='personal'?'个人资料':'本地资料';}
  function renderSources(items){
    const entries=items.reduce((n,i)=>n+Number(i.entry_count||0),0),visuals=items.reduce((n,i)=>n+Number(i.visual_count||0),0),web=items.filter(i=>i.source_type==='web_capture').length;
    q('#sourceLedgerSummary').innerHTML=`<span>${fmt(items.length)} 个来源</span><span>${fmt(entries)} 条资料</span><span>${fmt(visuals)} 个视觉参照</span><span>${fmt(web)} 个网页来源</span>`;
    q('#sourceLedger').innerHTML=items.length?items.map(item=>{
      const isPreset = item.source_type === 'git' || item.deletable === false;
      const actionHtml = isPreset
        ? `<button type="button" class="source-delete-btn disabled" disabled title="内置资料库不能在页面删除">内置资料库</button>`
        : `<button type="button" class="source-delete-btn" data-source-id="${esc(item.source_id)}" data-name="${esc(item.name)}" data-entries="${Number(item.entry_count||0)}">删除来源</button>`;
      return `<article class="source-ledger-row"><div class="source-ledger-name"><strong>${esc(item.name)}</strong><span>${esc(sourceType(item))} · 更新于 ${esc(date(item.updated_at))}</span></div><div class="source-ledger-metric"><strong>${fmt(item.entry_count)}</strong><span>可检索条目</span></div><div class="source-ledger-metric"><strong>${fmt(item.visual_count)}</strong><span>视觉参照</span></div><div class="source-ledger-license"><strong>${esc(displayLicense(item.license))}</strong><span>许可 · ${item.url?`<a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">查看来源</a>`:'本地来源'}</span></div><div class="source-ledger-action">${actionHtml}</div></article>`;
    }).join(''):'<div class="source-center-empty">还没有已索引来源。</div>';
  }
  function renderCaptures(items){
    q('#sourceCaptureList').innerHTML=items.length?items.map(item=>`<article class="source-capture-card">${item.media_kind==='image'?`<img class="source-capture-visual" src="/api/web-captures/${encodeURIComponent(item.capture_id)}/media" alt="${esc(item.title)}" loading="lazy">`:''}<div class="source-capture-meta"><span>${esc(item.site_label||'网页')}</span><span>${esc(safetyLabels[item.safety]||'尚未分级')}</span><span class="${item.cached?'cached':''}">${item.cached?'已离线缓存':'只保存链接'}</span></div><h3>${esc(item.title||'未命名网页资料')}</h3><p>${esc(item.note||'没有个人备注')}</p><a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">打开原始网页 ↗</a><details><summary>查看来源与校验信息</summary>许可：${esc(displayLicense(item.license))}<br>保存时间：${esc(date(item.captured_at))}<br>内容 SHA-256：${esc(item.content_sha256||'—')}<br>保存方式：${esc(policyLabels[item.cache_policy]||'未记录')}</details><button type="button" class="capture-delete-btn" data-capture-id="${esc(item.capture_id)}" data-title="${esc(item.title||item.capture_id)}">删除这条摘录</button></article>`).join(''):'<div class="source-center-empty"><strong>还没有网页资料。</strong><br>把常用提示词页面、GitHub 提示词库文件或视觉参考直链保存到左侧。</div>';
  }
  async function ensure(){const [sources,captures]=await Promise.all([api('/api/sources'),api('/api/web-captures')]);renderSources(sources);renderCaptures(captures);}
  q('#sourceCaptureForm').addEventListener('submit',async event=>{event.preventDefault();const button=event.currentTarget.querySelector('button'),message=q('#sourceCaptureMessage');button.disabled=true;button.textContent='正在核对并保存…';message.textContent='正在检查这个站点允许保存哪些内容。';try{const saved=await api('/api/web-captures',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:q('#sourceCaptureUrl').value,title:q('#sourceCaptureTitle').value,note:q('#sourceCaptureNote').value,safety:q('#sourceCaptureSafety').value,license_name:q('#sourceCaptureLicense').value})});message.textContent=saved.cached?'已经保存离线副本，并记录原始来源。':'已经保存链接、标题和个人备注；这个站点的正文或作品图没有下载。';q('#sourceCaptureUrl').value='';q('#sourceCaptureTitle').value='';q('#sourceCaptureNote').value='';await ensure();if(window.loadPromptHubStats)await window.loadPromptHubStats();}catch(error){message.textContent=error.message;}finally{button.disabled=false;button.textContent='＋ 保存这条网页资料';}});

  q('#sourceLedger').addEventListener('click', async event => {
    const btn = event.target.closest('.source-delete-btn');
    if (!btn || btn.disabled) return;
    const sourceId = btn.dataset.sourceId;
    const name = btn.dataset.name || sourceId;
    const entries = Number(btn.dataset.entries) || 0;
    const confirmed = confirm(
      `确定要删除资料来源「${name}」吗？\n\n` +
      `• 将删除 ${entries} 条检索条目及派生离线缓存文件\n` +
      `• 人工标记（收藏/评分/备注）默认会被安全保留\n\n` +
      `点击「确定」继续，点击「取消」返回。`
    );
    if (!confirmed) return;
    const purge = confirm(
      `是否同时彻底清除该来源下的人工标记（收藏、评分、备注）？\n\n` +
      `• 点击「确定」：彻底清除所有人工标记\n` +
      `• 点击「取消」：安全保留人工标记（推荐，未来重新添加来源后可自动恢复）`
    );
    btn.disabled = true;
    btn.textContent = '正在删除…';
    try {
      const res = await api(`/api/sources/${encodeURIComponent(sourceId)}?purge_marks=${purge}`, {method: 'DELETE'});
      alert(`来源删除成功：已删除 ${res.deleted_entries} 条条目，清除 ${res.deleted_files} 个缓存文件，${res.purged_marks ? `彻底清除 ${res.purged_marks} 条人工标记` : `安全保留 ${res.retained_marks} 条人工标记`}。`);
      await ensure();
      if (window.loadPromptHubStats) await window.loadPromptHubStats();
    } catch (error) {
      alert(`删除失败：${error.message}`);
      btn.disabled = false;
      btn.textContent = '删除来源';
    }
  });

  q('#sourceCaptureList').addEventListener('click', async event => {
    const btn = event.target.closest('.capture-delete-btn');
    if (!btn || btn.disabled) return;
    const captureId = btn.dataset.captureId;
    const title = btn.dataset.title || captureId;
    const confirmed = confirm(
      `确定要删除网页摘录「${title}」吗？\n\n` +
      `• 将删除该条目的检索条目与本地离线文件\n` +
      `• 人工标记默认会被安全保留\n\n` +
      `点击「确定」继续，点击「取消」返回。`
    );
    if (!confirmed) return;
    const purge = confirm(
      `是否同时彻底清除该摘录的人工标记（收藏、评分、备注）？\n\n` +
      `• 点击「确定」：彻底清除人工标记\n` +
      `• 点击「取消」：安全保留人工标记`
    );
    btn.disabled = true;
    btn.textContent = '正在删除…';
    try {
      const res = await api(`/api/web-captures/${encodeURIComponent(captureId)}?purge_marks=${purge}`, {method: 'DELETE'});
      alert(`网页摘录已删除：${res.purged_marks ? `彻底清除 ${res.purged_marks} 条人工标记` : `安全保留 ${res.retained_marks} 条人工标记`}。`);
      await ensure();
      if (window.loadPromptHubStats) await window.loadPromptHubStats();
    } catch (error) {
      alert(`删除失败：${error.message}`);
      btn.disabled = false;
      btn.textContent = '删除这条摘录';
    }
  });

  window.ensureSourceCenter=ensure;
})();
</script>"""
