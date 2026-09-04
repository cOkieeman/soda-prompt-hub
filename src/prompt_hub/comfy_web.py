COMFY_STYLES = r"""
<style>
  .comfy-page { width: min(1480px, calc(100% - 36px)); margin: 18px auto 60px; }
  .comfy-page .eyebrow, .comfy-page .section-label, .comfy-panel label { text-transform: none; }
  .comfy-hero { display: grid; grid-template-columns: 1.15fr .85fr; min-height: 330px; border: 1px solid var(--line); background: var(--paper); box-shadow: var(--shadow); }
  .comfy-hero-copy { position: relative; overflow: hidden; padding: 48px; border-right: 1px solid var(--line); background: linear-gradient(135deg, rgba(216,75,42,.08), transparent 55%); }
  .comfy-hero-copy::after { content: "结果 / 05"; position: absolute; right: -8px; bottom: -20px; color: rgba(23,24,21,.06); font: 900 72px/1 monospace; transform: rotate(-5deg); }
  .comfy-hero h1 { max-width: 720px; margin: 12px 0 16px; font: 900 clamp(46px, 7vw, 90px)/.83 Georgia, serif; letter-spacing: -.06em; }
  .comfy-hero p { max-width: 720px; line-height: 1.7; }
  .comfy-flow { display: flex; flex-direction: column; justify-content: center; padding: 38px; background: #d8d1bf; }
  .comfy-flow ol { margin: 18px 0 0; padding: 0; list-style: none; counter-reset: flow; }
  .comfy-flow li { display: grid; grid-template-columns: 32px 1fr; gap: 12px; padding: 11px 0; border-top: 1px solid rgba(23,24,21,.18); font-weight: 750; }
  .comfy-flow li::before { counter-increment: flow; content: "0" counter(flow); color: var(--signal); font: 900 10px monospace; }
  .comfy-controls { display: grid; grid-template-columns: 1fr 1fr .8fr; gap: 12px; margin: 14px 0; }
  .comfy-panel { border: 1px solid var(--line); background: var(--paper); padding: 20px; }
  .comfy-panel h2 { margin: 0 0 14px; font: 900 16px Georgia, serif; }
  .comfy-panel label { display: grid; gap: 7px; color: var(--muted); font: 800 9px/1.4 monospace; text-transform: uppercase; }
  .comfy-panel input, .comfy-panel select { width: 100%; min-height: 42px; border: 1px solid var(--line); background: #fbf6ec; padding: 9px; color: var(--ink); }
  .comfy-file { display: flex !important; align-items: center; justify-content: center; min-height: 42px; border: 1px dashed rgba(23,24,21,.42); background: #eee7da; cursor: pointer; color: var(--ink) !important; }
  .comfy-button { min-height: 40px; border: 1px solid var(--ink); background: var(--ink); padding: 9px 13px; color: var(--paper); font: 900 9px monospace; cursor: pointer; }
  .comfy-button.secondary { background: transparent; color: var(--ink); }
  .comfy-button.signal { border-color: var(--signal); background: var(--signal); }
  .comfy-button:disabled { opacity: .45; cursor: not-allowed; }
  .comfy-status { min-height: 42px; margin: 0 0 14px; border-left: 5px solid var(--acid); background: rgba(215,228,85,.19); padding: 12px 15px; font: 800 10px/1.6 monospace; }
  .comfy-head { display: flex; align-items: end; justify-content: space-between; gap: 16px; margin: 28px 0 12px; }
  .comfy-head h2 { margin: 0; font: 900 30px Georgia, serif; }
  .comfy-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
  .comfy-card { display: grid; grid-template-rows: 250px auto; min-width: 0; border: 1px solid var(--line); background: var(--paper); box-shadow: 6px 8px 0 rgba(23,24,21,.09); }
  .comfy-card-image { position: relative; display: block; width: 100%; min-width: 0; overflow: hidden; border-bottom: 1px solid var(--line); background: #1e1f1c; }
  .comfy-card-image img { display: block; width: 100%; max-width: 100%; min-width: 0; height: 100%; object-fit: contain; }
  .comfy-disposition { position: absolute; top: 10px; left: 10px; border: 1px solid var(--ink); background: var(--acid); padding: 6px 8px; color: var(--ink); font: 900 8px monospace; }
  .comfy-card-body { min-width: 0; padding: 16px; }
  .comfy-card-title { display: flex; justify-content: space-between; gap: 12px; }
  .comfy-card-title strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .comfy-card-title span { color: var(--muted); font: 800 8px monospace; white-space: nowrap; }
  .comfy-meta-summary { margin: 12px 0; padding: 10px; border: 1px solid rgba(23,24,21,.15); background: #eee7da; font: 9px/1.6 monospace; }
  .comfy-no-meta { border-color: var(--signal); color: #9d321e; }
  .comfy-prompt { max-height: 72px; overflow: auto; margin: 7px 0; white-space: pre-wrap; word-break: break-word; }
  .comfy-details summary { cursor: pointer; font: 900 9px monospace; }
  .comfy-details pre { max-height: 260px; overflow: auto; white-space: pre-wrap; word-break: break-word; padding: 10px; background: #20211e; color: #ece8dc; font: 8px/1.5 monospace; }
  .comfy-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-top: 12px; }
  .comfy-empty { grid-column: 1 / -1; min-height: 260px; display: grid; place-items: center; border: 1px dashed rgba(23,24,21,.35); background: rgba(236,232,220,.65); text-align: center; }
  @media (max-width: 1000px) { .comfy-controls, .comfy-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .comfy-controls .comfy-panel:last-child { grid-column: 1 / -1; } }
  @media (max-width: 760px) { .comfy-page { width: min(100% - 18px, 1480px); margin-top: 9px; } .comfy-hero, .comfy-controls, .comfy-grid { grid-template-columns: 1fr; } .comfy-hero-copy { padding: 30px 22px; border-right: 0; border-bottom: 1px solid var(--line); } .comfy-flow { padding: 24px 22px; } .comfy-controls .comfy-panel:last-child { grid-column: auto; } .comfy-card { grid-template-rows: 230px auto; } .comfy-actions { grid-template-columns: 1fr; } .comfy-head { display: block; } }
</style>
"""

COMFY_HTML = r"""
<section class="comfy-page" id="comfyPage" hidden>
  <section class="comfy-hero">
    <div class="comfy-hero-copy"><span class="eyebrow">从 5060 Ti 带回 Mac</span><h1>Windows<br>出图结果</h1><p>在这里导入 ComfyUI 生成的图片，并读取图片中实际保存的工作流和生成参数。没有参数的图片也能保存，但系统不会猜测或补写。</p></div>
    <aside class="comfy-flow"><span class="section-label">处理顺序</span><ol><li>选择一张图片，或扫描已经挂载的结果目录</li><li>核对模型、LoRA、提示词和生成参数</li><li>选择这张图属于哪个创作项目</li><li>决定作为参考、数据集候选、失败记录或下一版起点</li></ol></aside>
  </section>
  <section class="comfy-controls">
    <form class="comfy-panel" id="comfyFileForm"><h2>1. 导入一张图片</h2><label class="comfy-file" for="comfyFile">选择 PNG / JPEG / WebP<input id="comfyFile" type="file" accept="image/png,image/jpeg,image/webp" hidden></label><p id="comfyFileName">尚未选择图片</p><button class="comfy-button signal" type="submit">导入并读取生成参数</button></form>
    <form class="comfy-panel" id="comfyDirectoryForm"><h2>或：扫描整个结果文件夹</h2><label>Mac 能看到的文件夹路径<input id="comfyDirectory" placeholder="/Volumes/ComfyUI/output"></label><p>可以填写 Finder 已挂载的 SMB 目录。系统只读取，不会移动、改名或覆盖 Windows 文件。</p><button class="comfy-button" type="submit">扫描这个文件夹</button></form>
    <div class="comfy-panel"><h2>2. 选择它属于哪个项目</h2><label>创作项目<select id="comfyProject"><option value="">请选择项目</option></select></label><p>除了“记录为失败测试”，其他处理方式都需要先选择项目。</p><button class="comfy-button secondary" id="comfyRefresh" type="button">刷新结果列表</button></div>
  </section>
  <div class="comfy-status" id="comfyStatus">先导入图片，或扫描 Windows 的结果文件夹。</div>
  <div class="comfy-head"><div><span class="section-label">已经导入到 Mac 的图片</span><h2>等待您处理</h2></div><label>只看<select id="comfyFilter"><option value="">全部</option><option value="unreviewed">未审核</option><option value="candidate">数据集候选</option><option value="failed_test">失败测试</option><option value="reference">已关联参考</option></select></label></div>
  <div class="comfy-grid" id="comfyGrid"></div>
</section>
"""

COMFY_SCRIPT = r"""
<script>
(() => {
  const state = {results: [], projects: []};
  const labels = {unreviewed:'未审核', candidate:'数据集候选', failed_test:'失败测试', reference:'已关联'};
  const api = async (url, options={}) => { const response=await fetch(url,options); const payload=await response.json().catch(()=>({})); if(!response.ok) throw new Error(payload.detail||`请求失败：${response.status}`); return payload; };
  const jsonOptions = payload => ({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const value = (metadata, key, fallback='—') => metadata?.[key] ?? fallback;
  function metadataMarkup(result) {
    const metadata=result.metadata||{};
    if(!result.metadata_present) return '<div class="comfy-meta-summary comfy-no-meta"><strong>图片里没有保存生成参数</strong><br>仍然可以保留并关联项目，但这里不会猜测参数。</div>';
    const loras=(metadata.loras||[]).map(item=>`${item.name} @ ${item.strength_model??'?'}`).join(' · ')||'无';
    const prompts=metadata.positive_prompts?.length?metadata.positive_prompts:metadata.text_prompts||[];
    return `<div class="comfy-meta-summary"><strong>${escapeHtml(metadata.checkpoint||'未识别模型')}</strong><br>随机种子 ${escapeHtml(value(metadata,'seed'))} · 步数 ${escapeHtml(value(metadata,'steps'))} · CFG ${escapeHtml(value(metadata,'cfg'))}<br>采样器 ${escapeHtml(metadata.sampler||'未识别')} · 调度器 ${escapeHtml(metadata.scheduler||'未识别')}<br>LoRA：${escapeHtml(loras)}${prompts.length?`<p class="comfy-prompt">${escapeHtml(prompts.join('\n'))}</p>`:''}</div>`;
  }
  function card(result) {
    const associated=(result.associations||[]).map(item=>item.id).join(' · ');
    return `<article class="comfy-card" data-comfy-result="${escapeHtml(result.result_id)}"><a class="comfy-card-image" href="${escapeHtml(result.original_url)}" target="_blank" rel="noopener"><img src="${escapeHtml(result.thumbnail_url)}" alt="${escapeHtml(result.filename)}"><span class="comfy-disposition">${escapeHtml(labels[result.disposition]||result.disposition)}</span></a><div class="comfy-card-body"><div class="comfy-card-title"><strong>${escapeHtml(result.filename)}</strong><span>${result.width}×${result.height}</span></div>${metadataMarkup(result)}${associated?`<p>已关联：${escapeHtml(associated)}</p>`:''}<details class="comfy-details"><summary>查看图片中的原始技术信息</summary><pre>${escapeHtml(JSON.stringify(result.metadata||{},null,2))}</pre></details><div class="comfy-actions"><button class="comfy-button secondary" data-comfy-action="attach">只作为项目参考</button><button class="comfy-button signal" data-comfy-action="candidate">加入数据集候选</button><button class="comfy-button secondary" data-comfy-action="failed">记录为失败测试</button><button class="comfy-button" data-comfy-action="branch">用这张图建立下一版</button></div></div></article>`;
  }
  function render() { const filter=$('#comfyFilter').value; const items=state.results.filter(item=>!filter||item.disposition===filter); $('#comfyGrid').innerHTML=items.length?items.map(card).join(''):'<div class="comfy-empty"><div><strong>这里还没有对应的图片</strong><p>导入图片后会先进入“未审核”。</p></div></div>'; }
  function status(message) { $('#comfyStatus').textContent=message; }
  async function load() { [state.results,state.projects]=await Promise.all([api('/api/comfy-results?limit=300'),api('/api/creative/projects?limit=100')]); const selected=$('#comfyProject').value; $('#comfyProject').innerHTML='<option value="">请选择项目</option>'+state.projects.map(item=>`<option value="${escapeHtml(item.project_id)}">第 ${item.lineage?.iteration||1} 版 · ${escapeHtml(item.title)}</option>`).join(''); if(state.projects.some(item=>item.project_id===selected)) $('#comfyProject').value=selected; render(); }
  async function importFile(event) { event.preventDefault(); const file=$('#comfyFile').files[0]; if(!file) return status('请先选择一张图片。'); status(`正在读取 ${file.name}…`); const outcome=await api('/api/comfy-results/import?filename='+encodeURIComponent(file.name),{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream'},body:file}); await load(); status(outcome.duplicate?'这张图已经在回流库中，未重复建立记录。':`已导入 ${file.name}；请核对参数并选择处理方式。`); }
  async function importDirectory(event) { event.preventDefault(); const path=$('#comfyDirectory').value.trim(); if(!path) return status('请填写 ComfyUI 输出目录或 SMB 挂载目录。'); status('正在只读扫描目录…'); const report=await api('/api/comfy-results/import-directory',jsonOptions({source_path:path})); await load(); status(`扫描 ${report.scanned} 张：新增 ${report.imported}，重复 ${report.duplicates}，失败 ${report.failed.length}。源目录未修改。`); }
  async function act(resultId, action) { const projectId=$('#comfyProject').value; if(action!=='failed'&&!projectId) return status('请先在上方选择这张图所属的创作项目。'); if(action==='failed') { await api(`/api/comfy-results/${encodeURIComponent(resultId)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({disposition:'failed_test'})}); status('已记录为失败测试；图片没有进入任何训练集。'); }
    else if(action==='branch') { const child=await api(`/api/comfy-results/${encodeURIComponent(resultId)}/branch/${encodeURIComponent(projectId)}`,{method:'POST'}); status(`已建立 ${child.title}；来源工作流和参数已经保存在版本记录中。`); }
    else { const endpoint=action==='candidate'?'candidate':'attach'; await api(`/api/comfy-results/${encodeURIComponent(resultId)}/${endpoint}/${encodeURIComponent(projectId)}`,{method:'POST'}); status(action==='candidate'?'已关联并加入数据集候选；仍需在创作台确认图片说明。':'已关联项目；图片尚未进入数据集。'); }
    await load(); }
  $('#comfyFile').addEventListener('change',event=>{ const file=event.target.files[0]; $('#comfyFileName').textContent=file?`${file.name} · ${(file.size/1024/1024).toFixed(2)} MiB`:'尚未选择图片'; });
  $('#comfyFileForm').addEventListener('submit',event=>importFile(event).catch(error=>status(error.message)));
  $('#comfyDirectoryForm').addEventListener('submit',event=>importDirectory(event).catch(error=>status(error.message)));
  $('#comfyRefresh').addEventListener('click',()=>load().then(()=>status('结果列表已刷新。')).catch(error=>status(error.message)));
  $('#comfyFilter').addEventListener('change',render);
  $('#comfyGrid').addEventListener('click',event=>{ const button=event.target.closest('[data-comfy-action]'); if(!button) return; const card=button.closest('[data-comfy-result]'); button.disabled=true; act(card.dataset.comfyResult,button.dataset.comfyAction).catch(error=>status(error.message)).finally(()=>button.disabled=false); });
  window.ensureComfyResults=load;
})();
</script>
"""
