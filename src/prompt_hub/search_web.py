SEARCH_STYLES = r"""
<style>
  .discovery-page { margin-top: 18px; }
  .discovery-page[hidden] { display: none; }
  .discovery-hero { display: grid; grid-template-columns: minmax(0,1.35fr) minmax(300px,.65fr); border: 1px solid var(--line); background: var(--paper); box-shadow: var(--shadow); }
  .discovery-copy { position: relative; overflow: hidden; min-height: 330px; padding: 48px; border-right: 1px solid var(--line); }
  .discovery-copy::after { content: "FIND / 02"; position: absolute; right: -8px; bottom: -20px; color: rgba(23,24,21,.06); font: 900 78px/1 monospace; transform: rotate(-5deg); }
  .discovery-copy h1 { margin: 18px 0 13px; font: 800 clamp(52px,7vw,96px)/.84 "Iowan Old Style",serif; letter-spacing: -.055em; }
  .discovery-copy p { max-width: 690px; color: var(--muted); line-height: 1.7; }
  .discovery-index { display: flex; flex-direction: column; justify-content: center; padding: 34px; background: var(--ink); color: var(--paper); }
  .discovery-index strong { display: block; margin: 12px 0 8px; color: var(--acid); font: 800 21px/1.2 "Iowan Old Style",serif; }
  .discovery-index p { color: #aaa99f; font-size: 11px; line-height: 1.6; }
  .discovery-index-list { display: grid; gap: 6px; margin-top: 12px; }
  .discovery-index-item { border-top: 1px solid rgba(236,232,220,.22); padding-top: 8px; font: 8px/1.5 monospace; }
  .discovery-search { display: grid; grid-template-columns: minmax(0,1fr) 190px auto; gap: 8px; margin: 14px 0; padding: 16px; border: 1px solid var(--line); background: var(--paper); box-shadow: var(--shadow); }
  .discovery-search input, .discovery-search select { min-width: 0; border: 1px solid var(--line); background: #fbf6ec; padding: 12px; color: var(--ink); }
  .discovery-search button { border: 1px solid var(--signal); background: var(--signal); padding: 10px 18px; color: white; font: 900 9px monospace; }
  .discovery-status { min-height: 46px; margin-bottom: 14px; border-left: 5px solid var(--acid); background: var(--paper); padding: 13px 16px; box-shadow: var(--shadow); font: 800 9px/1.65 monospace; }
  .discovery-status.active { border-left-color: #38664f; }
  .discovery-groups { display: grid; gap: 14px; }
  .discovery-group { border: 1px solid var(--line); background: var(--paper); box-shadow: var(--shadow); }
  .discovery-group-head { display: flex; align-items: end; justify-content: space-between; gap: 12px; padding: 18px 20px; border-bottom: 1px solid var(--line); }
  .discovery-group-head h2 { margin: 3px 0 0; font: 800 28px "Iowan Old Style",serif; }
  .discovery-group-head span { color: var(--signal); font: 900 11px monospace; }
  .discovery-grid { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 1px; background: var(--line); }
  .discovery-card { min-width: 0; background: #f2ecdf; }
  .discovery-visual { display: block; aspect-ratio: 4/3; overflow: hidden; background: #20211e; }
  .discovery-visual img { width: 100%; height: 100%; object-fit: cover; }
  .discovery-placeholder { display: grid; height: 100%; place-items: center; color: #8f8e84; font: 900 8px monospace; }
  .discovery-card-body { padding: 14px; }
  .discovery-card h3 { margin: 0 0 8px; overflow-wrap: anywhere; font: 800 15px/1.2 "Iowan Old Style",serif; }
  .discovery-card p { max-height: 75px; overflow: auto; margin: 0; color: #5f6059; font-size: 10px; line-height: 1.55; white-space: pre-wrap; }
  .discovery-meta { display: block; margin-top: 10px; color: var(--signal); font: 800 8px/1.5 monospace; }
  .discovery-empty { grid-column: 1/-1; min-height: 150px; display: grid; place-items: center; padding: 28px; background: #e3dccd; text-align: center; }
  .discovery-empty strong { display: block; font: 800 20px "Iowan Old Style",serif; }
  .discovery-empty span { display: block; margin-top: 7px; color: var(--muted); font-size: 10px; }
  @media (max-width: 1000px) { .discovery-grid { grid-template-columns: repeat(2,minmax(0,1fr)); } }
  @media (max-width: 620px) { .discovery-hero, .discovery-search, .discovery-grid { grid-template-columns: 1fr; } .discovery-copy { min-height: 0; padding: 30px 22px; border-right: 0; border-bottom: 1px solid var(--line); } .discovery-index { padding: 24px 22px; } .discovery-group-head { align-items: start; } }
</style>
"""

SEARCH_HTML = r"""
<section class="discovery-page" id="discoveryPage" hidden>
  <section class="discovery-hero">
    <div class="discovery-copy"><span class="eyebrow">Local retrieval / source first</span><h1>智能<br>检索</h1><p>先查本机提示词与视觉资料；真实视觉索引存在时，再加入数据集相似图和 Windows LoRA 预览。每条结果都说明为什么命中、来自哪里。</p></div>
    <aside class="discovery-index"><span class="section-label">Visual index status</span><strong id="discoveryIndexTitle">正在读取索引</strong><p id="discoveryIndexMessage">这里只认可版本固定的 CLIP / SigLIP embedding。</p><div class="discovery-index-list" id="discoveryIndexList"></div></aside>
  </section>
  <form class="discovery-search" id="discoverySearchForm"><input id="discoveryQuery" required maxlength="1000" placeholder="服装、动作、构图、场景、灯光或画风……"><select id="discoverySafety"><option value="">全部分级</option><option value="sfw">SFW</option><option value="suggestive">Suggestive</option><option value="adult">Adult</option><option value="explicit-adult">Explicit adult</option></select><button type="submit">检索本地资料</button></form>
  <div class="discovery-status" id="discoveryStatus">输入关键词后会先返回本地 FTS 结果。没有真实 embedding 时，视觉分组保持空白。</div>
  <div class="discovery-groups" id="discoveryGroups"></div>
</section>
"""

SEARCH_SCRIPT = r"""
<script>
(() => {
  const state={indexes:[],payload:null};
  const groupHints={prompt_library:'输入服装、动作、构图、场景、灯光或画风关键词。',visual_references:'当前关键词没有命中带图片的资料。',my_datasets:'等待 5060 Ti 生成真实视觉索引后，这里显示相似数据集图片。',windows_loras:'等待 Windows Worker 读取 LoRA Manager 插件和 ComfyUI LoRA 目录后，这里显示只读 LoRA 与预览图索引。'};
  async function api(url,options={}) { const response=await fetch(url,options); const payload=await response.json().catch(()=>({})); if(!response.ok) throw new Error(payload.detail||`请求失败: ${response.status}`); return payload; }
  function visual(item) { const ref=item.visuals?.[0]||{}, thumbnail=item.thumbnail_url||ref.thumbnail_url||'', original=item.original_url||ref.original_url||''; if(!thumbnail) return '<div class="discovery-visual"><span class="discovery-placeholder">TEXT / NO PREVIEW</span></div>'; const image=`<img src="${escapeHtml(thumbnail)}" alt="${escapeHtml(item.title||item.asset_id||'视觉参考')}" loading="lazy">`; return original?`<a class="discovery-visual" href="${escapeHtml(original)}" target="_blank" rel="noopener">${image}</a>`:`<div class="discovery-visual">${image}</div>`; }
  function card(item) { const rawContent=item.content||item.metadata?.caption||item.source_path||'', source=item.source_name||item.source_id||item.worker_id||item.generated_by||'local', title=item.kind==='tag'?(window.displayCanonicalTag?.(item.title)||item.title):(item.title||item.asset_id||'未命名资料'), content=item.kind==='tag'&&window.getTagDisplayLanguage?.()==='zh'?`标准英文输出：${rawContent}`:rawContent, tags=(item.tags||[]).map(tag=>window.displayCanonicalTag?.(tag)||tag); return `<article class="discovery-card">${visual(item)}<div class="discovery-card-body"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(content)}${tags.length?`\n标签：${escapeHtml(tags.join(', '))}`:''}</p><span class="discovery-meta">${escapeHtml(item.match_reason||'本地索引')}<br>SOURCE / ${escapeHtml(source)}</span></div></article>`; }
  async function prepareTagLabels(payload) { const values=(payload.groups||[]).flatMap(group=>(group.results||[]).flatMap(item=>item.kind==='tag'?[item.title,...String(item.content||'').split(',')]:item.tags||[])); await window.ensureTagLabels?.(values); }
  function render(payload) { state.payload=payload; const groups=payload.groups||[]; $('#discoveryGroups').innerHTML=groups.map(group=>`<section class="discovery-group"><div class="discovery-group-head"><div><span class="section-label">${escapeHtml(group.key.replaceAll('_',' / '))}</span><h2>${escapeHtml(group.label)}</h2></div><span>${formatNumber(group.results?.length||0)}</span></div><div class="discovery-grid">${group.results?.length?group.results.map(card).join(''):`<div class="discovery-empty"><div><strong>当前没有结果</strong><span>${escapeHtml(groupHints[group.key]||'调整条件后再试。')}</span></div></div>`}</div></section>`).join(''); const semantic=payload.semantic||{}; $('#discoveryStatus').classList.toggle('active',semantic.status==='active'); $('#discoveryStatus').textContent=semantic.message||'检索完成。'; }
  async function loadIndexes() { state.indexes=await api('/api/embedding-indexes'); if(!state.indexes.length) { $('#discoveryIndexTitle').textContent='等待真实视觉索引'; $('#discoveryIndexMessage').textContent='Mac 已准备好事实源和校验接口；5060 Ti 生成并回传 CLIP / SigLIP 向量后自动启用。'; $('#discoveryIndexList').innerHTML='<div class="discovery-index-item">0 INDEX · 不使用随机向量或颜色特征代替</div>'; return; } $('#discoveryIndexTitle').textContent=`${state.indexes.length} 个版本化索引`; $('#discoveryIndexMessage').textContent='不同模型与 revision 并存；查询只在兼容版本内计算。'; $('#discoveryIndexList').innerHTML=state.indexes.map(item=>`<div class="discovery-index-item">${escapeHtml(item.model_id)} / ${escapeHtml(item.model_revision)}<br>${item.dimension}D · ${formatNumber(item.item_count)} ITEMS</div>`).join(''); }
  async function search(event) { event?.preventDefault(); const query=$('#discoveryQuery').value.trim(); if(!query) return; $('#discoveryStatus').textContent='正在检索本机资料……'; const payload=await api('/api/hybrid-search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,safety:$('#discoverySafety').value,limit:24})}); await prepareTagLabels(payload); render(payload); }
  async function openSimilar(sourceSha,label='当前图片') { await window.setPromptHubView?.('discover'); $('#discoveryStatus').textContent=`正在查找与 ${label} 相似的真实索引图片……`; try { const payload=await api('/api/hybrid-search/by-source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_sha256:sourceSha,limit:40})}); await prepareTagLabels(payload); render(payload); } catch(error) { $('#discoveryStatus').classList.remove('active'); $('#discoveryStatus').textContent=`${error.message}。等待 5060 Ti 完成真实视觉索引后再试。`; } }
  async function ensure() { await loadIndexes(); if(!state.payload) render({semantic:{status:'not_requested',message:'输入关键词后会先返回本地 FTS 结果。没有真实 embedding 时，视觉分组保持空白。'},groups:[['prompt_library','提示词资料'],['visual_references','视觉参考'],['my_datasets','我的数据集'],['windows_loras','Windows LoRA']].map(([key,label])=>({key,label,results:[]}))}); }
  $('#discoverySearchForm').addEventListener('submit',event=>search(event).catch(error=>$('#discoveryStatus').textContent=error.message));
  window.addEventListener('tag-language-change',()=>{ if(state.payload) render(state.payload); });
  window.ensureHybridSearch=ensure;
  window.openSimilarImage=openSimilar;
})();
</script>
"""
