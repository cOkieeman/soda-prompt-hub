LORA_STYLES = r"""
<style>
  .lora-page { display: grid; gap: 18px; }
  .lora-hero { display: grid; grid-template-columns: 1.2fr .8fr; background: var(--paper); box-shadow: var(--shadow); }
  .lora-hero-copy { padding: clamp(30px, 5vw, 58px); }
  .lora-hero-copy h1 { margin: 18px 0; font-size: clamp(48px, 7vw, 88px); }
  .lora-hero-copy p { max-width: 720px; color: #55564f; line-height: 1.7; }
  .lora-flow { padding: 30px; background: var(--ink); color: var(--paper); }
  .lora-flow ol { margin: 24px 0 0; padding: 0; list-style: none; counter-reset: steps; }
  .lora-flow li { counter-increment: steps; display: grid; grid-template-columns: 38px 1fr; gap: 12px; padding: 14px 0; border-top: 1px solid rgba(236,232,220,.2); font-size: 12px; line-height: 1.5; }
  .lora-flow li::before { content: "0" counter(steps); color: var(--acid); font: 800 16px/1 monospace; }
  .lora-desk { display: grid; grid-template-columns: minmax(280px, .32fr) minmax(0, 1fr); gap: 18px; }
  .lora-sidebar, .lora-main { background: var(--paper); box-shadow: var(--shadow); padding: 26px; min-width: 0; }
  .lora-main { display: grid; gap: 18px; align-content: start; }
  .lora-form { display: grid; gap: 12px; }
  .lora-form label, .lora-fieldset { display: grid; gap: 6px; color: #55564f; font: 700 10px/1.3 monospace; letter-spacing: .04em; }
  .lora-form input, .lora-form select, .lora-form textarea { width: 100%; border: 1px solid var(--line); background: #f7f2e7; padding: 10px; color: var(--ink); }
  .lora-form textarea { min-height: 72px; resize: vertical; }
  .lora-checks { display: flex; flex-wrap: wrap; gap: 8px; }
  .lora-checks label { display: inline-flex; grid-template-columns: auto 1fr; align-items: center; gap: 6px; padding: 8px; border: 1px solid var(--line); background: #e3ddce; cursor: pointer; }
  .lora-primary, .lora-secondary { border: 1px solid var(--ink); padding: 11px 13px; cursor: pointer; font: 800 10px/1 monospace; letter-spacing: .06em; }
  .lora-primary { background: var(--signal); color: white; border-color: var(--signal); }
  .lora-secondary { background: transparent; color: var(--ink); }
  .lora-project-list { margin-top: 24px; display: grid; gap: 8px; }
  .lora-project-button { width: 100%; border: 1px solid var(--line); background: #e4dece; padding: 12px; cursor: pointer; text-align: left; }
  .lora-project-button[aria-current="true"] { border-color: var(--signal); box-shadow: inset 4px 0 0 var(--signal); }
  .lora-project-button strong, .lora-project-button small { display: block; }
  .lora-project-button small { margin-top: 6px; color: var(--muted); font: 700 9px/1.4 monospace; }
  .lora-empty { min-height: 360px; display: grid; place-items: center; text-align: center; border: 1px dashed var(--line); color: var(--muted); padding: 30px; }
  .lora-project-head { display: flex; justify-content: space-between; gap: 18px; align-items: start; border-bottom: 1px solid var(--line); padding-bottom: 18px; }
  .lora-project-head h2 { margin: 5px 0; font: 700 38px/1 "Iowan Old Style", serif; }
  .lora-project-head p { margin: 0; color: var(--muted); font: 700 9px/1.5 monospace; overflow-wrap: anywhere; }
  .lora-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
  .lora-stat { padding: 13px; background: var(--ink); color: var(--paper); }
  .lora-stat strong, .lora-stat span { display: block; }
  .lora-stat strong { color: var(--acid); font: 800 24px/1 monospace; }
  .lora-stat span { margin-top: 7px; color: #aaa99f; font-size: 9px; }
  .lora-panel { border-top: 6px solid var(--ink); background: #e4dece; padding: 18px; }
  .lora-panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 14px; }
  .lora-panel h3 { margin: 0; font: 700 24px/1 "Iowan Old Style", serif; }
  .lora-workspace-picker { display: grid; grid-template-columns: 1fr auto; gap: 8px; }
  .lora-workspace-picker select { min-width: 0; border: 1px solid var(--line); background: #f7f2e7; padding: 10px; }
  .lora-source-grid, .lora-asset-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
  .lora-source-card, .lora-asset-card { background: #f4efe3; border: 1px solid var(--line); min-width: 0; overflow: hidden; }
  .lora-source-card img, .lora-asset-card img { width: 100%; aspect-ratio: 1; object-fit: cover; background: #cbc5b7; display: block; }
  .lora-source-card label { display: grid; grid-template-columns: auto 1fr; gap: 7px; padding: 9px; align-items: start; font-size: 10px; overflow-wrap: anywhere; cursor: pointer; }
  .lora-asset-body { padding: 10px; display: grid; gap: 8px; }
  .lora-asset-name { margin: 0; font: 700 9px/1.4 monospace; overflow-wrap: anywhere; }
  .lora-asset-body select { width: 100%; border: 1px solid var(--line); background: white; padding: 7px; font-size: 10px; }
  .lora-coverage-editor summary { cursor: pointer; color: var(--signal); font: 800 9px/1.4 monospace; }
  .lora-chip-group { margin-top: 8px; }
  .lora-chip-group strong { display: block; margin-bottom: 4px; font-size: 9px; }
  .lora-chip-group label { display: inline-flex; gap: 3px; align-items: center; margin: 2px; padding: 5px; background: #ddd6c6; font-size: 8px; cursor: pointer; }
  .lora-matrix { display: grid; gap: 10px; }
  .lora-matrix-row { display: grid; grid-template-columns: 86px 1fr; gap: 10px; border-top: 1px solid var(--line); padding-top: 10px; }
  .lora-matrix-row > strong { color: var(--signal); font: 800 10px/1.4 monospace; }
  .lora-matrix-items { display: flex; flex-wrap: wrap; gap: 5px; }
  .lora-matrix-item { padding: 6px 8px; background: #cac4b5; color: #55564f; font-size: 9px; }
  .lora-matrix-item.complete { background: var(--acid); color: var(--ink); }
  .lora-warning { padding: 10px; border-left: 4px solid var(--signal); background: #f1e4d7; color: #6e392d; font-size: 10px; line-height: 1.5; }
  .lora-coverage-actions { display: flex; flex-wrap: wrap; justify-content: end; gap: 7px; }
  .lora-coverage-result { margin: 0 0 12px; padding: 10px; border-left: 4px solid var(--acid); background: #f3ede0; color: var(--muted); font: 9px/1.5 monospace; }
  .lora-review-badge { width: fit-content; padding: 4px 6px; background: var(--acid); color: var(--ink); font: 800 7px/1 monospace; }
  @media (max-width: 900px) {
    .lora-hero, .lora-desk { grid-template-columns: 1fr; }
    .lora-source-grid, .lora-asset-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  @media (max-width: 560px) {
    .lora-sidebar, .lora-main { padding: 18px; }
    .lora-stats { grid-template-columns: repeat(2, 1fr); }
    .lora-source-grid, .lora-asset-grid { grid-template-columns: 1fr; }
    .lora-project-head { display: block; }
    .lora-matrix-row { grid-template-columns: 1fr; }
  }
</style>
"""

LORA_HTML = r"""
<section class="lora-page" id="loraPage" hidden>
  <section class="lora-hero">
    <div class="lora-hero-copy">
      <div class="eyebrow">Soda / LoRA project desk</div>
      <h1>LoRA<br>项目台</h1>
      <p>Mac 负责角色定义、选图、覆盖审核和不可变数据集版本；不会改写 OC Manager、原图或原 caption。冻结版本交给 5060 Ti 后，由 Windows 的 AnimaLoraStudio 完成最终筛标、正则和训练。</p>
    </div>
    <aside class="lora-flow">
      <p class="section-label">Four-step flow / 操作顺序</p>
      <ol><li>选择角色、服装、角色服装一体或画风</li><li>写清 Trigger 与固定、可控、变量、禁止漂移</li><li>引用图片，自动初审覆盖后按需人工修正</li><li>确认保留项并冻结数据集交付版本</li></ol>
    </aside>
  </section>
  <section class="lora-desk">
    <aside class="lora-sidebar">
      <p class="section-label">New project / 新建项目</p>
      <form class="lora-form" id="loraCreateForm">
        <label>项目名<input id="loraCreateName" maxlength="160" placeholder="例如：阿莉娅角色 LoRA"></label>
        <label>项目类型<select id="loraCreateType"><option value="character">角色 Character</option><option value="outfit">服装 Outfit</option><option value="character_outfit">角色 + 签名服装</option><option value="style">画风 Style</option></select></label>
        <label>Trigger word<input id="loraCreateTrigger" required pattern="[a-z][a-z0-9_]{2,63}" placeholder="ariya_character"></label>
        <label>从 OC Manager 开始（可选）<select id="loraCreateOc"><option value="">不关联 OC</option></select></label>
        <fieldset class="lora-fieldset"><span>目标模型</span><div class="lora-checks"><label><input type="checkbox" name="loraFamily" value="anima" checked> Anima</label><label><input type="checkbox" name="loraFamily" value="krea2" checked> Krea 2</label></div></fieldset>
        <button class="lora-primary" type="submit">建立项目 →</button>
      </form>
      <div class="lora-project-list" id="loraProjectList"></div>
    </aside>
    <main class="lora-main">
      <div class="lora-empty" id="loraEmpty"><div><strong>先建立或选择一个 LoRA 项目</strong><p>项目建立后，再从已扫描的数据集工作区选图。</p></div></div>
      <div id="loraProjectDetail" hidden>
        <div class="lora-project-head"><div><span class="section-label" id="loraProjectType"></span><h2 id="loraProjectTitle"></h2><p id="loraProjectPath"></p></div><button class="lora-secondary" id="loraSaveProject">保存项目定义</button></div>
        <div class="lora-stats" id="loraStats"></div>
        <section class="lora-panel">
          <div class="lora-panel-head"><h3>1. 项目边界</h3><span class="section-label">Concept binding</span></div>
          <div class="lora-form">
            <label>Trigger word<input id="loraEditTrigger"></label>
            <fieldset class="lora-fieldset"><span>目标模型</span><div class="lora-checks"><label><input type="checkbox" name="loraEditFamily" value="anima"> Anima</label><label><input type="checkbox" name="loraEditFamily" value="krea2"> Krea 2</label></div></fieldset>
            <label>固定特征（主要绑定 Trigger，一行一个）<textarea id="loraFixed"></textarea></label>
            <label>可控特征（需要单独开关，一行一个）<textarea id="loraControllable"></textarea></label>
            <label>允许变化（必须由逐图 caption 如实描述，一行一个）<textarea id="loraVariable"></textarea></label>
            <label>禁止漂移（出现即需要复查，一行一个）<textarea id="loraForbidden"></textarea></label>
            <label>数据集说明<textarea id="loraDatasetNotes"></textarea></label>
            <label>训练尺寸<select id="loraResolution"><option>512</option><option>768</option><option selected>1024</option><option>1280</option><option>1536</option></select></label>
            <label>交付目标<input id="loraTrainingNode" value="5060ti"></label>
            <label>固定测试计划<textarea id="loraTestPlan" placeholder="trigger-only、换装、不同镜头、早中晚 checkpoint 对照……"></textarea></label>
          </div>
        </section>
        <section class="lora-panel">
          <div class="lora-panel-head"><h3>2. 从数据集选图</h3><span class="section-label">Read-only source</span></div>
          <div class="lora-workspace-picker"><select id="loraWorkspaceSelect"><option value="">选择已扫描的数据集工作区</option></select><button class="lora-secondary" id="loraLoadWorkspace">读取图片</button></div>
          <div id="loraWorkspaceAssets"></div>
        </section>
        <section class="lora-panel">
          <div class="lora-panel-head"><h3>3. 已引用图片</h3><span class="section-label">Review & coverage</span></div>
          <div class="lora-asset-grid" id="loraAssetGrid"></div>
        </section>
        <section class="lora-panel">
          <div class="lora-panel-head"><div><h3>4. 覆盖缺口</h3><span class="section-label">Dataset matrix / review before apply</span></div><div class="lora-coverage-actions"><button class="lora-secondary" id="loraCoveragePreview">预览自动初审</button><button class="lora-primary" id="loraCoverageApply" disabled>确认加入建议</button></div></div>
          <p class="lora-coverage-result" id="loraCoverageResult">根据文件名、原 caption 和图片横竖尺寸做保守初审；只补充有明确证据的项，不会改变保留/排除状态。</p>
          <div id="loraWarnings"></div><div class="lora-matrix" id="loraMatrix"></div>
        </section>
        <section class="lora-panel">
          <div class="lora-panel-head"><h3>5. 冻结数据集交付包</h3><button class="lora-primary" id="loraFreezeProject">生成新冻结版本</button></div>
          <p class="archive-notice">Mac 只冻结“保留”和“正则图”及其已审核 Caption，不执行训练；Windows AnimaLoraStudio 继续负责最终筛标、正则和训练。旧版本不会被覆盖。</p>
          <div id="loraExports"></div>
        </section>
      </div>
    </main>
  </section>
</section>
"""

LORA_SCRIPT = r"""
<script>
(() => {
  const state = {projects:[], active:null, options:null, workspaces:[], oc:[], sourceReport:null, coveragePreview:null};
  const splitLines = value => String(value || '').split(/\n|,/).map(item => item.trim()).filter(Boolean);
  const jsonOptions = body => ({method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  async function api(url, options={}) { const response=await fetch(url,options); const payload=await response.json().catch(()=>({})); if(!response.ok) throw new Error(payload.detail || `请求失败 ${response.status}`); return payload; }
  function families(name) { return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(item=>item.value); }
  function setFamilies(name, values) { document.querySelectorAll(`input[name="${name}"]`).forEach(item=>item.checked=values.includes(item.value)); }
  function projectButton(item) { const active=state.active?.project_id===item.project_id; return `<button class="lora-project-button" data-lora-project="${escapeHtml(item.project_id)}" aria-current="${active}"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.concept_type)} · ${escapeHtml(item.trigger_word)} · R${item.revision}</small></button>`; }
  function renderProjectList() { $('#loraProjectList').innerHTML=state.projects.length?state.projects.map(projectButton).join(''):'<p class="archive-notice">还没有 LoRA 项目。</p>'; }
  function fillProjectForm(project) { $('#loraEditTrigger').value=project.trigger_word; setFamilies('loraEditFamily',project.target_families); $('#loraFixed').value=(project.features.fixed||[]).join('\n'); $('#loraControllable').value=(project.features.controllable||[]).join('\n'); $('#loraVariable').value=(project.features.variable||[]).join('\n'); $('#loraForbidden').value=(project.features.forbidden_drift||[]).join('\n'); $('#loraDatasetNotes').value=project.dataset_notes||''; $('#loraResolution').value=String(project.training_resolution); $('#loraTrainingNode').value=project.training_node||'5060ti'; $('#loraTestPlan').value=project.test_plan||''; }
  function renderStats(project) { const report=project.coverage_report, counts=report.status_counts||{}; $('#loraStats').innerHTML=`<div class="lora-stat"><strong>${report.total_assets}</strong><span>全部引用</span></div><div class="lora-stat"><strong>${counts.approved||0}</strong><span>已保留</span></div><div class="lora-stat"><strong>${counts.needs_more||0}</strong><span>待补图</span></div><div class="lora-stat"><strong>${report.gap_count}</strong><span>覆盖缺口</span></div>`; }
  function coverageInputs(asset) { const selected=asset.coverage||{}; return Object.entries(state.options.coverage_dimensions).map(([dimension,items])=>`<div class="lora-chip-group"><strong>${escapeHtml(state.options.coverage_labels_zh[dimension])}</strong>${items.map(item=>`<label><input type="checkbox" data-coverage="${escapeHtml(dimension)}" value="${escapeHtml(item.id)}" ${(selected[dimension]||[]).includes(item.id)?'checked':''}> ${escapeHtml(item.label_zh)} (${escapeHtml(item.id)})</label>`).join('')}</div>`).join(''); }
  function assetCard(asset) { const statuses={candidate:'候选',approved:'保留',excluded:'排除',needs_more:'待补图',regularization:'正则图'}, review=asset.coverage_review?.status==='confirmed'?'<span class="lora-review-badge">覆盖初审已确认</span>':''; return `<article class="lora-asset-card" data-lora-asset="${escapeHtml(asset.asset_id)}"><a href="${escapeHtml(asset.original_url)}" target="_blank" rel="noopener"><img src="${escapeHtml(asset.thumbnail_url)}" alt=""></a><div class="lora-asset-body"><p class="lora-asset-name">${escapeHtml(asset.relative_path)}</p>${review}<select data-asset-status>${Object.entries(statuses).map(([id,label])=>`<option value="${id}" ${asset.status===id?'selected':''}>${label}</option>`).join('')}</select><details class="lora-coverage-editor"><summary>检查或修正这张图的覆盖</summary>${coverageInputs(asset)}<div class="lora-chip-group"><strong>人工风险标记</strong>${state.options.risk_flags.map(flag=>`<label><input type="checkbox" data-risk value="${escapeHtml(flag)}" ${(asset.risk_flags||[]).includes(flag)?'checked':''}> ${escapeHtml(state.options.risk_flag_labels_zh?.[flag]||flag)} (${escapeHtml(flag)})</label>`).join('')}</div><button class="lora-primary" data-save-asset>保存这张图</button></details></div></article>`; }
  function renderAssets(project) { $('#loraAssetGrid').innerHTML=project.assets.length?project.assets.map(assetCard).join(''):'<p class="archive-notice">尚未引用图片。先在上方选择一个数据集工作区。</p>'; }
  function coverageLabel(dimension,value) { const item=(state.options.coverage_dimensions[dimension]||[]).find(candidate=>candidate.id===value); return item?.label_zh ? `${item.label_zh} (${item.id})` : value; }
  function renderMatrix(project) { const report=project.coverage_report; const warnings=[]; if(report.exact_duplicate_assets) warnings.push(`发现 ${report.exact_duplicate_assets} 张完全重复引用`); (report.biases||[]).forEach(item=>warnings.push(`${state.options.coverage_labels_zh[item.dimension]}过度集中在“${coverageLabel(item.dimension,item.value)}”`)); Object.entries(report.risk_counts||{}).forEach(([flag,count])=>warnings.push(`${state.options.risk_flag_labels_zh?.[flag]||flag} (${flag})：${count} 张`)); $('#loraWarnings').innerHTML=warnings.map(value=>`<p class="lora-warning">${escapeHtml(value)}</p>`).join(''); $('#loraMatrix').innerHTML=report.dimensions.map(dimension=>`<div class="lora-matrix-row"><strong>${escapeHtml(dimension.label_zh)} (${escapeHtml(dimension.id)})</strong><div class="lora-matrix-items">${dimension.items.map(item=>`<span class="lora-matrix-item ${item.complete?'complete':''}">${escapeHtml(item.label_zh)} (${escapeHtml(item.id)}) ${item.count}/${item.minimum}</span>`).join('')}</div></div>`).join(''); }
  function renderExports(project) { $('#loraExports').innerHTML=(project.exports||[]).length?[...project.exports].reverse().map(item=>`<p><a class="lora-secondary" href="${escapeHtml(item.download_url)}">下载 ${escapeHtml(item.version_id)}</a> · ${item.image_count} 张 · ${escapeHtml((item.families||[]).join(' + '))}</p>`).join(''):'<p>尚无冻结版本。先确认保留图片与目标 Profile caption。</p>'; }
  function renderActive() { const project=state.active; if(project) { const index=state.projects.findIndex(item=>item.project_id===project.project_id); if(index>=0) state.projects[index]={...state.projects[index],...project}; } renderProjectList(); $('#loraEmpty').hidden=Boolean(project); $('#loraProjectDetail').hidden=!project; if(!project) return; $('#loraProjectType').textContent=`${project.concept_type.toUpperCase()} / ${project.target_families.join(' + ').toUpperCase()}`; $('#loraProjectTitle').textContent=project.name; $('#loraProjectPath').textContent=`Mac 项目目录：${project.project_path}`; fillProjectForm(project); renderStats(project); renderAssets(project); renderMatrix(project); renderExports(project); }
  async function loadProjects(preferred='') { state.projects=await api('/api/lora/projects'); const id=preferred||state.active?.project_id||state.projects[0]?.project_id; state.active=id?await api(`/api/lora/projects/${encodeURIComponent(id)}`):null; renderActive(); }
  async function createProject(event) { event.preventDefault(); const targetFamilies=families('loraFamily'); if(!targetFamilies.length) return alert('至少选择一个目标模型。'); const payload={name:$('#loraCreateName').value.trim()||'未命名 LoRA 项目',concept_type:$('#loraCreateType').value,trigger_word:$('#loraCreateTrigger').value.trim(),target_families:targetFamilies,source_oc_character_id:$('#loraCreateOc').value,features:{fixed:[],controllable:[],variable:[],forbidden_drift:[]},training_resolution:1024,training_node:'5060ti'}; const project=await api('/api/lora/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); event.target.reset(); document.querySelector('input[name="loraFamily"][value="anima"]').checked=true; document.querySelector('input[name="loraFamily"][value="krea2"]').checked=true; await loadProjects(project.project_id); }
  async function saveProject() { const payload={trigger_word:$('#loraEditTrigger').value.trim(),target_families:families('loraEditFamily'),features:{fixed:splitLines($('#loraFixed').value),controllable:splitLines($('#loraControllable').value),variable:splitLines($('#loraVariable').value),forbidden_drift:splitLines($('#loraForbidden').value)},dataset_notes:$('#loraDatasetNotes').value,training_resolution:Number($('#loraResolution').value),training_node:$('#loraTrainingNode').value.trim(),test_plan:$('#loraTestPlan').value}; state.active=await api(`/api/lora/projects/${state.active.project_id}`,jsonOptions(payload)); renderActive(); }
  async function loadWorkspaceReport() { const id=$('#loraWorkspaceSelect').value; if(!id) return; state.sourceReport=await api(`/api/dataset-workspaces/${id}/report`); const existing=new Set((state.active.assets||[]).filter(item=>item.workspace_id===id).map(item=>item.relative_path)); const images=(state.sourceReport.images||[]).filter(item=>item.valid&&!existing.has(item.relative_path)); $('#loraWorkspaceAssets').innerHTML=images.length?`<div class="lora-source-grid">${images.map(item=>`<article class="lora-source-card"><img src="${escapeHtml(item.thumbnail_url)}" alt=""><label><input type="checkbox" data-source-path value="${escapeHtml(item.relative_path)}"> <span>${escapeHtml(item.relative_path)}</span></label></article>`).join('')}</div><button class="lora-primary" id="loraAddSelected">引用选中的图片</button>`:'<p class="archive-notice">这个工作区没有新的可引用图片。</p>'; $('#loraAddSelected')?.addEventListener('click',addSelectedAssets); }
  async function addSelectedAssets() { const paths=[...document.querySelectorAll('[data-source-path]:checked')].map(item=>item.value); if(!paths.length) return alert('请先选择图片。'); state.active=await api(`/api/lora/projects/${state.active.project_id}/assets`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace_id:$('#loraWorkspaceSelect').value,paths})}); renderActive(); await loadWorkspaceReport(); }
  async function saveAsset(card) { const assetId=card.dataset.loraAsset, coverage={}; card.querySelectorAll('[data-coverage]:checked').forEach(item=>(coverage[item.dataset.coverage]??=[]).push(item.value)); const risk_flags=[...card.querySelectorAll('[data-risk]:checked')].map(item=>item.value); state.active=await api(`/api/lora/projects/${state.active.project_id}/assets/${assetId}`,jsonOptions({status:card.querySelector('[data-asset-status]').value,coverage,risk_flags})); renderActive(); }
  async function previewCoverage() { if(!state.active?.assets?.length) return alert('请先从数据集工作区引用图片。'); state.coveragePreview=await api(`/api/lora/projects/${state.active.project_id}/coverage/preview`,{method:'POST'}); const preview=state.coveragePreview, examples=preview.items.slice(0,4).map(item=>item.relative_path).join('、'); $('#loraCoverageResult').textContent=preview.suggested_values?`检查 ${preview.inspected_assets} 张：${preview.suggested_assets} 张有明确证据，可补 ${preview.suggested_values} 个覆盖项。${examples?`例如：${examples}`:''}`:`已检查 ${preview.inspected_assets} 张，没有新的可靠覆盖建议；现有人工标记保持不变。`; $('#loraCoverageApply').disabled=!preview.suggested_values; }
  async function applyCoverage() { const preview=state.coveragePreview; if(!preview?.suggested_values) return; if(!confirm(`确认把 ${preview.suggested_assets} 张图片的 ${preview.suggested_values} 个覆盖建议合并进项目？\n不会覆盖现有标记，也不会改变候选、保留或排除状态。`)) return; const result=await api(`/api/lora/projects/${state.active.project_id}/coverage/apply`,{method:'POST'}); state.active=result.project; state.coveragePreview=null; $('#loraCoverageApply').disabled=true; $('#loraCoverageResult').textContent=`已确认 ${result.preview.suggested_assets} 张、${result.preview.suggested_values} 个覆盖项；仍可逐图展开检查和修正。`; renderActive(); }
  async function freezeProject() { if(!confirm('将当前已保留图片冻结为新的不可变训练版本？')) return; const result=await api(`/api/lora/projects/${state.active.project_id}/freeze`,{method:'POST'}); state.active=result.project; renderActive(); }
  async function ensure() { if(!state.options) { [state.options,state.workspaces]=await Promise.all([api('/api/lora/options'),api('/api/dataset-workspaces')]); const ocResult=await api('/api/oc-manager/characters?limit=50'); state.oc=ocResult.results||[]; $('#loraCreateOc').innerHTML='<option value="">不关联 OC</option>'+state.oc.map(item=>`<option value="${escapeHtml(item.character_id)}">${escapeHtml(item.name)} · ${escapeHtml(item.world||'未分组')}</option>`).join(''); $('#loraWorkspaceSelect').innerHTML='<option value="">选择已扫描的数据集工作区</option>'+state.workspaces.map(item=>`<option value="${escapeHtml(item.workspace_id)}">${escapeHtml(item.name)} · ${item.summary?.valid_image_count||0} 张</option>`).join(''); } await loadProjects(); }
  $('#loraCreateForm').addEventListener('submit',event=>createProject(event).catch(error=>alert(error.message)));
  $('#loraProjectList').addEventListener('click',event=>{ const button=event.target.closest('[data-lora-project]'); if(button) loadProjects(button.dataset.loraProject).catch(error=>alert(error.message)); });
  $('#loraSaveProject').addEventListener('click',()=>saveProject().catch(error=>alert(error.message)));
  $('#loraLoadWorkspace').addEventListener('click',()=>loadWorkspaceReport().catch(error=>alert(error.message)));
  $('#loraAssetGrid').addEventListener('click',event=>{ const button=event.target.closest('[data-save-asset]'); if(button) saveAsset(button.closest('[data-lora-asset]')).catch(error=>alert(error.message)); });
  $('#loraCoveragePreview').addEventListener('click',()=>previewCoverage().catch(error=>alert(error.message)));
  $('#loraCoverageApply').addEventListener('click',()=>applyCoverage().catch(error=>alert(error.message)));
  $('#loraFreezeProject').addEventListener('click',()=>freezeProject().catch(error=>alert(error.message)));
  window.ensureLoraProject=ensure;
})();
</script>
"""
