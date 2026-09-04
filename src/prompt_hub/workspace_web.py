# ruff: noqa: E501, RUF001

WORKSPACE_HTML = r"""
<section class="dataset-page" id="workspacePage" hidden>
  <header class="dataset-heading">
    <div><span class="eyebrow">只在 Mac 上整理</span><h1>数据集工作台</h1></div>
    <div class="dataset-heading-copy"><p>从本地图片文件夹开始，按五步完成检查、标签、人工审核和交付。源图片与原始说明文字始终只读。</p><div class="dataset-mode-switch" aria-label="数据集页面显示模式"><button id="datasetModeSimple" type="button" aria-pressed="true">简单模式</button><button id="datasetModeAdvanced" type="button" aria-pressed="false">高级检查</button></div></div>
  </header>
  <div class="dataset-layout">
    <aside class="dataset-sidebar">
      <form id="datasetImportForm">
        <span class="dataset-step-kicker">01 · 导入素材</span>
        <label>数据集文件夹路径<input id="datasetSourcePath" required placeholder="/Users/your-name/Pictures/my-dataset"></label>
        <label>显示名称（可选）<input id="datasetName" maxlength="160" placeholder="角色名 / 项目名"></label>
        <button class="dataset-primary" type="submit">读取文件夹并开始检查</button>
        <p class="dataset-hint">只读取并建立 Mac 工作区，不会移动、改名或覆盖文件夹中的任何内容。</p>
      </form>
      <div class="dataset-sidebar-head"><strong>最近工作区</strong><span id="datasetWorkspaceCount">0</span></div>
      <div id="datasetWorkspaceList" class="dataset-workspace-list"></div>
    </aside>
    <main class="dataset-main">
      <div id="datasetEmpty" class="dataset-empty">
        <span>01</span><h2>先读取一个图片文件夹</h2><p>扫描完成后，这里会显示缩略图、缺少的图片说明、坏图、重复图片和审核状态。</p>
      </div>
      <div id="datasetDesk" hidden>
        <div class="dataset-titlebar">
          <div><span class="section-label">当前数据集</span><h2 id="datasetActiveName">—</h2><p id="datasetActivePath">—</p><div class="dataset-origin" id="datasetOrigin"></div></div>
          <div class="dataset-title-actions"><button id="datasetRescan">重新扫描</button><button class="danger" id="datasetRemove">移除记录</button></div>
        </div>
        <div id="datasetJobPanel" class="dataset-job-panel" hidden></div>
        <nav class="dataset-journey" id="datasetJourney" aria-label="数据集交付五步流程">
          <button type="button" data-dataset-step="1"><span>01</span><strong>导入素材</strong><small>选择本地文件夹</small></button>
          <button type="button" data-dataset-step="2"><span>02</span><strong>检查问题</strong><small>坏图与重复</small></button>
          <button type="button" data-dataset-step="3"><span>03</span><strong>准备标签</strong><small>WD14 / 旧标签</small></button>
          <button type="button" data-dataset-step="4"><span>04</span><strong>人工审核</strong><small>确认图片和说明文字</small></button>
          <button type="button" data-dataset-step="5"><span>05</span><strong>生成交付版本</strong><small>建立独立副本</small></button>
        </nav>
        <section class="dataset-readiness" id="datasetReadiness">
          <div class="dataset-readiness-copy"><span class="section-label" id="datasetCurrentStepLabel">当前步骤</span><h3 id="datasetReadinessTitle">正在判断数据集状态</h3><p id="datasetReadinessMessage">扫描完成后会告诉你还缺什么，以及下一步应该点哪里。</p><ul id="datasetBlockingList"></ul></div>
          <div class="dataset-readiness-action"><label>本次交付使用哪种说明<select id="datasetDeliveryProfile"><option value="anima">Anima · 英文标签</option><option value="krea2">Krea 2 · 英文自然语言</option></select></label><button class="dataset-primary" id="datasetNextAction" type="button">查看下一步</button><small>两种格式分开计算、分开保存，不会互相覆盖。</small></div>
        </section>
        <div class="dataset-stats" id="datasetStats"></div>
        <section class="dataset-curation-panel" data-dataset-stage-panel="3">
          <div class="dataset-curation-head"><div><span class="section-label">03 · 准备标签</span><h3 id="datasetCurationTitle">选择一种方式准备图片说明</h3></div><p id="datasetCurationHint">优先使用已有 `.txt`；缺少 Anima 标签时再运行 WD14。所有结果先保存在 Prompt Hub，不写回原文件夹。</p></div>
          <div class="dataset-curation-grid">
            <div class="dataset-curation-block">
              <strong>方案 A · 接续已有 .txt</strong>
              <p class="dataset-hint">适合已经打过标签的数据集。先看会影响哪些图片，确认后写入所选格式，并留下可回退的修改记录。</p>
              <div class="dataset-thresholds"><label>写入哪种格式<select id="datasetSourceCaptionProfile"><option value="anima">Anima 标签</option><option value="krea2">Krea 2 自然语言</option></select></label><label>写入后的状态<select id="datasetSourceCaptionStatus"><option value="draft">待审核</option><option value="reviewed">已人工审核</option></select></label></div>
              <label class="dataset-inline-check"><input id="datasetSourceCaptionOverwrite" type="checkbox"> 替换这种格式已有的内容</label>
              <div class="dataset-action-row"><button data-source-caption-scope="all">预览全部图片</button><button data-source-caption-scope="selected">预览已选图片</button><button id="datasetSourceCaptionApply" disabled>确认写入并保存修改记录</button></div>
              <p id="datasetSourceCaptionResult" class="dataset-hint">默认只填空白内容，不改原 `.txt`，也不运行 WD14。</p>
            </div>
            <div class="dataset-curation-block" data-caption-profile="anima">
              <strong>方案 B · WD14 生成 Anima 草稿</strong>
              <p class="dataset-hint">只在缺少 Anima 标签时使用。结果是待人工检查的草稿，不会直接进入交付版本。</p>
              <div class="dataset-thresholds"><label>普通标签最低可信度<input id="datasetGeneralThreshold" type="number" min="0" max="1" step="0.05" value="0.35"></label><label>角色标签最低可信度<input id="datasetCharacterThreshold" type="number" min="0" max="1" step="0.05" value="0.85"></label></div>
              <div class="dataset-action-row"><button data-wd14-scope="selected">为已选生成草稿</button><button data-wd14-scope="untagged">补齐未打标草稿</button><button data-wd14-scope="failed">重试失败项</button><button class="dataset-advanced-only" data-wd14-scope="all">高级：全部重跑</button></div>
            </div>
            <div class="dataset-curation-block" data-caption-profile="anima">
              <strong>方案 C · 批量整理 Anima 标签</strong>
              <p class="dataset-hint">对已选图片统一增删标签。先预览变化，确认时才写入并建立快照。</p>
              <label>增加标签<input id="datasetBulkAdd" list="datasetTagSuggestions" placeholder="银发, solo"></label><label>删除标签<input id="datasetBulkRemove" list="datasetTagSuggestions" placeholder="水印, text"></label>
              <datalist id="datasetTagSuggestions"></datalist>
              <div class="dataset-action-row"><label class="dataset-inline-check"><input id="datasetBulkSort" type="checkbox"> 排序</label><button id="datasetBulkPreview">预览标签修改</button><button id="datasetBulkApply" disabled>确认写入并建快照</button></div>
              <p id="datasetBulkResult" class="dataset-hint">先选择图片，再预览。确认修改前会自动保存一份可回退记录。</p>
            </div>
            <div class="dataset-curation-block" data-caption-profile="krea2">
              <strong>方案 D · Krea 2 视觉草稿</strong>
              <label>本地视觉模型<select id="datasetKrea2Model"><option value="">正在读取 LM Studio……</option></select></label>
              <div class="dataset-action-row"><button data-krea2-vlm-scope="selected">为已选生成草稿</button><button data-krea2-vlm-scope="missing">补齐缺少的草稿</button><button data-krea2-vlm-scope="failed">重试失败项</button></div>
              <p id="datasetKrea2QueueHint" class="dataset-hint">模型只生成英文草稿，不会覆盖已经确认的 Krea 2 说明；请在图片详情中对照并确认。</p>
            </div>
            <div class="dataset-curation-block">
              <strong>标签统计与修改记录</strong>
              <div id="datasetAnalytics" class="dataset-analytics">尚未产生标签统计。</div>
              <div class="dataset-snapshot-row"><select id="datasetSnapshot"><option value="">选择修改记录</option></select><button id="datasetRollbackSnapshot">恢复到这里</button></div>
              <p class="dataset-hint">修改记录只保存 Prompt Hub 内的说明文字变化；恢复旧记录也不会改写原 `.txt`。</p>
            </div>
          </div>
        </section>
        <section class="dataset-assets-panel" data-dataset-stage-panel="2,4">
          <div class="dataset-stage-heading"><div><span class="section-label" id="datasetAssetStepLabel">02 · 检查问题</span><h3 id="datasetAssetStepTitle">检查坏图、重复和缺失项</h3></div><p id="datasetAssetStepHint">先处理会阻止交付的问题；近似重复只提醒，不会自动删除。</p></div>
          <div class="dataset-toolbar">
            <label>图片状态<select id="datasetValidity"><option value="all">全部图片</option><option value="valid">有效图片</option><option value="invalid">坏图</option></select></label>
            <label>原始 .txt<select id="datasetCaptionFilter"><option value="all">全部</option><option value="paired">已有原说明</option><option value="missing">缺少原说明</option></select></label>
            <label>人工审核<select id="datasetReviewFilter"><option value="all">全部</option><option value="pending">未审核</option><option value="approved">保留</option><option value="needs_review">待复查</option><option value="excluded">排除</option></select></label>
            <label>重复检查<select id="datasetDuplicateFilter"><option value="all">全部</option><option value="exact">完全重复</option><option value="near">近似重复</option><option value="unique">无重复</option></select></label>
            <label class="dataset-advanced-only">文件格式<select id="datasetFormatFilter"><option value="all">全部格式</option></select></label>
            <label class="dataset-advanced-only">最短边<select id="datasetSizeFilter"><option value="0">不限</option><option value="512">≥ 512</option><option value="768">≥ 768</option><option value="1024">≥ 1024</option></select></label>
          </div>
          <div class="dataset-bulkbar">
            <label><input type="checkbox" id="datasetSelectVisible"> 选择当前筛选结果</label>
            <span id="datasetSelectionCount">已选 0 张</span>
            <button data-bulk-status="approved">审核通过并保留</button><button data-bulk-status="needs_review">标记待复查</button><button data-bulk-status="excluded">排除所选</button><button id="datasetClearSelection">清空选择</button>
          </div>
          <p class="dataset-write-note" id="datasetReviewWriteNote">这些按钮只写入 Prompt Hub 的审核记录，不会移动或删除源图片。</p>
          <div class="dataset-results-head"><strong id="datasetResultCount">0 张</strong><span id="datasetScanTime"></span></div>
          <nav id="datasetPagination" class="dataset-pagination" aria-label="数据集分页" hidden>
            <button id="datasetPreviousPage" type="button">上一页</button>
            <span id="datasetPageStatus">第 1 / 1 页</span>
            <button id="datasetNextPage" type="button">下一页</button>
          </nav>
          <div id="datasetGrid" class="dataset-grid"></div>
        </section>
        <section class="dataset-delivery-panel" id="datasetDeliveryPanel" data-dataset-stage-panel="5">
          <header class="dataset-delivery-head"><span class="section-label">05 · 生成交付版本</span><h3>建立可以带到 Windows 的数据集副本</h3><p id="datasetDeliverySummary">完成图片和说明文字审核后，这里会显示可交付数量。</p></header>
          <div class="dataset-delivery-grid">
            <article class="dataset-preflight" id="datasetPreflight"><div><strong>交付前检查</strong><span id="datasetPreflightBadge">尚未检查</span></div><p id="datasetPreflightSummary">系统会检查坏图、缺少说明、未审核、完全重复和同名 `.txt` 冲突。</p><ul id="datasetPreflightIssues"></ul><button id="datasetRunPreflight" type="button">重新检查当前选择</button></article>
            <article class="dataset-delivery-action"><strong>保存到这台 Mac</strong><p>系统会建立一个新的独立版本，包含图片副本、同名 `.txt` 和校验清单（`manifest.json`、`audit.json`、`hashes.sha256`）。重复点击不会覆盖旧版本，也不修改源文件夹。</p><button class="dataset-primary" id="datasetExportActiveProfile" type="button">生成并保存到 Mac</button><p>这里不会启动 Windows 训练；训练、正则和最终筛标继续在 AnimaLoraStudio 中完成。</p><p id="datasetExportResult" class="dataset-hint"></p></article>
          </div>
          <section class="dataset-delivery-history"><div class="dataset-delivery-history-head"><div><span class="section-label">以前生成的版本</span><h4>交付历史</h4></div><p>每次生成都会保留独立版本。可以下载 ZIP、在 Finder 中打开，或复制到已经挂载的 5060 Ti。</p></div><div id="datasetDeliveryHistory" class="dataset-delivery-list"><p class="dataset-hint">还没有交付版本。</p></div><p id="datasetCopyResult" class="dataset-hint"></p></section>
        </section>
      </div>
    </main>
  </div>
  <dialog id="datasetDetail" class="dataset-dialog">
    <button class="dataset-dialog-close" id="datasetDetailClose" aria-label="关闭">×</button>
    <div class="dataset-dialog-image"><img id="datasetDetailImage" alt="数据集原图预览"><button id="datasetPrevious" aria-label="上一张">←</button><button id="datasetNext" aria-label="下一张">→</button></div>
    <div class="dataset-dialog-body">
      <span class="section-label">逐张检查</span><h2 id="datasetDetailName">—</h2><p id="datasetDetailMeta"></p>
      <label>审核状态<select id="datasetDetailStatus"><option value="pending">未审核</option><option value="approved">保留</option><option value="needs_review">待复查</option><option value="excluded">排除</option></select></label>
      <label>原始图片说明（只读）<textarea id="datasetDetailCaption" readonly></textarea></label>
      <div class="dataset-caption-profile"><strong>Anima · 标准英文标签</strong><span id="datasetDetailWD14">尚未运行 WD14</span></div>
      <div id="datasetDetailTagChips" class="dataset-tag-chips"></div>
      <textarea id="datasetDetailAnima" maxlength="12000" aria-label="Anima 英文标签"></textarea>
      <div class="dataset-caption-profile"><strong>Krea 2 · 英文自然语言</strong><span>与 Anima 分开保存</span></div>
      <textarea id="datasetDetailKrea2" maxlength="12000" aria-label="Krea 2 英文自然语言说明"></textarea>
      <div class="dataset-caption-profile"><strong>视觉模型草稿 · 待确认</strong><span id="datasetDetailKrea2VLM">尚无草稿</span></div>
      <textarea id="datasetDetailKrea2Draft" maxlength="12000" aria-label="Krea 2 视觉模型英文草稿" placeholder="先在工作台运行 Krea 2 视觉草稿队列"></textarea>
      <p id="datasetDetailKrea2Warning" class="dataset-vlm-warning" hidden></p>
      <div class="dataset-action-row"><button id="datasetDetailDraftSave">只保存草稿</button><button class="dataset-primary" id="datasetDetailDraftConfirm">确认写入 Krea 2</button></div>
      <p class="dataset-hint">确认时系统会保存一份可回退的修改记录；Anima 与 WD14 不会改变。</p>
      <div class="dataset-similar-panel"><button id="datasetFindSimilar" disabled>以此图查相似</button><span id="datasetFindSimilarStatus">正在检查真实视觉索引……</span></div>
      <label>审核备注<textarea id="datasetDetailNote" maxlength="2000" placeholder="记录质量、特征、需要修正的标签……"></textarea></label>
      <button class="dataset-primary" id="datasetDetailSave">保存审核和两种说明</button>
      <details><summary>文件指纹与来源</summary><pre id="datasetDetailHashes"></pre></details>
    </div>
  </dialog>
</section>
"""

WORKSPACE_STYLES = r"""
<style>
  .dataset-page { margin-top: 18px; border: 1px solid var(--line); background: var(--paper); box-shadow: var(--shadow); }
  #workspacePage .eyebrow, #workspacePage .section-label, #workspacePage label, #workspacePage .dataset-primary, #workspacePage .dataset-sidebar-head, #workspacePage .dataset-stat span, #workspacePage .dataset-curation-block > strong, #workspacePage .dataset-preflight strong, #workspacePage .dataset-delivery-action > strong { text-transform: none; }
  .dataset-page[hidden] { display: none; }
  .dataset-page [data-dataset-stage-panel][hidden] { display: none !important; }
  .dataset-page [data-caption-profile][hidden] { display: none !important; }
  .dataset-heading { display: flex; justify-content: space-between; align-items: end; gap: 28px; padding: 25px 28px; border-bottom: 1px solid var(--line); background: linear-gradient(110deg, #ece5d5 0 72%, var(--acid) 72%); }
  .dataset-heading h1 { margin: 5px 0 0; font: 700 clamp(38px, 5vw, 68px)/.9 "Iowan Old Style", serif; letter-spacing: -.045em; }
  .dataset-heading p { max-width: 520px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.6; }
  .dataset-heading-copy { display: grid; justify-items: end; gap: 12px; }
  .dataset-mode-switch { display: inline-flex; padding: 3px; border: 1px solid var(--ink); background: rgba(244,237,223,.85); }
  .dataset-mode-switch button { padding: 7px 10px; color: var(--muted); font: 800 8px/1 monospace; }
  .dataset-mode-switch button[aria-pressed="true"] { background: var(--ink); color: var(--paper); }
  .dataset-layout { display: grid; grid-template-columns: 285px minmax(0, 1fr); min-height: 720px; }
  .dataset-sidebar { padding: 20px; border-right: 1px solid var(--line); background: #ddd5c5; }
  .dataset-sidebar form { display: grid; gap: 10px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }
  .dataset-step-kicker { color: var(--signal); font: 900 9px/1 monospace; letter-spacing: .08em; }
  .dataset-sidebar label, .dataset-toolbar label, .dataset-dialog-body label { display: grid; gap: 6px; color: var(--muted); font: 800 9px monospace; text-transform: uppercase; letter-spacing: .06em; }
  .dataset-sidebar input, .dataset-toolbar select, .dataset-dialog-body select, .dataset-dialog-body textarea { width: 100%; border: 1px solid var(--line); background: #f7f1e5; color: var(--ink); padding: 9px; font: 11px/1.45 monospace; }
  .dataset-primary { border: 1px solid var(--signal); background: var(--signal); color: white; padding: 10px 12px; text-align: left; font: 800 9px monospace; text-transform: uppercase; }
  .dataset-hint { margin: 0; color: var(--muted); font-size: 10px; line-height: 1.5; }
  .dataset-sidebar-head { display: flex; justify-content: space-between; margin: 18px 0 8px; font: 800 9px monospace; text-transform: uppercase; }
  .dataset-workspace-list { min-width: 0; display: grid; gap: 7px; }
  .dataset-workspace-item { width: 100%; min-width: 0; max-width: 100%; overflow: hidden; border: 1px solid rgba(31,29,25,.25); background: #eee7da; padding: 10px; text-align: left; }
  .dataset-workspace-item.active { border-color: var(--signal); box-shadow: inset 4px 0 var(--acid); }
  .dataset-workspace-item strong, .dataset-workspace-item span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dataset-workspace-item strong { font-size: 11px; }
  .dataset-workspace-item span { margin-top: 5px; color: var(--muted); font: 8px monospace; }
  .dataset-main { min-width: 0; padding: 24px; background-image: linear-gradient(rgba(31,29,25,.03) 1px, transparent 1px); background-size: 100% 36px; }
  .dataset-empty { max-width: 520px; margin: 110px auto; text-align: center; }
  .dataset-empty span { display: inline-grid; width: 54px; aspect-ratio: 1; place-items: center; border: 1px solid var(--ink); background: var(--acid); font: 900 12px monospace; }
  .dataset-empty h2 { margin: 18px 0 7px; font: 700 34px "Iowan Old Style", serif; }
  .dataset-empty p { color: var(--muted); font-size: 12px; }
  .dataset-titlebar { display: flex; justify-content: space-between; gap: 18px; align-items: end; }
  .dataset-titlebar h2 { margin: 4px 0; font: 700 32px "Iowan Old Style", serif; }
  .dataset-titlebar p { max-width: 760px; margin: 0; overflow-wrap: anywhere; color: var(--muted); font: 9px monospace; }
  .dataset-origin { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-top: 8px; color: var(--muted); font: 8px/1.45 monospace; }
  .dataset-origin button, .dataset-origin a { border: 1px solid var(--ink); padding: 5px 7px; color: var(--ink); text-decoration: none; font: 800 7px monospace; }
  .dataset-origin .independent { border-left: 4px solid var(--acid); padding: 5px 8px; background: #e4ddce; }
  .dataset-title-actions { display: flex; gap: 7px; }
  .dataset-title-actions button, .dataset-bulkbar button { border: 1px solid var(--ink); padding: 8px 9px; font: 800 8px monospace; }
  .dataset-title-actions .danger { color: var(--signal); border-color: var(--signal); }
  .dataset-job-panel { margin-top: 14px; border: 1px solid var(--ink); background: #171714; color: #f4eddf; padding: 12px; }
  .dataset-job-line { display: grid; grid-template-columns: 90px minmax(0,1fr) auto; gap: 10px; align-items: center; }
  .dataset-job-line progress { width: 100%; accent-color: var(--acid); }
  .dataset-job-line button { color: var(--acid); border-bottom: 1px solid currentColor; font: 800 8px monospace; }
  .dataset-job-line span { font: 8px monospace; }
  .dataset-job-message { margin: 7px 0 0; color: #bdb5a6; font: 9px monospace; }
  .dataset-journey { display: grid; grid-template-columns: repeat(5,minmax(0,1fr)); margin-top: 18px; border: 1px solid var(--ink); background: var(--line); gap: 1px; }
  .dataset-journey button { position: relative; display: grid; min-width: 0; gap: 6px; padding: 13px 11px; background: #e9e2d4; text-align: left; }
  .dataset-journey button::after { content: ""; position: absolute; inset: auto 0 0; height: 4px; background: transparent; }
  .dataset-journey button span { color: var(--signal); font: 900 9px/1 monospace; }
  .dataset-journey button strong { font: 800 10px/1.2 monospace; }
  .dataset-journey button small { overflow: hidden; color: var(--muted); font: 8px/1.35 monospace; text-overflow: ellipsis; white-space: nowrap; }
  .dataset-journey button.complete::after { background: #52735d; }
  .dataset-journey button.current { background: var(--ink); color: var(--paper); }
  .dataset-journey button.current::after { background: var(--acid); }
  .dataset-journey button.current small { color: #c6c0b4; }
  .dataset-journey button.blocked::after { background: var(--signal); }
  .dataset-readiness { display: grid; grid-template-columns: minmax(0,1fr) minmax(210px,.36fr); gap: 20px; padding: 18px; border: 1px solid var(--ink); border-top: 0; background: #f3ecde; }
  .dataset-readiness-copy h3, .dataset-stage-heading h3, .dataset-delivery-panel h3 { margin: 5px 0 7px; font: 700 26px/1.05 "Iowan Old Style", serif; }
  .dataset-readiness-copy p, .dataset-stage-heading p, .dataset-delivery-panel p { margin: 0; color: var(--muted); font-size: 10px; line-height: 1.55; }
  .dataset-readiness-copy ul { display: grid; gap: 5px; margin: 11px 0 0; padding: 0; list-style: none; }
  .dataset-readiness-copy li { padding-left: 14px; color: #6e392d; font: 9px/1.45 monospace; }
  .dataset-readiness-copy li::before { content: "→"; margin-left: -14px; margin-right: 6px; color: var(--signal); }
  .dataset-readiness-action { display: grid; align-content: start; gap: 9px; }
  .dataset-readiness-action label { display: grid; gap: 5px; color: var(--muted); font: 800 8px/1.3 monospace; }
  .dataset-readiness-action select { width: 100%; border: 1px solid var(--line); background: white; padding: 9px; color: var(--ink); font: 10px monospace; }
  .dataset-readiness-action small { color: var(--muted); font: 8px/1.45 monospace; }
  .dataset-stats { display: grid; grid-template-columns: repeat(8, minmax(0,1fr)); gap: 1px; margin-top: 15px; border: 1px solid var(--line); background: var(--line); }
  .dataset-stat { min-width: 0; background: #eee7da; padding: 11px; }
  .dataset-stat strong, .dataset-stat span { display: block; }
  .dataset-stat strong { font: 800 18px monospace; }
  .dataset-stat span { margin-top: 3px; color: var(--muted); font: 8px monospace; text-transform: uppercase; }
  .dataset-toolbar { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 8px; margin-top: 14px; padding: 12px; border: 1px solid var(--line); background: #e1d9ca; }
  .dataset-bulkbar { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-top: 9px; }
  .dataset-bulkbar label, .dataset-bulkbar span { margin-right: 6px; color: var(--muted); font: 9px monospace; }
  .dataset-results-head { display: flex; justify-content: space-between; margin-top: 15px; font: 9px monospace; }
  .dataset-assets-panel { margin-top: 14px; padding: 14px; border: 1px solid var(--ink); background: #eee7da; }
  .dataset-stage-heading { display: flex; justify-content: space-between; gap: 20px; align-items: end; }
  .dataset-stage-heading p { max-width: 520px; }
  .dataset-write-note { margin: 8px 0 0; color: var(--muted); font: 8px/1.45 monospace; }
  .dataset-pagination { display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 10px; }
  .dataset-pagination button { border: 1px solid var(--ink); padding: 7px 10px; font: 800 8px monospace; }
  .dataset-pagination button:disabled { opacity: .35; }
  .dataset-pagination span { min-width: 96px; text-align: center; color: var(--muted); font: 9px monospace; }
  .dataset-curation-panel { margin-top: 14px; border: 1px solid var(--ink); background: #eee7da; }
  .dataset-curation-head { display: flex; justify-content: space-between; gap: 20px; padding: 14px; border-bottom: 1px solid var(--line); }
  .dataset-curation-head h3 { margin: 3px 0 0; font: 700 24px "Iowan Old Style", serif; }
  .dataset-curation-head p { max-width: 520px; margin: 0; color: var(--muted); font-size: 10px; line-height: 1.5; }
  .dataset-curation-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); }
  .dataset-curation-block { min-width: 0; padding: 13px; border-right: 1px solid var(--line); }
  .dataset-curation-block:last-child { border-right: 0; }
  .dataset-curation-block > strong { display: block; margin-bottom: 10px; font: 800 9px monospace; text-transform: uppercase; }
  .dataset-curation-block label { display: grid; gap: 4px; margin-top: 7px; color: var(--muted); font: 8px monospace; text-transform: uppercase; }
  .dataset-curation-block input, .dataset-curation-block select, .dataset-snapshot-row select { width: 100%; border: 1px solid var(--line); background: #f8f2e7; padding: 7px; font: 10px monospace; }
  .dataset-thresholds { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
  .dataset-action-row, .dataset-snapshot-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
  .dataset-action-row button, .dataset-snapshot-row button { border: 1px solid var(--ink); padding: 7px; font: 800 7px monospace; }
  .dataset-action-row button:disabled { opacity: .35; }
  .dataset-inline-check { display: flex !important; align-items: center; grid-template-columns: auto 1fr; }
  .dataset-inline-check input { width: auto; }
  .dataset-analytics { min-height: 44px; color: var(--muted); font: 8px/1.5 monospace; }
  .dataset-analytics-tags, .dataset-tag-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
  .dataset-analytics-tags span, .dataset-analytics-tags button, .dataset-tag-chips button { border: 1px solid rgba(31,29,25,.28); padding: 4px 5px; background: transparent; font: 7px monospace; }
  .dataset-analytics-tags button { cursor: pointer; }
  .dataset-tag-chips button.selected { background: var(--acid); border-color: var(--ink); }
  .dataset-caption-profile { display: flex; justify-content: space-between; gap: 8px; margin-top: 14px; color: var(--muted); font: 8px monospace; }
  .dataset-vlm-warning { border-left: 4px solid var(--signal); padding: 7px 9px; background: #e7d5c7; color: #8a3328 !important; }
  .dataset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(165px, 1fr)); gap: 9px; margin-top: 8px; }
  .dataset-card { position: relative; min-width: 0; border: 1px solid var(--line); background: #f4eddf; }
  .dataset-card.selected { border-color: var(--signal); box-shadow: inset 0 4px var(--acid); }
  .dataset-card.invalid { background: #dfd2c7; }
  .dataset-card-preview { width: 100%; aspect-ratio: 1; border: 0; background: #d7d0c3; padding: 0; }
  .dataset-card-preview img { width: 100%; height: 100%; object-fit: cover; }
  .dataset-card-placeholder { display: grid; width: 100%; height: 100%; place-items: center; color: #8a3328; font: 800 10px monospace; }
  .dataset-card-select { position: absolute; top: 8px; left: 8px; width: 22px; height: 22px; accent-color: var(--signal); }
  .dataset-card-body { padding: 9px; }
  .dataset-card-body strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 10px; }
  .dataset-card-meta, .dataset-card-flags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
  .dataset-card-meta span, .dataset-card-flags span { border: 1px solid rgba(31,29,25,.22); padding: 3px 4px; color: var(--muted); font: 7px monospace; }
  .dataset-card-flags .alert { color: #9a3023; border-color: rgba(154,48,35,.35); }
  .dataset-card-flags .ok { color: #325f49; }
  .dataset-dialog { width: min(1080px, calc(100% - 28px)); max-height: calc(100vh - 28px); border: 1px solid var(--ink); background: #ece6d8; padding: 0; color: var(--ink); }
  .dataset-dialog::backdrop { background: rgba(16,17,14,.82); backdrop-filter: blur(3px); }
  .dataset-dialog[open] { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(310px, .65fr); }
  .dataset-dialog-close { position: absolute; z-index: 3; top: 8px; right: 10px; width: 34px; height: 34px; background: var(--signal); color: white; font-size: 20px; }
  .dataset-dialog-image { position: relative; display: grid; place-items: center; min-height: 560px; background: #191a17; }
  .dataset-dialog-image img { max-width: 100%; max-height: calc(100vh - 30px); object-fit: contain; }
  .dataset-dialog-image button { position: absolute; top: 50%; width: 38px; height: 46px; background: rgba(236,232,220,.85); font-size: 18px; }
  #datasetPrevious { left: 10px; } #datasetNext { right: 10px; }
  .dataset-dialog-body { overflow: auto; padding: 28px; }
  .dataset-dialog-body h2 { margin: 6px 0; overflow-wrap: anywhere; font: 700 28px "Iowan Old Style", serif; }
  .dataset-dialog-body > p { color: var(--muted); font: 9px/1.5 monospace; }
  .dataset-dialog-body label { margin-top: 14px; }
  .dataset-dialog-body textarea { min-height: 95px; resize: vertical; text-transform: none; }
  .dataset-dialog-body details { margin-top: 15px; color: var(--muted); font: 9px monospace; }
  .dataset-similar-panel { display: grid; gap: 7px; margin-top: 14px; border-left: 4px solid var(--acid); background: #e2dccd; padding: 10px; }
  .dataset-similar-panel button { width: fit-content; border: 1px solid var(--ink); background: var(--ink); color: var(--paper); padding: 8px 10px; font: 800 8px monospace; }
  .dataset-similar-panel button:disabled { opacity: .45; }
  .dataset-similar-panel span { color: var(--muted); font: 8px/1.5 monospace; }
  .dataset-dialog-body pre { white-space: pre-wrap; overflow-wrap: anywhere; }
  .dataset-delivery-panel { margin-top: 14px; padding: 20px; border: 1px solid var(--ink); background: #eee7da; }
  .dataset-delivery-head { max-width: 760px; }
  .dataset-delivery-grid { display: grid; grid-template-columns: minmax(0,1fr) minmax(280px,.72fr); gap: 12px; margin-top: 16px; }
  .dataset-preflight { display: grid; align-content: start; gap: 9px; padding: 14px; border: 1px solid var(--ink); background: #f7f1e5; }
  .dataset-preflight > div { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
  .dataset-preflight strong, .dataset-delivery-action > strong { font: 800 9px monospace; text-transform: uppercase; }
  .dataset-preflight span { border: 1px solid var(--line); padding: 4px 6px; color: var(--muted); font: 800 7px monospace; }
  .dataset-preflight.ready span { border-color: #52735d; color: #325f49; background: #dfe7d8; }
  .dataset-preflight.blocked span { border-color: var(--signal); color: #8a3328; background: #ead8cd; }
  .dataset-preflight ul { display: grid; gap: 5px; margin: 0; padding: 0; list-style: none; }
  .dataset-preflight li { border-left: 3px solid var(--signal); padding: 5px 8px; background: #e8ded0; font: 8px/1.45 monospace; }
  .dataset-preflight li.warning { border-color: #9a7b30; }
  .dataset-preflight button { width: fit-content; border: 1px solid var(--ink); padding: 7px 9px; font: 800 8px monospace; }
  .dataset-delivery-action { display: grid; align-content: start; gap: 9px; padding: 14px; border: 1px solid var(--ink); background: rgba(247,241,229,.9); }
  .dataset-delivery-action .dataset-primary { text-align: center; }
  .dataset-delivery-history { margin-top: 14px; border-top: 1px solid var(--ink); padding-top: 14px; }
  .dataset-delivery-history-head { display: flex; justify-content: space-between; gap: 20px; align-items: end; }
  .dataset-delivery-history-head h4 { margin: 3px 0 0; font: 700 22px "Iowan Old Style", serif; }
  .dataset-delivery-history-head p { max-width: 520px; margin: 0; color: var(--muted); font: 9px/1.5 monospace; }
  .dataset-delivery-list { display: grid; gap: 8px; margin-top: 10px; }
  .dataset-delivery-card { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 12px; padding: 12px; border: 1px solid var(--line); background: #f7f1e5; }
  .dataset-delivery-card h5 { margin: 0 0 6px; overflow-wrap: anywhere; font: 800 10px monospace; }
  .dataset-delivery-meta, .dataset-delivery-copy { color: var(--muted); font: 8px/1.55 monospace; }
  .dataset-delivery-actions { display: flex; flex-wrap: wrap; align-content: start; justify-content: end; gap: 6px; }
  .dataset-delivery-actions a, .dataset-delivery-actions button { border: 1px solid var(--ink); padding: 7px 8px; background: transparent; color: var(--ink); font: 800 7px monospace; text-decoration: none; }
  .dataset-delivery-actions button.primary { background: var(--ink); color: var(--paper); }
  .dataset-page[data-dataset-mode="simple"] .dataset-advanced-only { display: none !important; }
  @media (max-width: 1050px) { .dataset-stats { grid-template-columns: repeat(4,1fr); } .dataset-journey button small { display: none; } }
  @media (max-width: 900px) { .dataset-layout { grid-template-columns: 230px minmax(0,1fr); } .dataset-toolbar { grid-template-columns: repeat(2,1fr); } .dataset-curation-grid, .dataset-delivery-grid { grid-template-columns: 1fr; } .dataset-curation-block { border-right: 0; border-bottom: 1px solid var(--line); } .dataset-readiness { grid-template-columns: 1fr; background: #eee7da; } }
  @media (max-width: 620px) { .dataset-heading { display: block; background: #ece5d5; } .dataset-heading-copy { justify-items: start; margin-top: 12px; } .dataset-layout { display: block; } .dataset-sidebar { border-right: 0; border-bottom: 1px solid var(--line); } .dataset-titlebar, .dataset-curation-head, .dataset-stage-heading, .dataset-delivery-history-head { display: block; } .dataset-title-actions, .dataset-curation-head p, .dataset-stage-heading p, .dataset-delivery-history-head p { margin-top: 12px; } .dataset-journey { grid-template-columns: 1fr; } .dataset-journey button { grid-template-columns: 32px 1fr; align-items: center; } .dataset-journey button small { display: block; grid-column: 2; } .dataset-stats, .dataset-toolbar { grid-template-columns: repeat(2,1fr); } .dataset-grid { grid-template-columns: 1fr; } .dataset-delivery-card { grid-template-columns: 1fr; } .dataset-delivery-actions { justify-content: start; } .dataset-dialog[open] { display: block; overflow: auto; } .dataset-dialog-image { min-height: 360px; } }
</style>
"""

WORKSPACE_SCRIPT = r"""
<script>
(() => {
  const state = {workspaces: [], active: null, report: null, analytics: null, models: [], exports: [], preflight: null, visible: [], pageItems: [], page: 1, pageSize: 200, selected: new Set(), detailIndex: -1, poll: null, bulkPreview: null, sourceCaptionPreview: null, mode: 'simple', step: 0};
  const labels = {pending:'未审核', approved:'保留', needs_review:'待复查', excluded:'排除'};
  const workspaceStatusLabels = {registered:'等待扫描', scanning:'正在扫描', ready:'可使用', failed:'扫描失败', queued:'等待扫描', canceled:'已取消'};
  const stepNames = {1:'导入素材',2:'检查问题',3:'准备标签',4:'人工审核',5:'生成交付版本'};
  async function api(url, options={}) { const response = await fetch(url, options); const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || `请求失败：${response.status}`); return data; }
  const jsonOptions = body => ({method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  function duplicateSets() { const exact = new Set(), near = new Set(); (state.report?.exact_duplicates || []).forEach(group => group.files.forEach(path => exact.add(path))); (state.report?.near_duplicates || []).forEach(group => group.files.forEach(path => near.add(path))); return {exact, near}; }
  function renderWorkspaces() { $('#datasetWorkspaceCount').textContent = state.workspaces.length; $('#datasetWorkspaceList').innerHTML = state.workspaces.length ? state.workspaces.map(item => `<button class="dataset-workspace-item ${state.active?.workspace_id === item.workspace_id ? 'active' : ''}" data-workspace-id="${escapeHtml(item.workspace_id)}"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(workspaceStatusLabels[item.status] || '状态待确认')} · ${formatNumber(item.summary?.image_count || 0)} 张</span><span>${escapeHtml(item.source_path)}</span></button>`).join('') : '<p class="dataset-hint">还没有读取过数据集。</p>'; }
  function renderDatasetOrigin() { const origin=state.active?.origin||{}, container=$('#datasetOrigin'); if(origin.kind!=='creative_project'||!origin.project_id) { container.innerHTML='<span class="independent">外部独立数据集 · 不要求绑定创作项目</span>'; return; } const assets=Array.isArray(origin.result_asset_ids)?origin.result_asset_ids:[]; container.innerHTML=`<span>来源：${escapeHtml(origin.project_title||'创作项目')} · V${Number(origin.project_iteration)||1} · ${assets.length} 张结果图</span><button type="button" data-origin-project="${escapeHtml(origin.project_id)}">返回来源项目</button>${assets.slice(0,3).map((id,index)=>`<a href="/result-media/${encodeURIComponent(origin.project_id)}/original/${encodeURIComponent(id)}" target="_blank" rel="noreferrer">来源图 ${index+1}</a>`).join('')}`; }
  function stat(value, label) { return `<div class="dataset-stat"><strong>${formatNumber(value)}</strong><span>${label}</span></div>`; }
  function formatDatasetBytes(value) { const bytes=Number(value)||0; if(bytes>=1073741824) return `${(bytes/1073741824).toFixed(1)} GiB`; if(bytes>=1048576) return `${(bytes/1048576).toFixed(1)} MiB`; if(bytes>=1024) return `${(bytes/1024).toFixed(1)} KiB`; return `${bytes} B`; }
  function deliverySelectionKey(profile=$('#datasetDeliveryProfile').value || 'anima') { return `${profile}|${[...state.selected].sort().join('|')}`; }
  function renderPreflight() { const panel=$('#datasetPreflight'), current=state.preflight?._selectionKey===deliverySelectionKey()?state.preflight:null, profileName=($('#datasetDeliveryProfile').value||'anima')==='anima'?'Anima':'Krea 2'; panel.classList.toggle('ready',Boolean(current?.ready)); panel.classList.toggle('blocked',Boolean(current&&!current.ready)); if(!state.selected.size) { $('#datasetPreflightBadge').textContent='等待选择'; $('#datasetPreflightSummary').textContent='先在第 4 步选择要交付的图片，并将图片审核为保留。'; $('#datasetPreflightIssues').innerHTML=''; return; } if(!current) { $('#datasetPreflightBadge').textContent='等待检查'; $('#datasetPreflightSummary').textContent=`将检查 ${state.selected.size} 张图片的 ${profileName} 交付条件。`; $('#datasetPreflightIssues').innerHTML=''; return; } $('#datasetPreflightBadge').textContent=current.ready?'可以生成':`${current.blockers.length} 类问题`; $('#datasetPreflightSummary').textContent=current.ready?`${current.selected_count} 张图片已通过交付前检查。`:`${current.selected_count} 张图片还不能生成交付版本，请按下面提示处理。`; $('#datasetPreflightIssues').innerHTML=[...(current.blockers||[]).map(item=>`<li>${escapeHtml(item.label)} · ${item.count||0} 项</li>`),...(current.warnings||[]).map(item=>`<li class="warning">提醒：${escapeHtml(item.label)} · ${item.count||0} 项</li>`)].join(''); }
  function renderExports() { const profile=$('#datasetDeliveryProfile').value||'anima', items=state.exports.filter(item=>item.profile_id===profile), profileName=profile==='anima'?'Anima':'Krea 2'; $('#datasetDeliveryHistory').innerHTML=items.length?items.map(item=>{ const copy=(item.copies||[]).find(entry=>entry.node_id==='compute_5060ti'), copyText=!copy?'尚未复制到 5060 Ti':copy.status==='completed'?'已复制到 5060 Ti':copy.status==='already_present'?'5060 Ti 已有此版本':`复制失败：${copy.error||'共享目录不可用'}`, when=String(item.created_at||'').slice(0,16).replace('T',' '), origin=item.origin||{}, sourceLinks=origin.project_id?`<button data-origin-project="${escapeHtml(origin.project_id)}">来源项目</button>${(item.source_result_asset_ids||[]).slice(0,2).map((id,index)=>`<a href="/result-media/${encodeURIComponent(origin.project_id)}/original/${encodeURIComponent(id)}" target="_blank" rel="noreferrer">来源图 ${index+1}</a>`).join('')}`:''; return `<article class="dataset-delivery-card" data-export-version="${escapeHtml(item.version_id)}"><div><h5>${escapeHtml(item.version_id)}</h5><div class="dataset-delivery-meta">${profileName} · ${formatNumber(item.image_count||0)} 张图片 · ${formatNumber(item.file_count||0)} 个文件 · ${formatDatasetBytes(item.total_bytes)} · ${escapeHtml(when)}</div><div class="dataset-delivery-copy">${escapeHtml(copyText)}</div></div><div class="dataset-delivery-actions">${sourceLinks}<a href="${escapeHtml(item.download_url)}">下载 ZIP</a><button data-export-action="reveal" ${item.directory_available?'':'disabled'}>打开 Finder</button><button class="primary" data-export-action="copy" ${item.directory_available?'':'disabled'}>复制到 5060 Ti</button></div></article>`; }).join(''):`<p class="dataset-hint">还没有 ${profileName} 交付版本。Anima 与 Krea 2 的历史会分开显示。</p>`; }
  function deliveryState() { const images=state.report?.images || [], profile=$('#datasetDeliveryProfile').value || 'anima', exact=new Set(); (state.report?.exact_duplicates || []).forEach(group=>group.files.forEach(path=>exact.add(path))); const statusOf=item=>item.review?.status || 'pending', captionOf=item=>item.curation?.captions?.[profile] || {}, active=images.filter(item=>item.valid && statusOf(item)!=='excluded'), selected=images.filter(item=>state.selected.has(item.relative_path)), exactBlockingGroups=(state.report?.exact_duplicates || []).filter(group=>group.files.filter(path=>{ const item=images.find(candidate=>candidate.relative_path===path); return item && item.valid && statusOf(item)!=='excluded'; }).length>1), invalidOpen=images.filter(item=>!item.valid && statusOf(item)!=='excluded'), missing=active.filter(item=>!String(captionOf(item).current || '').trim()), captionDraft=active.filter(item=>String(captionOf(item).current || '').trim() && captionOf(item).status!=='reviewed'), pending=active.filter(item=>statusOf(item)==='pending'), needsReview=active.filter(item=>statusOf(item)==='needs_review'), approved=images.filter(item=>item.valid && statusOf(item)==='approved'), excluded=images.filter(item=>statusOf(item)==='excluded'), reviewed=images.filter(item=>statusOf(item)!=='pending'), deliverable=selected.filter(item=>item.valid && statusOf(item)==='approved' && String(captionOf(item).current || '').trim() && captionOf(item).status==='reviewed'), selectedBlocked=selected.filter(item=>!deliverable.includes(item)); let recommended=1; if(state.report) { if(invalidOpen.length || exactBlockingGroups.length) recommended=2; else if(missing.length) recommended=3; else if(captionDraft.length || pending.length || needsReview.length || !approved.length || !selected.length) recommended=4; else recommended=5; } return {profile,images,active,selected,exact,invalidOpen,exactBlockingGroups,missing,captionDraft,pending,needsReview,approved,excluded,deliverable,selectedBlocked,recommended,reviewed:reviewed.length,nearGroups:state.report?.near_duplicates?.length || 0}; }
  function renderStats() { const d=deliveryState(), duplicates=new Set([...d.exact]); (state.report?.near_duplicates || []).forEach(group=>group.files.forEach(path=>duplicates.add(path))); $('#datasetStats').innerHTML=stat(d.active.length,'有效候选')+stat(d.invalidOpen.length,'坏图待处理')+stat(duplicates.size,'重复提示')+stat(d.missing.length,`缺少 ${d.profile==='anima'?'Anima':'Krea 2'} 图片说明`)+stat(d.pending.length,'待审核')+stat(d.reviewed,'已审核')+stat(d.excluded.length,'已排除')+stat(d.deliverable.length,'当前可交付'); }
  function renderStagePanels(step) { const advanced=state.mode==='advanced', profile=$('#datasetDeliveryProfile').value || 'anima'; $('#workspacePage').dataset.datasetMode=state.mode; $('#datasetModeSimple').setAttribute('aria-pressed',String(!advanced)); $('#datasetModeAdvanced').setAttribute('aria-pressed',String(advanced)); document.querySelectorAll('[data-dataset-stage-panel]').forEach(panel=>{ const stages=panel.dataset.datasetStagePanel.split(','); panel.hidden=!advanced && !stages.includes(String(step)); }); document.querySelectorAll('[data-caption-profile]').forEach(block=>{ block.hidden=!advanced&&block.dataset.captionProfile!==profile; }); $('#datasetCurationTitle').textContent=profile==='anima'?'准备 Anima 英文标签':'准备 Krea 2 英文自然语言说明'; $('#datasetCurationHint').textContent=profile==='anima'?'优先接续已有 `.txt`；缺少标签时再运行 WD14。所有结果先进入 Prompt Hub，不写回原文件夹。':'优先接续已有英文自然语言 `.txt`；没有时再用视觉模型生成草稿，并在逐图审核后确认。'; const jobPanel=$('#datasetJobPanel'); if(jobPanel.dataset.jobState==='completed') jobPanel.hidden=!advanced; const review=step===4; $('#datasetAssetStepLabel').textContent=review?'04 · 人工审核':'02 · 检查问题'; $('#datasetAssetStepTitle').textContent=review?'逐张确认图片与说明文字':'检查坏图、重复和缺失项'; $('#datasetAssetStepHint').textContent=review?'先筛选未审核图片，打开缩略图检查说明文字；批量操作只适合已经确认过的同类图片。':'先处理会阻止交付的问题；近似重复只提醒，不会自动删除。'; $('#datasetReviewWriteNote').textContent=review?'“审核通过并保留”会写入 Prompt Hub 审核记录并保留选择，方便第 5 步交付；不会改动源图片。':'排除操作只写入 Prompt Hub 审核记录，不会移动或删除源图片。'; }
  function renderJourney() { const d=deliveryState(), step=state.step || d.recommended, profileName=d.profile==='anima'?'Anima':'Krea 2', scanClear=Boolean(state.report)&&!d.invalidOpen.length&&!d.exactBlockingGroups.length, captionsReady=Boolean(state.report)&&d.active.length>0&&!d.missing.length, reviewReady=captionsReady&&!d.captionDraft.length&&!d.pending.length&&!d.needsReview.length&&d.approved.length>0&&d.deliverable.length>0, statuses={1:Boolean(state.report),2:scanClear,3:captionsReady,4:reviewReady,5:state.exports.some(item=>item.profile_id===d.profile)}; document.querySelectorAll('[data-dataset-step]').forEach(button=>{ const value=Number(button.dataset.datasetStep); button.classList.toggle('current',value===step); button.classList.toggle('complete',Boolean(statuses[value])); button.classList.toggle('blocked',value===d.recommended&&value>1&&!statuses[value]); button.setAttribute('aria-current',value===step?'step':'false'); }); const copy={1:{title:'先读取一个本地图片文件夹',message:'Prompt Hub 会建立只读工作区，并自动扫描图片、同名 .txt、坏图与重复。',action:'回到左侧填写文件夹路径'},2:{title:scanClear?'文件检查已经通过':'先处理会阻止交付的问题',message:scanClear?'没有发现未处理的坏图或完全重复，可以继续准备标签。':`还有 ${d.invalidOpen.length} 张坏图、${d.exactBlockingGroups.length} 组完全重复需要明确排除。`,action:scanClear?'继续准备标签':'查看问题图片'},3:{title:captionsReady?`${profileName} 图片说明已经齐全`:`还缺 ${d.missing.length} 份 ${profileName} 图片说明`,message:captionsReady?(d.captionDraft.length?`图片说明已齐，但其中 ${d.captionDraft.length} 份仍是草稿，请在人工审核时确认。`:'不需要重复生成标签，可以直接进入人工审核。'):'可以使用已有 .txt，或用对应工具生成缺少的草稿。',action:captionsReady?'进入人工审核':'打开标签准备工具'},4:{title:reviewReady?'图片和说明文字已满足交付要求':'需要人工决定哪些图片保留',message:reviewReady?`已选择 ${d.deliverable.length} 张可交付图片。生成版本前仍可逐张复查。`:`${d.pending.length} 张未审核，${d.needsReview.length} 张待复查，${d.captionDraft.length} 份图片说明尚未确认；当前选择 ${d.selected.length} 张。`,action:reviewReady?'检查交付内容':'查看待审核图片'},5:{title:d.deliverable.length?'可以生成当前数据集版本':'还没有可交付的图片',message:d.deliverable.length?`${d.deliverable.length} 张图片将按 ${profileName} 格式建立独立副本。`:'返回人工审核：选择图片、标记保留，并确认当前格式的图片说明。',action:d.deliverable.length?'生成并保存副本':'返回人工审核'}}[step]; $('#datasetCurrentStepLabel').textContent=`第 ${step} 步 · ${stepNames[step]}`; $('#datasetReadinessTitle').textContent=copy.title; $('#datasetReadinessMessage').textContent=copy.message; $('#datasetNextAction').textContent=copy.action; const blockers=[]; if(d.invalidOpen.length) blockers.push(`${d.invalidOpen.length} 张坏图尚未排除`); if(d.exactBlockingGroups.length) blockers.push(`${d.exactBlockingGroups.length} 组完全重复尚未处理`); if(d.missing.length) blockers.push(`${d.missing.length} 份 ${profileName} 图片说明缺失`); if(d.captionDraft.length) blockers.push(`${d.captionDraft.length} 份 ${profileName} 图片说明仍是草稿`); if(d.pending.length) blockers.push(`${d.pending.length} 张图片尚未审核`); if(d.needsReview.length) blockers.push(`${d.needsReview.length} 张图片标记为待复查`); if(d.selectedBlocked.length) blockers.push(`已选图片中有 ${d.selectedBlocked.length} 张暂时不能交付`); $('#datasetBlockingList').innerHTML=blockers.slice(0,4).map(item=>`<li>${escapeHtml(item)}</li>`).join(''); $('#datasetDeliverySummary').textContent=d.deliverable.length?`当前选择中有 ${d.deliverable.length} 张通过审核，并且已经确认 ${profileName} 图片说明。`:`当前选择中没有可交付图片。请返回第 4 步完成选择、图片审核和 ${profileName} 图片说明确认。`; $('#datasetExportActiveProfile').textContent=`生成并保存 ${profileName} 到 Mac`; $('#datasetExportActiveProfile').disabled=!d.deliverable.length||Boolean(d.selectedBlocked.length); renderStagePanels(step); renderPreflight(); renderExports(); }
  function filteredImages() { const {exact, near} = duplicateSets(); const validity=$('#datasetValidity').value, caption=$('#datasetCaptionFilter').value, review=$('#datasetReviewFilter').value, duplicate=$('#datasetDuplicateFilter').value, format=$('#datasetFormatFilter').value, minSize=Number($('#datasetSizeFilter').value); return (state.report?.images || []).filter(item => { const status=item.review?.status || 'pending', inExact=exact.has(item.relative_path), inNear=near.has(item.relative_path); if (validity==='valid' && !item.valid) return false; if (validity==='invalid' && item.valid) return false; if (caption!=='all' && item.caption_status!==caption) return false; if (review!=='all' && status!==review) return false; if (format!=='all' && item.format!==format) return false; if (minSize && Math.min(item.width,item.height)<minSize) return false; if (duplicate==='exact' && !inExact) return false; if (duplicate==='near' && !inNear) return false; if (duplicate==='unique' && (inExact || inNear)) return false; return true; }); }
  function renderGrid(resetPage=false) { const {exact, near}=duplicateSets(); state.visible=filteredImages(); const pageCount=Math.max(1,Math.ceil(state.visible.length/state.pageSize)); if (resetPage) state.page=1; state.page=Math.min(Math.max(state.page,1),pageCount); const start=(state.page-1)*state.pageSize; state.pageItems=state.visible.slice(start,start+state.pageSize); $('#datasetResultCount').textContent=`${formatNumber(state.visible.length)} 张`; $('#datasetSelectionCount').textContent=`已选 ${formatNumber(state.selected.size)} 张`; $('#datasetSelectVisible').checked=state.visible.length>0 && state.visible.every(item => state.selected.has(item.relative_path)); $('#datasetPagination').hidden=state.visible.length<=state.pageSize; $('#datasetPageStatus').textContent=`第 ${formatNumber(state.page)} / ${formatNumber(pageCount)} 页 · 每页最多 ${formatNumber(state.pageSize)} 张`; $('#datasetPreviousPage').disabled=state.page<=1; $('#datasetNextPage').disabled=state.page>=pageCount; $('#datasetGrid').innerHTML=state.pageItems.length ? state.pageItems.map((item,index) => { const status=item.review?.status || 'pending', tagStatus=item.curation?.wd14?.status || 'untagged', vlmStatus=item.curation?.krea2_vlm?.status || 'empty', profile=$('#datasetDeliveryProfile').value, profileCaption=item.curation?.captions?.[profile] || {}; const flags=[item.caption_status==='missing'?'<span class="alert">缺少原说明</span>':'<span class="ok">已有原说明</span>', String(profileCaption.current || '').trim()?(profileCaption.status==='reviewed'?`<span class="ok">${profile==='anima'?'Anima':'Krea 2'} 已确认</span>`:`<span>${profile==='anima'?'Anima':'Krea 2'} 草稿</span>`):`<span class="alert">缺 ${profile==='anima'?'Anima':'Krea 2'}</span>`, tagStatus==='completed'?'<span class="ok">WD14 已完成</span>':tagStatus==='failed'?'<span class="alert">WD14 失败</span>':'', ['completed','confirmed'].includes(vlmStatus)?'<span class="ok">Krea 草稿</span>':vlmStatus==='failed'?'<span class="alert">Krea 草稿失败</span>':'', !item.valid?'<span class="alert">坏图</span>':'', exact.has(item.relative_path)?'<span class="alert">完全重复</span>':'', near.has(item.relative_path)?'<span>近似重复</span>':'', `<span>${labels[status]}</span>`].join(''); return `<article class="dataset-card ${state.selected.has(item.relative_path)?'selected':''} ${item.valid?'':'invalid'}" data-dataset-index="${index}"><input class="dataset-card-select" type="checkbox" ${state.selected.has(item.relative_path)?'checked':''} aria-label="选择 ${escapeHtml(item.filename)}"><button class="dataset-card-preview" ${item.valid?'':'disabled'}>${item.thumbnail_url?`<img src="${escapeHtml(item.thumbnail_url)}" loading="lazy" alt="${escapeHtml(item.filename)}">`:'<span class="dataset-card-placeholder">无法预览</span>'}</button><div class="dataset-card-body"><strong>${escapeHtml(item.filename)}</strong><div class="dataset-card-meta"><span>${item.width}×${item.height}</span><span>${escapeHtml(item.format || '未知')}</span><span>${(item.bytes/1024).toFixed(0)} KiB</span></div><div class="dataset-card-flags">${flags}</div></div></article>`; }).join('') : '<div class="dataset-empty"><h2>当前筛选没有图片</h2><p>调整上方条件即可恢复显示。</p></div>'; renderStats(); renderJourney(); }
  function configureFormats() { const selected=$('#datasetFormatFilter').value; const formats=[...new Set((state.report?.images || []).map(item=>item.format).filter(Boolean))].sort(); $('#datasetFormatFilter').innerHTML='<option value="all">全部格式</option>'+formats.map(value=>`<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join(''); if (formats.includes(selected)) $('#datasetFormatFilter').value=selected; }
  async function loadModels() { const select=$('#datasetKrea2Model'), previous=select.value; try { const result=await api('/api/local-models'); state.models=(result.models || []).filter(item=>item.vision); const preferred=state.models.find(item=>item.loaded && /qwen.*3\.5.*9b/i.test(item.id)) || state.models.find(item=>item.loaded) || state.models.find(item=>/qwen.*3\.5.*9b/i.test(item.id)) || state.models[0]; select.innerHTML=state.models.length?state.models.map(item=>`<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}${item.loaded?' · 已加载':''}</option>`).join(''):'<option value="">LM Studio 没有可用视觉模型</option>'; if (state.models.some(item=>item.id===previous)) select.value=previous; else if (preferred) select.value=preferred.id; } catch(error) { state.models=[]; select.innerHTML='<option value="">LM Studio 当前不可连接</option>'; $('#datasetKrea2QueueHint').textContent=`视觉草稿暂不可用：${error.message}`; } }
  async function loadReport() { if (!state.active) return; state.report=await api(`/api/dataset-workspaces/${encodeURIComponent(state.active.workspace_id)}/report`); state.selected=new Set((state.report.images || []).filter(item=>item.review?.selected).map(item=>item.relative_path)); state.preflight=null; configureFormats(); renderGrid(); $('#datasetScanTime').textContent=`扫描于 ${(state.report.scanned_at || '').slice(0,16).replace('T',' ')}`; await Promise.all([loadAnalytics(),loadSnapshots(),loadExports()]); renderJourney(); }
  async function selectWorkspace(id) { state.page=1; state.step=0; state.exports=[]; state.preflight=null; state.active=state.workspaces.find(item=>item.workspace_id===id) || null; renderWorkspaces(); $('#datasetEmpty').hidden=Boolean(state.active); $('#datasetDesk').hidden=!state.active; if (!state.active) { state.report=null; return; } $('#datasetActiveName').textContent=state.active.name; $('#datasetActivePath').textContent=state.active.source_path; renderDatasetOrigin(); if (state.active.current_report) await loadReport(); else { state.report=null; renderGrid(); } await refreshJobs(); }
  async function loadWorkspaces(preferred='') { state.workspaces=await api('/api/dataset-workspaces'); renderWorkspaces(); const id=preferred || state.active?.workspace_id || state.workspaces[0]?.workspace_id; if (id) await selectWorkspace(id); }
  async function importWorkspace(event) { event.preventDefault(); const button=event.submitter; button.disabled=true; try { const result=await api('/api/dataset-workspaces/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_path:$('#datasetSourcePath').value.trim(),name:$('#datasetName').value.trim()})}); await loadWorkspaces(result.workspace.workspace_id); startPolling(); } catch(error) { alert(`读取失败：${error.message}`); } finally { button.disabled=false; } }
  function renderJob(job) { const panel=$('#datasetJobPanel'); if (!job) { panel.hidden=true; panel.dataset.jobState=''; return; } const active=['queued','running'].includes(job.status), total=Math.max(job.progress_total,1), types={dataset_wd14:'WD14 生成标签',dataset_krea2_vlm:'Krea 2 视觉草稿',dataset_scan:'扫描数据集'}, statuses={queued:'等待开始',running:'正在处理',completed:'已完成',failed:'执行失败',canceled:'已取消'}, type=types[job.job_type] || '数据集任务'; const action=active?`<button data-job-action="cancel" data-job-id="${job.job_id}">取消</button>`:['failed','canceled'].includes(job.status)?`<button data-job-action="retry" data-job-id="${job.job_id}">重试</button>`:''; panel.dataset.jobState=job.status; panel.hidden=state.mode==='simple'&&job.status==='completed'; panel.innerHTML=`<div class="dataset-job-line"><span>${escapeHtml(type)} · ${escapeHtml(statuses[job.status] || job.status)}</span><progress value="${job.progress_current}" max="${total}"></progress>${action}</div><p class="dataset-job-message">${escapeHtml(job.progress_message || job.error || '等待处理')}</p>`; }
  async function refreshJobs() { if (!state.active) return false; const jobs=await api('/api/jobs?limit=100'), related=jobs.filter(item=>['dataset_scan','dataset_wd14','dataset_krea2_vlm'].includes(item.job_type) && item.payload?.workspace_id===state.active.workspace_id), job=related.find(item=>['queued','running'].includes(item.status)) || related[0]; renderJob(job); if (job && ['queued','running'].includes(job.status)) return true; const active=await api(`/api/dataset-workspaces/${state.active.workspace_id}`); const shouldLoad=Boolean(active.current_report) && (!state.report || active.current_report!==state.active.current_report || job?.status==='completed'); Object.assign(state.active,active); if (shouldLoad) await loadReport(); renderWorkspaces(); return false; }
  function startPolling() { clearInterval(state.poll); state.poll=setInterval(async()=>{ try { const running=await refreshJobs(); if (!running) clearInterval(state.poll); } catch(error) { console.error(error); clearInterval(state.poll); } },900); }
  async function updateReviews(items) { if (!state.active || !items.length) return; await api(`/api/dataset-workspaces/${state.active.workspace_id}/review`,jsonOptions({items})); await loadReport(); }
  function selectedPaths(scope='selected') { if (scope==='filtered') return state.visible.map(item=>item.relative_path); return [...state.selected]; }
  async function queueWd14(scope) { if (!state.active) return; const paths=scope==='selected'?selectedPaths():[]; if (scope==='selected' && !paths.length) return alert('请先选择要打标的图片。'); if (scope==='all' && !confirm('重新打标整个工作区会替换尚未人工确认的 Anima 草稿。继续吗？')) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/wd14`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope,paths,general_threshold:Number($('#datasetGeneralThreshold').value),character_threshold:Number($('#datasetCharacterThreshold').value),provider:'cpu',overwrite:scope==='all'})}); renderJob(result.job); startPolling(); }
  async function queueKrea2VLM(scope) { if (!state.active) return; const model=$('#datasetKrea2Model').value, paths=scope==='selected'?selectedPaths():[]; if (!model) return alert('请先在 LM Studio 中准备并加载一个视觉模型。'); if (scope==='selected' && !paths.length) return alert('请先选择要生成草稿的图片。'); const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/krea2-vlm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope,paths,model})}); renderJob(result.job); $('#datasetKrea2QueueHint').textContent='队列已开始。模型结果只会进入待确认草稿。'; startPolling(); }
  async function loadTagCatalog() { const payload=await api('/api/tags/catalog?language=zh'); $('#datasetTagSuggestions').innerHTML=(payload.items||[]).map(item=>`<option value="${escapeHtml(item.zh || item.en)}">${escapeHtml(item.en)}</option>`).join(''); }
  function appendBulkTag(tag) { const input=$('#datasetBulkAdd'), values=input.value.split(',').map(value=>value.trim()).filter(Boolean); if (!values.some(value=>value.toLowerCase()===tag.toLowerCase())) values.push(tag); input.value=values.join(', '); state.bulkPreview=null; $('#datasetBulkApply').disabled=true; $('#datasetBulkResult').textContent=`已选择 ${window.displayCanonicalTag?.(tag)||tag}；请先预览修改。`; }
  async function loadAnalytics() { if (!state.active) return; state.analytics=await api(`/api/dataset-workspaces/${state.active.workspace_id}/analytics`); const top=(state.analytics.frequencies || []).slice(0,18); await window.ensureTagLabels?.(top.map(item=>item.tag)); const chips=top.map(item=>`<button type="button" data-bulk-tag="${escapeHtml(item.tag)}" title="加入批量添加">${escapeHtml(window.displayCanonicalTag?.(item.tag) || item.tag)} · ${item.count}</button>`).join(''); $('#datasetAnalytics').innerHTML=`<strong>${formatNumber(state.analytics.captioned_images)} 张有 Anima 标签 · ${formatNumber(state.analytics.unique_tags)} 个标签 · ${formatNumber((state.analytics.conflicts||[]).length)} 个冲突提示</strong><div class="dataset-analytics-tags">${chips || '<span>暂无标签</span>'}</div>`; }
  async function loadSnapshots() { if (!state.active) return; const snapshots=await api(`/api/dataset-workspaces/${state.active.workspace_id}/snapshots`), selected=$('#datasetSnapshot').value; $('#datasetSnapshot').innerHTML='<option value="">选择修改记录</option>'+snapshots.map(item=>`<option value="${escapeHtml(item.snapshot_id)}">${escapeHtml(item.profile_id.toUpperCase())} · ${escapeHtml(item.operation)} · ${item.changed} 张 · ${escapeHtml(item.created_at.slice(0,16).replace('T',' '))}</option>`).join(''); if (snapshots.some(item=>item.snapshot_id===selected)) $('#datasetSnapshot').value=selected; }
  async function loadExports() { if(!state.active) return; state.exports=await api(`/api/dataset-workspaces/${state.active.workspace_id}/exports`); renderExports(); }
  function sourceCaptionPayload(scope) { return {profile_id:$('#datasetSourceCaptionProfile').value,paths:scope==='selected'?selectedPaths():[],overwrite_existing:$('#datasetSourceCaptionOverwrite').checked,caption_status:$('#datasetSourceCaptionStatus').value}; }
  async function previewSourceCaptions(scope) { if(!state.active) return; if(scope==='selected'&&!state.selected.size) return alert('请先选择要接续原说明文字的图片。'); const payload=sourceCaptionPayload(scope), result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/source-captions/preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); state.sourceCaptionPreview={payload,result}; const invalid=result.invalid?.length||0; $('#datasetSourceCaptionResult').textContent=`检查 ${result.inspected} 张：可接续 ${result.changed} 张，已有内容跳过 ${result.skipped_existing} 张，空白跳过 ${result.skipped_empty} 张，不符合英文要求 ${invalid} 张。`; $('#datasetSourceCaptionApply').disabled=!result.changed; }
  async function applySourceCaptions() { const preview=state.sourceCaptionPreview; if(!preview?.result?.changed) return; const profile=preview.payload.profile_id.toUpperCase(), status=preview.payload.caption_status==='reviewed'?'已人工审核':'待审核'; if(!confirm(`确认把 ${preview.result.changed} 份原说明文字接入 ${profile}，状态设为“${status}”？\n系统只创建一条批量修改记录，不会改写原 .txt。`)) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/source-captions/apply`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(preview.payload)}); $('#datasetSourceCaptionResult').textContent=`已接续 ${result.changed} 张到 ${profile}；修改记录 ${result.snapshot}。`; state.sourceCaptionPreview=null; $('#datasetSourceCaptionApply').disabled=true; await loadReport(); }
  function bulkPayload() { return {paths:selectedPaths(),add:$('#datasetBulkAdd').value.split(',').map(value=>value.trim()).filter(Boolean),remove:$('#datasetBulkRemove').value.split(',').map(value=>value.trim()).filter(Boolean),replace:{},sort:$('#datasetBulkSort').checked}; }
  async function previewBulkTags() { if (!state.active || !state.selected.size) return alert('请先选择要整理的图片。'); state.bulkPreview=await api(`/api/dataset-workspaces/${state.active.workspace_id}/bulk-tags/preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bulkPayload())}); const s=state.bulkPreview.summary; $('#datasetBulkResult').textContent=`将修改 ${state.bulkPreview.changed} 张；增加 ${s.added_instances} 个、删除 ${s.removed_instances} 个标签；冲突提示 ${state.bulkPreview.conflicts.length} 个。`; $('#datasetBulkApply').disabled=!state.bulkPreview.changed; }
  async function applyBulkTags() { if (!state.bulkPreview?.changed || !confirm(`确认修改 ${state.bulkPreview.changed} 张图片的说明文字？系统会先保存一条可回退记录。`)) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/bulk-tags/apply`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bulkPayload())}); $('#datasetBulkResult').textContent=`已修改 ${result.changed} 张；修改记录 ${result.snapshot}。`; state.bulkPreview=null; $('#datasetBulkApply').disabled=true; await loadReport(); }
  async function runPreflight() { if(!state.active) return null; const profile=$('#datasetDeliveryProfile').value, paths=selectedPaths(); if(!paths.length) { state.preflight=null; renderPreflight(); return null; } $('#datasetPreflightBadge').textContent='正在检查'; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/preflight`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:profile,paths})}); result._selectionKey=deliverySelectionKey(profile); state.preflight=result; renderPreflight(); return result; }
  async function exportVersion(profile) { if (!state.active || !state.selected.size) return alert('请先选择并标记保留要导出的图片。'); const preflight=await runPreflight(); if(!preflight?.ready) return alert('交付前检查尚未通过，请先处理红色问题。'); const profileName=profile==='anima'?'Anima':'Krea 2'; if(!confirm(`确认用 ${state.selected.size} 张图片生成 ${profileName} 数据集副本？\n系统会建立新的 Mac 版本，不会改动源图片和原 .txt。`)) return; const button=$('#datasetExportActiveProfile'); button.disabled=true; button.textContent='正在生成并核对文件…'; try { const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/export`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:profile,paths:selectedPaths()})}); $('#datasetExportResult').innerHTML=`已生成 ${escapeHtml(result.version_id)} · ${result.image_count} 张 · ${result.file_count} 个文件 · <a href="${escapeHtml(result.download_url)}">下载 ZIP</a>`; await loadExports(); state.step=5; } finally { renderJourney(); } }
  async function revealExport(versionId) { await api(`/api/dataset-workspaces/${state.active.workspace_id}/exports/${encodeURIComponent(versionId)}/reveal`,{method:'POST'}); $('#datasetCopyResult').textContent=`已在 Finder 中显示 ${versionId}。`; }
  async function copyExport(versionId, button) { if(!confirm(`把版本 ${versionId} 复制到已挂载的 5060 Ti 共享目录？\n目标按数据集名和版本号隔离，不会覆盖旧版本。`)) return; button.disabled=true; button.textContent='正在复制并核对哈希…'; try { const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/exports/${encodeURIComponent(versionId)}/copy`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({node_id:'compute_5060ti'})}); $('#datasetCopyResult').textContent=result.status==='already_present'?`5060 Ti 已存在 ${versionId}，没有覆盖。`:`已复制 ${result.file_count} 个文件到 5060 Ti，并完成哈希核对。`; await loadExports(); } finally { button.disabled=false; button.textContent='复制到 5060 Ti'; } }
  async function rollbackSnapshot() { const id=$('#datasetSnapshot').value; if (!id || !confirm(`恢复说明文字修改记录 ${id}？当前内容也会先保存，之后仍可找回。`)) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/snapshots/${encodeURIComponent(id)}/rollback`,{method:'POST'}); $('#datasetBulkResult').textContent=`已恢复 ${result.changed} 张；同时保存了当前内容，记录编号 ${result.snapshot}。`; await loadReport(); }
  function detailItem() { return state.pageItems[state.detailIndex]; }
  async function renderDetailTags(item) { const caption=$('#datasetDetailAnima').value, tags=caption.split(',').map(value=>value.trim()).filter(Boolean), candidates=[...new Set([...(item.curation?.wd14?.general || []).map(value=>value.tag).filter(Boolean),...tags])], selected=new Set(tags); await window.ensureTagLabels?.(candidates); $('#datasetDetailTagChips').innerHTML=candidates.map(tag=>`<button class="${selected.has(tag)?'selected':''}" data-detail-tag="${escapeHtml(tag)}" aria-pressed="${selected.has(tag)}">${escapeHtml(window.displayCanonicalTag?.(tag) || tag)}</button>`).join(''); }
  function renderDetail() { const item=detailItem(); if (!item) return; const wd14=item.curation?.wd14 || {status:'untagged'}, vlm=item.curation?.krea2_vlm || {status:'empty'}, anima=item.curation?.captions?.anima || {}, krea=item.curation?.captions?.krea2 || {}, vlmTime=vlm.created_at?` · ${vlm.created_at.slice(0,16).replace('T',' ')}`:''; $('#datasetDetailImage').src=item.original_url; $('#datasetDetailName').textContent=item.relative_path; $('#datasetDetailMeta').textContent=`${item.width}×${item.height} · ${item.format} · ${(item.bytes/1024).toFixed(1)} KiB`; $('#datasetDetailStatus').value=item.review?.status || 'pending'; $('#datasetDetailCaption').value=item.caption || ''; $('#datasetDetailAnima').value=anima.current || ''; $('#datasetDetailKrea2').value=krea.current || ''; $('#datasetDetailKrea2Draft').value=vlm.draft || ''; $('#datasetDetailWD14').textContent=wd14.status==='completed'?`${wd14.model || 'WD14'} · ${wd14.provider || 'CPU'} · 草稿待人工检查`:wd14.status==='failed'?`失败：${wd14.error || '未知错误'}`:'尚未运行 WD14'; $('#datasetDetailKrea2VLM').textContent=vlm.status==='failed'?`失败：${vlm.error || '未知错误'}`:['completed','confirmed'].includes(vlm.status)?`${vlm.model || '人工保存草稿'}${vlmTime}${vlm.status==='confirmed'?' · 已确认':''}`:'尚无草稿'; $('#datasetDetailKrea2Warning').hidden=!vlm.safety_warning; $('#datasetDetailKrea2Warning').textContent=vlm.safety_warning || ''; $('#datasetDetailDraftConfirm').disabled=!vlm.draft; $('#datasetDetailNote').value=item.review?.note || ''; $('#datasetDetailHashes').textContent=`SHA-256：${item.sha256}\npHash：${item.phash || '—'}\n原始说明：${item.caption_path || '缺失'}\n来源文件：${item.relative_path}\nAnima 状态：${anima.status || 'empty'}\nKrea 2 状态：${krea.status || 'empty'}\n视觉草稿哈希：${vlm.source_sha256 || '—'}`; $('#datasetPrevious').disabled=state.detailIndex<=0; $('#datasetNext').disabled=state.detailIndex>=state.pageItems.length-1; $('#datasetFindSimilar').disabled=true; $('#datasetFindSimilarStatus').textContent='正在检查真实视觉索引……'; refreshSimilarStatus(item).catch(error=>$('#datasetFindSimilarStatus').textContent=error.message); renderDetailTags(item).catch(console.error); }
  async function refreshSimilarStatus(item) { const digest=item.sha256, result=await api(`/api/hybrid-search/source-status?source_sha256=${encodeURIComponent(digest)}`); if(detailItem()?.sha256!==digest) return; $('#datasetFindSimilar').disabled=!result.available; $('#datasetFindSimilarStatus').textContent=result.available?`已进入 ${result.indexes.length} 个真实索引，可以查相似图。`:'等待 5060 Ti 生成真实 CLIP / SigLIP 索引；当前不生成伪结果。'; }
  function openDetail(index) { state.detailIndex=index; renderDetail(); $('#datasetDetail').showModal(); }
  function moveDetail(offset) { const next=state.detailIndex+offset; if (next<0 || next>=state.pageItems.length) return; state.detailIndex=next; renderDetail(); }
  async function saveDetail() { const item=detailItem(); if (!item) return; const requests=[api(`/api/dataset-workspaces/${state.active.workspace_id}/review`,jsonOptions({items:[{relative_path:item.relative_path,status:$('#datasetDetailStatus').value,selected:state.selected.has(item.relative_path),note:$('#datasetDetailNote').value}]}))], anima=$('#datasetDetailAnima').value.trim(), krea=$('#datasetDetailKrea2').value.trim(); if (anima!==String(item.curation?.captions?.anima?.current || '')) requests.push(api(`/api/dataset-workspaces/${state.active.workspace_id}/caption`,jsonOptions({relative_path:item.relative_path,profile_id:'anima',caption:anima,caption_status:'reviewed'}))); if (krea!==String(item.curation?.captions?.krea2?.current || '')) requests.push(api(`/api/dataset-workspaces/${state.active.workspace_id}/caption`,jsonOptions({relative_path:item.relative_path,profile_id:'krea2',caption:krea,caption_status:'reviewed'}))); await Promise.all(requests); await loadReport(); state.detailIndex=state.pageItems.findIndex(candidate=>candidate.relative_path===item.relative_path); renderDetail(); }
  async function saveKrea2Draft(confirmDraft) { const item=detailItem(), draft=$('#datasetDetailKrea2Draft').value.trim(); if (!item) return; if (confirmDraft && !draft) return alert('确认前需要一份英文 Krea 2 草稿。'); if (confirmDraft && !confirm('确认把这份视觉模型草稿写入正式 Krea 2 图片说明？系统会先保存可回退的修改记录。')) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/krea2-draft`,jsonOptions({relative_path:item.relative_path,draft,confirm:confirmDraft})); await loadReport(); state.detailIndex=state.pageItems.findIndex(candidate=>candidate.relative_path===item.relative_path); renderDetail(); if (confirmDraft) $('#datasetDetailKrea2VLM').textContent=`已确认写入 Krea 2 · ${result.snapshot}`; }
  async function rescan() { if (!state.active) return; await api(`/api/dataset-workspaces/${state.active.workspace_id}/rescan`,{method:'POST'}); await loadWorkspaces(state.active.workspace_id); startPolling(); }
  async function removeWorkspace() { if (!state.active || !confirm(`只移除 Prompt Hub 中的“${state.active.name}”记录和派生缩略图。原文件夹不会删除。继续吗？`)) return; const source=state.active.source_path; await api(`/api/dataset-workspaces/${state.active.workspace_id}`,{method:'DELETE'}); state.active=null; state.report=null; await loadWorkspaces(); alert(`工作区记录已移除。源目录保持不变：\n${source}`); }
  function setDatasetMode(mode) { state.mode=mode==='advanced'?'advanced':'simple'; try { localStorage.setItem('soda-dataset-mode',state.mode); } catch(error) { console.debug(error); } renderJourney(); }
  function setDatasetStep(step,{preset=false,scroll=true}={}) { state.step=Math.min(5,Math.max(1,Number(step)||1)); const d=deliveryState(); if(preset&&state.step===2) { $('#datasetValidity').value=d.invalidOpen.length?'invalid':'all'; $('#datasetDuplicateFilter').value=!d.invalidOpen.length&&d.exactBlockingGroups.length?'exact':'all'; $('#datasetReviewFilter').value='all'; renderGrid(true); } else if(preset&&state.step===4) { $('#datasetValidity').value='valid'; $('#datasetDuplicateFilter').value='all'; $('#datasetReviewFilter').value=d.pending.length?'pending':d.needsReview.length?'needs_review':'all'; renderGrid(true); } else renderJourney(); if(state.step===5) runPreflight().catch(error=>{$('#datasetPreflightSummary').textContent=error.message;}); if(scroll) { const target=state.step===1?$('#datasetImportForm'):state.step===3?document.querySelector('[data-dataset-stage-panel="3"]'):state.step===5?$('#datasetDeliveryPanel'):document.querySelector('[data-dataset-stage-panel="2,4"]'); target?.scrollIntoView({behavior:'smooth',block:'start'}); if(state.step===1) $('#datasetSourcePath').focus(); } }
  function runDatasetNextAction() { const d=deliveryState(), step=state.step || d.recommended; if(step===1) return setDatasetStep(1,{scroll:true}); if(step===2&&d.invalidOpen.length+d.exactBlockingGroups.length===0) return setDatasetStep(3); if(step===3&&!d.missing.length) return setDatasetStep(4,{preset:true}); if(step===4&&!d.captionDraft.length&&!d.pending.length&&!d.needsReview.length&&d.deliverable.length) return setDatasetStep(5); if(step===5&&!d.deliverable.length) return setDatasetStep(4,{preset:true}); setDatasetStep(step,{preset:true}); }
  async function ensureWorkspace() { try { state.mode=localStorage.getItem('soda-dataset-mode')==='advanced'?'advanced':'simple'; } catch(error) { console.debug(error); } await Promise.all([loadModels(),loadTagCatalog(),loadWorkspaces()]); if (state.active) { const running=await refreshJobs(); if (running) startPolling(); } renderJourney(); }
  async function openDatasetWorkspace(workspaceId,step=0) { await loadWorkspaces(workspaceId); if(step) setDatasetStep(step,{preset:true,scroll:true}); const running=await refreshJobs(); if(running) startPolling(); }
  window.openDatasetWorkspace=openDatasetWorkspace;
  $('#datasetImportForm').addEventListener('submit',importWorkspace);
  $('#datasetModeSimple').addEventListener('click',()=>setDatasetMode('simple'));
  $('#datasetModeAdvanced').addEventListener('click',()=>setDatasetMode('advanced'));
  $('#datasetJourney').addEventListener('click',event=>{ const button=event.target.closest('[data-dataset-step]'); if(button) setDatasetStep(button.dataset.datasetStep,{preset:true}); });
  $('#datasetDeliveryProfile').addEventListener('change',event=>{ $('#datasetSourceCaptionProfile').value=event.target.value; state.step=0; state.preflight=null; renderGrid(true); });
  $('#datasetNextAction').addEventListener('click',runDatasetNextAction);
  $('#datasetRunPreflight').addEventListener('click',()=>runPreflight().catch(error=>alert(error.message)));
  $('#datasetExportActiveProfile').addEventListener('click',()=>exportVersion($('#datasetDeliveryProfile').value).catch(error=>alert(error.message)));
  $('#datasetDeliveryHistory').addEventListener('click',event=>{ const button=event.target.closest('[data-export-action]'), card=event.target.closest('[data-export-version]'); if(!button||!card) return; if(button.dataset.exportAction==='reveal') revealExport(card.dataset.exportVersion).catch(error=>alert(error.message)); else copyExport(card.dataset.exportVersion,button).catch(error=>alert(error.message)); });
  $('#datasetDesk').addEventListener('click',event=>{ const button=event.target.closest('[data-origin-project]'); if(button) window.openCreativeProject?.(button.dataset.originProject).catch(error=>alert(error.message)); });
  $('#datasetWorkspaceList').addEventListener('click',event=>{ const button=event.target.closest('[data-workspace-id]'); if (button) selectWorkspace(button.dataset.workspaceId).catch(console.error); });
  ['#datasetValidity','#datasetCaptionFilter','#datasetReviewFilter','#datasetDuplicateFilter','#datasetFormatFilter','#datasetSizeFilter'].forEach(selector=>$(selector).addEventListener('change',()=>renderGrid(true)));
  $('#datasetGrid').addEventListener('click',event=>{ const card=event.target.closest('[data-dataset-index]'); if (!card) return; const item=state.pageItems[Number(card.dataset.datasetIndex)]; if (event.target.classList.contains('dataset-card-select')) { event.target.checked ? state.selected.add(item.relative_path) : state.selected.delete(item.relative_path); renderGrid(); } else if (event.target.closest('.dataset-card-preview')) openDetail(Number(card.dataset.datasetIndex)); });
  $('#datasetPreviousPage').addEventListener('click',()=>{ if (state.page<=1) return; state.page-=1; renderGrid(); $('#datasetPagination').scrollIntoView({block:'nearest'}); });
  $('#datasetNextPage').addEventListener('click',()=>{ if (state.page*state.pageSize>=state.visible.length) return; state.page+=1; renderGrid(); $('#datasetPagination').scrollIntoView({block:'nearest'}); });
  $('#datasetSelectVisible').addEventListener('change',event=>{ state.visible.forEach(item=>event.target.checked?state.selected.add(item.relative_path):state.selected.delete(item.relative_path)); renderGrid(); });
  $('#datasetClearSelection').addEventListener('click',()=>{ state.selected.clear(); renderGrid(); });
  document.querySelectorAll('[data-bulk-status]').forEach(button=>button.addEventListener('click',()=>{ const items=(state.report?.images || []).filter(item=>state.selected.has(item.relative_path)).map(item=>({relative_path:item.relative_path,status:button.dataset.bulkStatus,selected:true,note:item.review?.note || ''})); updateReviews(items).catch(error=>alert(error.message)); }));
  document.querySelectorAll('[data-wd14-scope]').forEach(button=>button.addEventListener('click',()=>queueWd14(button.dataset.wd14Scope).catch(error=>alert(error.message))));
  document.querySelectorAll('[data-krea2-vlm-scope]').forEach(button=>button.addEventListener('click',()=>queueKrea2VLM(button.dataset.krea2VlmScope).catch(error=>alert(error.message))));
  document.querySelectorAll('[data-source-caption-scope]').forEach(button=>button.addEventListener('click',()=>previewSourceCaptions(button.dataset.sourceCaptionScope).catch(error=>alert(error.message))));
  $('#datasetSourceCaptionApply').addEventListener('click',()=>applySourceCaptions().catch(error=>alert(error.message)));
  ['#datasetSourceCaptionProfile','#datasetSourceCaptionStatus','#datasetSourceCaptionOverwrite'].forEach(selector=>$(selector).addEventListener('change',()=>{ state.sourceCaptionPreview=null; $('#datasetSourceCaptionApply').disabled=true; $('#datasetSourceCaptionResult').textContent='设置已改变，请重新预览。'; }));
  $('#datasetBulkPreview').addEventListener('click',()=>previewBulkTags().catch(error=>alert(error.message))); $('#datasetBulkApply').addEventListener('click',()=>applyBulkTags().catch(error=>alert(error.message)));
  $('#datasetAnalytics').addEventListener('click',event=>{ const button=event.target.closest('[data-bulk-tag]'); if (button) appendBulkTag(button.dataset.bulkTag); });
  document.querySelectorAll('[data-export-profile]').forEach(button=>button.addEventListener('click',()=>exportVersion(button.dataset.exportProfile).catch(error=>alert(error.message)))); $('#datasetRollbackSnapshot').addEventListener('click',()=>rollbackSnapshot().catch(error=>alert(error.message)));
  $('#datasetRescan').addEventListener('click',()=>rescan().catch(error=>alert(error.message))); $('#datasetRemove').addEventListener('click',()=>removeWorkspace().catch(error=>alert(error.message)));
  $('#datasetDetailClose').addEventListener('click',()=>$('#datasetDetail').close()); $('#datasetPrevious').addEventListener('click',()=>moveDetail(-1)); $('#datasetNext').addEventListener('click',()=>moveDetail(1)); $('#datasetDetailSave').addEventListener('click',()=>saveDetail().catch(error=>alert(error.message)));
  $('#datasetDetailDraftSave').addEventListener('click',()=>saveKrea2Draft(false).catch(error=>alert(error.message))); $('#datasetDetailDraftConfirm').addEventListener('click',()=>saveKrea2Draft(true).catch(error=>alert(error.message)));
  $('#datasetFindSimilar').addEventListener('click',()=>{ const item=detailItem(); if(!item) return; $('#datasetDetail').close(); window.openSimilarImage?.(item.sha256,item.filename||item.relative_path); });
  $('#datasetDetailTagChips').addEventListener('click',event=>{ const button=event.target.closest('[data-detail-tag]'); if (!button) return; const tag=button.dataset.detailTag, tags=$('#datasetDetailAnima').value.split(',').map(value=>value.trim()).filter(Boolean), selected=new Set(tags); selected.has(tag)?selected.delete(tag):selected.add(tag); $('#datasetDetailAnima').value=[...selected].join(', '); renderDetailTags(detailItem()).catch(console.error); });
  $('#datasetDetail').addEventListener('keydown',event=>{ if (event.key==='ArrowLeft') moveDetail(-1); if (event.key==='ArrowRight') moveDetail(1); });
  $('#datasetJobPanel').addEventListener('click',async event=>{ const button=event.target.closest('[data-job-action]'); if (!button) return; const action=button.dataset.jobAction; await api(`/api/jobs/${button.dataset.jobId}/${action}`,{method:'POST'}); startPolling(); });
  window.addEventListener('tag-language-change',()=>{ if (state.analytics) loadAnalytics().catch(console.error); if ($('#datasetDetail').open && detailItem()) renderDetailTags(detailItem()).catch(console.error); });
  window.ensureDatasetWorkspace=ensureWorkspace;
})();
</script>
"""
