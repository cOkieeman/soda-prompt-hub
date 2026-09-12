LORA_STYLES = r"""
<style>
  .lora-page { display: grid; gap: 18px; }
  .lora-page .eyebrow, .lora-page .section-label, .lora-page .lora-form label, .lora-page .lora-fieldset { text-transform: none; }
  .lora-hero { display: grid; grid-template-columns: 1.2fr .8fr; background: var(--paper); box-shadow: var(--shadow); }
  .lora-hero-copy { padding: clamp(30px, 5vw, 58px); }
  .lora-hero-copy h1 { margin: 18px 0; font-size: clamp(48px, 7vw, 88px); }
  .lora-hero-copy p { max-width: 720px; color: var(--ink-soft); line-height: 1.7; }
  .lora-flow { padding: 30px; background: var(--ink); color: var(--paper); }
  .lora-flow .section-label { color: var(--on-ink-muted); }
  .lora-flow ol { margin: 24px 0 0; padding: 0; list-style: none; counter-reset: steps; }
  .lora-flow li { counter-increment: steps; display: grid; grid-template-columns: 38px 1fr; gap: 12px; padding: 14px 0; border-top: 1px solid rgba(236,232,220,.2); font-size: 12px; line-height: 1.5; }
  .lora-flow li::before { content: "0" counter(steps); color: var(--acid); font: 800 16px/1 monospace; }
  .lora-desk { display: grid; grid-template-columns: minmax(280px, .32fr) minmax(0, 1fr); gap: 18px; }
  .lora-sidebar, .lora-main { background: var(--paper); box-shadow: var(--shadow); padding: 26px; min-width: 0; }
  .lora-main { display: grid; gap: 18px; align-content: start; }
  .lora-form { display: grid; gap: 12px; }
  .lora-form label, .lora-fieldset { display: grid; gap: 6px; color: var(--muted); font: 800 9px/1.3 monospace; letter-spacing: .1em; }
  .lora-form input, .lora-form select, .lora-form textarea { width: 100%; border: 1px solid var(--line); background: var(--field); padding: 10px; color: var(--ink); }
  .lora-form textarea { min-height: 72px; resize: vertical; }
  .lora-checks { display: flex; flex-wrap: wrap; gap: 8px; }
  .lora-checks label { display: inline-flex; grid-template-columns: auto 1fr; align-items: center; gap: 6px; padding: 8px; border: 1px solid var(--line); background: var(--paper-wash); cursor: pointer; }
  .lora-format-help { margin: 0; color: var(--muted); font: 9px/1.55 monospace; }
  .lora-delivery-readiness { display: grid; gap: 9px; margin: 12px 0; }
  .lora-delivery-format { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 10px; align-items: center; padding: 12px; border: 1px solid var(--line); background: var(--paper-lift); }
  .lora-delivery-format.ready { border-color: var(--ink); box-shadow: inset 4px 0 0 var(--acid); background: var(--paper-lift); }
  .lora-delivery-format.blocked { border-color: var(--signal); box-shadow: inset 4px 0 0 var(--signal); background: #f1e4d7; }
  .lora-delivery-format strong, .lora-delivery-format span { display: block; }
  .lora-delivery-format strong { font: 800 10px/1.35 monospace; }
  .lora-delivery-format span { margin-top: 5px; color: var(--muted); font: 9px/1.5 monospace; }
  .lora-delivery-format button { border: 1px solid var(--ink); padding: 8px 10px; background: transparent; color: var(--ink); font: 800 8px/1.2 monospace; cursor: pointer; transition: background var(--motion-base) var(--ease-standard), color var(--motion-base) var(--ease-standard); }
  .lora-delivery-format button:hover:not(:disabled) { background: var(--ink); color: var(--acid); }
  .lora-primary, .lora-secondary { border: 1px solid var(--ink); padding: 11px 13px; cursor: pointer; font: 800 10px/1 monospace; letter-spacing: .1em; transition: background var(--motion-base) var(--ease-standard), color var(--motion-base) var(--ease-standard), transform var(--motion-base) var(--ease-standard), box-shadow var(--motion-base) var(--ease-standard); }
  .lora-primary { background: var(--signal); color: var(--cream); border-color: var(--signal); }
  .lora-primary:hover:not(:disabled) { transform: translate(-2px, -2px); box-shadow: var(--hard-lift); }
  .lora-secondary { background: transparent; color: var(--ink); }
  .lora-secondary:hover:not(:disabled) { background: var(--ink); color: var(--acid); }
  .lora-project-list { margin-top: 24px; display: grid; gap: 8px; }
  .lora-project-button { width: 100%; border: 1px solid var(--line); background: var(--paper-wash); padding: 12px; cursor: pointer; text-align: left; }
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
  .lora-stat span { margin-top: 7px; color: var(--on-ink-faint); font-size: 9px; }
  .lora-journey { position: sticky; top: 10px; z-index: 6; display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); gap: 1px; border: 1px solid var(--line); background: var(--line); box-shadow: var(--shadow); }
  .lora-journey button { min-width: 0; border: 0; background: var(--paper-deep); padding: 11px 8px; color: var(--ink); text-align: left; cursor: pointer; }
  .lora-journey button[aria-current="step"] { background: var(--ink); color: var(--paper); }
  .lora-journey button span, .lora-journey button strong { display: block; }
  .lora-journey button span { color: var(--signal); font: 800 8px monospace; }
  .lora-journey button[aria-current="step"] span { color: var(--acid); }
  .lora-journey button strong { margin-top: 4px; overflow: hidden; font: 800 11px/1.25 "Iowan Old Style",serif; text-overflow: ellipsis; white-space: nowrap; }
  .lora-step-panel[hidden] { display: none; }
  .lora-panel { border-top: 6px solid var(--ink); background: var(--paper-wash); padding: 18px; }
  .lora-panel-head { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 14px; }
  .lora-panel h3 { margin: 0; font: 700 24px/1 "Iowan Old Style", serif; }
  .lora-workspace-picker { display: grid; grid-template-columns: 1fr auto; gap: 8px; }
  .lora-workspace-picker select { min-width: 0; border: 1px solid var(--line); background: var(--field); padding: 10px; }
  .lora-source-grid, .lora-asset-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
  .lora-source-card, .lora-asset-card { background: var(--paper-lift); border: 1px solid var(--line); min-width: 0; overflow: hidden; }
  .lora-source-card img, .lora-asset-card img { width: 100%; aspect-ratio: 1; object-fit: cover; background: var(--paper-deep); display: block; }
  .lora-source-card label { display: grid; grid-template-columns: auto 1fr; gap: 7px; padding: 9px; align-items: start; font-size: 10px; overflow-wrap: anywhere; cursor: pointer; }
  .lora-asset-body { padding: 10px; display: grid; gap: 8px; }
  .lora-asset-name { margin: 0; font: 700 9px/1.4 monospace; overflow-wrap: anywhere; }
  .lora-asset-body select { width: 100%; border: 1px solid var(--line); background: var(--field); padding: 7px; font-size: 10px; }
  .lora-coverage-editor summary { cursor: pointer; color: var(--signal); font: 800 9px/1.4 monospace; }
  .lora-chip-group { margin-top: 8px; }
  .lora-chip-group strong { display: block; margin-bottom: 4px; font-size: 9px; }
  .lora-chip-group label { display: inline-flex; gap: 3px; align-items: center; margin: 2px; padding: 5px; background: var(--paper-deep); font-size: 8px; cursor: pointer; }
  .lora-matrix { display: grid; gap: 10px; }
  .lora-matrix-row { display: grid; grid-template-columns: 86px 1fr; gap: 10px; border-top: 1px solid var(--line); padding-top: 10px; }
  .lora-matrix-row > strong { color: var(--signal); font: 800 10px/1.4 monospace; }
  .lora-matrix-items { display: flex; flex-wrap: wrap; gap: 5px; }
  .lora-matrix-item { padding: 6px 8px; background: var(--paper-deep); color: var(--ink-soft); font-size: 9px; }
  .lora-matrix-item.complete { background: var(--acid); color: var(--ink); }
  .lora-warning { padding: 10px; border-left: 4px solid var(--signal); background: var(--paper-panel); color: var(--signal); font-size: 10px; line-height: 1.5; font-family: monospace; }
  .lora-coverage-actions { display: flex; flex-wrap: wrap; justify-content: end; gap: 7px; }
  .lora-coverage-result { margin: 0 0 12px; padding: 10px; border-left: 4px solid var(--acid); background: var(--paper-panel); color: var(--muted); font: 800 9px/1.5 monospace; }
  .lora-review-badge { width: fit-content; padding: 4px 6px; background: var(--acid); color: var(--ink); font: 800 7px/1 monospace; }
  .lora-pagination { display: flex; justify-content: center; align-items: center; gap: 12px; margin: 0 0 14px; }
  .lora-pagination[hidden] { display: none; }
  .lora-pagination button { border: 1px solid var(--ink); background: transparent; padding: 8px 10px; color: var(--ink); font: 800 9px monospace; cursor: pointer; }
  .lora-pagination button:disabled { cursor: default; opacity: .35; }
  .lora-pagination span { min-width: 120px; color: var(--muted); text-align: center; font: 800 9px monospace; }
  @media (max-width: 900px) {
    .lora-hero, .lora-desk { grid-template-columns: 1fr; }
    .lora-source-grid, .lora-asset-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  }
  @media (max-width: 560px) {
    .lora-sidebar, .lora-main { padding: 18px; }
    .lora-stats { grid-template-columns: repeat(2, 1fr); }
    .lora-source-grid, .lora-asset-grid { grid-template-columns: 1fr; }
    .lora-project-head { display: block; }
    .lora-journey { grid-template-columns: repeat(5,1fr); }
    .lora-journey button { padding: 9px 4px; text-align: center; }
    .lora-journey button strong { font-size: 9px; }
    .lora-matrix-row { grid-template-columns: 1fr; }
  }
</style>
"""

LORA_HTML = r"""
<section class="lora-page" id="loraPage" hidden>
  <section class="lora-hero">
    <div class="lora-hero-copy">
      <div class="eyebrow">LoRA 数据集准备</div>
      <h1>LoRA<br>数据集</h1>
      <p>这里用来确定 LoRA 要学习什么、选择训练图片，并生成数据集副本。Mac 不会改写 OC Manager、原图或原始说明；筛标、正则和训练仍在 Windows 的 AnimaLoraStudio 中完成。</p>
    </div>
    <aside class="lora-flow">
      <p class="section-label">从哪里开始</p>
      <ol><li>新建项目，说明这是角色、服装还是画风 LoRA</li><li>从已经扫描的数据集中选择训练图片</li><li>检查是否缺少角度、动作或服装变化</li><li>确认后生成交付版本，再到 Windows 训练</li></ol>
    </aside>
  </section>
  <section class="lora-desk">
    <aside class="lora-sidebar">
      <p class="section-label">新建 LoRA 数据集项目</p>
      <form class="lora-form" id="loraCreateForm">
        <label>项目名<input id="loraCreateName" maxlength="160" placeholder="例如：阿莉娅角色 LoRA"></label>
        <label>要训练什么<select id="loraCreateType"><option value="character">角色</option><option value="outfit">服装</option><option value="character_outfit">角色和固定服装</option><option value="style">画风</option></select></label>
        <label>触发词<input id="loraCreateTrigger" required pattern="[a-z][a-z0-9_]{2,63}" placeholder="例如：ariya_character"></label>
        <label>从 OC Manager 开始（可选）<select id="loraCreateOc"><option value="">不关联 OC</option></select></label>
        <fieldset class="lora-fieldset"><span>需要交付的数据集格式</span><div class="lora-checks"><label><input type="checkbox" name="loraFamily" value="anima" checked> Anima · 英文标签</label><label><input type="checkbox" name="loraFamily" value="krea2" checked> Krea 2 · 英文自然语言</label></div><p class="lora-format-help">同时选择时，每张保留图片都要完成两种说明，最后生成两套独立数据集。</p></fieldset>
        <button class="lora-primary" type="submit">建立 LoRA 数据集项目 →</button>
      </form>
      <div class="lora-project-list" id="loraProjectList"></div>
    </aside>
    <main class="lora-main">
      <div class="lora-empty" id="loraEmpty"><div><strong>先建立或选择一个 LoRA 项目</strong><p>项目建立后，再从已扫描的数据集工作区选图。</p></div></div>
      <div id="loraProjectDetail" hidden>
        <div class="lora-project-head"><div><span class="section-label" id="loraProjectType"></span><h2 id="loraProjectTitle"></h2><p id="loraProjectPath"></p></div><button class="lora-secondary" id="loraSaveProject">保存项目定义</button></div>
        <div class="lora-stats" id="loraStats"></div>
        <nav class="lora-journey" id="loraJourney" aria-label="LoRA 数据集五步流程">
          <button type="button" data-lora-step="1" aria-current="step"><span>01</span><strong>定义目标</strong></button>
          <button type="button" data-lora-step="2"><span>02</span><strong>选择图片</strong></button>
          <button type="button" data-lora-step="3"><span>03</span><strong>审核图片</strong></button>
          <button type="button" data-lora-step="4"><span>04</span><strong>检查缺口</strong></button>
          <button type="button" data-lora-step="5"><span>05</span><strong>交付版本</strong></button>
        </nav>
        <section class="lora-panel lora-step-panel" data-lora-panel="1">
          <div class="lora-panel-head"><h3>1. 说明 LoRA 要学习什么</h3><span class="section-label">不确定时只填触发词即可</span></div>
          <div class="lora-form">
            <label>触发词<input id="loraEditTrigger"></label>
            <fieldset class="lora-fieldset"><span>需要交付的数据集格式</span><div class="lora-checks"><label><input type="checkbox" name="loraEditFamily" value="anima"> Anima · 英文标签</label><label><input type="checkbox" name="loraEditFamily" value="krea2"> Krea 2 · 英文自然语言</label></div><p class="lora-format-help">Anima 可用 WD14 起草；Krea 2 需要视觉模型起草英文自然语言。两种结果都必须人工确认。</p></fieldset>
            <label>每张图都应该有的固定特征（一行一个）<textarea id="loraFixed"></textarea></label>
            <label>希望以后能单独控制的特征（一行一个）<textarea id="loraControllable"></textarea></label>
            <label>允许在训练图中变化的内容（一行一个）<textarea id="loraVariable"></textarea></label>
            <label>不希望 LoRA 学进去的内容（一行一个）<textarea id="loraForbidden"></textarea></label>
            <label>数据集说明<textarea id="loraDatasetNotes"></textarea></label>
            <label>训练尺寸<select id="loraResolution"><option>512</option><option>768</option><option selected>1024</option><option>1280</option><option>1536</option></select></label>
            <label>交付去向（只作记录，不会自动开始训练）<input id="loraTrainingNode" value="Windows 训练设备"></label>
            <label>训练后准备怎样测试<textarea id="loraTestPlan" placeholder="只用触发词、换装、不同镜头、不同 checkpoint 对照……"></textarea></label>
          </div>
        </section>
        <section class="lora-panel lora-step-panel" data-lora-panel="2" hidden>
          <div class="lora-panel-head"><h3>2. 从数据集选图</h3><span class="section-label">只读取来源数据集</span></div>
          <div class="lora-workspace-picker"><select id="loraWorkspaceSelect"><option value="">选择已扫描的数据集工作区</option></select><button class="lora-secondary" id="loraLoadWorkspace">读取图片</button></div>
          <div id="loraWorkspaceAssets"></div>
        </section>
        <section class="lora-panel lora-step-panel" data-lora-panel="3" hidden>
          <div class="lora-panel-head"><h3>3. 检查已选图片</h3><span class="section-label">逐张确认用途和质量</span></div>
          <nav class="lora-pagination" id="loraPagination" aria-label="LoRA 图片分页" hidden><button id="loraPreviousPage" type="button">上一页</button><span id="loraPageStatus">第 1 / 1 页</span><button id="loraNextPage" type="button">下一页</button></nav>
          <div class="lora-asset-grid" id="loraAssetGrid"></div>
        </section>
        <section class="lora-panel lora-step-panel" data-lora-panel="4" hidden>
          <div class="lora-panel-head"><div><h3>4. 看看还缺哪些图片</h3><span class="section-label">角度、动作、表情、服装和背景</span></div><div class="lora-coverage-actions"><button class="lora-secondary" id="loraCoveragePreview">检查现有图片</button><button class="lora-primary" id="loraCoverageApply" disabled>把检查结果写入图片记录</button></div></div>
          <p class="lora-coverage-result" id="loraCoverageResult">系统会根据文件名、原始说明和图片尺寸做保守判断。它不会替您决定保留或排除图片。</p>
          <div id="loraWarnings"></div><div class="lora-matrix" id="loraMatrix"></div>
        </section>
        <section class="lora-panel lora-step-panel" data-lora-panel="5" hidden>
          <div class="lora-panel-head"><h3>5. 生成数据集交付版本</h3><button class="lora-primary" id="loraFreezeProject">生成新的交付版本</button></div>
          <p class="archive-notice">Mac 只复制已经确认保留的图片和说明文字，不执行训练。Windows AnimaLoraStudio 继续负责最终筛标、正则和训练，旧版本不会被覆盖。</p>
          <div class="lora-delivery-readiness" id="loraDeliveryReadiness"><p class="archive-notice">正在检查两种说明文字是否齐全……</p></div>
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
  const state = {projects:[], active:null, readiness:null, options:null, workspaces:[], oc:[], sourceReport:null, sourceImages:[], sourceSelected:new Set(), sourcePage:1, sourcePageSize:12, coveragePreview:null, step:1, assetPage:1, assetPageSize:12};
  const splitLines = value => String(value || '').split(/\n|,/).map(item => item.trim()).filter(Boolean);
  const jsonOptions = body => ({method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  async function api(url, options={}) { const response=await fetch(url,options); const payload=await response.json().catch(()=>({})); if(!response.ok) throw new Error(payload.detail || `请求失败 ${response.status}`); return payload; }
  function families(name) { return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(item=>item.value); }
  function setFamilies(name, values) { document.querySelectorAll(`input[name="${name}"]`).forEach(item=>item.checked=values.includes(item.value)); }
  function projectButton(item) { const active=state.active?.project_id===item.project_id,types={character:'角色',outfit:'服装',character_outfit:'角色和固定服装',style:'画风'}; return `<button class="lora-project-button" data-lora-project="${escapeHtml(item.project_id)}" aria-current="${active}"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(types[item.concept_type]||item.concept_type)} · 触发词 ${escapeHtml(item.trigger_word)} · 第 ${item.revision} 次修改</small></button>`; }
  function renderProjectList() { $('#loraProjectList').innerHTML=state.projects.length?state.projects.map(projectButton).join(''):'<p class="archive-notice">还没有 LoRA 项目。</p>'; }
  function fillProjectForm(project) { $('#loraEditTrigger').value=project.trigger_word; setFamilies('loraEditFamily',project.target_families); $('#loraFixed').value=(project.features.fixed||[]).join('\n'); $('#loraControllable').value=(project.features.controllable||[]).join('\n'); $('#loraVariable').value=(project.features.variable||[]).join('\n'); $('#loraForbidden').value=(project.features.forbidden_drift||[]).join('\n'); $('#loraDatasetNotes').value=project.dataset_notes||''; $('#loraResolution').value=String(project.training_resolution); $('#loraTrainingNode').value=project.training_node||'Windows 训练设备'; $('#loraTestPlan').value=project.test_plan||''; }
  function renderStats(project) { const report=project.coverage_report, counts=report.status_counts||{}; $('#loraStats').innerHTML=`<div class="lora-stat"><strong>${report.total_assets}</strong><span>已经选入</span></div><div class="lora-stat"><strong>${counts.approved||0}</strong><span>确认保留</span></div><div class="lora-stat"><strong>${counts.needs_more||0}</strong><span>需要补图</span></div><div class="lora-stat"><strong>${report.gap_count}</strong><span>缺少的画面类型</span></div>`; }
  function renderReadiness(project) { const readiness=state.readiness?.project_id===project.project_id?state.readiness:null, container=$('#loraDeliveryReadiness'), button=$('#loraFreezeProject'); if(!readiness) { container.innerHTML='<p class="archive-notice">正在检查两种说明文字是否齐全……</p>'; button.disabled=true; return; } const labels={anima:'Anima · 英文标签',krea2:'Krea 2 · 英文自然语言'}, actions={anima:'去准备 Anima 标签',krea2:'去生成 Krea 2 说明'}; if(!readiness.eligible_count) { container.innerHTML='<p class="lora-warning">还没有确认保留的图片。先到第 3 步选择图片并标记为“保留”。</p>'; button.disabled=true; return; } const cards=project.target_families.map(family=>{ const item=readiness.families?.[family]||{total:readiness.eligible_count,complete:0}, problems=[]; if(item.missing) problems.push(`缺少 ${item.missing} 张`); if(item.pending_review) problems.push(`${item.pending_review} 张尚未确认`); if(item.non_english) problems.push(`${item.non_english} 张不是纯英文`); if(item.missing_trigger) problems.push(`${item.missing_trigger} 张缺少触发词`); const workspace=item.workspace_ids?.[0]||'', detail=item.ready?'可以生成':problems.join('；')||'尚未完成'; return `<article class="lora-delivery-format ${item.ready?'ready':'blocked'}"><div><strong>${escapeHtml(labels[family]||family)}：当前 ${item.complete}/${item.total} 张已完成</strong><span>${escapeHtml(detail)}</span></div>${item.ready||!workspace?'':`<button type="button" data-open-caption-workspace="${escapeHtml(workspace)}" data-caption-family="${escapeHtml(family)}">${escapeHtml(actions[family]||'去补齐说明')}</button>`}</article>`; }).join(''); const duplicate=readiness.duplicate_count?`<p class="lora-warning">还有 ${readiness.duplicate_count} 张完全重复图片，生成前需要排除。</p>`:''; container.innerHTML=cards+duplicate; button.disabled=!readiness.ready; }
  function setLoraStep(step,{focus=false}={}) { state.step=Math.min(Math.max(Number(step)||1,1),5); document.querySelectorAll('[data-lora-step]').forEach(button=>{ const active=Number(button.dataset.loraStep)===state.step; button.setAttribute('aria-current',active?'step':'false'); if(active&&focus) button.focus(); }); document.querySelectorAll('[data-lora-panel]').forEach(panel=>panel.hidden=Number(panel.dataset.loraPanel)!==state.step); $('#loraSaveProject').hidden=state.step!==1; }
  function coverageInputs(asset) { const selected=asset.coverage||{}; return Object.entries(state.options.coverage_dimensions).map(([dimension,items])=>`<div class="lora-chip-group"><strong>${escapeHtml(state.options.coverage_labels_zh[dimension])}</strong>${items.map(item=>`<label><input type="checkbox" data-coverage="${escapeHtml(dimension)}" value="${escapeHtml(item.id)}" ${(selected[dimension]||[]).includes(item.id)?'checked':''}> ${escapeHtml(item.label_zh)}</label>`).join('')}</div>`).join(''); }
  function assetCard(asset) { const statuses={candidate:'候选',approved:'保留',excluded:'排除',needs_more:'待补图',regularization:'正则图'}, review=asset.coverage_review?.status==='confirmed'?'<span class="lora-review-badge">画面检查已确认</span>':''; return `<article class="lora-asset-card" data-lora-asset="${escapeHtml(asset.asset_id)}"><a href="${escapeHtml(asset.original_url)}" target="_blank" rel="noopener"><img src="${escapeHtml(asset.thumbnail_url)}" alt="${escapeHtml(asset.relative_path)}" loading="lazy"></a><div class="lora-asset-body"><p class="lora-asset-name">${escapeHtml(asset.relative_path)}</p>${review}<select data-asset-status aria-label="这张图片的处理状态">${Object.entries(statuses).map(([id,label])=>`<option value="${id}" ${asset.status===id?'selected':''}>${label}</option>`).join('')}</select><span class="lora-asset-save-status" data-asset-save-status aria-live="polite"></span><details class="lora-coverage-editor" data-editor-ready="false"><summary>检查或修正这张图的内容分类</summary></details></div></article>`; }
  function renderCoverageEditor(details,asset) { if(details.dataset.editorReady==='true') return; details.insertAdjacentHTML('beforeend',`${coverageInputs(asset)}<div class="lora-chip-group"><strong>需要人工注意的问题</strong>${state.options.risk_flags.map(flag=>`<label><input type="checkbox" data-risk value="${escapeHtml(flag)}" ${(asset.risk_flags||[]).includes(flag)?'checked':''}> ${escapeHtml(state.options.risk_flag_labels_zh?.[flag]||flag)}</label>`).join('')}</div><button class="lora-primary" data-save-asset>保存这张图</button>`); details.dataset.editorReady='true'; }
  function renderAssets(project) { const pageCount=Math.max(1,Math.ceil(project.assets.length/state.assetPageSize)); state.assetPage=Math.min(Math.max(state.assetPage,1),pageCount); const start=(state.assetPage-1)*state.assetPageSize,pageItems=project.assets.slice(start,start+state.assetPageSize); $('#loraPagination').hidden=project.assets.length<=state.assetPageSize; $('#loraPageStatus').textContent=`第 ${state.assetPage} / ${pageCount} 页 · ${project.assets.length} 张`; $('#loraPreviousPage').disabled=state.assetPage<=1; $('#loraNextPage').disabled=state.assetPage>=pageCount; $('#loraAssetGrid').innerHTML=pageItems.length?pageItems.map(assetCard).join(''):'<p class="archive-notice">尚未引用图片。先在“选择图片”中读取一个数据集工作区。</p>'; }
  function renderSourceImages() { const pageCount=Math.max(1,Math.ceil(state.sourceImages.length/state.sourcePageSize)); state.sourcePage=Math.min(Math.max(state.sourcePage,1),pageCount); const start=(state.sourcePage-1)*state.sourcePageSize,pageItems=state.sourceImages.slice(start,start+state.sourcePageSize); if(!pageItems.length) { $('#loraWorkspaceAssets').innerHTML='<p class="archive-notice">这个工作区没有新的可引用图片。</p>'; return; } $('#loraWorkspaceAssets').innerHTML=`<nav class="lora-pagination" aria-label="待选图片分页" ${state.sourceImages.length<=state.sourcePageSize?'hidden':''}><button type="button" data-source-page="previous" ${state.sourcePage<=1?'disabled':''}>上一页</button><span>第 ${state.sourcePage} / ${pageCount} 页 · ${state.sourceImages.length} 张</span><button type="button" data-source-page="next" ${state.sourcePage>=pageCount?'disabled':''}>下一页</button></nav><div class="lora-source-grid">${pageItems.map(item=>`<article class="lora-source-card"><img src="${escapeHtml(item.thumbnail_url)}" alt="${escapeHtml(item.relative_path)}" loading="lazy"><label><input type="checkbox" data-source-path value="${escapeHtml(item.relative_path)}" ${state.sourceSelected.has(item.relative_path)?'checked':''}> <span>${escapeHtml(item.relative_path)}</span></label></article>`).join('')}</div><button class="lora-primary" type="button" data-add-selected ${state.sourceSelected.size?'':'disabled'}>引用已选图片（${state.sourceSelected.size}）</button>`; }
  function coverageLabel(dimension,value) { const item=(state.options.coverage_dimensions[dimension]||[]).find(candidate=>candidate.id===value); return item?.label_zh||value; }
  function renderMatrix(project) { const report=project.coverage_report; const warnings=[]; if(report.exact_duplicate_assets) warnings.push(`发现 ${report.exact_duplicate_assets} 张完全重复引用`); (report.biases||[]).forEach(item=>warnings.push(`${state.options.coverage_labels_zh[item.dimension]}过度集中在“${coverageLabel(item.dimension,item.value)}”`)); Object.entries(report.risk_counts||{}).forEach(([flag,count])=>warnings.push(`${state.options.risk_flag_labels_zh?.[flag]||flag}：${count} 张`)); $('#loraWarnings').innerHTML=warnings.map(value=>`<p class="lora-warning">${escapeHtml(value)}</p>`).join(''); $('#loraMatrix').innerHTML=report.dimensions.map(dimension=>`<div class="lora-matrix-row"><strong>${escapeHtml(dimension.label_zh)}</strong><div class="lora-matrix-items">${dimension.items.map(item=>`<span class="lora-matrix-item ${item.complete?'complete':''}">${escapeHtml(item.label_zh)} ${item.count}/${item.minimum}</span>`).join('')}</div></div>`).join(''); }
  function renderExports(project) { $('#loraExports').innerHTML=(project.exports||[]).length?[...project.exports].reverse().map(item=>`<p><a class="lora-secondary" href="${escapeHtml(item.download_url)}">下载 ${escapeHtml(item.version_id)}</a> · ${item.image_count} 张 · ${escapeHtml((item.families||[]).join(' + '))}</p>`).join(''):'<p>还没有交付版本。请先确认要保留的图片和对应说明文字。</p>'; }
  function renderActive() { const project=state.active; if(project) { const index=state.projects.findIndex(item=>item.project_id===project.project_id); if(index>=0) state.projects[index]={...state.projects[index],...project}; } renderProjectList(); $('#loraEmpty').hidden=Boolean(project); $('#loraProjectDetail').hidden=!project; if(!project) return; const types={character:'角色 LoRA',outfit:'服装 LoRA',character_outfit:'角色与固定服装 LoRA',style:'画风 LoRA'}, families={anima:'Anima',krea2:'Krea 2'}; $('#loraProjectType').textContent=`${types[project.concept_type]||'LoRA 数据集'} · ${project.target_families.map(item=>families[item]||item).join(' + ')}`; $('#loraProjectTitle').textContent=project.name; $('#loraProjectPath').textContent=`Mac 项目目录：${project.project_path}`; fillProjectForm(project); renderStats(project); renderAssets(project); renderMatrix(project); renderReadiness(project); renderExports(project); setLoraStep(state.step); }
  async function refreshReadiness() { const id=state.active?.project_id; if(!id) { state.readiness=null; return; } const readiness=await api(`/api/lora/projects/${encodeURIComponent(id)}/readiness`); if(state.active?.project_id!==id) return; state.readiness=readiness; renderReadiness(state.active); }
  async function loadProjects(preferred='') { state.projects=await api('/api/lora/projects'); const id=preferred||state.active?.project_id||state.projects[0]?.project_id; state.readiness=null; if(id) [state.active,state.readiness]=await Promise.all([api(`/api/lora/projects/${encodeURIComponent(id)}`),api(`/api/lora/projects/${encodeURIComponent(id)}/readiness`)]); else state.active=null; renderActive(); }
  function resetProjectView() { state.step=1; state.assetPage=1; state.sourceReport=null; state.sourceImages=[]; state.sourceSelected.clear(); state.sourcePage=1; $('#loraWorkspaceAssets').innerHTML=''; }
  async function createProject(event) { event.preventDefault(); const targetFamilies=families('loraFamily'); if(!targetFamilies.length) return alert('至少选择一种需要交付的数据集格式。'); const payload={name:$('#loraCreateName').value.trim()||'未命名 LoRA 项目',concept_type:$('#loraCreateType').value,trigger_word:$('#loraCreateTrigger').value.trim(),target_families:targetFamilies,source_oc_character_id:$('#loraCreateOc').value,features:{fixed:[],controllable:[],variable:[],forbidden_drift:[]},training_resolution:1024,training_node:'Windows 训练设备'}; const project=await api('/api/lora/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); event.target.reset(); document.querySelector('input[name="loraFamily"][value="anima"]').checked=true; document.querySelector('input[name="loraFamily"][value="krea2"]').checked=true; resetProjectView(); await loadProjects(project.project_id); }
  async function saveProject() { const targetFamilies=families('loraEditFamily'); if(!targetFamilies.length) return alert('至少选择一种需要交付的数据集格式。'); const payload={trigger_word:$('#loraEditTrigger').value.trim(),target_families:targetFamilies,features:{fixed:splitLines($('#loraFixed').value),controllable:splitLines($('#loraControllable').value),variable:splitLines($('#loraVariable').value),forbidden_drift:splitLines($('#loraForbidden').value)},dataset_notes:$('#loraDatasetNotes').value,training_resolution:Number($('#loraResolution').value),training_node:$('#loraTrainingNode').value.trim(),test_plan:$('#loraTestPlan').value}; state.active=await api(`/api/lora/projects/${state.active.project_id}`,jsonOptions(payload)); state.readiness=null; renderActive(); await refreshReadiness(); }
  async function loadWorkspaceReport() { const id=$('#loraWorkspaceSelect').value; if(!id) return; state.sourceReport=await api(`/api/dataset-workspaces/${id}/report`); const existing=new Set((state.active.assets||[]).filter(item=>item.workspace_id===id).map(item=>item.relative_path)); state.sourceImages=(state.sourceReport.images||[]).filter(item=>item.valid&&!existing.has(item.relative_path)); state.sourceSelected.clear(); state.sourcePage=1; renderSourceImages(); }
  async function addSelectedAssets() { const paths=[...state.sourceSelected]; if(!paths.length) return alert('请先选择图片。'); state.active=await api(`/api/lora/projects/${state.active.project_id}/assets`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({workspace_id:$('#loraWorkspaceSelect').value,paths})}); state.readiness=null; state.assetPage=Math.ceil(state.active.assets.length/state.assetPageSize)||1; renderActive(); await Promise.all([loadWorkspaceReport(),refreshReadiness()]); setLoraStep(3); }
  async function saveAsset(card) { const assetId=card.dataset.loraAsset, coverage={}; card.querySelectorAll('[data-coverage]:checked').forEach(item=>(coverage[item.dataset.coverage]??=[]).push(item.value)); const risk_flags=[...card.querySelectorAll('[data-risk]:checked')].map(item=>item.value); state.active=await api(`/api/lora/projects/${state.active.project_id}/assets/${assetId}`,jsonOptions({status:card.querySelector('[data-asset-status]').value,coverage,risk_flags})); state.readiness=null; renderActive(); await refreshReadiness(); }
  async function saveAssetStatus(card) { const assetId=card.dataset.loraAsset, select=card.querySelector('[data-asset-status]'), message=card.querySelector('[data-asset-save-status]'), previous=state.active.assets.find(item=>item.asset_id===assetId)?.status || 'candidate'; select.disabled=true; message.textContent='正在保存…'; try { state.active=await api(`/api/lora/projects/${state.active.project_id}/assets/${assetId}`,jsonOptions({status:select.value})); state.readiness=null; renderActive(); await refreshReadiness(); const refreshed=[...document.querySelectorAll('[data-lora-asset]')].find(item=>item.dataset.loraAsset===assetId); if(refreshed) refreshed.querySelector('[data-asset-save-status]').textContent='已保存'; } catch(error) { select.disabled=false; select.value=previous; message.textContent=`保存失败：${error.message}`; throw error; } }
  async function previewCoverage() { if(!state.active?.assets?.length) return alert('请先从数据集工作区引用图片。'); state.coveragePreview=await api(`/api/lora/projects/${state.active.project_id}/coverage/preview`,{method:'POST'}); const preview=state.coveragePreview, examples=preview.items.slice(0,4).map(item=>item.relative_path).join('、'); $('#loraCoverageResult').textContent=preview.suggested_values?`检查 ${preview.inspected_assets} 张：${preview.suggested_assets} 张有明确证据，可补 ${preview.suggested_values} 个覆盖项。${examples?`例如：${examples}`:''}`:`已检查 ${preview.inspected_assets} 张，没有新的可靠覆盖建议；现有人工标记保持不变。`; $('#loraCoverageApply').disabled=!preview.suggested_values; }
  async function applyCoverage() { const preview=state.coveragePreview; if(!preview?.suggested_values) return; if(!confirm(`确认把 ${preview.suggested_assets} 张图片的 ${preview.suggested_values} 个覆盖建议合并进项目？\n不会覆盖现有标记，也不会改变候选、保留或排除状态。`)) return; const result=await api(`/api/lora/projects/${state.active.project_id}/coverage/apply`,{method:'POST'}); state.active=result.project; state.coveragePreview=null; $('#loraCoverageApply').disabled=true; $('#loraCoverageResult').textContent=`已确认 ${result.preview.suggested_assets} 张、${result.preview.suggested_values} 个覆盖项；仍可逐图展开检查和修正。`; renderActive(); }
  async function freezeProject() { if(!state.readiness?.ready) return alert('还有图片或说明文字没有完成，请先按上面的提示补齐。'); if(!confirm('用当前确认保留的图片生成新的数据集副本？\n如果同时选择 Anima 和 Krea 2，会生成两套独立目录；旧版本和原图片都不会被修改。')) return; const result=await api(`/api/lora/projects/${state.active.project_id}/freeze`,{method:'POST'}); state.active=result.project; renderActive(); }
  async function ensure() { if(!state.options) { [state.options,state.workspaces]=await Promise.all([api('/api/lora/options'),api('/api/dataset-workspaces')]); const ocResult=await api('/api/oc-manager/characters?limit=50'); state.oc=ocResult.results||[]; $('#loraCreateOc').innerHTML='<option value="">不关联 OC</option>'+state.oc.map(item=>`<option value="${escapeHtml(item.character_id)}">${escapeHtml(item.name)} · ${escapeHtml(item.world||'未分组')}</option>`).join(''); $('#loraWorkspaceSelect').innerHTML='<option value="">选择已扫描的数据集工作区</option>'+state.workspaces.map(item=>`<option value="${escapeHtml(item.workspace_id)}">${escapeHtml(item.name)} · ${item.summary?.valid_image_count||0} 张</option>`).join(''); } await loadProjects(); }
  $('#loraCreateForm').addEventListener('submit',event=>createProject(event).catch(error=>alert(error.message)));
  $('#loraProjectList').addEventListener('click',event=>{ const button=event.target.closest('[data-lora-project]'); if(!button) return; resetProjectView(); loadProjects(button.dataset.loraProject).catch(error=>alert(error.message)); });
  $('#loraSaveProject').addEventListener('click',()=>saveProject().catch(error=>alert(error.message)));
  $('#loraLoadWorkspace').addEventListener('click',()=>loadWorkspaceReport().catch(error=>alert(error.message)));
  $('#loraJourney').addEventListener('click',event=>{ const button=event.target.closest('[data-lora-step]'); if(button) setLoraStep(button.dataset.loraStep); });
  $('#loraJourney').addEventListener('keydown',event=>{ const button=event.target.closest('[data-lora-step]'); if(!button||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return; event.preventDefault(); const current=Number(button.dataset.loraStep), next=event.key==='Home'?1:event.key==='End'?5:Math.min(Math.max(current+(event.key==='ArrowRight'?1:-1),1),5); setLoraStep(next,{focus:true}); });
  $('#loraWorkspaceAssets').addEventListener('change',event=>{ const input=event.target.closest('[data-source-path]'); if(!input) return; if(input.checked) state.sourceSelected.add(input.value); else state.sourceSelected.delete(input.value); const button=$('[data-add-selected]'); if(button) { button.disabled=!state.sourceSelected.size; button.textContent=`引用已选图片（${state.sourceSelected.size}）`; } });
  $('#loraWorkspaceAssets').addEventListener('click',event=>{ const pageButton=event.target.closest('[data-source-page]'); if(pageButton) { state.sourcePage+=pageButton.dataset.sourcePage==='next'?1:-1; renderSourceImages(); return; } const addButton=event.target.closest('[data-add-selected]'); if(addButton) addSelectedAssets().catch(error=>alert(error.message)); });
  $('#loraPreviousPage').addEventListener('click',()=>{ if(state.assetPage<=1) return; state.assetPage-=1; renderAssets(state.active); });
  $('#loraNextPage').addEventListener('click',()=>{ if(state.assetPage*state.assetPageSize>=state.active.assets.length) return; state.assetPage+=1; renderAssets(state.active); });
  $('#loraAssetGrid').addEventListener('click',event=>{ const card=event.target.closest('[data-lora-asset]'); if(!card) return; const summary=event.target.closest('summary'); if(summary) { const asset=state.active.assets.find(item=>item.asset_id===card.dataset.loraAsset); if(asset) renderCoverageEditor(summary.closest('details'),asset); return; } const button=event.target.closest('[data-save-asset]'); if(button) saveAsset(card).catch(error=>alert(error.message)); });
  $('#loraAssetGrid').addEventListener('change',event=>{ const select=event.target.closest('[data-asset-status]'); if(!select) return; const card=select.closest('[data-lora-asset]'); saveAssetStatus(card).catch(error=>console.error(error)); });
  $('#loraCoveragePreview').addEventListener('click',()=>previewCoverage().catch(error=>alert(error.message)));
  $('#loraCoverageApply').addEventListener('click',()=>applyCoverage().catch(error=>alert(error.message)));
  $('#loraFreezeProject').addEventListener('click',()=>freezeProject().catch(error=>alert(error.message)));
  $('#loraDeliveryReadiness').addEventListener('click',event=>{ const button=event.target.closest('[data-open-caption-workspace]'); if(!button) return; const workspaceId=button.dataset.openCaptionWorkspace, family=button.dataset.captionFamily; window.setPromptHubView?.('datasets').then(()=>{ const profile=$('#datasetDeliveryProfile'); if(profile) { profile.value=family; profile.dispatchEvent(new Event('change')); } return window.openDatasetWorkspace?.(workspaceId,3); }).catch(error=>alert(error.message)); });
  window.ensureLoraProject=ensure;
})();
</script>
"""
