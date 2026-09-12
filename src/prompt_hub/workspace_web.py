# ruff: noqa: E501, RUF001

WORKSPACE_HTML = r"""
<section class="dataset-page" id="workspacePage" hidden>
  <header class="dataset-heading">
    <div><span class="eyebrow">只在 Mac 上整理</span><h1>数据集工作台</h1></div>
    <div class="dataset-heading-copy"><p>从本地图片文件夹开始，按五步完成检查、标签、人工审核和交付。源图片与原始说明文字始终只读。</p><div class="dataset-mode-switch" aria-label="数据集页面显示模式"><button id="datasetModeSimple" type="button" aria-pressed="true">简单模式</button><button id="datasetModeAdvanced" type="button" aria-pressed="false">高级检查</button></div></div>
  </header>
  <div class="dataset-layout">
    <aside class="dataset-sidebar">
      <section class="dataset-continue" id="datasetContinue" hidden>
        <span>继续上次整理</span>
        <strong id="datasetContinueName">—</strong>
        <p id="datasetContinueStatus">正在读取工作区状态</p>
        <button class="dataset-primary" id="datasetContinueButton" type="button">继续整理</button>
      </section>
      <form id="datasetImportForm">
        <span class="dataset-step-kicker" id="datasetImportKicker">01 · 导入素材</span>
        <label>数据集文件夹路径
          <button class="dataset-pick-folder" id="datasetPickFolder" type="button">选择文件夹…</button>
          <span class="dataset-picked-path" id="datasetPickedPath">尚未选择文件夹</span>
        </label>
        <details class="dataset-manual-path">
          <summary>手动输入路径（外接卷或深层目录）</summary>
          <input id="datasetSourcePath" placeholder="/Users/your-name/Pictures/my-dataset">
        </details>
        <label class="dataset-zip-row">或上传 zip 数据包
          <button class="dataset-pick-folder" id="datasetPickZip" type="button">选择 zip 文件…</button>
          <input id="datasetZipFile" type="file" accept=".zip,application/zip" hidden>
          <span class="dataset-picked-path" id="datasetPickedZip">尚未选择 zip</span>
          <button class="dataset-primary" id="datasetZipUpload" type="button" disabled>上传并导入 zip</button>
        </label>
        <label>显示名称（可选）<input id="datasetName" maxlength="160" placeholder="角色名 / 项目名"></label>
        <button class="dataset-primary" id="datasetImportSubmit" type="submit">读取文件夹并开始检查</button>
        <div class="dataset-import-progress" id="datasetImportProgress" hidden>
          <strong id="datasetImportProgressTitle">正在导入 zip</strong>
          <progress id="datasetImportProgressBar" value="0" max="1"></progress>
          <span id="datasetImportProgressMessage">等待开始</span>
          <div class="dataset-action-row"><button id="datasetZipCancel" type="button">取消</button></div>
        </div>
        <div class="dataset-manifest-note" id="datasetManifestNote" hidden></div>
        <p class="dataset-hint">只读取并建立 Mac 工作区，不会移动、改名或覆盖文件夹中的任何内容；上传的 zip 只解压到 Prompt Hub 自己的目录。</p>
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
          <div class="dataset-curation-block dataset-caption-rules" id="datasetCaptionRules">
            <strong>说明文字设置</strong>
            <p class="dataset-hint">下面两种自动生成方式共用这些设置。读取已有 `.txt` 不受影响。</p>
            <div class="dataset-thresholds">
              <label>训练内容<select id="datasetCaptionMode"></select></label>
              <label id="datasetCaptionTriggerWrap" hidden><span id="datasetCaptionTriggerLabel">触发词</span><input id="datasetCaptionTrigger" maxlength="80" placeholder="例如 miru"></label>
              <label>说明长度<input id="datasetCaptionMaxTokens" type="number" min="40" max="2000" step="10"></label>
            </div>
            <p id="datasetCaptionModeHint" class="dataset-hint"></p>
            <label class="dataset-inline-check"><input id="datasetCaptionMediaTags" type="checkbox"> 保留图片真实媒材（摄影、插画、3D 等）</label>
            <details id="datasetCaptionOptions">
              <summary>可选内容</summary>
              <div class="dataset-caption-options" id="datasetCaptionOptionList"></div>
            </details>
            <div class="dataset-caption-presets">
              <label>已保存的设置<select id="datasetCaptionPreset"><option value="">不套用</option></select></label>
              <label>另存为<input id="datasetCaptionPresetName" maxlength="40" placeholder="例如 肖像-miru"></label>
              <div class="dataset-action-row"><button id="datasetCaptionPresetSave" type="button">保存当前设置</button><button id="datasetCaptionPresetDelete" type="button">删除所选</button></div>
              <p id="datasetCaptionPresetHint" class="dataset-hint">设置只存在这台机器的浏览器里，不会写进工作区。</p>
            </div>
          </div>
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
              <div class="dataset-thresholds"><label>打标模型<select id="datasetTaggerMode"><option value="wd14">WD14 本地模型</option><option value="model">使用模型</option></select></label><label id="datasetTaggerModelWrap" hidden>用于打标的模型<select id="datasetTaggerModel"><option value="">正在读取视觉模型……</option></select></label></div>
              <p id="datasetTaggerHint" class="dataset-hint">默认使用 WD14；也可以改用已连接的视觉模型生成 Booru 标签草稿。</p>
              <div class="dataset-thresholds" id="datasetWd14Thresholds"><label>图片类型<select id="datasetLocalTaggerModel"><option value="">正在读取本地打标模型……</option></select></label><p class="dataset-hint" id="datasetWd14Calibration">正在读取打标模型设置……</p></div>
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
            <button data-bulk-status="approved">审核通过并保留</button><button data-bulk-status="needs_review">标记待复查</button><button data-bulk-status="excluded">排除所选</button><button id="datasetBulkKrea2Confirm" type="button">写入 Krea 2</button><button id="datasetClearSelection">清空选择</button>
            <span id="datasetBulkKrea2Result" class="dataset-hint"></span>
          </div>
          <div class="dataset-bulkbar" id="datasetReviewToolsBar">
            <label for="datasetTriggerWord">触发词</label>
            <input id="datasetTriggerWord" class="dataset-trigger-input" type="text" maxlength="120" placeholder="例如 soda_char" aria-label="要插入到最前面的触发词">
            <button id="datasetInsertTrigger" type="button">插入触发词</button>
            <button id="datasetConfirmCaptions" type="button">标记说明已确认</button><button id="datasetBulkTranslate" type="button">批次翻译</button>
            <span id="datasetReviewToolsResult" class="dataset-hint"></span>
          </div>
          <p class="dataset-write-note" id="datasetReviewToolsNote">触发词会插到所选图片当前格式说明的最前面，已确认的说明保持确认状态；「标记说明已确认」只改判断不改文字；批次翻译只生成中文对照，交付的始终是英文原文。</p>
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
          <section class="dataset-delivery-history"><div class="dataset-delivery-history-head"><div><span class="section-label">以前生成的版本</span><h4>交付历史</h4></div><p><span>每次生成都会保留独立版本。可以下载 ZIP、在 Finder 中打开，或复制到已经挂载的设备：</span> <span data-remote-device-name>__PROMPT_HUB_DEVICE_NAME_HTML__</span>。</p></div><div id="datasetDeliveryHistory" class="dataset-delivery-list"><p class="dataset-hint">还没有交付版本。</p></div><p id="datasetCopyResult" class="dataset-hint"></p></section>
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
      <div class="dataset-caption-profile"><strong>中文对照（只读）</strong><span id="datasetDetailKrea2LocaleStatus">保存或确认前可先对照</span></div>
      <textarea id="datasetDetailKrea2Locale" readonly aria-label="Krea 2 草稿中文对照" placeholder="点“翻译成中文对照”查看这段草稿的中文意思"></textarea>
      <div class="dataset-action-row"><button id="datasetDetailKrea2Translate">翻译成中文对照</button></div>
      <label>修正意见<textarea id="datasetDetailKrea2Revision" maxlength="4000" placeholder="可以直接贴改写后的整段中文。也可以只写一句要求。例如：加入对肤色的描述"></textarea></label>
      <div class="dataset-action-row"><button id="datasetDetailKrea2Revise">按修正意见改写草稿</button><span id="datasetDetailKrea2ReviseStatus" class="dataset-hint">改写结果会放回英文草稿框，保存前仍可继续修改。</span></div>
      <p id="datasetDetailKrea2Warning" class="dataset-vlm-warning" hidden></p>
      <div class="dataset-action-row"><button id="datasetDetailDraftSave">只保存草稿</button><button class="dataset-primary" id="datasetDetailDraftConfirm">确认写入 Krea 2</button></div>
      <p class="dataset-hint">确认时系统会保存一份可回退的修改记录；Anima 与 WD14 不会改变。</p>
      <div class="dataset-similar-panel"><button id="datasetFindSimilar" disabled>以此图查相似</button><span id="datasetFindSimilarStatus">正在检查真实视觉索引……</span></div>
      <div class="dataset-action-row"><button class="dataset-primary" id="datasetDetailApprove">审核通过并看下一张</button><button id="datasetDetailSave">只保存不改状态</button></div>
      <details><summary>文件指纹与来源</summary><pre id="datasetDetailHashes"></pre></details>
    </div>
  </dialog>
  <dialog id="datasetBrowseDialog" class="dataset-dialog dataset-browse-dialog">
    <button class="dataset-dialog-close" id="datasetBrowseClose" aria-label="关闭">×</button>
    <div class="dataset-browse-body">
      <span class="section-label">选择数据集文件夹</span>
      <h2>浏览这台 Mac</h2>
      <p class="dataset-hint">范围仅限于个人主目录和已挂载的外接卷；已导入和不可选择的文件夹会直接标注，浏览不会写回任何内容。</p>
      <div class="dataset-browse-quick" id="datasetBrowseQuick"></div>
      <nav class="dataset-browse-crumbs" id="datasetBrowseCrumbs"></nav>
      <div class="dataset-browse-rows" id="datasetBrowseRows"></div>
      <p class="dataset-hint" id="datasetBrowseNote"></p>
      <div class="dataset-action-row"><button class="dataset-primary" id="datasetBrowsePickCurrent" type="button" hidden>选择当前文件夹</button></div>
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
  .dataset-continue { display: grid; gap: 8px; margin-bottom: 18px; padding: 14px; border: 1px solid var(--ink); background: var(--acid); box-shadow: 5px 5px 0 rgba(31,29,25,.16); }
  .dataset-continue[hidden] { display: none; }
  .dataset-continue > span { color: #55564f; font: 900 8px/1 monospace; letter-spacing: .08em; }
  .dataset-continue > strong { overflow: hidden; font: 700 21px/1.1 "Iowan Old Style", serif; text-overflow: ellipsis; white-space: nowrap; }
  .dataset-continue > p { margin: 0; color: #55564f; font: 9px/1.45 monospace; }
  .dataset-continue .dataset-primary { background: var(--ink); border-color: var(--ink); color: var(--paper); text-align: center; }
  .dataset-sidebar form { display: grid; gap: 10px; padding-bottom: 18px; border-bottom: 1px solid var(--line); }
  .dataset-step-kicker { color: var(--signal); font: 900 9px/1 monospace; letter-spacing: .08em; }
  .dataset-sidebar label, .dataset-toolbar label, .dataset-dialog-body label { display: grid; gap: 6px; color: var(--muted); font: 800 9px monospace; text-transform: uppercase; letter-spacing: .06em; }
  .dataset-sidebar input, .dataset-toolbar select, .dataset-curation-block select, .dataset-curation-block input, .dataset-dialog-body select, .dataset-dialog-body textarea { width: 100%; border: 1px solid var(--line); background: #f7f1e5; color: var(--ink); padding: 9px; font: 11px/1.45 monospace; }
  .dataset-primary { border: 1px solid var(--signal); background: var(--signal); color: white; padding: 10px 12px; text-align: left; font: 800 9px monospace; text-transform: uppercase; }
  .dataset-hint { margin: 0; color: var(--muted); font-size: 10px; line-height: 1.5; }
  .dataset-pick-folder { width: 100%; border: 1px solid var(--ink); background: #f7f1e5; color: var(--ink); padding: 10px 12px; text-align: left; font: 800 9px/1 monospace; text-transform: uppercase; letter-spacing: .06em; }
  .dataset-picked-path { display: block; min-height: 14px; overflow-wrap: anywhere; color: var(--signal); font: 8px/1.4 monospace; text-transform: none; letter-spacing: 0; }
  .dataset-manual-path { color: var(--muted); font: 9px/1.45 monospace; text-transform: uppercase; }
  .dataset-manual-path summary { cursor: pointer; color: var(--muted); font: 800 8px monospace; }
  .dataset-manual-path input { margin-top: 7px; }
  .dataset-zip-row .dataset-pick-folder, .dataset-zip-row .dataset-primary { width: auto; }
  .dataset-import-progress { display: grid; gap: 7px; padding: 11px; border: 1px solid var(--ink); background: #171714; color: #f4eddf; }
  .dataset-import-progress[hidden], .dataset-manifest-note[hidden] { display: none; }
  .dataset-import-progress strong { font: 800 9px/1 monospace; }
  .dataset-import-progress progress { width: 100%; accent-color: var(--acid); }
  .dataset-import-progress span { font: 8px/1.5 monospace; }
  .dataset-import-progress button { border: 1px solid rgba(244,237,223,.5); background: transparent; color: #f4eddf; padding: 7px 9px; font: 800 8px monospace; }
  .dataset-manifest-note { display: grid; gap: 7px; padding: 11px; border-left: 4px solid var(--acid); background: #e4ddce; }
  .dataset-manifest-note strong { font: 800 9px monospace; }
  .dataset-manifest-note span { color: var(--muted); font: 9px/1.5 monospace; }
  .dataset-manifest-note button { width: fit-content; border: 1px solid var(--ink); padding: 7px 9px; font: 800 8px monospace; }
  .dataset-browse-dialog { width: min(760px, calc(100% - 28px)); max-height: calc(100vh - 28px); }
  .dataset-browse-dialog[open] { display: block; }
  .dataset-browse-body { overflow: auto; max-height: calc(100vh - 28px); padding: 26px; }
  .dataset-browse-body h2 { margin: 5px 0 7px; font: 700 26px "Iowan Old Style", serif; }
  .dataset-browse-quick { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
  .dataset-browse-quick button { border: 1px solid var(--ink); padding: 7px 9px; background: transparent; color: var(--ink); font: 800 8px monospace; }
  .dataset-browse-quick button:disabled { opacity: .35; }
  .dataset-browse-crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-top: 13px; color: var(--muted); font: 8px monospace; }
  .dataset-browse-crumbs button { border: 0; padding: 0; background: transparent; color: var(--signal); text-decoration: underline; font: 8px monospace; }
  .dataset-browse-crumbs .current { color: var(--ink); font-weight: 800; }
  .dataset-browse-rows { display: grid; gap: 6px; margin-top: 10px; }
  .dataset-browse-row { display: grid; grid-template-columns: minmax(0,1fr) auto; border: 1px solid var(--line); background: #f7f1e5; }
  .dataset-browse-nav { display: grid; gap: 3px; min-width: 0; padding: 9px 11px; border: 0; background: transparent; text-align: left; cursor: pointer; }
  .dataset-browse-nav.static { cursor: default; }
  .dataset-browse-nav strong { overflow: hidden; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
  .dataset-browse-nav span { color: var(--muted); font: 8px monospace; }
  .dataset-browse-nav em { color: #8a3328; font: 8px/1.4 monospace; }
  .dataset-browse-row.blocked { background: #e5ded2; }
  .dataset-browse-row.blocked .dataset-browse-nav { color: #8f8e84; }
  .dataset-browse-pick { border: 0; border-left: 1px solid var(--line); background: var(--acid); padding: 0 14px; font: 900 9px monospace; }
  .dataset-browse-pick:disabled { background: transparent; color: #b9b3a6; }
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
  .dataset-journey button.current span { color: var(--acid); }
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
  .dataset-trigger-input { width: 180px; border: 1px solid var(--ink); padding: 7px 8px; font: 9px monospace; background: var(--paper); color: var(--ink); }
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
  #datasetWd14Thresholds { grid-template-columns: minmax(0,1fr); }
  .dataset-action-row, .dataset-snapshot-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
  .dataset-action-row button, .dataset-snapshot-row button { border: 1px solid var(--ink); padding: 7px; font: 800 7px monospace; }
  .dataset-action-row button:disabled { opacity: .35; }
  .dataset-inline-check { display: flex !important; align-items: center; grid-template-columns: auto 1fr; }
  .dataset-caption-rules { border-right: 0; border-bottom: 1px solid var(--line); }
  .dataset-caption-rules .dataset-thresholds { grid-template-columns: repeat(3, 1fr); }
  .dataset-caption-options { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 6px 14px; padding-top: 8px; }
  .dataset-caption-rules .dataset-inline-check { gap: 9px; cursor: pointer; }
  .dataset-caption-rules input[type="checkbox"] {
    appearance: none; -webkit-appearance: none; margin: 0;
    width: 34px !important; height: 19px; flex: 0 0 34px;
    border: 1px solid var(--line); border-radius: 999px;
    background: var(--paper-deep); position: relative; cursor: pointer;
    transition: background .15s ease, border-color .15s ease;
  }
  .dataset-caption-rules input[type="checkbox"]::after {
    content: ""; position: absolute; top: 2px; left: 2px;
    width: 13px; height: 13px; border-radius: 50%; background: #fff;
    box-shadow: 0 1px 2px rgba(23, 24, 21, .3);
    transition: transform .15s ease;
  }
  .dataset-caption-rules input[type="checkbox"]:checked { background: var(--signal); border-color: var(--signal); }
  .dataset-caption-rules input[type="checkbox"]:checked::after { transform: translateX(15px); }
  .dataset-caption-rules input[type="checkbox"]:focus-visible { outline: 2px solid var(--signal); outline-offset: 2px; }
  .dataset-source-gone { color: var(--signal); font-weight: 600; }
  .dataset-caption-presets { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; padding-top: 10px; border-top: 1px solid var(--line); margin-top: 10px; }
  .dataset-caption-presets .dataset-action-row, .dataset-caption-presets .dataset-hint { grid-column: 1 / -1; }
  #datasetDetailKrea2Locale { min-height: 68px; }
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
  const deviceName = () => window.getPromptHubDeviceName?.() || 'Windows 绘图设备';
  const state = {captionContract: null, captionOptions: {}, captionLocales: {}, taggerConfig: null, workspaces: [], active: null, report: null, analytics: null, models: [], exports: [], preflight: null, visible: [], pageItems: [], page: 1, pageSize: 24, selected: new Set(), detailIndex: -1, poll: null, bulkPreview: null, sourceCaptionPreview: null, mode: 'simple', step: 0, browse: null, zipFile: null, importJob: null};
  const compactDatasetView = window.matchMedia('(max-width: 700px)');
  const labels = {pending:'未审核', approved:'保留', needs_review:'待复查', excluded:'排除'};
  const workspaceStatusLabels = {registered:'等待扫描', scanning:'正在扫描', ready:'可使用', failed:'扫描失败', queued:'等待扫描', canceled:'已取消'};
  const stepNames = {1:'导入素材',2:'检查问题',3:'准备标签',4:'人工审核',5:'生成交付版本'};
  async function api(url, options={}) { const response = await fetch(url, options); const data = await response.json().catch(() => ({})); if (!response.ok) throw new Error(data.detail || `请求失败：${response.status}`); return data; }
  const jsonOptions = body => ({method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  // 完全重复是一组 files。近似重复是两边比出来的 left_files / right_files。
  // 当成同一种形状读的话。只要扫到一组近似重复。整个数据集页面就会在渲染时炸掉。
  function duplicateFiles(group) { return Array.isArray(group?.files) ? group.files : [...(group?.left_files || []), ...(group?.right_files || [])]; }
  function duplicateSets() { const exact = new Set(), near = new Set(); (state.report?.exact_duplicates || []).forEach(group => duplicateFiles(group).forEach(path => exact.add(path))); (state.report?.near_duplicates || []).forEach(group => duplicateFiles(group).forEach(path => near.add(path))); return {exact, near}; }
  function renderWorkspaces() { const latest=state.active || state.workspaces[0] || null, hasWorkspaces=Boolean(latest), status=latest?`${workspaceStatusLabels[latest.status] || '状态待确认'} · ${formatNumber(latest.summary?.image_count || 0)} 张图片`:''; $('#datasetWorkspaceCount').textContent = state.workspaces.length; $('#datasetWorkspaceList').innerHTML = state.workspaces.length ? state.workspaces.map(item => `<button class="dataset-workspace-item ${state.active?.workspace_id === item.workspace_id ? 'active' : ''}" data-workspace-id="${escapeHtml(item.workspace_id)}"><strong>${escapeHtml(item.name)}${item.source_origin==='zip_archive'?' · zip 导入':''}</strong><span>${escapeHtml(workspaceStatusLabels[item.status] || '状态待确认')} · ${formatNumber(item.summary?.image_count || 0)} 张</span><span>${escapeHtml(item.source_path)}</span>${item.source_available===false?'<span class="dataset-source-gone">来源目录已经不在</span>':''}</button>`).join('') : '<p class="dataset-hint">还没有读取过数据集。</p>'; $('#datasetContinue').hidden=!hasWorkspaces; $('#datasetContinueName').textContent=latest?.name || '—'; $('#datasetContinueStatus').textContent=status; $('#datasetImportKicker').textContent=hasWorkspaces?'导入另一个文件夹':'01 · 导入素材'; $('#datasetImportSubmit').textContent=hasWorkspaces?'读取新的文件夹':'读取文件夹并开始检查'; }
  function renderDatasetOrigin() { const origin=state.active?.origin||{}, container=$('#datasetOrigin'); if(origin.kind!=='creative_project'||!origin.project_id) { container.innerHTML='<span class="independent">外部独立数据集 · 不要求绑定创作项目</span>'; return; } const assets=Array.isArray(origin.result_asset_ids)?origin.result_asset_ids:[]; container.innerHTML=`<span>来源：${escapeHtml(origin.project_title||'创作项目')} · V${Number(origin.project_iteration)||1} · ${assets.length} 张结果图</span><button type="button" data-origin-project="${escapeHtml(origin.project_id)}">返回来源项目</button>${assets.slice(0,3).map((id,index)=>`<a href="/result-media/${encodeURIComponent(origin.project_id)}/original/${encodeURIComponent(id)}" target="_blank" rel="noreferrer">来源图 ${index+1}</a>`).join('')}`; }
  function stat(value, label) { return `<div class="dataset-stat"><strong>${formatNumber(value)}</strong><span>${label}</span></div>`; }
  function formatDatasetBytes(value) { const bytes=Number(value)||0; if(bytes>=1073741824) return `${(bytes/1073741824).toFixed(1)} GiB`; if(bytes>=1048576) return `${(bytes/1048576).toFixed(1)} MiB`; if(bytes>=1024) return `${(bytes/1024).toFixed(1)} KiB`; return `${bytes} B`; }
  function deliverySelectionKey(profile=$('#datasetDeliveryProfile').value || 'anima') { return `${profile}|${[...state.selected].sort().join('|')}`; }
  function renderPreflight() { const panel=$('#datasetPreflight'), current=state.preflight?._selectionKey===deliverySelectionKey()?state.preflight:null, profileName=($('#datasetDeliveryProfile').value||'anima')==='anima'?'Anima':'Krea 2'; panel.classList.toggle('ready',Boolean(current?.ready)); panel.classList.toggle('blocked',Boolean(current&&!current.ready)); if(!state.selected.size) { $('#datasetPreflightBadge').textContent='等待选择'; $('#datasetPreflightSummary').textContent='先在第 4 步选择要交付的图片，并将图片审核为保留。'; $('#datasetPreflightIssues').innerHTML=''; return; } if(!current) { $('#datasetPreflightBadge').textContent='等待检查'; $('#datasetPreflightSummary').textContent=`将检查 ${state.selected.size} 张图片的 ${profileName} 交付条件。`; $('#datasetPreflightIssues').innerHTML=''; return; } $('#datasetPreflightBadge').textContent=current.ready?'可以生成':`${current.blockers.length} 类问题`; $('#datasetPreflightSummary').textContent=current.ready?`${current.selected_count} 张图片已通过交付前检查。`:`${current.selected_count} 张图片还不能生成交付版本，请按下面提示处理。`; $('#datasetPreflightIssues').innerHTML=[...(current.blockers||[]).map(item=>`<li>${escapeHtml(item.label)} · ${item.count||0} 项</li>`),...(current.warnings||[]).map(item=>`<li class="warning">提醒：${escapeHtml(item.label)} · ${item.count||0} 项</li>`)].join(''); }
  function renderExports() { const profile=$('#datasetDeliveryProfile').value||'anima', items=state.exports.filter(item=>item.profile_id===profile), profileName=profile==='anima'?'Anima':'Krea 2',target=deviceName(); $('#datasetDeliveryHistory').innerHTML=items.length?items.map(item=>{ const copy=(item.copies||[]).find(entry=>entry.node_id==='compute_5060ti'), copyText=!copy?`尚未复制到 ${target}`:copy.status==='completed'?`已复制到 ${target}`:copy.status==='already_present'?`${target} 已有此版本`:`复制失败：${copy.error||'共享目录不可用'}`, when=String(item.created_at||'').slice(0,16).replace('T',' '), origin=item.origin||{}, sourceLinks=origin.project_id?`<button data-origin-project="${escapeHtml(origin.project_id)}">来源项目</button>${(item.source_result_asset_ids||[]).slice(0,2).map((id,index)=>`<a href="/result-media/${encodeURIComponent(origin.project_id)}/original/${encodeURIComponent(id)}" target="_blank" rel="noreferrer">来源图 ${index+1}</a>`).join('')}`:''; return `<article class="dataset-delivery-card" data-export-version="${escapeHtml(item.version_id)}"><div><h5>${escapeHtml(item.version_id)}</h5><div class="dataset-delivery-meta">${profileName} · ${formatNumber(item.image_count||0)} 张图片 · ${formatNumber(item.file_count||0)} 个文件 · ${formatDatasetBytes(item.total_bytes)} · ${escapeHtml(when)}</div><div class="dataset-delivery-copy">${escapeHtml(copyText)}</div></div><div class="dataset-delivery-actions">${sourceLinks}<a href="${escapeHtml(item.download_url)}">下载 ZIP</a><button data-export-action="reveal" ${item.directory_available?'':'disabled'}>打开 Finder</button><button class="primary" data-export-action="copy" ${item.directory_available?'':'disabled'}>复制到 ${escapeHtml(target)}</button></div></article>`; }).join(''):`<p class="dataset-hint">还没有 ${profileName} 交付版本。Anima 与 Krea 2 的历史会分开显示。</p>`; }
  function deliveryState() { const images=state.report?.images || [], profile=$('#datasetDeliveryProfile').value || 'anima', exact=new Set(); (state.report?.exact_duplicates || []).forEach(group=>duplicateFiles(group).forEach(path=>exact.add(path))); const statusOf=item=>item.review?.status || 'pending', captionOf=item=>item.curation?.captions?.[profile] || {}, active=images.filter(item=>item.valid && statusOf(item)!=='excluded'), selected=images.filter(item=>state.selected.has(item.relative_path)), exactBlockingGroups=(state.report?.exact_duplicates || []).filter(group=>duplicateFiles(group).filter(path=>{ const item=images.find(candidate=>candidate.relative_path===path); return item && item.valid && statusOf(item)!=='excluded'; }).length>1), invalidOpen=images.filter(item=>!item.valid && statusOf(item)!=='excluded'), missing=active.filter(item=>!String(captionOf(item).current || '').trim()), captionDraft=active.filter(item=>String(captionOf(item).current || '').trim() && captionOf(item).status!=='reviewed'), pending=active.filter(item=>statusOf(item)==='pending'), needsReview=active.filter(item=>statusOf(item)==='needs_review'), approved=images.filter(item=>item.valid && statusOf(item)==='approved'), excluded=images.filter(item=>statusOf(item)==='excluded'), reviewed=images.filter(item=>statusOf(item)!=='pending'), deliverable=selected.filter(item=>item.valid && statusOf(item)==='approved' && String(captionOf(item).current || '').trim() && captionOf(item).status==='reviewed'), selectedBlocked=selected.filter(item=>!deliverable.includes(item)); let recommended=1; if(state.report) { if(invalidOpen.length || exactBlockingGroups.length) recommended=2; else if(missing.length) recommended=3; else if(captionDraft.length || pending.length || needsReview.length || !approved.length || !selected.length) recommended=4; else recommended=5; } return {profile,images,active,selected,exact,invalidOpen,exactBlockingGroups,missing,captionDraft,pending,needsReview,approved,excluded,deliverable,selectedBlocked,recommended,reviewed:reviewed.length,nearGroups:state.report?.near_duplicates?.length || 0}; }
  function renderStats() { const d=deliveryState(), duplicates=new Set([...d.exact]); (state.report?.near_duplicates || []).forEach(group=>duplicateFiles(group).forEach(path=>duplicates.add(path))); $('#datasetStats').innerHTML=stat(d.active.length,'有效候选')+stat(d.invalidOpen.length,'坏图待处理')+stat(duplicates.size,'重复提示')+stat(d.missing.length,`缺少 ${d.profile==='anima'?'Anima':'Krea 2'} 图片说明`)+stat(d.pending.length,'待审核')+stat(d.reviewed,'已审核')+stat(d.excluded.length,'已排除')+stat(d.deliverable.length,'当前可交付'); }
  function renderStagePanels(step) { const advanced=state.mode==='advanced', profile=$('#datasetDeliveryProfile').value || 'anima'; $('#workspacePage').dataset.datasetMode=state.mode; $('#datasetModeSimple').setAttribute('aria-pressed',String(!advanced)); $('#datasetModeAdvanced').setAttribute('aria-pressed',String(advanced)); document.querySelectorAll('[data-dataset-stage-panel]').forEach(panel=>{ const stages=panel.dataset.datasetStagePanel.split(','); panel.hidden=!advanced && !stages.includes(String(step)); }); document.querySelectorAll('[data-caption-profile]').forEach(block=>{ block.hidden=!advanced&&block.dataset.captionProfile!==profile; }); $('#datasetCurationTitle').textContent=profile==='anima'?'准备 Anima 英文标签':'准备 Krea 2 英文自然语言说明'; $('#datasetCurationHint').textContent=profile==='anima'?'优先接续已有 `.txt`；缺少标签时再运行 WD14。所有结果先进入 Prompt Hub，不写回原文件夹。':'优先接续已有英文自然语言 `.txt`；没有时再用视觉模型生成草稿，并在逐图审核后确认。'; const jobPanel=$('#datasetJobPanel'); if(jobPanel.dataset.jobState==='completed') jobPanel.hidden=!advanced; const review=step===4; $('#datasetAssetStepLabel').textContent=review?'04 · 人工审核':'02 · 检查问题'; $('#datasetAssetStepTitle').textContent=review?'逐张确认图片与说明文字':'检查坏图、重复和缺失项'; $('#datasetAssetStepHint').textContent=review?'先筛选未审核图片，打开缩略图检查说明文字；批量操作只适合已经确认过的同类图片。':'先处理会阻止交付的问题；近似重复只提醒，不会自动删除。'; $('#datasetReviewWriteNote').textContent=review?'“审核通过并保留”会写入 Prompt Hub 审核记录并保留选择，方便第 5 步交付；不会改动源图片。':'排除操作只写入 Prompt Hub 审核记录，不会移动或删除源图片。'; const krea2Button=$('#datasetBulkKrea2Confirm'), krea2Ready=krea2DraftSelection().length; krea2Button.hidden=!(review||advanced); krea2Button.disabled=!krea2Ready; krea2Button.textContent=krea2Ready?`写入 Krea 2（${krea2Ready} 张）`:'写入 Krea 2'; krea2Button.title=krea2Ready?'把所选图片里已有的 Krea 2 视觉草稿一次写入正式说明':'所选图片里没有 Krea 2 草稿'; $('#datasetBulkKrea2Result').hidden=krea2Button.hidden; $('#datasetReviewToolsBar').hidden=krea2Button.hidden; $('#datasetReviewToolsNote').hidden=krea2Button.hidden; $('#datasetInsertTrigger').textContent=profile==='anima'?'插入触发词到 Anima':'插入触发词到 Krea 2'; $('#datasetConfirmCaptions').textContent=profile==='anima'?'标记 Anima 说明已确认':'标记 Krea 2 说明已确认'; }
  function renderJourney() { const d=deliveryState(), step=state.step || d.recommended, profileName=d.profile==='anima'?'Anima':'Krea 2', scanClear=Boolean(state.report)&&!d.invalidOpen.length&&!d.exactBlockingGroups.length, captionsReady=Boolean(state.report)&&d.active.length>0&&!d.missing.length, reviewReady=captionsReady&&!d.captionDraft.length&&!d.pending.length&&!d.needsReview.length&&d.approved.length>0&&d.deliverable.length>0, statuses={1:Boolean(state.report),2:scanClear,3:captionsReady,4:reviewReady,5:state.exports.some(item=>item.profile_id===d.profile)}; document.querySelectorAll('[data-dataset-step]').forEach(button=>{ const value=Number(button.dataset.datasetStep); button.classList.toggle('current',value===step); button.classList.toggle('complete',Boolean(statuses[value])); button.classList.toggle('blocked',value===d.recommended&&value>1&&!statuses[value]); button.setAttribute('aria-current',value===step?'step':'false'); }); const copy={1:{title:'先读取一个本地图片文件夹',message:'Prompt Hub 会建立只读工作区，并自动扫描图片、同名 .txt、坏图与重复。',action:'回到左侧填写文件夹路径'},2:{title:scanClear?'文件检查已经通过':'先处理会阻止交付的问题',message:scanClear?'没有发现未处理的坏图或完全重复，可以继续准备标签。':`还有 ${d.invalidOpen.length} 张坏图、${d.exactBlockingGroups.length} 组完全重复需要明确排除。`,action:scanClear?'继续准备标签':'查看问题图片'},3:{title:captionsReady?`${profileName} 图片说明已经齐全`:`还缺 ${d.missing.length} 份 ${profileName} 图片说明`,message:captionsReady?(d.captionDraft.length?`图片说明已齐，但其中 ${d.captionDraft.length} 份仍是草稿，请在人工审核时确认。`:'不需要重复生成标签，可以直接进入人工审核。'):'可以使用已有 .txt，或用对应工具生成缺少的草稿。',action:captionsReady?'进入人工审核':'打开标签准备工具'},4:{title:reviewReady?'图片和说明文字已满足交付要求':'需要人工决定哪些图片保留',message:reviewReady?`已选择 ${d.deliverable.length} 张可交付图片。生成版本前仍可逐张复查。`:`${d.pending.length} 张未审核，${d.needsReview.length} 张待复查，${d.captionDraft.length} 份图片说明尚未确认；当前选择 ${d.selected.length} 张。`,action:reviewReady?'检查交付内容':'查看待审核图片'},5:{title:d.deliverable.length?'可以生成当前数据集版本':'还没有可交付的图片',message:d.deliverable.length?`${d.deliverable.length} 张图片将按 ${profileName} 格式建立独立副本。`:'返回人工审核：选择图片、标记保留，并确认当前格式的图片说明。',action:d.deliverable.length?'生成并保存副本':'返回人工审核'}}[step]; $('#datasetCurrentStepLabel').textContent=`第 ${step} 步 · ${stepNames[step]}`; $('#datasetReadinessTitle').textContent=copy.title; $('#datasetReadinessMessage').textContent=copy.message; $('#datasetNextAction').textContent=copy.action; const blockers=[]; if(d.invalidOpen.length) blockers.push(`${d.invalidOpen.length} 张坏图尚未排除`); if(d.exactBlockingGroups.length) blockers.push(`${d.exactBlockingGroups.length} 组完全重复尚未处理`); if(d.missing.length) blockers.push(`${d.missing.length} 份 ${profileName} 图片说明缺失`); if(d.captionDraft.length) blockers.push(`${d.captionDraft.length} 份 ${profileName} 图片说明仍是草稿`); if(d.pending.length) blockers.push(`${d.pending.length} 张图片尚未审核`); if(d.needsReview.length) blockers.push(`${d.needsReview.length} 张图片标记为待复查`); if(d.selectedBlocked.length) blockers.push(`已选图片中有 ${d.selectedBlocked.length} 张暂时不能交付`); $('#datasetBlockingList').innerHTML=blockers.slice(0,4).map(item=>`<li>${escapeHtml(item)}</li>`).join(''); $('#datasetDeliverySummary').textContent=d.deliverable.length?`当前选择中有 ${d.deliverable.length} 张通过审核，并且已经确认 ${profileName} 图片说明。`:`当前选择中没有可交付图片。请返回第 4 步完成选择、图片审核和 ${profileName} 图片说明确认。`; $('#datasetExportActiveProfile').textContent=`生成并保存 ${profileName} 到 Mac`; $('#datasetExportActiveProfile').disabled=!d.deliverable.length||Boolean(d.selectedBlocked.length); renderStagePanels(step); renderPreflight(); renderExports(); }
  function taggerRecordLabel(record, completed=false) { const tagger=record?.tagger==='model'?'model':'wd14', model=record?.model || ''; if(tagger==='model') return completed?`模型已完成 · ${model || '视觉模型'}`:`模型失败 · ${model || '视觉模型'}`; return completed?'WD14 已完成':'WD14 失败'; }
  function taggerDetailLabel(record) { const tagger=record?.tagger==='model'?'model':'wd14', model=record?.model || ''; if(record?.status==='completed') return tagger==='model'?`模型已完成 · ${model || '视觉模型'} · 草稿待人工检查`:`${model || 'WD14'} · ${record.provider || 'CPU'} · 草稿待人工检查`; if(record?.status==='failed') return tagger==='model'?`模型失败 · ${model || '视觉模型'}：${record.error || '未知错误'}`:`WD14 失败：${record.error || '未知错误'}`; return '尚未运行打标'; }
  function updateDatasetTaggerMode() { const mode=$('#datasetTaggerMode').value, hasVision=state.models.length>0, option=[...$('#datasetTaggerMode').options].find(item=>item.value==='model'); if(option) option.disabled=!hasVision; if(mode==='model'&&!hasVision) $('#datasetTaggerMode').value='wd14'; const usingModel=$('#datasetTaggerMode').value==='model'; $('#datasetWd14Thresholds').hidden=usingModel; $('#datasetTaggerModelWrap').hidden=!usingModel; $('#datasetTaggerHint').textContent=usingModel?'模型会生成 Anima Booru 标签草稿；图片会发送到所选模型服务。':hasVision?'先按图片类型选择本地 Tagger；也可以改用已连接的视觉模型。':'先按图片类型选择本地 Tagger。没有可用视觉模型，因此“使用模型”已禁用。'; }
  function selectedLocalTagger() { return (state.taggerConfig?.models || []).find(item=>item.id===$('#datasetLocalTaggerModel').value); }
  function updateLocalTaggerCalibration() { const selected=selectedLocalTagger(); if(!selected) return; $('#datasetWd14Calibration').textContent=`${selected.label} · 普通标签阈值 ${selected.general_threshold} · 角色标签阈值 ${selected.character_threshold}${selected.available?' · 已安装':' · 本机未安装'}`; }
  function syncDatasetTaggerSelection() { const select=$('#datasetLocalTaggerModel'), models=state.taggerConfig?.models || []; if(!models.length) return; const preferred=state.report?.tagger_model_id || state.taggerConfig.default_id; if(models.some(item=>item.id===preferred)) select.value=preferred; updateLocalTaggerCalibration(); }
  function filteredImages() { const {exact, near} = duplicateSets(); const validity=$('#datasetValidity').value, caption=$('#datasetCaptionFilter').value, review=$('#datasetReviewFilter').value, duplicate=$('#datasetDuplicateFilter').value, format=$('#datasetFormatFilter').value, minSize=Number($('#datasetSizeFilter').value); return (state.report?.images || []).filter(item => { const status=item.review?.status || 'pending', inExact=exact.has(item.relative_path), inNear=near.has(item.relative_path); if (validity==='valid' && !item.valid) return false; if (validity==='invalid' && item.valid) return false; if (caption!=='all' && item.caption_status!==caption) return false; if (review!=='all' && status!==review) return false; if (format!=='all' && item.format!==format) return false; if (minSize && Math.min(item.width,item.height)<minSize) return false; if (duplicate==='exact' && !inExact) return false; if (duplicate==='near' && !inNear) return false; if (duplicate==='unique' && (inExact || inNear)) return false; return true; }); }
  function workspacePageSize() { return compactDatasetView.matches ? 12 : state.pageSize; }
  function renderGrid(resetPage=false) { const {exact, near}=duplicateSets(), pageSize=workspacePageSize(); state.visible=filteredImages(); const pageCount=Math.max(1,Math.ceil(state.visible.length/pageSize)); if (resetPage) state.page=1; state.page=Math.min(Math.max(state.page,1),pageCount); const start=(state.page-1)*pageSize; state.pageItems=state.visible.slice(start,start+pageSize); $('#datasetResultCount').textContent=`${formatNumber(state.visible.length)} 张`; $('#datasetSelectionCount').textContent=`已选 ${formatNumber(state.selected.size)} 张`; $('#datasetSelectVisible').checked=state.visible.length>0 && state.visible.every(item => state.selected.has(item.relative_path)); $('#datasetPagination').hidden=state.visible.length<=pageSize; $('#datasetPageStatus').textContent=`第 ${formatNumber(state.page)} / ${formatNumber(pageCount)} 页 · 每页最多 ${formatNumber(pageSize)} 张`; $('#datasetPreviousPage').disabled=state.page<=1; $('#datasetNextPage').disabled=state.page>=pageCount; $('#datasetGrid').innerHTML=state.pageItems.length ? state.pageItems.map((item,index) => { const status=item.review?.status || 'pending', wd14=item.curation?.wd14 || {}, tagStatus=wd14.status || 'untagged', vlmStatus=item.curation?.krea2_vlm?.status || 'empty', profile=$('#datasetDeliveryProfile').value, profileCaption=item.curation?.captions?.[profile] || {}; const flags=[item.caption_status==='missing'?'<span class="alert">缺少原说明</span>':'<span class="ok">已有原说明</span>', String(profileCaption.current || '').trim()?(profileCaption.status==='reviewed'?`<span class="ok">${profile==='anima'?'Anima':'Krea 2'} 已确认</span>`:`<span>${profile==='anima'?'Anima':'Krea 2'} 草稿</span>`):`<span class="alert">缺 ${profile==='anima'?'Anima':'Krea 2'}</span>`, tagStatus==='completed'?`<span class="ok">${escapeHtml(taggerRecordLabel(wd14,true))}</span>`:tagStatus==='failed'?`<span class="alert">${escapeHtml(taggerRecordLabel(wd14,false))}</span>`:'', ['completed','confirmed'].includes(vlmStatus)?'<span class="ok">Krea 草稿</span>':vlmStatus==='failed'?'<span class="alert">Krea 草稿失败</span>':'', !item.valid?'<span class="alert">坏图</span>':'', exact.has(item.relative_path)?'<span class="alert">完全重复</span>':'', near.has(item.relative_path)?'<span>近似重复</span>':'', `<span>${labels[status]}</span>`].join(''); return `<article class="dataset-card ${state.selected.has(item.relative_path)?'selected':''} ${item.valid?'':'invalid'}" data-dataset-index="${index}"><input class="dataset-card-select" type="checkbox" ${state.selected.has(item.relative_path)?'checked':''} aria-label="选择 ${escapeHtml(item.filename)}"><button class="dataset-card-preview" ${item.valid?'':'disabled'}>${item.thumbnail_url?`<img src="${escapeHtml(item.thumbnail_url)}" loading="lazy" alt="${escapeHtml(item.filename)}">`:'<span class="dataset-card-placeholder">无法预览</span>'}</button><div class="dataset-card-body"><strong>${escapeHtml(item.filename)}</strong><div class="dataset-card-meta"><span>${item.width}×${item.height}</span><span>${escapeHtml(item.format || '未知')}</span><span>${(item.bytes/1024).toFixed(0)} KiB</span></div><div class="dataset-card-flags">${flags}</div></div></article>`; }).join('') : '<div class="dataset-empty"><h2>当前筛选没有图片</h2><p>调整上方条件即可恢复显示。</p></div>'; renderStats(); renderJourney(); }
  function configureFormats() { const selected=$('#datasetFormatFilter').value; const formats=[...new Set((state.report?.images || []).map(item=>item.format).filter(Boolean))].sort(); $('#datasetFormatFilter').innerHTML='<option value="all">全部格式</option>'+formats.map(value=>`<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join(''); if (formats.includes(selected)) $('#datasetFormatFilter').value=selected; }
  async function loadModels() { const selects=[$('#datasetKrea2Model'),$('#datasetTaggerModel')], previous=selects.map(select=>select.value); try { const result=await api('/api/models'); state.models=(result.models || []).filter(item=>item.vision); const preferred=state.models.find(item=>item.loaded && /qwen.*3\.5.*9b/i.test(item.id)) || state.models.find(item=>item.loaded) || state.models.find(item=>/qwen.*3\.5.*9b/i.test(item.id)) || state.models[0]; selects.forEach((select,index)=>{ select.innerHTML=state.models.length?state.models.map(item=>`<option value="${escapeHtml(item.id)}" data-source="${escapeHtml(item.source || 'local')}">${escapeHtml(item.name || item.id)}${item.loaded?' · 已加载':''}</option>`).join(''):'<option value="">没有可用视觉模型</option>'; if (state.models.some(item=>item.id===previous[index])) select.value=previous[index]; else if (preferred) select.value=preferred.id; select.disabled=!state.models.length; }); updateDatasetTaggerMode(); } catch(error) { state.models=[]; selects.forEach(select=>{ select.innerHTML='<option value="">视觉模型当前不可连接</option>'; select.disabled=true; }); $('#datasetKrea2QueueHint').textContent=`视觉草稿暂不可用：${error.message}`; updateDatasetTaggerMode(); } }
  async function loadReport() { if (!state.active) return; state.report=await api(`/api/dataset-workspaces/${encodeURIComponent(state.active.workspace_id)}/report`); state.selected=new Set((state.report.images || []).filter(item=>item.review?.selected).map(item=>item.relative_path)); state.preflight=null; syncDatasetTaggerSelection(); configureFormats(); renderGrid(); $('#datasetScanTime').textContent=`扫描于 ${(state.report.scanned_at || '').slice(0,16).replace('T',' ')}`; await Promise.all([loadAnalytics(),loadSnapshots(),loadExports()]); renderJourney(); }
  async function selectWorkspace(id) { state.page=1; state.step=0; state.exports=[]; state.preflight=null; state.active=state.workspaces.find(item=>item.workspace_id===id) || null; renderWorkspaces(); $('#datasetEmpty').hidden=Boolean(state.active); $('#datasetDesk').hidden=!state.active; if (!state.active) { state.report=null; return; } $('#datasetActiveName').textContent=state.active.name; $('#datasetActivePath').textContent=state.active.source_path+(state.active.source_available===false?'（来源目录已经不在。请重新导入，或把目录放回原处）':''); $('#datasetActivePath').classList.toggle('dataset-source-gone',state.active.source_available===false); renderDatasetOrigin(); if (state.active.current_report) await loadReport(); else { state.report=null; renderGrid(); } await refreshJobs(); }
  async function loadWorkspaces(preferred='') { state.workspaces=await api('/api/dataset-workspaces'); renderWorkspaces(); const id=preferred || state.active?.workspace_id || state.workspaces[0]?.workspace_id; if (id) await selectWorkspace(id); }
  function countLabel(entry) { const text=`${formatNumber(entry.image_count)} 张图片`; return entry.image_count_capped?`500+ 张图片`:text; }
  function renderBrowse() { const payload=state.browse; if(!payload) return; const crumbs=payload.crumbs||[]; $('#datasetBrowseCrumbs').innerHTML=(payload.parent?`<button class="dataset-browse-up" data-browse-path="${escapeHtml(payload.parent)}">← 上一级</button>`:'')+crumbs.map((crumb,index)=>index===crumbs.length-1?`<span class="dataset-browse-crumb current">${escapeHtml(crumb.name)}</span>`:`<button class="dataset-browse-crumb" data-browse-path="${escapeHtml(crumb.path)}">${escapeHtml(crumb.name)}</button>`).join(' / '); $('#datasetBrowseQuick').innerHTML=(payload.quick||[]).map(item=>`<button type="button" data-browse-path="${escapeHtml(item.path)}" ${item.available?'':'disabled'}>${escapeHtml(item.label)}</button>`).join(''); const entries=payload.entries||[]; $('#datasetBrowseRows').innerHTML=entries.length?entries.map(entry=>{ const meta=[countLabel(entry)]; if(entry.imported) meta.push('已导入'); const reason=entry.reason?`<em>${escapeHtml(entry.reason)}</em>`:''; return `<div class="dataset-browse-row ${entry.selectable?'':'blocked'}"><button class="dataset-browse-nav" type="button" data-browse-path="${escapeHtml(entry.path)}"><strong>${escapeHtml(entry.name)}</strong><span>${meta.join(' · ')}</span>${reason}</button><button class="dataset-browse-pick" type="button" data-browse-pick="${escapeHtml(entry.path)}" ${entry.selectable?'':'disabled'}>选择</button></div>`; }).join(''):'<p class="dataset-hint">此文件夹没有子文件夹。</p>'; const skipped=(payload.skipped||[]).map(item=>`<div class="dataset-browse-row blocked"><span class="dataset-browse-nav static"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.reason)}</span></span></div>`).join(''); $('#datasetBrowseNote').innerHTML=skipped?`<strong>已跳过 ${payload.skipped.length} 项：</strong>${skipped}`:(payload.truncated?'文件夹太多，列表已截断。':''); $('#datasetBrowsePickCurrent').hidden=!payload.path; $('#datasetBrowsePickCurrent').disabled=!payload.selectable; $('#datasetBrowsePickCurrent').dataset.browsePick=payload.path||''; $('#datasetBrowsePickCurrent').textContent=payload.selectable?`选择当前文件夹：${payload.path}`:(payload.reason?`当前文件夹不可选：${payload.reason}`:'当前文件夹不可选'); }
  async function browseFolders(path='') { const query=path?`?path=${encodeURIComponent(path)}`:''; state.browse=await api(`/api/dataset-workspaces/browse${query}`); renderBrowse(); }
  function pickDatasetFolder(path) { $('#datasetSourcePath').value=path; $('#datasetPickedPath').textContent=path; $('#datasetBrowseDialog').close(); $('#datasetName').scrollIntoView({behavior:'smooth',block:'center'}); }
  function selectZipFile(file) { state.zipFile=file||null; $('#datasetPickedZip').textContent=file?`${file.name} · ${(file.size/1048576).toFixed(2)} MiB`:'尚未选择 zip'; $('#datasetZipUpload').disabled=!file; $('#datasetImportProgress').hidden=true; }
  function renderImportProgress(job) { if(!job){$('#datasetImportProgress').hidden=true;return;} const active=['queued','running'].includes(job.status); $('#datasetImportProgress').hidden=false; $('#datasetImportProgressTitle').textContent=job.status==='completed'?'zip 导入完成':job.status==='failed'?'zip 导入失败':job.status==='canceled'?'zip 导入已取消':'正在导入 zip'; $('#datasetImportProgressBar').max=Math.max(job.progress_total||1,1); $('#datasetImportProgressBar').value=job.progress_current||0; $('#datasetImportProgressMessage').textContent=job.progress_message||job.error||'等待处理'; $('#datasetZipCancel').hidden=!active; }
  function renderUploadProgress(loaded,total) { $('#datasetImportProgress').hidden=false; $('#datasetImportProgressTitle').textContent='正在上传 zip'; $('#datasetImportProgressBar').max=Math.max(total||1,1); $('#datasetImportProgressBar').value=loaded||0; $('#datasetImportProgressMessage').textContent=`已上传 ${(loaded/1048576).toFixed(1)} MiB / ${(total/1048576).toFixed(1)} MiB`; $('#datasetZipCancel').hidden=true; }
  function uploadZipFile(file) { const name=$('#datasetName').value.trim(); return new Promise((resolve,reject)=>{ const xhr=new XMLHttpRequest(); xhr.open('POST',`/api/dataset-workspaces/import-zip?filename=${encodeURIComponent(file.name)}&name=${encodeURIComponent(name)}`); xhr.setRequestHeader('Content-Type',file.type||'application/octet-stream'); xhr.upload.onprogress=event=>{ if(event.lengthComputable) renderUploadProgress(event.loaded,event.total); }; xhr.onload=()=>{ let payload={}; try { payload=JSON.parse(xhr.responseText||'{}'); } catch(error) { return reject(new Error('响应解析失败')); } if(xhr.status<200||xhr.status>=300) return reject(new Error(payload.detail||`请求失败：${xhr.status}`)); resolve(payload); }; xhr.onerror=()=>reject(new Error('上传中断，请检查后重试')); xhr.send(file); }); }
  async function pollImportJob(job) { renderImportProgress(job); while(['queued','running'].includes(job.status)){ await new Promise(resolve=>setTimeout(resolve,700)); job=await api(`/api/jobs/${encodeURIComponent(job.job_id)}`); renderImportProgress(job); } return job; }
  function showManifestSuggestion(manifest) { if(!manifest||!manifest.source) return; const profile=manifest.suggested_profile==='krea2'?'Krea 2':manifest.suggested_profile==='anima'?'Anima':''; $('#datasetManifestNote').hidden=false; $('#datasetManifestNote').innerHTML=`<strong>检测到 ${escapeHtml(manifest.source)} · ${escapeHtml(manifest.export_type)} 导出</strong>${profile?`<span>内容看起来是自然语言长句，建议使用 ${profile} 格式。</span><button type="button" id="datasetManifestAccept" data-profile="${manifest.suggested_profile}">改用 ${profile} 格式</button>`:'<span>导入已完成，可自行选择说明格式。</span>'}`; }
  async function importWorkspace(event) { event.preventDefault(); const path=$('#datasetSourcePath').value.trim(); if(!path) return alert('请先选择数据集文件夹，或在“手动输入路径”里填写完整路径。'); const button=event.submitter || $('#datasetImportSubmit'); button.disabled=true; try { const result=await api('/api/dataset-workspaces/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_path:path,name:$('#datasetName').value.trim()})}); await loadWorkspaces(result.workspace.workspace_id); startPolling(); } catch(error) { alert(`读取失败：${error.message}`); } finally { button.disabled=false; } }
  async function importZip() { const file=state.zipFile; if(!file) return; state.importJob=null; $('#datasetZipUpload').disabled=true; $('#datasetManifestNote').hidden=true;     try { const result=await uploadZipFile(file); state.importJob=result.job; const job=await pollImportJob(result.job); if(job.status==='completed'){ const workspace=job.result?.workspace; $('#datasetImportProgressMessage').textContent='解压完成，正在建立工作区并扫描……'; if(workspace?.workspace_id){ await api(`/api/dataset-workspaces/${encodeURIComponent(workspace.workspace_id)}/rescan`,{method:'POST'}); await loadWorkspaces(workspace.workspace_id); startPolling(); } showManifestSuggestion(job.result?.manifest); const skipped=job.result?.skipped?.length||0; $('#datasetImportProgressMessage').textContent=`已导入 ${job.result?.extracted_files||0} 个文件`+(skipped?`，跳过 ${skipped} 个不支持的文件`:'')+`。开始扫描 ${job.result?.workspace?.name||''}。`; $('#datasetPickedZip').textContent='尚未选择 zip'; state.zipFile=null; $('#datasetZipUpload').disabled=true; } else if(job.status==='failed'){ $('#datasetImportProgressMessage').textContent=`导入失败：${job.error||'未知错误'}`; } } catch(error) { renderImportProgress(null); $('#datasetManifestNote').hidden=false; $('#datasetManifestNote').innerHTML=`<strong>上传失败</strong><span>${escapeHtml(error.message)}</span>`; } finally { $('#datasetZipUpload').disabled=!state.zipFile; } }
  async function cancelImportJob() { if(!state.importJob) return; const job=await api(`/api/jobs/${encodeURIComponent(state.importJob.job_id)}/cancel`,{method:'POST'}); renderImportProgress(job); $('#datasetImportProgressMessage').textContent='已取消。可以重新选择 zip 上传。'; }
  function renderJob(job) { const panel=$('#datasetJobPanel'); if (!job) { panel.hidden=true; panel.dataset.jobState=''; return; } const active=['queued','running'].includes(job.status), total=Math.max(job.progress_total,1), types={dataset_wd14:job.payload?.tagger==='model'?'模型生成标签':'WD14 生成标签',dataset_krea2_vlm:'Krea 2 视觉草稿',dataset_krea2_locale:'Krea 2 中文对照',dataset_scan:'扫描数据集'}, statuses={queued:'等待开始',running:'正在处理',completed:'已完成',failed:'执行失败',canceled:'已取消'}, type=types[job.job_type] || '数据集任务'; const action=active?`<button data-job-action="cancel" data-job-id="${job.job_id}">取消</button>`:['failed','canceled'].includes(job.status)?`<button data-job-action="retry" data-job-id="${job.job_id}">重试</button>`:''; panel.dataset.jobState=job.status; panel.hidden=state.mode==='simple'&&job.status==='completed'; panel.innerHTML=`<div class="dataset-job-line"><span>${escapeHtml(type)} · ${escapeHtml(statuses[job.status] || job.status)}</span><progress value="${job.progress_current}" max="${total}"></progress>${action}</div><p class="dataset-job-message">${escapeHtml(job.progress_message || job.error || '等待处理')}</p>`; }
  async function refreshJobs() { if (!state.active) return false; const jobs=await api('/api/jobs?limit=100'), related=jobs.filter(item=>['dataset_scan','dataset_wd14','dataset_krea2_vlm','dataset_krea2_locale'].includes(item.job_type) && item.payload?.workspace_id===state.active.workspace_id), job=related.find(item=>['queued','running'].includes(item.status)) || related[0]; renderJob(job); if (job && ['queued','running'].includes(job.status)) return true; const active=await api(`/api/dataset-workspaces/${state.active.workspace_id}`); const shouldLoad=Boolean(active.current_report) && (!state.report || active.current_report!==state.active.current_report || job?.status==='completed'); Object.assign(state.active,active); if (shouldLoad) await loadReport(); renderWorkspaces(); return false; }
  function startPolling() { clearInterval(state.poll); state.poll=setInterval(async()=>{ try { const running=await refreshJobs(); if (!running) clearInterval(state.poll); } catch(error) { console.error(error); clearInterval(state.poll); } },900); }
  async function updateReviews(items) { if (!state.active || !items.length) return; await api(`/api/dataset-workspaces/${state.active.workspace_id}/review`,jsonOptions({items})); await loadReport(); }
  async function clearDatasetSelection() { if (!state.active || !state.selected.size) { state.selected.clear(); renderGrid(); return; } const items=(state.report?.images || []).filter(item=>state.selected.has(item.relative_path)).map(item=>({relative_path:item.relative_path,status:item.review?.status || 'pending',selected:false,note:item.review?.note || ''})); await updateReviews(items); }
  function selectedPaths(scope='selected') { if (scope==='filtered') return state.visible.map(item=>item.relative_path); return [...state.selected]; }
  async function queueWd14(scope) { if (!state.active) return; const paths=scope==='selected'?selectedPaths():[], tagger=$('#datasetTaggerMode').value, model=$('#datasetTaggerModel').value, localTagger=selectedLocalTagger(); if (scope==='selected' && !paths.length) return alert('请先选择要打标的图片。'); if (tagger==='model' && !model) return alert('请先选择用于打标的视觉模型。'); if(tagger==='wd14'&&!localTagger) return alert('请先选择与素材匹配的本地 Tagger。'); if(tagger==='wd14'&&!localTagger.available) return alert(`本机还没有安装 ${localTagger.label} Tagger（${localTagger.model}）。请先安装该模型，或选择已经安装的 Tagger。`); if (scope==='all' && !confirm('重新打标整个工作区会替换尚未人工确认的 Anima 草稿。继续吗？')) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/wd14`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope,paths,tagger,model,tagger_model_id:$('#datasetLocalTaggerModel').value,provider:'cpu',overwrite:scope==='all',...captionSettings()})}); renderJob(result.job); startPolling(); }
  async function queueKrea2VLM(scope) { if (!state.active) return; const model=$('#datasetKrea2Model').value, paths=scope==='selected'?selectedPaths():[]; if (!model) return alert('请先在 LM Studio 中准备并加载一个视觉模型。'); if (scope==='selected' && !paths.length) return alert('请先选择要生成草稿的图片。'); const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/krea2-vlm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope,paths,model,...captionSettings()})}); renderJob(result.job); $('#datasetKrea2QueueHint').textContent='队列已开始。模型结果只会进入待确认草稿。'; startPolling(); }
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
  async function copyExport(versionId, button) { const target=deviceName(); if(!confirm(`把版本 ${versionId} 复制到已挂载的 ${target} 共享目录？\n目标按数据集名和版本号隔离，不会覆盖旧版本。`)) return; button.disabled=true; button.textContent='正在复制并核对哈希…'; try { const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/exports/${encodeURIComponent(versionId)}/copy`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({node_id:'compute_5060ti'})}); $('#datasetCopyResult').textContent=result.status==='already_present'?`${target} 已存在 ${versionId}，没有覆盖。`:`已复制 ${result.file_count} 个文件到 ${target}，并完成哈希核对。`; await loadExports(); } finally { button.disabled=false; button.textContent=`复制到 ${target}`; } }
  async function rollbackSnapshot() { const id=$('#datasetSnapshot').value; if (!id || !confirm(`恢复说明文字修改记录 ${id}？当前内容也会先保存，之后仍可找回。`)) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/snapshots/${encodeURIComponent(id)}/rollback`,{method:'POST'}); $('#datasetBulkResult').textContent=`已恢复 ${result.changed} 张；同时保存了当前内容，记录编号 ${result.snapshot}。`; await loadReport(); }
  function detailItem() { return state.pageItems[state.detailIndex]; }
  async function renderDetailTags(item) { const caption=$('#datasetDetailAnima').value, tags=caption.split(',').map(value=>value.trim()).filter(Boolean), candidates=[...new Set([...(item.curation?.wd14?.general || []).map(value=>value.tag).filter(Boolean),...tags])], selected=new Set(tags); await window.ensureTagLabels?.(candidates); $('#datasetDetailTagChips').innerHTML=candidates.map(tag=>`<button class="${selected.has(tag)?'selected':''}" data-detail-tag="${escapeHtml(tag)}" aria-pressed="${selected.has(tag)}">${escapeHtml(window.displayCanonicalTag?.(tag) || tag)}</button>`).join(''); }
  function renderDetail() { const item=detailItem(); if (!item) return; const wd14=item.curation?.wd14 || {status:'untagged'}, vlm=item.curation?.krea2_vlm || {status:'empty'}, anima=item.curation?.captions?.anima || {}, krea=item.curation?.captions?.krea2 || {}, vlmTime=vlm.created_at?` · ${vlm.created_at.slice(0,16).replace('T',' ')}`:''; $('#datasetDetailImage').src=item.original_url; $('#datasetDetailName').textContent=item.relative_path; $('#datasetDetailMeta').textContent=`${item.width}×${item.height} · ${item.format} · ${(item.bytes/1024).toFixed(1)} KiB`; $('#datasetDetailStatus').value=item.review?.status || 'pending'; $('#datasetDetailCaption').value=item.caption || ''; $('#datasetDetailAnima').value=anima.current || ''; $('#datasetDetailKrea2').value=krea.current || ''; $('#datasetDetailKrea2Draft').value=vlm.draft || ''; restoreKrea2Locale(item); $('#datasetDetailKrea2Revision').value=''; $('#datasetDetailKrea2ReviseStatus').textContent='改写结果会放回英文草稿框，保存前仍可继续修改。'; $('#datasetDetailWD14').textContent=taggerDetailLabel(wd14); $('#datasetDetailKrea2VLM').textContent=vlm.status==='failed'?`失败：${vlm.error || '未知错误'}`:['completed','confirmed'].includes(vlm.status)?`${vlm.model || '人工保存草稿'}${vlmTime}${vlm.status==='confirmed'?' · 已确认':''}`:'尚无草稿'; $('#datasetDetailKrea2Warning').hidden=!vlm.safety_warning; $('#datasetDetailKrea2Warning').textContent=vlm.safety_warning || ''; $('#datasetDetailDraftConfirm').disabled=!vlm.draft; $('#datasetDetailHashes').textContent=`SHA-256：${item.sha256}\npHash：${item.phash || '—'}\n原始说明：${item.caption_path || '缺失'}\n来源文件：${item.relative_path}\nAnima 状态：${anima.status || 'empty'}\nKrea 2 状态：${krea.status || 'empty'}\n视觉草稿哈希：${vlm.source_sha256 || '—'}`; $('#datasetPrevious').disabled=state.detailIndex<=0; $('#datasetNext').disabled=state.detailIndex>=state.pageItems.length-1; $('#datasetFindSimilar').disabled=true; $('#datasetFindSimilarStatus').textContent='正在检查真实视觉索引……'; refreshSimilarStatus(item).catch(error=>$('#datasetFindSimilarStatus').textContent=error.message); renderDetailTags(item).catch(console.error); }
  async function refreshSimilarStatus(item) { const digest=item.sha256, result=await api(`/api/hybrid-search/source-status?source_sha256=${encodeURIComponent(digest)}`); if(detailItem()?.sha256!==digest) return; $('#datasetFindSimilar').disabled=!result.available; $('#datasetFindSimilarStatus').textContent=result.available?`已进入 ${result.indexes.length} 个真实索引，可以查相似图。`:'等待 Windows 设备生成真实 CLIP / SigLIP 索引；当前不生成伪结果。'; }
  function openDetail(index) { state.detailIndex=index; renderDetail(); $('#datasetDetail').showModal(); }
  function restoreKrea2Locale(item) {
    // 译文按图记住。翻过的那张切回来还在。不必重翻。
    // 但也不能就这样留着上一张的。挂在另一张草稿旁边会被当成这张的意思。
    const cached=state.captionLocales[item.relative_path];
    const draft=String(item.curation?.krea2_vlm?.draft || '');
    // 批次翻译的结果存在工作区里。逐张审核时不必再翻一次。
    const stored=item.curation?.krea2_locale || {};
    const storedUsable=String(stored.localized || '') && String(stored.source || '')===draft ? String(stored.localized) : '';
    // 草稿变了 重新生成或改写过 之后。旧译文对应的已经不是眼前这段。
    const usable=cached && cached.caption===draft ? cached.localized : storedUsable;
    $('#datasetDetailKrea2Locale').value=usable;
    $('#datasetDetailKrea2LocaleStatus').textContent=usable
      ? '仅供对照。导出的始终是英文草稿'
      : (cached?'草稿已变动。需要对照请重新翻译':'按需翻译。逐张确认时才发送请求');
  }

  function moveDetail(offset) { const next=state.detailIndex+offset; if (next<0 || next>=state.pageItems.length) return; state.detailIndex=next; renderDetail(); }
  async function approveDetail() {
    // 说明文字是即时改的。审核通过就是「这张我看完了」。
    // 顺手带到下一张——逐张确认时最常做的就是这个动作。
    const button=$('#datasetDetailApprove');
    const item=detailItem();
    if (!item) return;
    const previousIndex=state.detailIndex;
    button.disabled=true;
    try {
      $('#datasetDetailStatus').value='approved';
      await saveDetail();
      // 带着筛选审核时，通过的这张会离开清单。此时同一个位置就是下一张，
      // 不能再 +1（会跳过一张），也不能停在 -1（对话框会留着上一张的内容）。
      const stillListed=state.pageItems.some(candidate=>candidate.relative_path===item.relative_path);
      if (stillListed) { moveDetail(1); return; }
      if (!state.pageItems.length) { $('#datasetDetail').close(); return; }
      state.detailIndex=Math.min(previousIndex, state.pageItems.length-1);
      renderDetail();
    } finally { button.disabled=false; }
  }

  async function saveDetail() { const item=detailItem(); if (!item) return; const requests=[api(`/api/dataset-workspaces/${state.active.workspace_id}/review`,jsonOptions({items:[{relative_path:item.relative_path,status:$('#datasetDetailStatus').value,selected:state.selected.has(item.relative_path),}]}))], anima=$('#datasetDetailAnima').value.trim(), krea=$('#datasetDetailKrea2').value.trim(); if (anima!==String(item.curation?.captions?.anima?.current || '')) requests.push(api(`/api/dataset-workspaces/${state.active.workspace_id}/caption`,jsonOptions({relative_path:item.relative_path,profile_id:'anima',caption:anima,caption_status:'reviewed'}))); if (krea!==String(item.curation?.captions?.krea2?.current || '')) requests.push(api(`/api/dataset-workspaces/${state.active.workspace_id}/caption`,jsonOptions({relative_path:item.relative_path,profile_id:'krea2',caption:krea,caption_status:'reviewed'}))); await Promise.all(requests); await loadReport(); state.detailIndex=state.pageItems.findIndex(candidate=>candidate.relative_path===item.relative_path); renderDetail(); }
  async function saveKrea2Draft(confirmDraft) { const item=detailItem(), draft=$('#datasetDetailKrea2Draft').value.trim(); if (!item) return; if (confirmDraft && !draft) return alert('确认前需要一份英文 Krea 2 草稿。'); if (confirmDraft && !confirm('确认把这份视觉模型草稿写入正式 Krea 2 图片说明？系统会先保存可回退的修改记录。')) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/krea2-draft`,jsonOptions({relative_path:item.relative_path,draft,confirm:confirmDraft})); await loadReport(); state.detailIndex=state.pageItems.findIndex(candidate=>candidate.relative_path===item.relative_path); renderDetail(); if (confirmDraft) $('#datasetDetailKrea2VLM').textContent=`已确认写入 Krea 2 · ${result.snapshot}`; }
  function krea2DraftSelection() { return (state.report?.images || []).filter(item=>state.selected.has(item.relative_path) && String(item.curation?.krea2_vlm?.draft || '').trim()); }
  async function confirmKrea2Selection() { if (!state.active) return; if (!state.selected.size) return alert('请先选择要写入 Krea 2 的图片。'); const pending=krea2DraftSelection(); if (!pending.length) return alert('所选图片里没有可写入的 Krea 2 草稿。请先生成草稿，或在图片详情中逐张确认。'); if (!confirm(`确认把 ${pending.length} 份 Krea 2 视觉草稿写入正式说明？\n系统会保存一条可回退的修改记录；已经人工确认过的 Krea 2 说明不会被覆盖，Anima 标签与 WD14 也不会改变。`)) return; const button=$('#datasetBulkKrea2Confirm'); button.disabled=true; $('#datasetBulkKrea2Result').textContent='正在写入 Krea 2 说明…'; try { const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/krea2-drafts/confirm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({paths:pending.map(item=>item.relative_path)})}); const kept=result.skipped_reviewed?`，已人工确认、保持不变 ${result.skipped_reviewed} 张（要覆盖请在图片详情中逐张确认）`:''; $('#datasetBulkKrea2Result').textContent=result.confirmed?`已写入 ${result.confirmed} 张 Krea 2 说明，与现有说明相同、跳过 ${result.skipped_unchanged} 张${kept}；修改记录 ${result.snapshot}。`:`没有需要写入的图片：与现有说明相同 ${result.skipped_unchanged} 张${kept}。`; await loadReport(); } finally { button.disabled=false; } }
  async function insertTriggerWord() { if (!state.active) return; const trigger=$('#datasetTriggerWord').value.trim(); if (!trigger) return alert('请先填写要插入的触发词。'); if (!state.selected.size) return alert('请先选择要插入触发词的图片。'); const profile=$('#datasetDeliveryProfile').value || 'anima', profileName=profile==='anima'?'Anima':'Krea 2'; if (!confirm(`确认把「${trigger}」插到 ${state.selected.size} 张图片的 ${profileName} 说明最前面？\n系统会先保存一条可回退的修改记录，不会改动源 .txt。`)) return; const button=$('#datasetInsertTrigger'); button.disabled=true; $('#datasetReviewToolsResult').textContent='正在插入触发词…'; try { const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/bulk-tags/apply`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:profile,paths:selectedPaths(),prepend:[trigger]})}); $('#datasetReviewToolsResult').textContent=result.changed?`已在 ${result.changed} 张的 ${profileName} 说明最前面插入「${trigger}」；修改记录 ${result.snapshot}。`:`没有需要修改的图片：所选 ${profileName} 说明已经以「${trigger}」开头。`; await loadReport(); } finally { button.disabled=false; } }
  async function queueKrea2Locale() { if (!state.active) return; if (!state.selected.size) return alert('请先选择要翻译的图片。'); const pending=(state.report?.images || []).filter(item=>state.selected.has(item.relative_path) && (String(item.curation?.captions?.krea2?.current || '').trim() || String(item.curation?.krea2_vlm?.draft || '').trim())); if (!pending.length) return alert('所选图片里没有可翻译的 Krea 2 说明或草稿。'); if (!confirm(`确认翻译 ${pending.length} 张图片的 Krea 2 英文说明？\n译文只作中文对照，不会改动英文说明，也不会进入交付版本。`)) return; const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/krea2-locale`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scope:'selected',paths:selectedPaths()})}); renderJob(result.job); $('#datasetReviewToolsResult').textContent=`已开始翻译 ${pending.length} 张；译文会显示在图片详情的中文对照里。`; startPolling(); }
  async function confirmCaptionStatus() { if (!state.active) return; if (!state.selected.size) return alert('请先选择要确认说明的图片。'); const profile=$('#datasetDeliveryProfile').value || 'anima', profileName=profile==='anima'?'Anima':'Krea 2', pending=(state.report?.images || []).filter(item=>state.selected.has(item.relative_path) && String(item.curation?.captions?.[profile]?.current || '').trim() && item.curation?.captions?.[profile]?.status!=='reviewed'); if (!pending.length) return alert(`所选图片的 ${profileName} 说明都已经确认过，或者还没有内容。`); if (!confirm(`确认 ${pending.length} 张图片的 ${profileName} 说明？\n说明文字本身不会改动，只是标记为已人工确认，交付前检查才会放行。`)) return; const button=$('#datasetConfirmCaptions'); button.disabled=true; $('#datasetReviewToolsResult').textContent='正在标记已确认…'; try { const result=await api(`/api/dataset-workspaces/${state.active.workspace_id}/captions/confirm`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:profile,paths:selectedPaths()})}); $('#datasetReviewToolsResult').textContent=`已确认 ${result.confirmed} 张 ${profileName} 说明，早已确认 ${result.skipped_reviewed} 张，空白跳过 ${result.skipped_empty} 张${result.snapshot?`；修改记录 ${result.snapshot}`:''}。`; await loadReport(); } finally { button.disabled=false; } }
  async function rescan() { if (!state.active) return; await api(`/api/dataset-workspaces/${state.active.workspace_id}/rescan`,{method:'POST'}); await loadWorkspaces(state.active.workspace_id); startPolling(); }
  async function removeWorkspace() { if (!state.active) return; const zipArchive=state.active.source_origin==='zip_archive'; const message=zipArchive?'只移除 Prompt Hub 中的记录和解压副本；你上传的原始 zip 文件不会被删除。继续吗？':'只移除 Prompt Hub 中的记录和派生缩略图。原文件夹不会删除。继续吗？'; if (!confirm(message)) return; const source=state.active.source_path; await api(`/api/dataset-workspaces/${state.active.workspace_id}`,{method:'DELETE'}); state.active=null; state.report=null; await loadWorkspaces(); alert(zipArchive?`工作区记录和解压副本已移除。原始 zip 保持不变：\n${source}`:`工作区记录已移除。源目录保持不变：\n${source}`); }
  function setDatasetMode(mode) { state.mode=mode==='advanced'?'advanced':'simple'; try { localStorage.setItem('soda-dataset-mode',state.mode); } catch(error) { console.debug(error); } renderJourney(); }
  function setDatasetStep(step,{preset=false,scroll=true}={}) { state.step=Math.min(5,Math.max(1,Number(step)||1)); const d=deliveryState(); if(preset&&state.step===2) { $('#datasetValidity').value=d.invalidOpen.length?'invalid':'all'; $('#datasetDuplicateFilter').value=!d.invalidOpen.length&&d.exactBlockingGroups.length?'exact':'all'; $('#datasetReviewFilter').value='all'; renderGrid(true); } else if(preset&&state.step===4) { $('#datasetValidity').value='valid'; $('#datasetDuplicateFilter').value='all'; $('#datasetReviewFilter').value=d.pending.length?'pending':d.needsReview.length?'needs_review':'all'; renderGrid(true); } else renderJourney(); if(state.step===5) runPreflight().catch(error=>{$('#datasetPreflightSummary').textContent=error.message;});     if(scroll) { const target=state.step===1?$('#datasetImportForm'):state.step===3?document.querySelector('[data-dataset-stage-panel="3"]'):state.step===5?$('#datasetDeliveryPanel'):document.querySelector('[data-dataset-stage-panel="2,4"]'); target?.scrollIntoView({behavior:'smooth',block:'start'}); if(state.step===1) $('#datasetPickFolder').focus(); } }
  function runDatasetNextAction() { const d=deliveryState(), step=state.step || d.recommended; if(step===1) return setDatasetStep(1,{scroll:true}); if(step===2&&d.invalidOpen.length+d.exactBlockingGroups.length===0) return setDatasetStep(3); if(step===3&&!d.missing.length) return setDatasetStep(4,{preset:true}); if(step===4&&!d.captionDraft.length&&!d.pending.length&&!d.needsReview.length&&d.deliverable.length) return setDatasetStep(5); if(step===5&&!d.deliverable.length) return setDatasetStep(4,{preset:true}); setDatasetStep(step,{preset:true}); }
  async function continueWorkspace() { const id=state.active?.workspace_id || state.workspaces[0]?.workspace_id; if(!id) return; if(state.active?.workspace_id!==id) await selectWorkspace(id); const step=deliveryState().recommended; setDatasetStep(step,{preset:true,scroll:true}); }
  async function loadCaptionModes() {
    // 模式与开关一律从后端契约来。前端硬编 enum 就会跟后端各走各的——
    // 上一轮就是这样让 WD14 分支漏掉整组设置的。
    try { state.captionContract = await api('/api/dataset-workspaces/caption-modes'); }
    catch (error) { $('#datasetCaptionModeHint').textContent=`读取打标规则失败：${error.message}`; return; }
    const contract=state.captionContract;
    $('#datasetCaptionMode').innerHTML=contract.modes.map(mode=>`<option value="${escapeHtml(mode.id)}">${escapeHtml(mode.label)}</option>`).join('');
    $('#datasetCaptionMaxTokens').value=contract.max_tokens_default;
    $('#datasetCaptionMediaTags').checked=Boolean(contract.media_tags_default);
    renderCaptionOptions();
    updateCaptionMode();
    renderCaptionPresets();
  }

  function renderCaptionOptions() {
    const contract=state.captionContract; if(!contract) return;
    const profile=$('#datasetDeliveryProfile').value || 'anima';
    // 对当前格式无效的开关直接不显示。摆一个按了没反应的开关，
    // 比没有那个开关更糟——使用者会以为设定生效了。
    const usable=contract.options.filter(option=>option.profiles.includes(profile));
    $('#datasetCaptionOptionList').innerHTML=usable.map(option=>{
      const previous=state.captionOptions[option.id];
      const checked=(previous===undefined?option.default:previous)?' checked':'';
      return `<label class="dataset-inline-check"><input type="checkbox" data-caption-option="${escapeHtml(option.id)}"${checked}> ${escapeHtml(option.label)}</label>`;
    }).join('');
    $('#datasetCaptionOptions').hidden=!usable.length;
  }

  function updateCaptionMode(applyMediaDefault=false) {
    const contract=state.captionContract; if(!contract) return;
    const mode=contract.modes.find(item=>item.id===$('#datasetCaptionMode').value) || contract.modes[0];
    const needsTrigger=Boolean(mode.trigger_label);
    $('#datasetCaptionTriggerWrap').hidden=!needsTrigger;
    if(needsTrigger) $('#datasetCaptionTriggerLabel').textContent=mode.trigger_label;
    const filled=$('#datasetCaptionTrigger').value.trim();
    if(applyMediaDefault) $('#datasetCaptionMediaTags').checked=Boolean(contract.media_tags_by_mode?.[mode.id] ?? contract.media_tags_default);
    // 触发词非必填。留空不挡下队列，但要说清楚后果。
    if (!needsTrigger) $('#datasetCaptionModeHint').textContent='通用模式会描述画面中的主要内容。';
    else $('#datasetCaptionModeHint').textContent=`本模式不会描述：${mode.omits}。${filled?'触发词会放在说明开头，训练后可用它调用对应特征。':'触发词可以留空，但训练后无法用单个词调用这项特征。'}`;
  }

  function captionSettings() {
    const contract=state.captionContract;
    if(!contract) return {};
    const options={};
    document.querySelectorAll('[data-caption-option]').forEach(input=>{ options[input.dataset.captionOption]=input.checked; });
    return {
      mode: $('#datasetCaptionMode').value || 'general',
      trigger: $('#datasetCaptionTrigger').value.trim(),
      media_tags: $('#datasetCaptionMediaTags').checked,
      options,
      max_tokens: Number($('#datasetCaptionMaxTokens').value) || contract.max_tokens_default,
    };
  }

  const CAPTION_PRESET_KEY='soda-caption-presets';

  function readCaptionPresets() {
    // 浏览器可能禁用存储，或是留下上个版本写坏的内容。
    // 读不出来就当作没有预设，不能让整个规则面板跟着挂掉。
    try { const raw=localStorage.getItem(CAPTION_PRESET_KEY); const parsed=raw?JSON.parse(raw):{}; return (parsed && typeof parsed==='object' && !Array.isArray(parsed))?parsed:{}; }
    catch(error) { console.debug(error); return {}; }
  }

  function renderCaptionPresets(selected='') {
    const presets=readCaptionPresets(), names=Object.keys(presets).sort();
    $('#datasetCaptionPreset').innerHTML='<option value="">不套用</option>'+names.map(name=>`<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join('');
    $('#datasetCaptionPreset').value=selected;
    $('#datasetCaptionPresetDelete').disabled=!selected;
  }

  function applyCaptionPreset(name) {
    const preset=readCaptionPresets()[name];
    if(!preset) return;
    $('#datasetCaptionMode').value=preset.mode || 'general';
    $('#datasetCaptionTrigger').value=preset.trigger || '';
    $('#datasetCaptionMediaTags').checked=Boolean(preset.media_tags);
    $('#datasetCaptionMaxTokens').value=preset.max_tokens || state.captionContract?.max_tokens_default || 300;
    // 先写进 state 再重画，否则 renderCaptionOptions 会拿旧的勾选状态覆盖回去。
    state.captionOptions={...(preset.options || {})};
    renderCaptionOptions();
    updateCaptionMode();
    $('#datasetCaptionPresetHint').textContent=`已套用「${name}」。`;
  }

  function saveCaptionPreset() {
    const name=$('#datasetCaptionPresetName').value.trim();
    if(!name) return alert('请先填写设置名称。');
    const presets=readCaptionPresets();
    const existed=Object.prototype.hasOwnProperty.call(presets, name);
    if(existed && !confirm(`已经有一份叫「${name}」的设置。覆盖它吗？`)) return;
    presets[name]=captionSettings();
    try { localStorage.setItem(CAPTION_PRESET_KEY, JSON.stringify(presets)); }
    catch(error) { return alert(`保存失败：${error.message}`); }
    $('#datasetCaptionPresetName').value='';
    renderCaptionPresets(name);
    $('#datasetCaptionPresetHint').textContent=existed?`已覆盖「${name}」。`:`已保存「${name}」。`;
  }

  function deleteCaptionPreset() {
    const name=$('#datasetCaptionPreset').value;
    if(!name) return;
    if(!confirm(`删除设置「${name}」？`)) return;
    const presets=readCaptionPresets();
    delete presets[name];
    try { localStorage.setItem(CAPTION_PRESET_KEY, JSON.stringify(presets)); }
    catch(error) { return alert(`删除失败：${error.message}`); }
    renderCaptionPresets();
    $('#datasetCaptionPresetHint').textContent=`已删除「${name}」。`;
  }

  async function loadTaggerConfig() { try { const config=await api('/api/tagger-config'); state.taggerConfig=config; $('#datasetLocalTaggerModel').innerHTML=(config.models || []).map(item=>`<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)} · ${escapeHtml(item.available?'已安装':'未安装')}</option>`).join(''); syncDatasetTaggerSelection(); } catch(error) { $('#datasetLocalTaggerModel').innerHTML='<option value="">本地打标模型设置读取失败</option>'; $('#datasetWd14Calibration').textContent=`打标模型设置读取失败：${error.message}`; } }
  async function ensureWorkspace() { try { state.mode=localStorage.getItem('soda-dataset-mode')==='advanced'?'advanced':'simple'; } catch(error) { console.debug(error); } await Promise.all([loadModels(),loadTagCatalog(),loadWorkspaces(),loadTaggerConfig(),loadCaptionModes()]); if (state.active) { const running=await refreshJobs(); if (running) startPolling(); } renderJourney(); }
  async function openDatasetWorkspace(workspaceId,step=0) { await loadWorkspaces(workspaceId); if(step) setDatasetStep(step,{preset:true,scroll:true}); const running=await refreshJobs(); if(running) startPolling(); }
  window.openDatasetWorkspace=openDatasetWorkspace;
  $('#datasetImportForm').addEventListener('submit',importWorkspace);
  $('#datasetPickFolder').addEventListener('click',()=>{ $('#datasetBrowseDialog').showModal(); browseFolders().catch(error=>{$('#datasetBrowseRows').innerHTML=`<p class="dataset-hint">${escapeHtml(error.message)}</p>`;}); });
  $('#datasetBrowseClose').addEventListener('click',()=>$('#datasetBrowseDialog').close());
  $('#datasetBrowseDialog').addEventListener('click',event=>{ const pick=event.target.closest('[data-browse-pick]'); if(pick){ pickDatasetFolder(pick.dataset.browsePick); return; } const nav=event.target.closest('[data-browse-path]'); if(nav){ browseFolders(nav.dataset.browsePath).catch(error=>$('#datasetBrowseRows').innerHTML=`<p class="dataset-hint">${escapeHtml(error.message)}</p>`); } });
  $('#datasetBrowseDialog').addEventListener('close',()=>{ state.browse=null; $('#datasetBrowseRows').innerHTML=''; $('#datasetBrowseQuick').innerHTML=''; $('#datasetBrowseCrumbs').innerHTML=''; });
  $('#datasetPickZip').addEventListener('click',()=>$('#datasetZipFile').click());
  $('#datasetZipFile').addEventListener('change',event=>selectZipFile(event.target.files?.[0]));
  $('#datasetZipUpload').addEventListener('click',()=>importZip().catch(error=>alert(`上传失败：${error.message}`)));
  $('#datasetZipCancel').addEventListener('click',()=>cancelImportJob().catch(error=>alert(error.message)));
  $('#datasetManifestNote').addEventListener('click',event=>{ const button=event.target.closest('#datasetManifestAccept'); if(!button) return; $('#datasetDeliveryProfile').value=button.dataset.profile; $('#datasetSourceCaptionProfile').value=button.dataset.profile; $('#datasetManifestNote').hidden=true; $('#datasetImportProgressMessage').textContent=`已按建议切换为 ${button.dataset.profile==='krea2'?'Krea 2':'Anima'} 格式。`; });
  $('#datasetSourcePath').addEventListener('input',event=>{ $('#datasetPickedPath').textContent=event.target.value.trim()||'尚未选择文件夹'; });
  $('#datasetName').addEventListener('input',()=>{ $('#datasetZipUpload').disabled=!state.zipFile; });
  $('#datasetContinueButton').addEventListener('click',()=>continueWorkspace().catch(error=>alert(error.message)));
  $('#datasetModeSimple').addEventListener('click',()=>setDatasetMode('simple'));
  $('#datasetModeAdvanced').addEventListener('click',()=>setDatasetMode('advanced'));
  $('#datasetJourney').addEventListener('click',event=>{ const button=event.target.closest('[data-dataset-step]'); if(button) setDatasetStep(button.dataset.datasetStep,{preset:true}); });
  $('#datasetDeliveryProfile').addEventListener('change',event=>{ $('#datasetSourceCaptionProfile').value=event.target.value; renderCaptionOptions(); state.step=0; state.preflight=null; renderGrid(true); });
  $('#datasetTaggerMode').addEventListener('change',updateDatasetTaggerMode);
  $('#datasetLocalTaggerModel').addEventListener('change',updateLocalTaggerCalibration);
  $('#datasetNextAction').addEventListener('click',runDatasetNextAction);
  $('#datasetRunPreflight').addEventListener('click',()=>runPreflight().catch(error=>alert(error.message)));
  $('#datasetExportActiveProfile').addEventListener('click',()=>exportVersion($('#datasetDeliveryProfile').value).catch(error=>alert(error.message)));
  $('#datasetDeliveryHistory').addEventListener('click',event=>{ const button=event.target.closest('[data-export-action]'), card=event.target.closest('[data-export-version]'); if(!button||!card) return; if(button.dataset.exportAction==='reveal') revealExport(card.dataset.exportVersion).catch(error=>alert(error.message)); else copyExport(card.dataset.exportVersion,button).catch(error=>alert(error.message)); });
  $('#datasetDesk').addEventListener('click',event=>{ const button=event.target.closest('[data-origin-project]'); if(button) window.openCreativeProject?.(button.dataset.originProject).catch(error=>alert(error.message)); });
  $('#datasetWorkspaceList').addEventListener('click',event=>{ const button=event.target.closest('[data-workspace-id]'); if (button) selectWorkspace(button.dataset.workspaceId).catch(console.error); });
  ['#datasetValidity','#datasetCaptionFilter','#datasetReviewFilter','#datasetDuplicateFilter','#datasetFormatFilter','#datasetSizeFilter'].forEach(selector=>$(selector).addEventListener('change',()=>renderGrid(true)));
  $('#datasetGrid').addEventListener('click',event=>{ const card=event.target.closest('[data-dataset-index]'); if (!card) return; const item=state.pageItems[Number(card.dataset.datasetIndex)]; if (event.target.classList.contains('dataset-card-select')) { event.target.checked ? state.selected.add(item.relative_path) : state.selected.delete(item.relative_path); renderGrid(); } else if (event.target.closest('.dataset-card-preview')) openDetail(Number(card.dataset.datasetIndex)); });
  $('#datasetPreviousPage').addEventListener('click',()=>{ if (state.page<=1) return; state.page-=1; renderGrid(); $('#datasetPagination').scrollIntoView({block:'nearest'}); });
  $('#datasetNextPage').addEventListener('click',()=>{ if (state.page*workspacePageSize()>=state.visible.length) return; state.page+=1; renderGrid(); $('#datasetPagination').scrollIntoView({block:'nearest'}); });
  $('#datasetSelectVisible').addEventListener('change',event=>{ state.visible.forEach(item=>event.target.checked?state.selected.add(item.relative_path):state.selected.delete(item.relative_path)); renderGrid(); });
  $('#datasetInsertTrigger').addEventListener('click',()=>insertTriggerWord().catch(error=>{ $('#datasetReviewToolsResult').textContent=error.message; alert(error.message); }));
  $('#datasetConfirmCaptions').addEventListener('click',()=>confirmCaptionStatus().catch(error=>{ $('#datasetReviewToolsResult').textContent=error.message; alert(error.message); }));
  $('#datasetBulkTranslate').addEventListener('click',()=>queueKrea2Locale().catch(error=>{ $('#datasetReviewToolsResult').textContent=error.message; alert(error.message); }));
  $('#datasetBulkKrea2Confirm').addEventListener('click',()=>confirmKrea2Selection().catch(error=>{ $('#datasetBulkKrea2Result').textContent=error.message; alert(error.message); }));
  $('#datasetClearSelection').addEventListener('click',()=>clearDatasetSelection().catch(error=>alert(error.message)));
  compactDatasetView.addEventListener('change',()=>{ state.page=1; if (state.report) renderGrid(); });
  document.querySelectorAll('[data-bulk-status]').forEach(button=>button.addEventListener('click',()=>{ const items=(state.report?.images || []).filter(item=>state.selected.has(item.relative_path)).map(item=>({relative_path:item.relative_path,status:button.dataset.bulkStatus,selected:button.dataset.bulkStatus!=='excluded',note:item.review?.note || ''})); updateReviews(items).catch(error=>alert(error.message)); }));
  document.querySelectorAll('[data-wd14-scope]').forEach(button=>button.addEventListener('click',()=>queueWd14(button.dataset.wd14Scope).catch(error=>alert(error.message))));
  document.querySelectorAll('[data-krea2-vlm-scope]').forEach(button=>button.addEventListener('click',()=>queueKrea2VLM(button.dataset.krea2VlmScope).catch(error=>alert(error.message))));
  document.querySelectorAll('[data-source-caption-scope]').forEach(button=>button.addEventListener('click',()=>previewSourceCaptions(button.dataset.sourceCaptionScope).catch(error=>alert(error.message))));
  $('#datasetSourceCaptionApply').addEventListener('click',()=>applySourceCaptions().catch(error=>alert(error.message)));
  ['#datasetSourceCaptionProfile','#datasetSourceCaptionStatus','#datasetSourceCaptionOverwrite'].forEach(selector=>$(selector).addEventListener('change',()=>{ state.sourceCaptionPreview=null; $('#datasetSourceCaptionApply').disabled=true; $('#datasetSourceCaptionResult').textContent='设置已改变，请重新预览。'; }));
  $('#datasetBulkPreview').addEventListener('click',()=>previewBulkTags().catch(error=>alert(error.message))); $('#datasetBulkApply').addEventListener('click',()=>applyBulkTags().catch(error=>alert(error.message)));
  $('#datasetAnalytics').addEventListener('click',event=>{ const button=event.target.closest('[data-bulk-tag]'); if (button) appendBulkTag(button.dataset.bulkTag); });
  document.querySelectorAll('[data-export-profile]').forEach(button=>button.addEventListener('click',()=>exportVersion(button.dataset.exportProfile).catch(error=>alert(error.message)))); $('#datasetRollbackSnapshot').addEventListener('click',()=>rollbackSnapshot().catch(error=>alert(error.message)));
  $('#datasetRescan').addEventListener('click',()=>rescan().catch(error=>alert(error.message))); $('#datasetRemove').addEventListener('click',()=>removeWorkspace().catch(error=>alert(error.message)));
  $('#datasetDetailApprove').addEventListener('click',()=>approveDetail().catch(error=>alert(error.message)));
  $('#datasetDetailClose').addEventListener('click',()=>$('#datasetDetail').close()); $('#datasetPrevious').addEventListener('click',()=>moveDetail(-1)); $('#datasetNext').addEventListener('click',()=>moveDetail(1)); $('#datasetDetailSave').addEventListener('click',()=>saveDetail().catch(error=>alert(error.message)));
  $('#datasetDetailDraftSave').addEventListener('click',()=>saveKrea2Draft(false).catch(error=>alert(error.message))); $('#datasetDetailDraftConfirm').addEventListener('click',()=>saveKrea2Draft(true).catch(error=>alert(error.message)));
  $('#datasetFindSimilar').addEventListener('click',()=>{ const item=detailItem(); if(!item) return; $('#datasetDetail').close(); window.openSimilarImage?.(item.sha256,item.filename||item.relative_path); });
  $('#datasetCaptionMode').addEventListener('change',()=>updateCaptionMode(true));
  $('#datasetCaptionTrigger').addEventListener('input',updateCaptionMode);
  $('#datasetCaptionPreset').addEventListener('change',event=>{ $('#datasetCaptionPresetDelete').disabled=!event.target.value; if(event.target.value) applyCaptionPreset(event.target.value); });
  $('#datasetCaptionPresetSave').addEventListener('click',saveCaptionPreset);
  $('#datasetCaptionPresetDelete').addEventListener('click',deleteCaptionPreset);
  // 记住使用者的开关选择。切换交付格式会重画这份清单，
  // 不记的话每切一次就把人调好的设定清空。
  $('#datasetCaptionOptionList').addEventListener('change',event=>{ const input=event.target.closest('[data-caption-option]'); if(input) state.captionOptions[input.dataset.captionOption]=input.checked; });
  $('#datasetDetailKrea2Translate').addEventListener('click',async()=>{
    const caption=$('#datasetDetailKrea2Draft').value.trim();
    const status=$('#datasetDetailKrea2LocaleStatus');
    if(!caption){ status.textContent='草稿是空的，没有可对照的内容'; $('#datasetDetailKrea2Locale').value=''; return; }
    status.textContent='正在翻译……';
    try {
      const result=await api('/api/captions/localize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({caption})});
      $('#datasetDetailKrea2Locale').value=result.localized || '';
      const current=detailItem();
      if (current && result.localized) state.captionLocales[current.relative_path]={caption,localized:result.localized};
      status.textContent=result.localized?'仅供对照。导出的始终是英文草稿':'翻译服务没有返回结果。草稿本身不受影响';
    } catch(error) { $('#datasetDetailKrea2Locale').value=''; status.textContent=`翻译失败：${error.message}`; }
  });
  $('#datasetDetailKrea2Revise').addEventListener('click',async()=>{
    const caption=$('#datasetDetailKrea2Draft').value.trim();
    const instruction=$('#datasetDetailKrea2Revision').value.trim();
    const status=$('#datasetDetailKrea2ReviseStatus');
    if(!caption) return alert('草稿是空的。没有可改写的内容。');
    if(!instruction) return alert('请先填写修正意见。');
    const button=$('#datasetDetailKrea2Revise');
    button.disabled=true; status.textContent='正在改写……';
    try {
      const result=await api('/api/captions/revise',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({caption,instruction})});
      $('#datasetDetailKrea2Draft').value=result.revised;
      // 旧译文对应的是改写前的草稿。留着会对不上。比没有更容易误导。
      $('#datasetDetailKrea2Locale').value='';
      const revised=detailItem();
      if (revised) delete state.captionLocales[revised.relative_path];
      $('#datasetDetailKrea2LocaleStatus').textContent='草稿已改写。需要对照请重新翻译';
      status.textContent='已改写。草稿只在这里改动。按下方按钮才会保存。';
    } catch(error) {
      // 改写失败绝不能动既有草稿。那是使用者手上唯一的一份。
      status.textContent=`改写失败：${error.message}`;
    } finally { button.disabled=false; }
  });
  $('#datasetDetailTagChips').addEventListener('click',event=>{ const button=event.target.closest('[data-detail-tag]'); if (!button) return; const tag=button.dataset.detailTag, tags=$('#datasetDetailAnima').value.split(',').map(value=>value.trim()).filter(Boolean), selected=new Set(tags); selected.has(tag)?selected.delete(tag):selected.add(tag); $('#datasetDetailAnima').value=[...selected].join(', '); renderDetailTags(detailItem()).catch(console.error); });
  $('#datasetDetail').addEventListener('keydown',event=>{
    if (event.key!=='ArrowUp' && event.key!=='ArrowDown') return;
    // 对话框里有五个可输入栏位。在里面按方向键是要移动游标或换行，
    // 不是要换图——修正意见本来就是多行的，上下键必须留给它。
    const target=event.target;
    if (target && (target.isContentEditable || ['TEXTAREA','INPUT','SELECT'].includes(target.tagName))) return;
    event.preventDefault();
    moveDetail(event.key==='ArrowUp'?-1:1);
  });
  $('#datasetJobPanel').addEventListener('click',async event=>{ const button=event.target.closest('[data-job-action]'); if (!button) return; const action=button.dataset.jobAction; await api(`/api/jobs/${button.dataset.jobId}/${action}`,{method:'POST'}); startPolling(); });
  window.addEventListener('tag-language-change',()=>{ if (state.analytics) loadAnalytics().catch(console.error); if ($('#datasetDetail').open && detailItem()) renderDetailTags(detailItem()).catch(console.error); });
  window.ensureDatasetWorkspace=ensureWorkspace;
})();
</script>
"""
