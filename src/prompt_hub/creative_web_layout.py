from __future__ import annotations

CREATIVE_HTML = r"""
<section class="creative-page" id="creativePage" hidden>
  <header class="creative-heading"><div><span class="eyebrow">绘图项目</span><h1>创作台</h1></div><p>写想法，找参考，检查提示词，再出图。</p></header>
  <div class="creative-toolbar">
    <details class="creative-project-menu" id="creativeProjectMenu"><summary>项目与配方 ▾</summary><aside class="project-rail">
      <button class="rail-button primary" id="newCreativeProject">＋ 新建绘图项目</button>
      <p class="section-label">最近项目</p>
      <div class="project-list" id="creativeProjectList"></div>
<section class="rail-section">
        <p class="section-label">已保存配方</p>
        <div class="recipe-list" id="creativeRecipeList"></div>
      </section>
</aside></details>
    <div class="creative-toolbar-title">
      <div class="project-head">
        <div class="creative-field"><label for="creativeTitle">项目名</label><input id="creativeTitle" maxlength="160" placeholder="例如：黄昏图书馆调查员"></div>
        <div class="creative-field"><label for="creativeSafety">内容分级</label><select id="creativeSafety"><option value="sfw">普通</option><option value="suggestive">轻度成人向</option><option value="adult">成人向</option><option value="explicit-adult">明确成人向</option></select><p class="safety-note">只影响生成提示词时使用的规避词，不会隐藏或删除本地资料。</p></div>
      </div>
</div>
    <div class="output-profile-tabs"><button class="profile-tab active" data-profile="anima">ANIMA</button><button class="profile-tab" data-profile="krea2">KREA 2</button></div>      <p class="save-state" id="creativeSaveState" role="status" aria-live="polite">尚未建立项目</p>

  </div>
  <details class="creative-progress"><summary id="creativeJourneySummary">项目进度</summary>      <section class="project-journey" aria-labelledby="projectJourneyTitle">
        <div class="project-journey-head">
          <div><span class="section-label">当前项目做到哪一步</span><h2 id="projectJourneyTitle">从想法到数据集</h2></div>
          <button id="refreshProjectJourney" type="button">刷新状态</button>
        </div>
        <div class="project-journey-grid" id="projectJourneyGrid"><p class="project-journey-empty">正在汇总这个项目的进度……</p></div>
        <p class="project-journey-note" id="projectJourneyNote">这里显示已经完成的步骤。系统不会替您选择图片、通过审核或生成交付版本。</p>
      </section>
</details>
  <nav class="creative-stage-tabs" role="tablist" aria-label="创作步骤">
    <button type="button" id="creativeDesignTab" role="tab" aria-selected="true" aria-controls="creativeDesignStage" data-creative-stage="design">画面与提示词</button>
    <button type="button" id="creativeGenerationTab" role="tab" aria-selected="false" aria-controls="creativeGenerationStage" data-creative-stage="generation" tabindex="-1">出图设置</button>
    <button type="button" id="creativeReviewTab" role="tab" aria-selected="false" aria-controls="creativeReviewStage" data-creative-stage="review" tabindex="-1">结果复盘</button>
  </nav>
  <div class="creative-layout">
    <main class="creative-editor">
            <p class="lineage-notice" id="lineageNotice" hidden></p>

      <section id="creativeDesignStage" role="tabpanel" aria-labelledby="creativeDesignTab" data-creative-panel="design">
      <div class="creative-field"><label for="creativeBrief">先用中文写想法</label><textarea id="creativeBrief" maxlength="6000" placeholder="人物是谁、正在做什么、画面感觉、想突出什么……"></textarea></div>
      <div class="creative-quick-actions"><button id="generateScenePlans" type="button" class="scene-primary">帮我设计场景</button><button class="rail-button" id="sourceCreative">找提示词参考</button><button type="button" data-view="gallery">选参考图</button></div>
      <div class="creative-workflow-summary"><span id="creativeWorkflowSummary">尚未选择工作流</span><button type="button" data-creative-stage-link="generation">选择工作流 →</button></div>

      <details class="scene-design-panel" id="sceneDesignOptions"><summary>场景设计选项与方案</summary><div class="creative-details-body">
        <div class="creative-subsection-head"><div><span class="section-label">01 · 设计画面</span><h2 id="sceneDesignTitle">让想法变成一个具体瞬间</h2></div></div>
        <p class="scene-intro">AI 会给出不同的事件、镜头与画幅方案。先选打动你的方向，再确认写入；角色和画风可以在下方锁定。</p>
        <div class="scene-request-controls"><label>这次更想要什么<input id="sceneInstruction" maxlength="2000" placeholder="例如：更日常、强调人物关系、保留画风但换镜头"></label><label>画幅方向<select id="sceneCanvasDirection"><option value="">由场景决定</option><option value="landscape">横幅</option><option value="portrait">竖幅</option><option value="square">方形</option></select></label></div>
        <label class="scene-check"><input id="sceneCanvasLocked" type="checkbox">保留当前宽高，让 AI 按这个画幅设计</label>
        <p id="scenePlanStatus" class="scene-status" role="status" aria-live="polite">采用已有模型选择；先写一点想法，也可以从画廊加入参考。</p>
        <div id="scenePlanCards" class="scene-plan-cards"></div>
        <section id="sceneApplyPreview" class="scene-apply-preview" hidden aria-labelledby="sceneApplyTitle">
          <div class="scene-preview-head"><h3 id="sceneApplyTitle">采用前确认</h3><button id="closeScenePreview" type="button">关闭</button></div>
          <div id="sceneApplyContent"></div>
          <fieldset class="scene-apply-mode"><legend>如何写入画面方案</legend><label><input name="sceneApplyMode" value="empty" type="radio" checked>补充当前项目的空白项</label><label><input name="sceneApplyMode" value="branch" type="radio">创建下一版，更新未锁定内容</label></fieldset>
          <label class="scene-check"><input id="sceneApplyResolution" type="checkbox" checked>一起采用建议的生成宽高</label>
          <p id="sceneApplyImpact" class="scene-status"></p><button id="confirmScenePlan" type="button" class="scene-primary">确认采用</button>
        </section>
      </div></details>
      <details class="style-advice-panel" id="styleAdviceOptions"><summary>画风与 LoRA 搭配建议</summary><div class="creative-details-body">
        <div class="creative-subsection-head"><div><span class="section-label">02 · 选择画风</span><h2 id="styleAdviceTitle">搭配本地画风与 LoRA</h2></div><button id="generateStyleAdvice" type="button">帮我选搭配</button></div>
        <label class="creative-field" for="styleGoal">想要的视觉效果<input id="styleGoal" maxlength="2000" placeholder="例如：有体积、环境光自然，保留角色辨识度"></label>
        <p class="scene-intro">沿用“出图设置”中所选底模工作流，从已有 LoRA 中找少量搭配。没有依据的用途或权重会标为未知、待测试。</p>
        <p id="styleAdviceStatus" class="scene-status" role="status" aria-live="polite">先在“出图设置”选择 ComfyUI 工作流；可从画廊加入画风参考。</p>
        <div id="styleAdviceCards" class="style-advice-cards"></div>
        <section id="styleApplyPreview" class="scene-apply-preview" hidden><div class="scene-preview-head"><h3>确认这组搭配</h3><button id="closeStylePreview" type="button">关闭</button></div><div id="styleApplyContent"></div><p class="scene-status">采用后请先小图测试，并在实测记录中保存效果。</p><button id="confirmStyleAdvice" type="button" class="scene-primary">确认采用到所选工作流</button></section>
      </div></details>
      <section class="sourcing-panel" id="sourcingPanel" hidden>
        <div class="sourcing-panel-head"><div><h2>找到的参考资料</h2><p>这些内容来自本机资料库。只有点击“加入”后，才会放进当前画面。</p></div><button class="sourcing-close" id="closeSourcing">关闭</button></div>
        <p class="sourcing-status" id="sourcingStatus">正在检索…</p>
        <div class="sourcing-groups" id="sourcingGroups"></div>
      </section>
      <details class="creative-subsection creative-slot-details" id="creativeSlotDetails"><summary>细化画面 · 角色、服装、动作、构图、场景、灯光、画风</summary><div class="creative-details-body">
        <div class="creative-subsection-head"><h2>把画面拆成七部分</h2><span>不想被模型改动的内容可以锁定</span></div>
        <div class="tag-completion-banner" id="tagCompletionBanner" hidden></div>
        <div class="slot-grid" id="creativeSlots"></div>
        <div class="tag-autocomplete-dropdown" id="tagAutocompleteDropdown" hidden></div>
      </div></details>
      <section class="creative-subsection">
        <div class="creative-subsection-head"><h2>已选参考</h2><button type="button" data-view="gallery">从画廊选参考 →</button></div>
        <div class="reference-list" id="creativeReferences"></div>
      </section>

        <details class="creative-ai-settings"><summary>AI 助手与模型设置 <span id="creativeAiSummary">正在检查</span></summary><section class="rail-section">
        <p class="section-label">AI补全</p>
        <p class="lm-status" id="lmStatus">正在检查 LM Studio 和外部模型…</p>
        <select class="assist-select" id="lmModel"></select>
        <button class="rail-button" id="assistCreative" style="margin-top:7px">用所选模型补全空白项</button>
        <div class="assist-proposal" id="assistProposal" hidden>
          <strong>建议预览（尚未写入）</strong><pre id="assistPreview"></pre>
          <div class="assist-proposal-actions"><button class="rail-button primary" id="applyAssist">确认应用</button><button class="rail-button" id="cancelAssist">取消</button></div>
        </div>
        <p class="lm-status">外部模型在“设备连接 › 模型接入”里配置，可保存多组端点并勾选启用模型。</p>
        <button class="rail-button" id="openModelEndpointSettings" type="button">打开模型接入</button>
        <button class="rail-button" id="reloadCreativeResources" type="button">重新读取模型与清单</button>
</section><p class="lm-status" id="sourcingRailStatus">还没有查找参考</p></details>
      </section>
      <section id="creativeGenerationStage" role="tabpanel" aria-labelledby="creativeGenerationTab" data-creative-panel="generation" hidden>
        <h2>画幅与采样</h2><p class="scene-intro">画面方案推荐的宽高也可以在这里调整。</p><div class="generation-grid">
          <label>图片宽度<input id="genWidth" type="number" min="256" max="4096" step="8" placeholder="1024"></label>
          <label>图片高度<input id="genHeight" type="number" min="256" max="4096" step="8" placeholder="1536"></label>
          <label>生成步数<input id="genSteps" type="number" min="1" max="200" placeholder="28"></label>
          <label>CFG<input id="genCfg" type="number" min="0" max="30" step="0.1" placeholder="5"></label>
          <label>随机种子（Seed）<input id="genSeed" type="text" placeholder="-1"></label>
</div>
      <section class="workflow-dispatch">
        <div class="workflow-dispatch-head"><strong><span data-remote-device-name>__PROMPT_HUB_DEVICE_NAME_HTML__</span> / 生成工作流</strong><span>ComfyUI</span></div>
        <label for="workflowProfile">选择对应的 ComfyUI 工作流</label>
        <select id="workflowProfile"></select>
        <details class="workflow-controls" open>
          <summary>模型、LoRA 与采样参数</summary>
          <div class="workflow-control-list" id="workflowControlList"></div>
          <div class="workflow-pair"><label>采样器（Sampler）<select id="workflowSampler"></select></label><label>调度器（Scheduler）<select id="workflowScheduler"></select></label></div>
          <p class="workflow-lora-defaults" id="workflowDefaultLoras"></p>
          <div class="workflow-lora-rows" id="workflowLoraRows"></div>
          <button class="workflow-add-lora" id="workflowAddLora" type="button">＋ 添加测试 LoRA</button>
          <section class="workflow-lora-picker" id="workflowLoraPicker" hidden>
            <div class="workflow-lora-picker-head"><div><strong>选择 LoRA</strong><span>搜索或按 Windows 文件夹筛选</span></div><button id="workflowLoraPickerClose" type="button" aria-label="关闭 LoRA 选择器">×</button></div>
            <div class="workflow-lora-filter"><input id="workflowLoraSearch" type="search" placeholder="名称、路径、触发词或标签"><select id="workflowLoraFolder" aria-label="LoRA 文件夹"></select></div>
            <p id="workflowLoraPickerStatus"></p>
            <div class="workflow-lora-results" id="workflowLoraResults"></div>
          </section>
          <p id="workflowControlHint">正在读取 Windows 模型与 LoRA 清单…</p>
        </details>
        <label class="workflow-cost"><input id="workflowLowCost" type="checkbox" checked><span><strong>先做低成本测试</strong><small>跳过脸手精修与放大；确认构图后可关闭</small></span></label>
        <button class="creative-action primary" id="sendWorkflow" disabled>发送到 <span data-remote-device-name>__PROMPT_HUB_DEVICE_NAME_HTML__</span></button>
        <p id="workflowRunStatus">正在读取可用的 ComfyUI 工作流…</p>
        <button class="workflow-task-link" data-view="remote">查看任务状态</button>
      </section>

      </section>
      <section id="creativeReviewStage" role="tabpanel" aria-labelledby="creativeReviewTab" data-creative-panel="review" hidden>
      <section class="iteration-panel" id="iterationPanel" hidden>
        <div class="iteration-panel-head"><h2>本轮迭代对照</h2><span id="iterationVersion"></span></div>
        <p class="iteration-summary" id="iterationSummary"></p>
        <ul class="iteration-suggestions" id="iterationSuggestions"></ul>
        <div class="iteration-changes" id="iterationChanges"></div>
        <div class="iteration-panel-actions"><p id="iterationStatus">正在读取上一版…</p><button id="applyIterationSuggestions" disabled>暂无可应用建议</button></div>
      </section>
      <section class="creative-subsection" id="creativeResultsSection">
        <div class="creative-subsection-head"><h2>检查生成结果</h2><span>导入的图片只保存在本机</span></div>
        <div class="result-review-tools">
          <label>选择结果图<input id="resultImageFile" type="file" accept="image/png,image/jpeg,image/webp"></label>
          <label>用于看图的模型<select id="visionModel"></select></label>
          <button id="uploadResultImage">导入结果图</button>
        </div>
        <p class="result-review-status" id="resultReviewStatus">导入 PNG、JPEG 或 WebP 后，可选择一张进行反推与问题诊断。</p>
        <p class="result-review-status" id="resultModelHint">正在读取可用的视觉模型…</p>
        <div class="result-gallery" id="resultGallery"></div>
<details class="creative-dataset-tools"><summary>精选、打标与导出数据集</summary>        <div class="wd14-toolbar">
          <div class="wd14-toolbar-intro"><strong>WD14 · 生成 Anima 标签草稿</strong><p>只处理已经选中的图片。自动结果需要人工检查，一次最多处理 24 张。</p></div>
          <label>打标模型<select id="wd14TaggerMode"><option value="wd14">WD14 本地模型</option><option value="model">使用模型</option></select></label>
          <label id="wd14TaggerModelWrap" hidden>用于打标的模型<select id="wd14TaggerModel"><option value="">正在读取视觉模型……</option></select></label>
          <div class="wd14-thresholds" id="wd14Thresholds"><p class="result-review-status" id="wd14Calibration">正在读取打标模型校准值……</p><button type="button" class="optional-model-link" data-open-optional-models="wd-swinv2-tagger-v3">本地模型安装与状态 →</button></div>
          <button id="tagSelectedDataset" disabled>为已选图片生成标签草稿</button>
        </div>
        <p class="result-review-status" id="wd14TaggerHint">默认使用 WD14；也可以改用已连接的视觉模型生成 Booru 标签草稿。</p>
        <div class="dataset-export-panel">
          <label>导出哪种说明文字<select id="datasetProfile"><option value="anima">Anima 英文标签</option><option value="krea2">Krea 2 英文自然语言</option></select></label>
          <p id="datasetExportStatus">先在上方手动精选结果图；导出不会改动原图。</p>
          <button id="exportDataset" disabled>导出精选数据集 ZIP</button>
        </div>
</details>
        <section class="review-proposal" id="reviewProposal" hidden>
          <div class="review-proposal-head"><h3>视觉模型分析</h3><span id="reviewModelName"></span></div>
          <p class="review-summary" id="reviewSummary"></p>
          <h3 class="review-observed-title">实际观察</h3>
          <div class="review-slot-grid" id="reviewSlots"></div>
          <section class="review-next-slots" id="reviewNextSlots" hidden><h3>下一版槽位建议</h3><p>确认采用的是下面的建议，实际观察仅用于对照。锁定项保留；当前项目只补充空白项。</p><div id="reviewNextSlotList"></div></section>
          <section id="sceneReviewChecks" class="scene-review-checks" hidden><h3>对照画面方案</h3><p>实际观察与下一轮建议分别展示，建议不会自动写入。</p><div id="sceneReviewCheckList"></div></section>
          <div class="review-findings" id="reviewFindings"></div>
          <p class="review-warning" id="reviewWarning" hidden></p>
          <details class="review-prompts"><summary>查看反推的 Anima / Krea 2 Prompt</summary><pre id="reviewPrompts"></pre></details>
          <div class="review-actions"><button class="primary" id="branchReview">由此创建下一版</button><button id="applyReviewSlots">补充空槽位并写入备注</button><button id="applyReviewNotes">只写入实测备注</button><button id="closeReview">关闭预览</button></div>
        </section>
      </section>

        <details class="creative-test-notes"><summary>实测备注与结果路径</summary><div class="generation-grid">          <label class="wide">结果图路径或链接（每行一个）<textarea id="genResults" placeholder="Windows 结果图路径、共享目录地址或图片链接"></textarea></label>
          <label class="wide">实测备注<textarea id="creativeNotes" maxlength="6000" placeholder="哪组词有效、哪里需要降低权重、下一轮修改什么……"></textarea></label>
</div></details>
      </section>
    </main>
    <aside class="output-rail" id="creativeOutputRail">
      <button type="button" class="creative-preview-toggle" id="creativePreviewToggle" aria-expanded="false" aria-controls="creativePreviewContent">查看最终提示词 ▾</button>
      <div id="creativePreviewContent">
      <p class="section-label" style="color:#b9ae9f">最终提示词</p>

      <div class="output-block"><div class="output-block-head"><h3>正向提示词</h3><button class="output-copy" data-copy-output="positive">复制</button></div><pre class="output-text" id="creativePositive">先填写一部分画面内容。</pre></div>
      <div class="output-block"><div class="output-block-head"><h3>不希望出现</h3><button class="output-copy" data-copy-output="negative">复制</button></div><pre class="output-text output-negative" id="creativeNegative"></pre></div>
      <ul class="warning-list" id="creativeWarnings"></ul>

        <button type="button" class="creative-action primary" data-creative-stage-link="generation">前往出图设置 →</button>
        <details class="creative-recipe-tools"><summary>保存配方与导出</summary>      <input class="recipe-name" id="recipeName" maxlength="160" aria-label="配方名称（可选）" placeholder="配方名称（可选）">
      <div class="output-actions"><button class="creative-action primary" id="saveRecipe">保存为配方</button><button class="creative-action" id="exportCreative">导出 Anima + Krea 2 JSON</button><button class="creative-action" data-view="prompts">继续找参考资料</button></div>
</details>
      </div>
    </aside>
  </div>
</section>
<div class="oc-seed-modal" id="ocSeedModal" hidden>
    <button class="oc-seed-backdrop" type="button" data-oc-seed-close aria-label="关闭角色创作选择"></button>
    <section class="oc-seed-dialog" role="dialog" aria-modal="true" aria-labelledby="ocSeedTitle" tabindex="-1">
      <header class="oc-seed-head">
        <div><span class="section-label">OC Manager · 创作接入</span><h2 id="ocSeedTitle">选择这次要引用的角色资料</h2></div>
        <button type="button" data-oc-seed-close aria-label="关闭">×</button>
      </header>
      <p class="oc-seed-summary" id="ocSeedSummary">正在读取角色资料…</p>
      <div class="oc-seed-grid">
        <fieldset><legend>画面方向</legend><label class="oc-seed-radio"><input type="radio" name="ocSeedView" value="front" checked><span>正面</span></label><label class="oc-seed-radio"><input type="radio" name="ocSeedView" value="back"><span>背面</span></label></fieldset>
        <fieldset><legend>内容层级</legend><label class="oc-seed-radio"><input type="radio" name="ocSeedRating" value="sfw" checked><span>SFW</span></label><label class="oc-seed-radio"><input id="ocSeedNsfw" type="radio" name="ocSeedRating" value="nsfw"><span>NSFW</span></label></fieldset>
        <label class="oc-seed-toggle"><input id="ocSeedAppearance" type="checkbox" checked><span><strong>引用角色外观</strong><small>放入“角色”槽位；缺少分层外观时保留基本身份</small></span></label>
        <label class="oc-seed-select"><span>服装预设</span><select id="ocSeedOutfit"><option value="">不引用服装</option></select></label>
        <label class="oc-seed-toggle"><input id="ocSeedStory" type="checkbox"><span><strong>引用角色背景</strong><small>追加到创作想法，不写进画风</small></span></label>
        <label class="oc-seed-toggle"><input id="ocSeedGallery" type="checkbox"><span><strong>引用角色图库</strong><small>作为远程视觉参考，不下载原图</small></span></label>
        <label class="oc-seed-toggle"><input id="ocSeedWorld" type="checkbox"><span><strong>引用世界观</strong><small>把同世界 lore 追加到创作上下文</small></span></label>
        <label class="oc-seed-toggle"><input id="ocSeedRelationships" type="checkbox"><span><strong>引用角色关系</strong><small>仅记录关系事实，不当作视觉标签</small></span></label>
        <label class="oc-seed-toggle"><input id="ocSeedTimeline" type="checkbox"><span><strong>引用时间线</strong><small>把选角相关经历追加到创作上下文</small></span></label>
      </div>
      <section class="oc-seed-prompts">
        <div><strong>Prompt 快照（可选）</strong><small>逐条选择；只写入 OC 引用记录，不自动归类为画风</small></div>
        <div id="ocSeedPromptList"></div>
      </section>
      <section class="oc-seed-preview"><strong>将写入的外观与服装</strong><p id="ocSeedPreview">没有可用的分层外观。</p></section>
      <p class="oc-seed-note" id="ocSeedNote">已锁定的槽位不会被覆盖。</p>
      <footer class="oc-seed-actions"><button type="button" data-oc-seed-close>取消</button><button class="primary" id="applyOcSeed" type="button">确认并进入创作台</button></footer>
    </section>
  </div>
"""
