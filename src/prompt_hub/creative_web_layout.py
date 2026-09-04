from __future__ import annotations

CREATIVE_HTML = r"""
<section class="creative-page" id="creativePage" hidden>
  <div class="creative-heading">
    <div><span class="eyebrow">绘图项目</span><h1>绘图创作</h1></div>
    <p>先用中文写清想法，再把人物、服装、动作、构图、场景、灯光和画风分别整理好。右侧会生成 Anima 和 Krea 2 两种提示词，并自动保存到本机。</p>
  </div>
  <div class="creative-layout">
    <aside class="project-rail">
      <button class="rail-button primary" id="newCreativeProject">＋ 新建绘图项目</button>
      <p class="section-label">最近项目</p>
      <div class="project-list" id="creativeProjectList"></div>
      <section class="rail-section">
        <p class="section-label">从资料库找参考</p>
        <p class="lm-status">根据当前想法，从本机提示词库和视觉资料里查找可用参考。</p>
        <button class="rail-button" id="sourceCreative">从提示词库找参考</button>
        <p class="lm-status" id="sourcingRailStatus">还没有查找参考</p>
      </section>
      <section class="rail-section">
        <p class="section-label">让本地模型帮忙</p>
        <p class="lm-status" id="lmStatus">正在检查 LM Studio…</p>
        <select class="assist-select" id="lmModel"></select>
        <button class="rail-button" id="assistCreative" style="margin-top:7px">用本地模型补全空白项</button>
        <div class="assist-proposal" id="assistProposal" hidden>
          <strong>建议预览（尚未写入）</strong><pre id="assistPreview"></pre>
          <div class="assist-proposal-actions"><button class="rail-button primary" id="applyAssist">确认应用</button><button class="rail-button" id="cancelAssist">取消</button></div>
        </div>
      </section>
      <section class="rail-section">
        <p class="section-label">已保存配方</p>
        <div class="recipe-list" id="creativeRecipeList"></div>
      </section>
    </aside>
    <main class="creative-editor">
      <div class="project-head">
        <div class="creative-field"><label for="creativeTitle">项目名</label><input id="creativeTitle" maxlength="160" placeholder="例如：黄昏图书馆调查员"></div>
        <div class="creative-field"><label for="creativeSafety">内容分级</label><select id="creativeSafety"><option value="sfw">普通</option><option value="suggestive">轻度成人向</option><option value="adult">成人向</option><option value="explicit-adult">明确成人向</option></select><p class="safety-note">只影响生成提示词时使用的规避词，不会隐藏或删除本地资料。</p></div>
      </div>
      <p class="lineage-notice" id="lineageNotice" hidden></p>
      <section class="project-journey" aria-labelledby="projectJourneyTitle">
        <div class="project-journey-head">
          <div><span class="section-label">当前项目做到哪一步</span><h2 id="projectJourneyTitle">从想法到数据集</h2></div>
          <button id="refreshProjectJourney" type="button">刷新状态</button>
        </div>
        <div class="project-journey-grid" id="projectJourneyGrid"><p class="project-journey-empty">正在汇总这个项目的进度……</p></div>
        <p class="project-journey-note" id="projectJourneyNote">这里显示已经完成的步骤。系统不会替您选择图片、通过审核或生成交付版本。</p>
      </section>
      <section class="iteration-panel" id="iterationPanel" hidden>
        <div class="iteration-panel-head"><h2>本轮迭代对照</h2><span id="iterationVersion"></span></div>
        <p class="iteration-summary" id="iterationSummary"></p>
        <ul class="iteration-suggestions" id="iterationSuggestions"></ul>
        <div class="iteration-changes" id="iterationChanges"></div>
        <div class="iteration-panel-actions"><p id="iterationStatus">正在读取上一版…</p><button id="applyIterationSuggestions" disabled>暂无可应用建议</button></div>
      </section>
      <div class="creative-field"><label for="creativeBrief">先用中文写想法</label><textarea id="creativeBrief" maxlength="6000" placeholder="人物是谁、正在做什么、画面感觉、想突出什么……"></textarea></div>
      <section class="sourcing-panel" id="sourcingPanel" hidden>
        <div class="sourcing-panel-head"><div><h2>找到的参考资料</h2><p>这些内容来自本机资料库。只有点击“加入”后，才会放进当前画面。</p></div><button class="sourcing-close" id="closeSourcing">关闭</button></div>
        <p class="sourcing-status" id="sourcingStatus">正在检索…</p>
        <div class="sourcing-groups" id="sourcingGroups"></div>
      </section>
      <section class="creative-subsection">
        <div class="creative-subsection-head"><h2>把画面拆成七部分</h2><span>不想被模型改动的内容可以锁定</span></div>
        <div class="slot-grid" id="creativeSlots"></div>
      </section>
      <section class="creative-subsection">
        <div class="creative-subsection-head"><h2>视觉与资料参考</h2><span>从提示词库或 OC 角色卡加入</span></div>
        <div class="reference-list" id="creativeReferences"></div>
      </section>
      <section class="creative-subsection" id="creativeResultsSection">
        <div class="creative-subsection-head"><h2>检查生成结果</h2><span>导入的图片只保存在本机</span></div>
        <div class="result-review-tools">
          <label>选择结果图<input id="resultImageFile" type="file" accept="image/png,image/jpeg,image/webp"></label>
          <label>用于看图的本地模型<select id="visionModel"></select></label>
          <button id="uploadResultImage">导入结果图</button>
        </div>
        <p class="result-review-status" id="resultReviewStatus">导入 PNG、JPEG 或 WebP 后，可选择一张进行反推与问题诊断。</p>
        <p class="result-review-status" id="resultModelHint">正在读取 LM Studio 的视觉模型状态…</p>
        <div class="result-gallery" id="resultGallery"></div>
        <div class="wd14-toolbar">
          <div><strong>WD14 · 生成 Anima 标签草稿</strong><p>只处理已经选中的图片。自动结果需要人工检查，一次最多处理 24 张。</p></div>
          <label>普通标签最低可信度<input id="wd14GeneralThreshold" type="number" min="0" max="1" step="0.05" value="0.35"></label>
          <label>角色标签最低可信度<input id="wd14CharacterThreshold" type="number" min="0" max="1" step="0.05" value="0.85"></label>
          <button id="tagSelectedDataset" disabled>为已选图片生成标签草稿</button>
        </div>
        <div class="dataset-export-panel">
          <label>导出哪种说明文字<select id="datasetProfile"><option value="anima">Anima 英文标签</option><option value="krea2">Krea 2 英文自然语言</option></select></label>
          <p id="datasetExportStatus">先在上方手动精选结果图；导出不会改动原图。</p>
          <button id="exportDataset" disabled>导出精选数据集 ZIP</button>
        </div>
        <section class="review-proposal" id="reviewProposal" hidden>
          <div class="review-proposal-head"><h3>本地视觉分析</h3><span id="reviewModelName"></span></div>
          <p class="review-summary" id="reviewSummary"></p>
          <div class="review-slot-grid" id="reviewSlots"></div>
          <div class="review-findings" id="reviewFindings"></div>
          <p class="review-warning" id="reviewWarning" hidden></p>
          <details class="review-prompts"><summary>查看反推的 Anima / Krea 2 Prompt</summary><pre id="reviewPrompts"></pre></details>
          <div class="review-actions"><button class="primary" id="branchReview">由此创建下一版</button><button id="applyReviewSlots">补充空槽位并写入备注</button><button id="applyReviewNotes">只写入实测备注</button><button id="closeReview">关闭预览</button></div>
        </section>
      </section>
      <section class="creative-subsection">
        <div class="creative-subsection-head"><h2>实测记录</h2><span>随配方与 JSON 一起保存</span></div>
        <div class="generation-grid">
          <label>图片宽度<input id="genWidth" type="number" min="256" max="4096" step="8" placeholder="1024"></label>
          <label>图片高度<input id="genHeight" type="number" min="256" max="4096" step="8" placeholder="1536"></label>
          <label>生成步数<input id="genSteps" type="number" min="1" max="200" placeholder="28"></label>
          <label>CFG<input id="genCfg" type="number" min="0" max="30" step="0.1" placeholder="5"></label>
          <label>随机种子（Seed）<input id="genSeed" type="text" placeholder="-1"></label>
          <label class="wide">结果图路径或链接（每行一个）<textarea id="genResults" placeholder="Windows 结果图路径、共享目录地址或图片链接"></textarea></label>
          <label class="wide">实测备注<textarea id="creativeNotes" maxlength="6000" placeholder="哪组词有效、哪里需要降低权重、下一轮修改什么……"></textarea></label>
        </div>
      </section>
    </main>
    <aside class="output-rail">
      <p class="section-label" style="color:#b9ae9f">两种提示词结果</p>
      <div class="output-profile-tabs"><button class="profile-tab active" data-profile="anima">ANIMA</button><button class="profile-tab" data-profile="krea2">KREA 2</button></div>
      <div class="output-block"><header><h3>正向提示词</h3><button class="output-copy" data-copy-output="positive">复制</button></header><pre class="output-text" id="creativePositive">先填写一部分画面内容。</pre></div>
      <div class="output-block"><header><h3>不希望出现</h3><button class="output-copy" data-copy-output="negative">复制</button></header><pre class="output-text output-negative" id="creativeNegative"></pre></div>
      <ul class="warning-list" id="creativeWarnings"></ul>
      <section class="workflow-dispatch">
        <div class="workflow-dispatch-head"><strong>5060 Ti / 生成工作流</strong><span>ComfyUI</span></div>
        <label for="workflowProfile">选择对应的 ComfyUI 工作流</label>
        <select id="workflowProfile"></select>
        <details class="workflow-controls">
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
        <button class="creative-action primary" id="sendWorkflow" disabled>发送到 5060 Ti</button>
        <p id="workflowRunStatus">正在读取可用的 ComfyUI 工作流…</p>
        <button class="workflow-task-link" data-view="remote">查看任务状态</button>
      </section>
      <input class="recipe-name" id="recipeName" maxlength="160" aria-label="配方名称（可选）" placeholder="配方名称（可选）">
      <div class="output-actions"><button class="creative-action primary" id="saveRecipe">保存为配方</button><button class="creative-action" id="exportCreative">导出 Anima + Krea 2 JSON</button><button class="creative-action" data-view="prompts">继续找参考资料</button></div>
      <p class="save-state" id="creativeSaveState">尚未建立项目</p>
    </aside>
  </div>
</section>
"""
