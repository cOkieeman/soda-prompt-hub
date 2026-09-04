SEARCH_STYLES = r"""
<style>
  .discovery-page { margin-top: 18px; }
  .discovery-page[hidden] { display: none; }
  .discovery-hero { display: grid; grid-template-columns: minmax(0,1.35fr) minmax(300px,.65fr); border: 1px solid var(--line); background: var(--paper); box-shadow: var(--shadow); }
  .discovery-copy { position: relative; overflow: hidden; min-height: 330px; padding: 48px; border-right: 1px solid var(--line); }
  .discovery-copy::after { content: "查找 / 02"; position: absolute; right: -8px; bottom: -20px; color: rgba(23,24,21,.06); font: 900 78px/1 monospace; transform: rotate(-5deg); }
  .discovery-copy h1 { margin: 18px 0 13px; font: 800 clamp(52px,7vw,96px)/.84 "Iowan Old Style",serif; letter-spacing: -.055em; }
  .discovery-copy p { max-width: 690px; color: var(--muted); line-height: 1.7; }
  .discovery-index { display: flex; flex-direction: column; justify-content: center; padding: 34px; background: var(--ink); color: var(--paper); }
  .discovery-index .section-label { color: #b9ae9f; }
  .discovery-index strong { display: block; margin: 12px 0 8px; color: var(--acid); font: 800 21px/1.2 "Iowan Old Style",serif; }
  .discovery-index p { color: #aaa99f; font-size: 11px; line-height: 1.6; }
  .discovery-index-list { display: grid; gap: 6px; margin-top: 12px; }
  .discovery-index-item { border-top: 1px solid rgba(236,232,220,.22); padding-top: 8px; font: 8px/1.5 monospace; }
  .discovery-search { display: grid; grid-template-columns: minmax(0,1fr) 190px auto; gap: 8px; margin: 14px 0; padding: 16px; border: 1px solid var(--line); background: var(--paper); box-shadow: var(--shadow); }
  .discovery-search input, .discovery-search select { min-width: 0; border: 1px solid var(--line); background: #fbf6ec; padding: 12px; color: var(--ink); }
  .discovery-search button { border: 1px solid var(--signal); background: var(--signal); padding: 10px 18px; color: white; font: 900 9px monospace; }
  .discovery-modes { display:flex; gap:1px; margin-top:14px; background:var(--line); border:1px solid var(--line); box-shadow:var(--shadow); }
  .discovery-mode-button { flex:1; min-height:48px; border:0; background:var(--paper); color:var(--muted); cursor:pointer; font:900 10px/1 monospace; letter-spacing:.06em; }
  .discovery-mode-button[aria-pressed="true"] { background:var(--ink); color:var(--acid); }
  .visual-search-panel,.cluster-panel { margin:14px 0; padding:18px; background:var(--paper); border:1px solid var(--line); box-shadow:var(--shadow); }
  .visual-search-layout { display:grid; grid-template-columns:minmax(230px,.65fr) minmax(0,1.35fr); gap:18px; }
  .visual-drop { min-height:250px; display:grid; place-items:center; overflow:hidden; border:2px dashed var(--line); background:#ded7c8; cursor:pointer; text-align:center; }
  .visual-drop strong { display:block; font:800 24px/1.1 "Iowan Old Style",serif; }
  .visual-drop span { display:block; margin-top:8px; color:var(--muted); font-size:11px; }
  .visual-query-preview { width:100%; height:100%; min-height:246px; object-fit:cover; }
  .visual-search-controls { display:grid; align-content:start; gap:12px; }
  .visual-control-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:9px; }
  .visual-search-controls label { display:grid; gap:6px; color:var(--muted); font:800 9px/1 monospace; letter-spacing:.06em; }
  .visual-search-controls select { width:100%; min-width:0; border:1px solid var(--line); background:#fbf6ec; padding:11px; color:var(--ink); }
  .visual-actions { display:flex; flex-wrap:wrap; gap:8px; }
  .visual-action { border:1px solid var(--ink); background:transparent; color:var(--ink); padding:12px 14px; cursor:pointer; font:900 9px/1 monospace; }
  .visual-action.primary { border-color:var(--signal); background:var(--signal); color:white; }
  .visual-action.acid { border-color:var(--acid); background:var(--acid); }
  .visual-action:disabled { opacity:.45; cursor:not-allowed; }
  .visual-index-note { margin:0; padding:12px; border-left:4px solid var(--acid); background:#e3dccd; color:#55564f; font-size:11px; line-height:1.6; }
  .visual-job { display:grid; gap:7px; padding:11px; border:1px solid var(--line); }
  .visual-job progress { width:100%; accent-color:var(--signal); }
  .cluster-toolbar { display:flex; flex-wrap:wrap; justify-content:space-between; gap:10px; align-items:center; }
  .cluster-toolbar p { margin:0; color:var(--muted); font-size:11px; line-height:1.6; }
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
  @media (max-width: 760px) { .visual-search-layout,.visual-control-grid { grid-template-columns:1fr; }.visual-drop { min-height:190px; }.visual-query-preview { min-height:186px; } }
  @media (max-width: 620px) { .discovery-hero, .discovery-search, .discovery-grid { grid-template-columns: 1fr; } .discovery-copy { min-height: 0; padding: 30px 22px; border-right: 0; border-bottom: 1px solid var(--line); } .discovery-index { padding: 24px 22px; } .discovery-group-head { align-items: start; }.discovery-modes{display:grid;grid-template-columns:1fr}.visual-actions{display:grid}.visual-action{width:100%;text-align:left} }
</style>
"""

SEARCH_HTML = r"""
<section class="discovery-page" id="discoveryPage" hidden>
  <section class="discovery-hero">
    <div class="discovery-copy"><span class="eyebrow">只查本机资料</span><h1>智能<br>检索</h1><p>输入文字可以查提示词，放入参考图可以查构图、服装和画风相近的图片。结果都来自 Mac 已保存的资料，并保留原始来源。</p></div>
    <aside class="discovery-index"><span class="section-label">图片检索是否可用</span><strong id="discoveryIndexTitle">正在检查</strong><p id="discoveryIndexMessage">图片检索需要本机视觉模型和已经建立的图片索引。</p><div class="discovery-index-list" id="discoveryIndexList"></div></aside>
  </section>
  <nav class="discovery-modes" aria-label="检索方式"><button class="discovery-mode-button" type="button" data-discovery-mode="text" aria-pressed="true">用文字查提示词</button><button class="discovery-mode-button" type="button" data-discovery-mode="visual" aria-pressed="false">用参考图查相似图</button><button class="discovery-mode-button" type="button" data-discovery-mode="clusters" aria-pressed="false">按相似画面浏览</button></nav>
  <form class="discovery-search" id="discoverySearchForm"><input id="discoveryQuery" required maxlength="1000" placeholder="服装、动作、构图、场景、灯光或画风……"><select id="discoverySafety"><option value="">全部分级</option><option value="sfw">普通</option><option value="suggestive">轻度成人向</option><option value="adult">成人向</option><option value="explicit-adult">明确成人向</option></select><button type="submit">检索本地资料</button></form>
  <section class="visual-search-panel" id="visualSearchPanel" hidden>
    <div class="visual-search-layout">
      <label class="visual-drop" for="visualQueryFile"><input id="visualQueryFile" type="file" accept="image/png,image/jpeg,image/webp" hidden><span id="visualDropCopy"><strong>选择一张参考图</strong><span>PNG / JPEG / WebP，最多 25 MiB<br>图片只用于本次查询，不会自动收入资料库</span></span><img class="visual-query-preview" id="visualQueryPreview" alt="查询图片预览" hidden></label>
      <div class="visual-search-controls">
        <p class="section-label">缩小查找范围（可选）</p>
        <div class="visual-control-grid"><label>图片来自哪里<select id="visualAssetType"><option value="">全部视觉资料</option><option value="prompt_visual">提示词视觉参考</option><option value="dataset_image">我的数据集</option><option value="result_image">创作结果</option><option value="comfy_result">Windows 出图结果</option><option value="lora_preview">LoRA 示例图</option><option value="model_preview">底模示例图</option><option value="web_visual">网页视觉资料</option></select></label><label>内容分级<select id="visualSafety"><option value="">全部（含未分级）</option><option value="sfw">普通</option><option value="suggestive">轻度成人向</option><option value="adult">成人向</option><option value="explicit-adult">明确成人向</option><option value="unrated">尚未分级</option></select></label><label>只查某个项目或数据集<select id="visualScope"><option value="">全部项目</option></select></label></div>
        <div class="visual-actions"><button class="visual-action primary" id="visualQueryButton" type="button" disabled>查找相似图片</button><button class="visual-action acid" id="visualBuildButton" type="button">建立 / 更新本地索引</button></div>
        <p class="visual-index-note" id="visualIndexNote">正在检查本地视觉模型与索引。</p>
        <div class="visual-job" id="visualJob" hidden><strong id="visualJobTitle">本地索引任务</strong><progress id="visualJobProgress" value="0" max="1"></progress><span id="visualJobMessage">等待开始</span><div class="visual-actions"><button class="visual-action" id="visualJobPause" type="button">暂停</button><button class="visual-action" id="visualJobResume" type="button" hidden>继续</button></div></div>
      </div>
    </div>
  </section>
  <section class="cluster-panel" id="visualClusterPanel" hidden><div class="cluster-toolbar"><p><strong>相似画面分组</strong><br>系统会把画面相近的图片放在同一组，方便浏览相似构图、服装和画风。</p><button class="visual-action primary" id="visualClusterButton" type="button">开始分组浏览</button></div></section>
  <div class="discovery-status" id="discoveryStatus">输入关键词后会查找本地提示词。图片检索需要先建立本机图片索引。</div>
  <div class="discovery-groups" id="discoveryGroups"></div>
</section>
"""

SEARCH_SCRIPT = r"""
<script>
(() => {
  const state={indexes:[],payload:null,visualStatus:null,visualFile:null,visualJob:null,mode:'text'};
  const groupHints={prompt_library:'输入服装、动作、构图、场景、灯光或画风关键词。',visual_references:'当前关键词没有命中带图片的资料。',my_datasets:'建立 Mac 本地视觉索引后，这里显示相似数据集图片。',windows_loras:'LoRA 预览已经同步到 Mac 后，可以离线进入视觉索引。'};
  const groupLabels={prompt_library:'提示词库',visual_references:'视觉参考',my_datasets:'我的数据集',windows_loras:'Windows LoRA'};
  const assetTypeLabels={comfy_result:'Windows 出图',dataset_image:'数据集图片',lora_preview:'LoRA 示例图',model_preview:'底模示例图',prompt_visual:'提示词视觉参考',result_image:'创作结果',web_visual:'网页视觉资料'};
  const safetyLabels={sfw:'普通',suggestive:'轻度成人向',adult:'成人向','explicit-adult':'明确成人向',unrated:'尚未分级'};
  async function api(url,options={}) { const response=await fetch(url,options); const payload=await response.json().catch(()=>({})); if(!response.ok) throw new Error(payload.detail||`请求失败: ${response.status}`); return payload; }
  function visual(item) { const ref=item.visuals?.[0]||{}, meta=item.metadata||{}, thumbnail=item.thumbnail_url||meta.media_url||ref.thumbnail_url||'', original=item.original_url||meta.original_url||ref.original_url||''; if(!thumbnail) return '<div class="discovery-visual"><span class="discovery-placeholder">暂无预览图</span></div>'; const image=`<img src="${escapeHtml(thumbnail)}" alt="${escapeHtml(item.title||meta.title||item.asset_id||'视觉参考')}" loading="lazy">`; return original?`<a class="discovery-visual" href="${escapeHtml(original)}" target="_blank" rel="noopener">${image}</a>`:`<div class="discovery-visual">${image}</div>`; }
  function card(item) { const meta=item.metadata||{}, rawContent=item.content||meta.caption||'', source=item.source_name||meta.source_label||item.source_id||item.worker_id||item.generated_by||'Mac 本地', title=item.kind==='tag'?(window.displayCanonicalTag?.(item.title)||item.title):(item.title||meta.title||item.asset_id||'未命名资料'), content=item.kind==='tag'&&window.getTagDisplayLanguage?.()==='zh'?`标准英文输出：${rawContent}`:rawContent, tags=(item.tags||[]).map(tag=>window.displayCanonicalTag?.(tag)||tag), score=Number.isFinite(Number(item.score))?` · 相似度 ${Math.round(Number(item.score)*100)}%`:''; return `<article class="discovery-card">${visual(item)}<div class="discovery-card-body"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(content||'视觉相似结果')}</p><span class="discovery-meta">${escapeHtml(item.match_reason||'本地图片相似度')}${escapeHtml(score)}<br>来源：${escapeHtml(source)} · ${escapeHtml(safetyLabels[meta.safety||item.safety]||'尚未分级')}</span></div></article>`; }
  async function prepareTagLabels(payload) { const values=(payload.groups||[]).flatMap(group=>(group.results||[]).flatMap(item=>item.kind==='tag'?[item.title,...String(item.content||'').split(',')]:item.tags||[])); await window.ensureTagLabels?.(values); }
  function render(payload) { state.payload=payload; const groups=payload.groups||[]; $('#discoveryGroups').innerHTML=groups.map(group=>`<section class="discovery-group"><div class="discovery-group-head"><div><span class="section-label">${escapeHtml(groupLabels[group.key]||'本机资料')}</span><h2>${escapeHtml(group.label)}</h2></div><span>${formatNumber(group.results?.length||0)}</span></div><div class="discovery-grid">${group.results?.length?group.results.map(card).join(''):`<div class="discovery-empty"><div><strong>当前没有结果</strong><span>${escapeHtml(groupHints[group.key]||'调整条件后再试。')}</span></div></div>`}</div></section>`).join(''); const semantic=payload.semantic||{}; $('#discoveryStatus').classList.toggle('active',semantic.status==='active'); $('#discoveryStatus').textContent=semantic.message||'检索完成。'; }
  async function loadIndexes() { state.visualStatus=await api('/api/visual-index/status'); state.indexes=state.visualStatus.indexes||[]; const model=state.visualStatus.model||{}, current=state.visualStatus.current_index, counts=state.visualStatus.type_counts||{}; $('#visualBuildButton').disabled=!model.available; if(!model.available) { $('#discoveryIndexTitle').textContent='图片检索暂不可用'; $('#discoveryIndexMessage').textContent='本机还没有安装所需的视觉模型，目前仍可使用文字检索。'; $('#discoveryIndexList').innerHTML='<div class="discovery-index-item">视觉模型未安装 · 已索引 0 张</div>'; $('#visualIndexNote').textContent='视觉模型文件尚未安装，当前只能使用文字检索。'; return; } if(!current) { $('#discoveryIndexTitle').textContent='视觉模型已安装'; $('#discoveryIndexMessage').textContent='还没有建立图片索引。点击“建立 / 更新本地索引”即可开始。'; $('#discoveryIndexList').innerHTML='<div class="discovery-index-item">已索引 0 张图片</div>'; $('#visualIndexNote').textContent='首次建立可以暂停；继续时会跳过已经完成的图片。'; return; } $('#discoveryIndexTitle').textContent=`已经索引 ${formatNumber(current.item_count)} 张图片`; $('#discoveryIndexMessage').textContent='索引在 Mac 本地生成，图片不会上传。'; $('#discoveryIndexList').innerHTML=Object.entries(counts).map(([key,value])=>`<div class="discovery-index-item">${escapeHtml(assetTypeLabels[key]||'其他图片')} · ${formatNumber(value)} 张</div>`).join(''); $('#visualIndexNote').textContent=`再次更新时，只处理新增或已经变化的图片。`; }
  async function search(event) { event?.preventDefault(); const query=$('#discoveryQuery').value.trim(); if(!query) return; $('#discoveryStatus').textContent='正在检索本机资料……'; const payload=await api('/api/hybrid-search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,safety:$('#discoverySafety').value,limit:24})}); await prepareTagLabels(payload); render(payload); }
  function switchMode(mode) { state.mode=mode; document.querySelectorAll('[data-discovery-mode]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.discoveryMode===mode))); $('#discoverySearchForm').hidden=mode!=='text'; $('#visualSearchPanel').hidden=mode!=='visual'; $('#visualClusterPanel').hidden=mode!=='clusters'; if(mode==='visual') $('#discoveryStatus').textContent='选择一张参考图后，Mac 会在本地图片索引中查找相似画面。'; if(mode==='clusters') $('#discoveryStatus').textContent='点击“开始分组浏览”，无需输入关键词也能查看相近画面。'; }
  async function loadScopes() { const [projects,workspaces]=await Promise.all([api('/api/creative/projects'),api('/api/dataset-workspaces')]); $('#visualScope').innerHTML='<option value="">全部项目和数据集</option>'+projects.map(item=>`<option value="${escapeHtml(item.project_id)}">创作 · ${escapeHtml(item.title)}</option>`).join('')+workspaces.map(item=>`<option value="${escapeHtml(item.workspace_id)}">数据集 · ${escapeHtml(item.name)}</option>`).join(''); }
  function selectVisualFile(file) { state.visualFile=file||null; $('#visualQueryButton').disabled=!file; const preview=$('#visualQueryPreview'),copy=$('#visualDropCopy'); if(!file){preview.hidden=true;copy.hidden=false;return;} preview.src=URL.createObjectURL(file); preview.hidden=false; copy.hidden=true; $('#discoveryStatus').textContent=`已选择 ${file.name}，点击“查找相似图片”。`; }
  async function queryVisual() { if(!state.visualFile)return; $('#visualQueryButton').disabled=true; $('#discoveryStatus').textContent='Mac 正在分析参考图并查找相似图片……'; const params=new URLSearchParams({asset_types:$('#visualAssetType').value,safety:$('#visualSafety').value,scope_id:$('#visualScope').value,limit:'48'}); try { const payload=await api('/api/visual-search/query?'+params,{method:'POST',headers:{'Content-Type':state.visualFile.type||'application/octet-stream'},body:state.visualFile}); render({semantic:{status:'active',message:`找到 ${payload.matches?.length||0} 张真实相似图片；相似程度由本机视觉模型计算。`},groups:payload.groups||[]}); } finally { $('#visualQueryButton').disabled=!state.visualFile; } }
  function renderVisualJob(job) { state.visualJob=job; const active=['queued','running'].includes(job.status),paused=['canceled','failed'].includes(job.status); $('#visualJob').hidden=false; $('#visualJobTitle').textContent=job.status==='completed'?'本地索引已完成':paused?'本地索引已暂停':'Mac 正在建立视觉索引'; $('#visualJobProgress').max=Math.max(job.progress_total||1,1); $('#visualJobProgress').value=job.progress_current||0; $('#visualJobMessage').textContent=job.progress_message||job.error||'等待处理'; $('#visualJobPause').hidden=!active; $('#visualJobResume').hidden=!paused; }
  async function pollVisualJob(job) { renderVisualJob(job); while(['queued','running'].includes(job.status)){await new Promise(resolve=>setTimeout(resolve,600));job=await api(`/api/jobs/${encodeURIComponent(job.job_id)}`);renderVisualJob(job);} if(job.status==='completed'){const result=job.result||{}; $('#discoveryStatus').textContent=`本地索引完成：新增或更新 ${result.indexed||0} 张，跳过 ${result.skipped_unchanged||0} 张未变化图片，失败 ${result.failed||0} 张。`; await loadIndexes();} return job; }
  async function startVisualBuild() { $('#visualBuildButton').disabled=true; try { const result=await api('/api/visual-index/build',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"asset_types":[],"max_items":0}'}); await pollVisualJob(result.job); } finally { $('#visualBuildButton').disabled=!(state.visualStatus?.model?.available); } }
  async function pauseVisualJob() { if(!state.visualJob)return; const job=await api(`/api/jobs/${encodeURIComponent(state.visualJob.job_id)}/cancel`,{method:'POST'}); renderVisualJob(job); $('#discoveryStatus').textContent='已请求暂停。已经写入的向量会保留，点击“继续”时只补剩余图片。'; }
  async function resumeVisualJob() { if(!state.visualJob)return; const job=await api(`/api/jobs/${encodeURIComponent(state.visualJob.job_id)}/retry`,{method:'POST'}); await pollVisualJob(job); }
  async function loadClusters() { const current=state.visualStatus?.current_index; if(!current)throw new Error('还没有图片索引，请先建立索引'); $('#discoveryStatus').textContent='正在整理相似画面……'; const payload=await api(`/api/visual-index/${encodeURIComponent(current.index_id)}/clusters?limit=240&threshold=0.84`); const groups=(payload.clusters||[]).slice(0,24).map((cluster,index)=>({key:cluster.cluster_id,label:`相似画面组 ${String(index+1).padStart(2,'0')}`,results:cluster.items||[]})); render({semantic:{status:'active',message:`已从最多 240 张近期素材中整理出 ${payload.clusters?.length||0} 个相似画面组。`},groups}); }
  async function openSimilar(sourceSha,label='当前图片') { await window.setPromptHubView?.('discover'); switchMode('visual'); $('#discoveryStatus').textContent=`正在查找与 ${label} 相似的 Mac 本地图片……`; try { const payload=await api('/api/visual-search/by-source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_sha256:sourceSha,asset_types:[],safety:'',scope_id:'',limit:40})}); render({semantic:{status:'active',message:`已找到 ${payload.matches?.length||0} 张真实相似图片。`},groups:payload.groups||[]}); } catch(error) { $('#discoveryStatus').classList.remove('active'); $('#discoveryStatus').textContent=error.message; } }
  async function ensure() { await Promise.all([loadIndexes(),loadScopes()]); if(!state.payload) render({semantic:{status:'not_requested',message:'选择文字检索或图片检索。没有真实向量时，以图找图保持明确空状态。'},groups:[['prompt_library','提示词资料'],['visual_references','视觉参考'],['my_datasets','我的数据集'],['windows_loras','Windows LoRA']].map(([key,label])=>({key,label,results:[]}))}); }
  $('#discoverySearchForm').addEventListener('submit',event=>search(event).catch(error=>$('#discoveryStatus').textContent=error.message));
  document.querySelectorAll('[data-discovery-mode]').forEach(button=>button.addEventListener('click',()=>switchMode(button.dataset.discoveryMode)));
  $('#visualQueryFile').addEventListener('change',event=>selectVisualFile(event.target.files?.[0]));
  $('#visualQueryButton').addEventListener('click',()=>queryVisual().catch(error=>$('#discoveryStatus').textContent=error.message));
  $('#visualBuildButton').addEventListener('click',()=>startVisualBuild().catch(error=>$('#discoveryStatus').textContent=error.message));
  $('#visualJobPause').addEventListener('click',()=>pauseVisualJob().catch(error=>$('#discoveryStatus').textContent=error.message));
  $('#visualJobResume').addEventListener('click',()=>resumeVisualJob().catch(error=>$('#discoveryStatus').textContent=error.message));
  $('#visualClusterButton').addEventListener('click',()=>loadClusters().catch(error=>$('#discoveryStatus').textContent=error.message));
  window.addEventListener('tag-language-change',()=>{ if(state.payload) render(state.payload); });
  window.ensureHybridSearch=ensure;
  window.openSimilarImage=openSimilar;
})();
</script>
"""
