# ruff: noqa: E501, RUF001

WORKSPACE_HTML = r"""
<section class="dataset-page" id="workspacePage" hidden>
  <header class="dataset-heading">
    <div><span class="eyebrow">Dataset desk / local only</span><h1>数据集工作台</h1></div>
    <p>查看、筛选和审核任意本地图片目录。源图片与原 caption 始终只读；所有审核记录、缩略图和后续导出版本保存在 Prompt Hub。</p>
  </header>
  <div class="dataset-layout">
    <aside class="dataset-sidebar">
      <form id="datasetImportForm">
        <label>数据集文件夹路径<input id="datasetSourcePath" required placeholder="/Users/your-name/Pictures/my-dataset"></label>
        <label>显示名称（可选）<input id="datasetName" maxlength="160" placeholder="角色名 / 项目名"></label>
        <button class="dataset-primary" type="submit">读取并建立工作区</button>
        <p class="dataset-hint">不会移动、改名或覆盖文件夹中的任何内容。</p>
      </form>
      <div class="dataset-sidebar-head"><strong>最近工作区</strong><span id="datasetWorkspaceCount">0</span></div>
      <div id="datasetWorkspaceList" class="dataset-workspace-list"></div>
    </aside>
    <main class="dataset-main">
      <div id="datasetEmpty" class="dataset-empty">
        <span>01</span><h2>先读取一个图片文件夹</h2><p>扫描完成后，这里会显示缩略图、caption 缺失、坏图、重复图片和审核状态。</p>
      </div>
      <div id="datasetDesk" hidden>
        <div class="dataset-titlebar">
          <div><span class="section-label">Active workspace</span><h2 id="datasetActiveName">—</h2><p id="datasetActivePath">—</p></div>
          <div class="dataset-title-actions"><button id="datasetRescan">重新扫描</button><button class="danger" id="datasetRemove">移除记录</button></div>
        </div>
        <div id="datasetJobPanel" class="dataset-job-panel" hidden></div>
        <div class="dataset-stats" id="datasetStats"></div>
        <div class="dataset-toolbar">
          <label>状态<select id="datasetValidity"><option value="all">全部图片</option><option value="valid">有效图片</option><option value="invalid">坏图</option></select></label>
          <label>Caption<select id="datasetCaptionFilter"><option value="all">全部</option><option value="paired">已有 caption</option><option value="missing">缺 caption</option></select></label>
          <label>审核<select id="datasetReviewFilter"><option value="all">全部</option><option value="pending">未审核</option><option value="approved">保留</option><option value="needs_review">待复查</option><option value="excluded">排除</option></select></label>
          <label>重复<select id="datasetDuplicateFilter"><option value="all">全部</option><option value="exact">完全重复</option><option value="near">近似重复</option><option value="unique">无重复</option></select></label>
          <label>格式<select id="datasetFormatFilter"><option value="all">全部格式</option></select></label>
          <label>最短边<select id="datasetSizeFilter"><option value="0">不限</option><option value="512">≥ 512</option><option value="768">≥ 768</option><option value="1024">≥ 1024</option></select></label>
        </div>
        <div class="dataset-bulkbar">
          <label><input type="checkbox" id="datasetSelectVisible"> 选择当前筛选结果</label>
          <span id="datasetSelectionCount">已选 0 张</span>
          <button data-bulk-status="approved">标记保留</button><button data-bulk-status="needs_review">待复查</button><button data-bulk-status="excluded">排除</button><button id="datasetClearSelection">清空选择</button>
        </div>
        <section class="dataset-curation-panel">
          <div class="dataset-curation-head"><div><span class="section-label">02 / Caption desk</span><h3>自动打标与双 Caption</h3></div><p>WD14 只生成 Anima 英文草稿；Krea 2 自然语言单独审核。任何操作都不写回原文件夹。</p></div>
          <div class="dataset-curation-grid">
            <div class="dataset-curation-block">
              <strong>接续原始 .txt Caption</strong>
              <p class="dataset-hint">读取每张图片旁边的同名 .txt；先预览，再一次接入指定 Profile，并且只保存一个批次快照。</p>
              <div class="dataset-thresholds"><label>接入 Profile<select id="datasetSourceCaptionProfile"><option value="anima">Anima 标签</option><option value="krea2">Krea 2 自然语言</option></select></label><label>接入状态<select id="datasetSourceCaptionStatus"><option value="draft">待审核</option><option value="reviewed">已人工审核</option></select></label></div>
              <label class="dataset-inline-check"><input id="datasetSourceCaptionOverwrite" type="checkbox"> 替换该 Profile 已有内容</label>
              <div class="dataset-action-row"><button data-source-caption-scope="all">预览全部</button><button data-source-caption-scope="selected">预览已选</button><button id="datasetSourceCaptionApply" disabled>确认接续</button></div>
              <p id="datasetSourceCaptionResult" class="dataset-hint">默认只填空白 Profile，不改原 .txt，也不运行 WD14。</p>
            </div>
            <div class="dataset-curation-block">
              <strong>WD14 可恢复队列</strong>
              <div class="dataset-thresholds"><label>General<input id="datasetGeneralThreshold" type="number" min="0" max="1" step="0.05" value="0.35"></label><label>Character<input id="datasetCharacterThreshold" type="number" min="0" max="1" step="0.05" value="0.85"></label></div>
              <div class="dataset-action-row"><button data-wd14-scope="selected">打标已选</button><button data-wd14-scope="untagged">只跑未打标</button><button data-wd14-scope="failed">重试失败</button><button data-wd14-scope="all">全部重跑</button></div>
            </div>
            <div class="dataset-curation-block">
              <strong>批量整理 Anima 标签</strong>
              <p class="dataset-hint">可直接输入中文常用名或英文 tag；保存时统一转换为英文 canonical。</p>
              <label>增加标签<input id="datasetBulkAdd" list="datasetTagSuggestions" placeholder="银发, solo"></label><label>删除标签<input id="datasetBulkRemove" list="datasetTagSuggestions" placeholder="水印, text"></label>
              <datalist id="datasetTagSuggestions"></datalist>
              <div class="dataset-action-row"><label class="dataset-inline-check"><input id="datasetBulkSort" type="checkbox"> 排序</label><button id="datasetBulkPreview">预览修改</button><button id="datasetBulkApply" disabled>确认应用</button></div>
              <p id="datasetBulkResult" class="dataset-hint">先选择图片，再预览；应用前会自动保存 caption 快照。</p>
            </div>
            <div class="dataset-curation-block">
              <strong>Krea 2 视觉草稿队列</strong>
              <label>本地视觉模型<select id="datasetKrea2Model"><option value="">正在读取 LM Studio……</option></select></label>
              <div class="dataset-action-row"><button data-krea2-vlm-scope="selected">为已选生成</button><button data-krea2-vlm-scope="missing">只补缺草稿</button><button data-krea2-vlm-scope="failed">重试失败</button></div>
              <p id="datasetKrea2QueueHint" class="dataset-hint">模型只生成英文草稿，不会覆盖正式 Krea 2 caption；请在图片详情中对照并确认。</p>
            </div>
            <div class="dataset-curation-block">
              <strong>审计与版本导出</strong>
              <div id="datasetAnalytics" class="dataset-analytics">尚未产生标签统计。</div>
              <div class="dataset-action-row"><button data-export-profile="anima">导出 Anima 版本</button><button data-export-profile="krea2">导出 Krea 2 版本</button></div>
              <div class="dataset-snapshot-row"><select id="datasetSnapshot"><option value="">Caption 快照</option></select><button id="datasetRollbackSnapshot">回退</button></div>
              <p id="datasetExportResult" class="dataset-hint"></p>
            </div>
          </div>
        </section>
        <div class="dataset-results-head"><strong id="datasetResultCount">0 张</strong><span id="datasetScanTime"></span></div>
        <nav id="datasetPagination" class="dataset-pagination" aria-label="数据集分页" hidden>
          <button id="datasetPreviousPage" type="button">上一页</button>
          <span id="datasetPageStatus">第 1 / 1 页</span>
          <button id="datasetNextPage" type="button">下一页</button>
        </nav>
        <div id="datasetGrid" class="dataset-grid"></div>
      </div>
    </main>
  </div>
  <dialog id="datasetDetail" class="dataset-dialog">
    <button class="dataset-dialog-close" id="datasetDetailClose" aria-label="关闭">×</button>
    <div class="dataset-dialog-image"><img id="datasetDetailImage" alt="数据集原图预览"><button id="datasetPrevious" aria-label="上一张">←</button><button id="datasetNext" aria-label="下一张">→</button></div>
    <div class="dataset-dialog-body">
      <span class="section-label">Image review</span><h2 id="datasetDetailName">—</h2><p id="datasetDetailMeta"></p>
      <label>审核状态<select id="datasetDetailStatus"><option value="pending">未审核</option><option value="approved">保留</option><option value="needs_review">待复查</option><option value="excluded">排除</option></select></label>
      <label>原始 Caption（只读）<textarea id="datasetDetailCaption" readonly></textarea></label>
      <div class="dataset-caption-profile"><strong>Anima · 英文 canonical tags</strong><span id="datasetDetailWD14">尚未运行 WD14</span></div>
      <div id="datasetDetailTagChips" class="dataset-tag-chips"></div>
      <textarea id="datasetDetailAnima" maxlength="12000" aria-label="Anima 英文标签"></textarea>
      <div class="dataset-caption-profile"><strong>Krea 2 · 英文自然语言</strong><span>与 Anima 分开保存</span></div>
      <textarea id="datasetDetailKrea2" maxlength="12000" aria-label="Krea 2 英文自然语言 Caption"></textarea>
      <div class="dataset-caption-profile"><strong>视觉模型草稿 · 待确认</strong><span id="datasetDetailKrea2VLM">尚无草稿</span></div>
      <textarea id="datasetDetailKrea2Draft" maxlength="12000" aria-label="Krea 2 视觉模型英文草稿" placeholder="先在工作台运行 Krea 2 视觉草稿队列"></textarea>
      <p id="datasetDetailKrea2Warning" class="dataset-vlm-warning" hidden></p>
      <div class="dataset-action-row"><button id="datasetDetailDraftSave">只保存草稿</button><button class="dataset-primary" id="datasetDetailDraftConfirm">确认写入 Krea 2</button></div>
      <p class="dataset-hint">确认时系统会创建 Krea 2 caption 快照；Anima 与 WD14 不会改变。</p>
      <div class="dataset-similar-panel"><button id="datasetFindSimilar" disabled>以此图查相似</button><span id="datasetFindSimilarStatus">正在检查真实视觉索引……</span></div>
      <label>审核备注<textarea id="datasetDetailNote" maxlength="2000" placeholder="记录质量、特征、需要修正的标签……"></textarea></label>
      <button class="dataset-primary" id="datasetDetailSave">保存审核与双 Caption</button>
      <details><summary>文件指纹与来源</summary><pre id="datasetDetailHashes"></pre></details>
    </div>
  </dialog>
</section>
"""

WORKSPACE_STYLES = r"""
<style>
  .dataset-page { margin-top: 18px; border: 1px solid var(--line); background: var(--paper); box-shadow: var(--shadow); }
  .dataset-page[hidden] { display: none; }
  .dataset-heading { display: flex; justify-content: space-between; align-items: end; gap: 28px; padding: 25px 28px; border-bottom: 1px solid var(--line); background: linear-gradient(110deg, #ece5d5 0 72%, var(--acid) 72%); }
  .dataset-heading h1 { margin: 5px 0 0; font: 700 clamp(38px, 5vw, 68px)/.9 "Iowan Old Style", serif; letter-spacing: -.045em; }
  .dataset-heading p { max-width: 520px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.6; }
  .dataset-layout { display: grid; grid-template-columns: 285px minmax(0, 1fr); min-height: 720px; }
  .dataset-sidebar { padding: 20px; border-right: 1px solid var(--line); background: #ddd5c5; }
  .dataset-sidebar form { display: grid; gap: 10px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }
  .dataset-sidebar label, .dataset-toolbar label, .dataset-dialog-body label { display: grid; gap: 6px; color: var(--muted); font: 800 9px monospace; text-transform: uppercase; letter-spacing: .06em; }
  .dataset-sidebar input, .dataset-toolbar select, .dataset-dialog-body select, .dataset-dialog-body textarea { width: 100%; border: 1px solid var(--line); background: #f7f1e5; color: var(--ink); padding: 9px; font: 11px/1.45 monospace; }
  .dataset-primary { border: 1px solid var(--signal); background: var(--signal); color: white; padding: 10px 12px; text-align: left; font: 800 9px monospace; text-transform: uppercase; }
  .dataset-hint { margin: 0; color: var(--muted); font-size: 10px; line-height: 1.5; }
  .dataset-sidebar-head { display: flex; justify-content: space-between; margin: 18px 0 8px; font: 800 9px monospace; text-transform: uppercase; }
  .dataset-workspace-list { display: grid; gap: 7px; }
  .dataset-workspace-item { width: 100%; border: 1px solid rgba(31,29,25,.25); background: #eee7da; padding: 10px; text-align: left; }
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
  .dataset-title-actions { display: flex; gap: 7px; }
  .dataset-title-actions button, .dataset-bulkbar button { border: 1px solid var(--ink); padding: 8px 9px; font: 800 8px monospace; }
  .dataset-title-actions .danger { color: var(--signal); border-color: var(--signal); }
  .dataset-job-panel { margin-top: 14px; border: 1px solid var(--ink); background: #171714; color: #f4eddf; padding: 12px; }
  .dataset-job-line { display: grid; grid-template-columns: 90px minmax(0,1fr) auto; gap: 10px; align-items: center; }
  .dataset-job-line progress { width: 100%; accent-color: var(--acid); }
  .dataset-job-line button { color: var(--acid); border-bottom: 1px solid currentColor; font: 800 8px monospace; }
  .dataset-job-line span { font: 8px monospace; }
  .dataset-job-message { margin: 7px 0 0; color: #bdb5a6; font: 9px monospace; }
  .dataset-stats { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 1px; margin-top: 15px; border: 1px solid var(--line); background: var(--line); }
  .dataset-stat { min-width: 0; background: #eee7da; padding: 11px; }
  .dataset-stat strong, .dataset-stat span { display: block; }
  .dataset-stat strong { font: 800 18px monospace; }
  .dataset-stat span { margin-top: 3px; color: var(--muted); font: 8px monospace; text-transform: uppercase; }
  .dataset-toolbar { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 8px; margin-top: 14px; padding: 12px; border: 1px solid var(--line); background: #e1d9ca; }
  .dataset-bulkbar { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; margin-top: 9px; }
  .dataset-bulkbar label, .dataset-bulkbar span { margin-right: 6px; color: var(--muted); font: 9px monospace; }
  .dataset-results-head { display: flex; justify-content: space-between; margin-top: 15px; font: 9px monospace; }
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
  @media (max-width: 900px) { .dataset-layout { grid-template-columns: 230px minmax(0,1fr); } .dataset-stats { grid-template-columns: repeat(3,1fr); } .dataset-toolbar { grid-template-columns: repeat(3,1fr); } .dataset-curation-grid { grid-template-columns: 1fr; } .dataset-curation-block { border-right: 0; border-bottom: 1px solid var(--line); } }
  @media (max-width: 620px) { .dataset-heading { display: block; background: #ece5d5; } .dataset-heading p { margin-top: 12px; } .dataset-layout { display: block; } .dataset-sidebar { border-right: 0; border-bottom: 1px solid var(--line); } .dataset-titlebar, .dataset-curation-head { display: block; } .dataset-title-actions, .dataset-curation-head p { margin-top: 12px; } .dataset-stats, .dataset-toolbar { grid-template-columns: repeat(2,1fr); } .dataset-grid { grid-template-columns: 1fr; } .dataset-dialog[open] { display: block; overflow: auto; } .dataset-dialog-image { min-height: 360px; } }
</style>
"""

WORKSPACE_SCRIPT = r"""
<script>
(() => {
  const state = {workspaces: [], active: null, report: null, analytics: null, models: [], visible: [], pageItems: [], page: 1, pageSize: 200, selected: new Set(), detailIndex: -1, poll: null, bulkPreview: null, sourceCaptionPreview: null};
  const labels = {pending:'未审核', approved:'保留', needs_review:'待复查', excluded:'排除'};
  async function api(url, options={}) { const response = await fetch(url, options); const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || `请求失败：${response.status}`); return data; }
  const jsonOptions = body => ({method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  function duplicateSets() { const exact = new Set(), near = new Set(); (state.report?.exact_duplicates || []).forEach(group => group.files.forEach(path => exact.add(path))); (state.report?.near_duplicates || []).forEach(group => group.files.forEach(path => near.add(path))); return {exact, near}; }
  function renderWorkspaces() { $('#datasetWorkspaceCount').textContent = state.workspaces.length; $('#datasetWorkspaceList').innerHTML = state.workspaces.length ? state.workspaces.map(item => `<button class="dataset-workspace-item ${state.active?.workspace_id === item.workspace_id ? 'active' : ''}" data-workspace-id="${escapeHtml(item.workspace_id)}"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.status)} · ${formatNumber(item.summary?.image_count || 0)} 张</span><span>${escapeHtml(item.source_path)}</span></button>`).join('') : '<p class="dataset-hint">还没有读取过数据集。</p>'; }
  function stat(value, label) { return `<div class="dataset-stat"><strong>${formatNumber(value)}</strong><span>${label}</span></div>`; }
  function renderStats() { const s = state.report?.summary || {}; $('#datasetStats').innerHTML = stat(s.image_count,'图片') + stat(s.valid_image_count,'有效') + stat(s.missing_caption_count,'缺 caption') + stat(s.invalid_image_count,'坏图') + stat(s.exact_duplicate_groups,'完全重复组') + stat(s.near_duplicate_groups,'近似重复组'); }
  function filteredImages() { const {exact, near} = duplicateSets(); const validity=$('#datasetValidity').value, caption=$('#datasetCaptionFilter').value, review=$('#datasetReviewFilter').value, duplicate=$('#datasetDuplicateFilter').value, format=$('#datasetFormatFilter').value, minSize=Number($('#datasetSizeFilter').value); return (state.report?.images || []).filter(item => { const status=item.review?.status || 'pending', inExact=exact.has(item.relative_path), inNear=near.has(item.relative_path); if (validity==='valid' && !item.valid) return false; if (validity==='invalid' && item.valid) return false; if (caption!=='all' && item.caption_status!==caption) return false; if (review!=='all' && status!==review) return false; if (format!=='all' && item.format!==format) return false; if (minSize && Math.min(item.width,item.height)<minSize) return false; if (duplicate==='exact' && !inExact) return false; if (duplicate==='near' && !inNear) return false; if (duplicate==='unique' && (inExact || inNear)) return false; return true; }); }
  function renderGrid(resetPage=false) { const {exact, near}=duplicateSets(); state.visible=filteredImages(); const pageCount=Math.max(1,Math.ceil(state.visible.length/state.pageSize)); if (resetPage) state.page=1; state.page=Math.min(Math.max(state.page,1),pageCount); const start=(state.page-1)*state.pageSize; state.pageItems=state.visible.slice(start,start+state.pageSize); $('#datasetResultCount').textContent=`${formatNumber(state.visible.length)} 张`; $('#datasetSelectionCount').textContent=`已选 ${formatNumber(state.selected.size)} 张`; $('#datasetSelectVisible').checked=state.visible.length>0 && state.visible.every(item => state.selected.has(item.relative_path)); $('#datasetPagination').hidden=state.visible.length<=state.pageSize; $('#datasetPageStatus').textContent=`第 ${formatNumber(state.page)} / ${formatNumber(pageCount)} 页 · 每页最多 ${formatNumber(state.pageSize)} 张`; $('#datasetPreviousPage').disabled=state.page<=1; $('#datasetNextPage').disabled=state.page>=pageCount; $('#datasetGrid').innerHTML=state.pageItems.length ? state.pageItems.map((item,index) => { const status=item.review?.status || 'pending', tagStatus=item.curation?.wd14?.status || 'untagged', vlmStatus=item.curation?.krea2_vlm?.status || 'empty'; const flags=[item.caption_status==='missing'?'<span class="alert">缺原 caption</span>':'<span class="ok">有原 caption</span>', tagStatus==='completed'?'<span class="ok">WD14 已完成</span>':tagStatus==='failed'?'<span class="alert">WD14 失败</span>':'<span>未打标</span>', ['completed','confirmed'].includes(vlmStatus)?'<span class="ok">Krea 草稿</span>':vlmStatus==='failed'?'<span class="alert">Krea 草稿失败</span>':'', !item.valid?'<span class="alert">坏图</span>':'', exact.has(item.relative_path)?'<span class="alert">完全重复</span>':'', near.has(item.relative_path)?'<span>近似重复</span>':'', `<span>${labels[status]}</span>`].join(''); return `<article class="dataset-card ${state.selected.has(item.relative_path)?'selected':''} ${item.valid?'':'invalid'}" data-dataset-index="${index}"><input class="dataset-card-select" type="checkbox" ${state.selected.has(item.relative_path)?'checked':''} aria-label="选择 ${escapeHtml(item.filename)}"><button class="dataset-card-preview" ${item.valid?'':'disabled'}>${item.thumbnail_url?`<img src="${escapeHtml(item.thumbnail_url)}" loading="lazy" alt="${escapeHtml(item.filename)}">`:'<span class="dataset-card-placeholder">无法预览</span>'}</button><div class="dataset-card-body"><strong>${escapeHtml(item.filename)}</strong><div class="dataset-card-meta"><span>${item.width}×${item.height}</span><span>${escapeHtml(item.format || '未知')}</span><span>${(item.bytes/1024).toFixed(0)} KiB</span></div><div class="dataset-card-flags">${flags}</div></div></article>`; }).join('') : '<div class="dataset-empty"><h2>当前筛选没有图片</h2><p>调整上方条件即可恢复显示。</p></div>'; }
  function configureFormats() { const selected=$('#datasetFormatFilter').value; const formats=[...new Set((state.report?.images || []).map(item=>item.format).filter(Boolean))].sort(); $('#datasetFormatFilter').innerHTML='<option value="all">全部格式</option>'+formats.map(value=>`<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join(''); if (formats.includes(selected)) $('#datasetFormatFilter').value=selected; }
  async function loadModels() { const select=$('#datasetKrea2Model'), previous=select.value; try { const result=await api('/api/local-models'); state.models=(result.models || []).filter(item=>item.vision); const preferred=state.models.find(item=>item.loaded && /qwen.*3\.5.*9b/i.test(item.id)) || state.models.find(item=>item.loaded) || state.models.find(item=>/qwen.*3\.5.*9b/i.test(item.id)) || state.models[0]; select.innerHTML=state.models.length?state.models.map(item=>`<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}${item.loaded?' · 已加载':''}</option>`).join(''):'<option value="">LM Studio 没有可用视觉模型</option>'; if (state.models.some(item=>item.id===previous)) select.value=previous; else if (preferred) select.value=preferred.id; } catch(error) { state.models=[]; select.innerHTML='<option value="">LM Studio 当前不可连接</option>'; $('#datasetKrea2QueueHint').textContent=`视觉草稿暂不可用：${error.message}`; } }
  async function loadReport() { if (!state.active) return; state.report=await api(`/api/dataset-workspaces/${encodeURIComponent(state.active.workspace_id)}/report`); state.selected=new Set((state.report.images || []).filter(item=>item.review?.selected).map(item=>item.relative_path)); configureFormats(); renderStats(); renderGrid(); $('#datasetScanTime').textContent=`扫描于 ${(state.report.scanned_at || '').slice(0,16).replace('T',' ')}`; await Promise.all([loadAnalytics(),loadSnapshots()]); }
  async function selectWorkspace(id) { state.page=1; state.active=state.workspaces.find(item=>item.workspace_id===id) || null; renderWorkspaces(); $('#datasetEmpty').hidden=Boolean(state.active); $('#datasetDesk').hidden=!state.active; if (!state.active) return; $('#datasetActiveName').textContent=state.active.name; $('#datasetActivePath').textContent=state.active.source_path; if (state.active.current_report) await loadReport(); else { state.report=null; renderStats(); renderGrid(); } await refreshJobs(); }
  async function loadWorkspaces(preferred='') { state.workspaces=await api('/api/dataset-workspaces'); renderWorkspaces(); const id=preferred || state.active?.workspace_id || state.workspaces[0]?.workspace_id; if (id) await selectWorkspace(id); }
  async function importWorkspace(event) { event.preventDefault(); const button=event.submitter; button.disabled=true; try { const result=await api('/api/dataset-workspaces/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_path:$('#datasetSourcePath').value.trim(),name:$('#datasetName').value.trim()})}); await loadWorkspaces(result.workspace.workspace_id); startPolling(); } catch(error) { alert(`读取失败：${error.message}`); } finally { button.disabled=false; } }
  function renderJob(job) { if (!job) { $('#datasetJobPanel').hidden=true; return; } const active=['queued','running'].includes(job.status), total=Math.max(job.progress_total,1), types={dataset_wd14:'WD14 QUEUE',dataset_krea2_vlm:'KREA 2 VLM',dataset_scan:'DATASET SCAN'}, type=types[job.job_type] || job.job_type; const action=active?`<button data-job-action="cancel" data-job-id="${job.job_id}">取消</button>`:['failed','canceled'].includes(job.status)?`<button data-job-action="retry" data-job-id="${job.job_id}">重试</button>`:''; $('#datasetJobPanel').hidden=false; $('#datasetJobPanel').innerHTML=`<div class="dataset-job-line"><span>${escapeHtml(type)} · ${escapeHtml(job.status.toUpperCase())}</span><progress value="${job.progress_current}" max="${total}"></progress>${action}</div><p class="dataset-job-message">${escapeHtml(job.progress_message || job.error || '等待处理')}</p>`; }
  async function refreshJobs() { if (!state.active) return false; const jobs=await api('/api/jobs?limit=100'), related=jobs.filter(item=>['dataset_scan','dataset_wd14','dataset_krea2_vlm'].includes(item.job_type) && item.payload?.workspace_id===state.active.workspace_id), job=related.find(item=>['queued','running'].includes(item.status)) || related[0]; renderJob(job); if (job && ['queued','running'].includes(job.status)) return true; const active=await api(`/api/dataset-workspaces/${state.active.workspace_id}`); const shouldLoad=Boolean(active.current_report) && (!state.report || active.current_report!==state.active.current_report || job?.status==='completed'); Object.assign(state.active,active); if (shouldLoad) await loadReport(); renderWorkspaces(); return false; }
  function startPolling() { clearInterval(state.poll); state.poll=setInterval(async()=>{ try { const running=await refreshJobs(); if (!running) clearInterval(state.poll); } catch(error) { console.error(error); clearInterval(state.poll); } },900); }
  async function updateReviews(items) { if (!state.active || !items.length) return; await api(`/api/dataset-workspaces/${state.active.workspace_id}/review`,jsonOptions({items})); await loadReport(); }
  function selectedPaths(scope='selected') { if (scope==='filtered') return state.visible.map(item=>item.relative_path); return [...state.selected]; }
  async function queueWd14(scope) { if (!state.active) return; const paths=scope==='selected'?selectedPaths():[]; if (scope==='selected' && !paths.length) return alert('请先选择要打标的图片。'); if (scope==='all' && !confirm('重新打标整个工作区会替换尚未人工确认的 Anima 草稿。继续吗？')) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/wd14`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope,paths,general_threshold:Number($('#datasetGeneralThreshold').value),character_threshold:Number($('#datasetCharacterThreshold').value),provider:'cpu',overwrite:scope==='all'})}); renderJob(result.job); startPolling(); }
  async function queueKrea2VLM(scope) { if (!state.active) return; const model=$('#datasetKrea2Model').value, paths=scope==='selected'?selectedPaths():[]; if (!model) return alert('请先在 LM Studio 中准备并加载一个视觉模型。'); if (scope==='selected' && !paths.length) return alert('请先选择要生成草稿的图片。'); const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/krea2-vlm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope,paths,model})}); renderJob(result.job); $('#datasetKrea2QueueHint').textContent='队列已开始。模型结果只会进入待确认草稿。'; startPolling(); }
  async function loadTagCatalog() { const payload=await api('/api/tags/catalog?language=zh'); $('#datasetTagSuggestions').innerHTML=(payload.items||[]).map(item=>`<option value="${escapeHtml(item.zh || item.en)}">${escapeHtml(item.en)}</option>`).join(''); }
  function appendBulkTag(tag) { const input=$('#datasetBulkAdd'), values=input.value.split(',').map(value=>value.trim()).filter(Boolean); if (!values.some(value=>value.toLowerCase()===tag.toLowerCase())) values.push(tag); input.value=values.join(', '); state.bulkPreview=null; $('#datasetBulkApply').disabled=true; $('#datasetBulkResult').textContent=`已选择 ${window.displayCanonicalTag?.(tag)||tag}；请先预览修改。`; }
  async function loadAnalytics() { if (!state.active) return; state.analytics=await api(`/api/dataset-workspaces/${state.active.workspace_id}/analytics`); const top=(state.analytics.frequencies || []).slice(0,18); await window.ensureTagLabels?.(top.map(item=>item.tag)); const chips=top.map(item=>`<button type="button" data-bulk-tag="${escapeHtml(item.tag)}" title="加入批量添加">${escapeHtml(window.displayCanonicalTag?.(item.tag) || item.tag)} · ${item.count}</button>`).join(''); $('#datasetAnalytics').innerHTML=`<strong>${formatNumber(state.analytics.captioned_images)} 张有 Anima caption · ${formatNumber(state.analytics.unique_tags)} 个标签 · ${formatNumber((state.analytics.conflicts||[]).length)} 个冲突提示</strong><div class="dataset-analytics-tags">${chips || '<span>暂无标签</span>'}</div>`; }
  async function loadSnapshots() { if (!state.active) return; const snapshots=await api(`/api/dataset-workspaces/${state.active.workspace_id}/snapshots`), selected=$('#datasetSnapshot').value; $('#datasetSnapshot').innerHTML='<option value="">Caption 快照</option>'+snapshots.map(item=>`<option value="${escapeHtml(item.snapshot_id)}">${escapeHtml(item.profile_id.toUpperCase())} · ${escapeHtml(item.operation)} · ${item.changed} 张 · ${escapeHtml(item.created_at.slice(0,16).replace('T',' '))}</option>`).join(''); if (snapshots.some(item=>item.snapshot_id===selected)) $('#datasetSnapshot').value=selected; }
  function sourceCaptionPayload(scope) { return {profile_id:$('#datasetSourceCaptionProfile').value,paths:scope==='selected'?selectedPaths():[],overwrite_existing:$('#datasetSourceCaptionOverwrite').checked,caption_status:$('#datasetSourceCaptionStatus').value}; }
  async function previewSourceCaptions(scope) { if(!state.active) return; if(scope==='selected'&&!state.selected.size) return alert('请先选择要接续原 Caption 的图片。'); const payload=sourceCaptionPayload(scope), result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/source-captions/preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); state.sourceCaptionPreview={payload,result}; const invalid=result.invalid?.length||0; $('#datasetSourceCaptionResult').textContent=`检查 ${result.inspected} 张：可接续 ${result.changed} 张，已有内容跳过 ${result.skipped_existing} 张，空白跳过 ${result.skipped_empty} 张，不符合英文要求 ${invalid} 张。`; $('#datasetSourceCaptionApply').disabled=!result.changed; }
  async function applySourceCaptions() { const preview=state.sourceCaptionPreview; if(!preview?.result?.changed) return; const profile=preview.payload.profile_id.toUpperCase(), status=preview.payload.caption_status==='reviewed'?'已人工审核':'待审核'; if(!confirm(`确认把 ${preview.result.changed} 份原 Caption 接入 ${profile}，状态设为“${status}”？\n系统只创建一个批次快照，不会改写原 .txt。`)) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/source-captions/apply`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(preview.payload)}); $('#datasetSourceCaptionResult').textContent=`已接续 ${result.changed} 张到 ${profile}；批次快照 ${result.snapshot}。`; state.sourceCaptionPreview=null; $('#datasetSourceCaptionApply').disabled=true; await loadReport(); }
  function bulkPayload() { return {paths:selectedPaths(),add:$('#datasetBulkAdd').value.split(',').map(value=>value.trim()).filter(Boolean),remove:$('#datasetBulkRemove').value.split(',').map(value=>value.trim()).filter(Boolean),replace:{},sort:$('#datasetBulkSort').checked}; }
  async function previewBulkTags() { if (!state.active || !state.selected.size) return alert('请先选择要整理的图片。'); state.bulkPreview=await api(`/api/dataset-workspaces/${state.active.workspace_id}/bulk-tags/preview`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bulkPayload())}); const s=state.bulkPreview.summary; $('#datasetBulkResult').textContent=`将修改 ${state.bulkPreview.changed} 张；增加 ${s.added_instances} 个、删除 ${s.removed_instances} 个标签；冲突提示 ${state.bulkPreview.conflicts.length} 个。`; $('#datasetBulkApply').disabled=!state.bulkPreview.changed; }
  async function applyBulkTags() { if (!state.bulkPreview?.changed || !confirm(`确认修改 ${state.bulkPreview.changed} 张 Caption？系统会先保存可回退快照。`)) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/bulk-tags/apply`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(bulkPayload())}); $('#datasetBulkResult').textContent=`已修改 ${result.changed} 张；快照 ${result.snapshot}。`; state.bulkPreview=null; $('#datasetBulkApply').disabled=true; await loadReport(); }
  async function exportVersion(profile) { if (!state.active || !state.selected.size) return alert('请先选择并标记保留要导出的图片。'); const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/export`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:profile,paths:selectedPaths()})}); $('#datasetExportResult').innerHTML=`已冻结 ${escapeHtml(result.version_id)} · ${result.image_count} 张 · <a href="${escapeHtml(result.download_url)}">下载 ZIP</a>`; }
  async function rollbackSnapshot() { const id=$('#datasetSnapshot').value; if (!id || !confirm(`回退 Caption 快照 ${id}？当前状态也会先保存为新的回退记录。`)) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/snapshots/${encodeURIComponent(id)}/rollback`,{method:'POST'}); $('#datasetBulkResult').textContent=`已回退 ${result.changed} 张；新快照 ${result.snapshot}。`; await loadReport(); }
  function detailItem() { return state.pageItems[state.detailIndex]; }
  async function renderDetailTags(item) { const caption=$('#datasetDetailAnima').value, tags=caption.split(',').map(value=>value.trim()).filter(Boolean), candidates=[...new Set([...(item.curation?.wd14?.general || []).map(value=>value.tag).filter(Boolean),...tags])], selected=new Set(tags); await window.ensureTagLabels?.(candidates); $('#datasetDetailTagChips').innerHTML=candidates.map(tag=>`<button class="${selected.has(tag)?'selected':''}" data-detail-tag="${escapeHtml(tag)}" aria-pressed="${selected.has(tag)}">${escapeHtml(window.displayCanonicalTag?.(tag) || tag)}</button>`).join(''); }
  function renderDetail() { const item=detailItem(); if (!item) return; const wd14=item.curation?.wd14 || {status:'untagged'}, vlm=item.curation?.krea2_vlm || {status:'empty'}, anima=item.curation?.captions?.anima || {}, krea=item.curation?.captions?.krea2 || {}, vlmTime=vlm.created_at?` · ${vlm.created_at.slice(0,16).replace('T',' ')}`:''; $('#datasetDetailImage').src=item.original_url; $('#datasetDetailName').textContent=item.relative_path; $('#datasetDetailMeta').textContent=`${item.width}×${item.height} · ${item.format} · ${(item.bytes/1024).toFixed(1)} KiB`; $('#datasetDetailStatus').value=item.review?.status || 'pending'; $('#datasetDetailCaption').value=item.caption || ''; $('#datasetDetailAnima').value=anima.current || ''; $('#datasetDetailKrea2').value=krea.current || ''; $('#datasetDetailKrea2Draft').value=vlm.draft || ''; $('#datasetDetailWD14').textContent=wd14.status==='completed'?`${wd14.model || 'WD14'} · ${wd14.provider || 'CPU'} · 草稿待人工检查`:wd14.status==='failed'?`失败：${wd14.error || '未知错误'}`:'尚未运行 WD14'; $('#datasetDetailKrea2VLM').textContent=vlm.status==='failed'?`失败：${vlm.error || '未知错误'}`:['completed','confirmed'].includes(vlm.status)?`${vlm.model || '人工保存草稿'}${vlmTime}${vlm.status==='confirmed'?' · 已确认':''}`:'尚无草稿'; $('#datasetDetailKrea2Warning').hidden=!vlm.safety_warning; $('#datasetDetailKrea2Warning').textContent=vlm.safety_warning || ''; $('#datasetDetailDraftConfirm').disabled=!vlm.draft; $('#datasetDetailNote').value=item.review?.note || ''; $('#datasetDetailHashes').textContent=`SHA-256  ${item.sha256}\npHash     ${item.phash || '—'}\nCaption   ${item.caption_path || '缺失'}\nSource    ${item.relative_path}\nAnima     ${anima.status || 'empty'}\nKrea 2    ${krea.status || 'empty'}\nVLM hash  ${vlm.source_sha256 || '—'}`; $('#datasetPrevious').disabled=state.detailIndex<=0; $('#datasetNext').disabled=state.detailIndex>=state.pageItems.length-1; $('#datasetFindSimilar').disabled=true; $('#datasetFindSimilarStatus').textContent='正在检查真实视觉索引……'; refreshSimilarStatus(item).catch(error=>$('#datasetFindSimilarStatus').textContent=error.message); renderDetailTags(item).catch(console.error); }
  async function refreshSimilarStatus(item) { const digest=item.sha256, result=await api(`/api/hybrid-search/source-status?source_sha256=${encodeURIComponent(digest)}`); if(detailItem()?.sha256!==digest) return; $('#datasetFindSimilar').disabled=!result.available; $('#datasetFindSimilarStatus').textContent=result.available?`已进入 ${result.indexes.length} 个真实索引，可以查相似图。`:'等待 5060 Ti 生成真实 CLIP / SigLIP 索引；当前不生成伪结果。'; }
  function openDetail(index) { state.detailIndex=index; renderDetail(); $('#datasetDetail').showModal(); }
  function moveDetail(offset) { const next=state.detailIndex+offset; if (next<0 || next>=state.pageItems.length) return; state.detailIndex=next; renderDetail(); }
  async function saveDetail() { const item=detailItem(); if (!item) return; const requests=[api(`/api/dataset-workspaces/${state.active.workspace_id}/review`,jsonOptions({items:[{relative_path:item.relative_path,status:$('#datasetDetailStatus').value,selected:state.selected.has(item.relative_path),note:$('#datasetDetailNote').value}]}))], anima=$('#datasetDetailAnima').value.trim(), krea=$('#datasetDetailKrea2').value.trim(); if (anima!==String(item.curation?.captions?.anima?.current || '')) requests.push(api(`/api/dataset-workspaces/${state.active.workspace_id}/caption`,jsonOptions({relative_path:item.relative_path,profile_id:'anima',caption:anima,caption_status:'reviewed'}))); if (krea!==String(item.curation?.captions?.krea2?.current || '')) requests.push(api(`/api/dataset-workspaces/${state.active.workspace_id}/caption`,jsonOptions({relative_path:item.relative_path,profile_id:'krea2',caption:krea,caption_status:'reviewed'}))); await Promise.all(requests); await loadReport(); state.detailIndex=state.pageItems.findIndex(candidate=>candidate.relative_path===item.relative_path); renderDetail(); }
  async function saveKrea2Draft(confirmDraft) { const item=detailItem(), draft=$('#datasetDetailKrea2Draft').value.trim(); if (!item) return; if (confirmDraft && !draft) return alert('确认前需要一份英文 Krea 2 草稿。'); if (confirmDraft && !confirm('确认把这份视觉模型草稿写入正式 Krea 2 caption？系统会先保存可回退快照。')) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/krea2-draft`,jsonOptions({relative_path:item.relative_path,draft,confirm:confirmDraft})); await loadReport(); state.detailIndex=state.pageItems.findIndex(candidate=>candidate.relative_path===item.relative_path); renderDetail(); if (confirmDraft) $('#datasetDetailKrea2VLM').textContent=`已确认写入 Krea 2 · ${result.snapshot}`; }
  async function rescan() { if (!state.active) return; await api(`/api/dataset-workspaces/${state.active.workspace_id}/rescan`,{method:'POST'}); await loadWorkspaces(state.active.workspace_id); startPolling(); }
  async function removeWorkspace() { if (!state.active || !confirm(`只移除 Prompt Hub 中的“${state.active.name}”记录和派生缩略图。原文件夹不会删除。继续吗？`)) return; const source=state.active.source_path; await api(`/api/dataset-workspaces/${state.active.workspace_id}`,{method:'DELETE'}); state.active=null; state.report=null; await loadWorkspaces(); alert(`工作区记录已移除。源目录保持不变：\n${source}`); }
  async function ensureWorkspace() { await Promise.all([loadModels(),loadTagCatalog(),loadWorkspaces()]); if (state.active) { const running=await refreshJobs(); if (running) startPolling(); } }
  $('#datasetImportForm').addEventListener('submit',importWorkspace);
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
