from __future__ import annotations

CREATIVE_HTML = r"""
<section class="creative-page" id="creativePage" hidden>
  <div class="creative-heading">
    <div><span class="eyebrow">Soda / Creative project</span><h1>Drawing Desk</h1></div>
    <p>同一个创作项目保留七个语义槽位，再分别输出 Anima 标签版与 Krea 2 自然语言版。项目、锁定状态和参考资料都会自动保存到本机。</p>
  </div>
  <div class="creative-layout">
    <aside class="project-rail">
      <button class="rail-button primary" id="newCreativeProject">＋ 新建绘图项目</button>
      <p class="section-label">Recent projects / 最近项目</p>
      <div class="project-list" id="creativeProjectList"></div>
      <section class="rail-section">
        <p class="section-label">Local archive / 智能取材</p>
        <p class="lm-status">先从本机真实资料库返回候选，再用已加载模型补充检索词。</p>
        <button class="rail-button" id="sourceCreative">从本地库智能取材</button>
        <p class="lm-status" id="sourcingRailStatus">尚未取材</p>
      </section>
      <section class="rail-section">
        <p class="section-label">Local model / 本地辅助</p>
        <p class="lm-status" id="lmStatus">正在加载可用模型…</p>
        <select class="assist-select" id="lmModel"></select>
        <button class="rail-button" id="assistCreative" style="margin-top:7px">整理未锁定槽位</button>
        <div class="assist-proposal" id="assistProposal" hidden>
          <strong>建议预览（尚未写入）</strong><pre id="assistPreview"></pre>
          <div class="assist-proposal-actions"><button class="rail-button primary" id="applyAssist">确认应用</button><button class="rail-button" id="cancelAssist">取消</button></div>
        </div>
      </section>
      <section class="rail-section">
        <p class="section-label">Model selection / 模型选择</p>
        <p class="lm-status">文本与视觉任务可使用不同模型</p>
        <label class="model-label">文本模型</label>
        <select class="model-select" id="textModelSelect"></select>
        <label class="model-label" style="margin-top:8px">视觉模型</label>
        <select class="model-select" id="visionModelSelect"></select>
        <p class="lm-status" style="margin-top:14px">已管理的模型 / Managed models</p>
        <div class="managed-model-list" id="managedModelList"></div>
      </section>
      <section class="rail-section">
        <p class="section-label">Saved recipes / 配方</p>
        <div class="recipe-list" id="creativeRecipeList"></div>
      </section>
    </aside>
    <main class="creative-editor">
      <div class="project-head">
        <div class="creative-field"><label for="creativeTitle">项目名</label><input id="creativeTitle" maxlength="160" placeholder="例如：黄昏图书馆调查员"></div>
        <div class="creative-field"><label for="creativeSafety">成人分级</label><select id="creativeSafety"><option value="sfw">SFW</option><option value="suggestive">Suggestive</option><option value="adult">Adult</option><option value="explicit-adult">Explicit adult</option></select><p class="safety-note">只影响对应 Profile 的规避词，不改变本地资料。</p></div>
      </div>
      <p class="lineage-notice" id="lineageNotice" hidden></p>
      <section class="iteration-panel" id="iterationPanel" hidden>
        <div class="iteration-panel-head"><h2>本轮迭代对照</h2><span id="iterationVersion"></span></div>
        <p class="iteration-summary" id="iterationSummary"></p>
        <ul class="iteration-suggestions" id="iterationSuggestions"></ul>
        <div class="iteration-changes" id="iterationChanges"></div>
        <div class="iteration-panel-actions"><p id="iterationStatus">正在读取上一版…</p><button id="applyIterationSuggestions" disabled>暂无可应用建议</button></div>
      </section>
      <div class="creative-field"><label for="creativeBrief">先用中文写想法</label><textarea id="creativeBrief" maxlength="6000" placeholder="人物是谁、正在做什么、画面感觉、想突出什么……"></textarea></div>
      <section class="sourcing-panel" id="sourcingPanel" hidden>
        <div class="sourcing-panel-head"><div><h2>智能取材候选</h2><p>候选来自本机资料库；点“加入”后才会写进槽位与参考资料。</p></div><button class="sourcing-close" id="closeSourcing">CLOSE</button></div>
        <p class="sourcing-status" id="sourcingStatus">正在检索…</p>
        <div class="sourcing-groups" id="sourcingGroups"></div>
      </section>
      <section class="creative-subsection">
        <div class="creative-subsection-head"><h2>七个创作槽位</h2><span>锁定后，本地模型不会改写</span></div>
        <div class="slot-grid" id="creativeSlots"></div>
      </section>
      <section class="creative-subsection">
        <div class="creative-subsection-head"><h2>视觉与资料参考</h2><span>从提示词库或 OC 角色卡加入</span></div>
        <div class="reference-list" id="creativeReferences"></div>
      </section>
      <section class="creative-subsection">
        <div class="creative-subsection-head"><h2>结果图复盘</h2><span>图片只保存并分析在本机</span></div>
        <div class="result-review-tools">
          <label>选择结果图<input id="resultImageFile" type="file" accept="image/png,image/jpeg,image/webp"></label>
          <label>本地视觉模型<select id="visionModel"></select></label>
          <button id="uploadResultImage">导入结果图</button>
        </div>
        <p class="result-review-status" id="resultReviewStatus">导入 PNG、JPEG 或 WebP 后，可选择一张进行反推与问题诊断。</p>
        <p class="result-review-status" id="resultModelHint">正在加载视觉模型…</p>
        <div class="result-gallery" id="resultGallery"></div>
        <div class="wd14-toolbar">
          <div><strong>WD14 · ANIMA 自动打标</strong><p>只处理已精选图片；rating 仅供审核，不写入 caption。同步批量最多 24 张。</p></div>
          <label>General 阈值<input id="wd14GeneralThreshold" type="number" min="0" max="1" step="0.05" value="0.35"></label>
          <label>Character 阈值<input id="wd14CharacterThreshold" type="number" min="0" max="1" step="0.05" value="0.85"></label>
          <button id="tagSelectedDataset" disabled>打标全部精选</button>
        </div>
        <div class="dataset-export-panel">
          <label>Caption Profile<select id="datasetProfile"><option value="anima">Anima tags</option><option value="krea2">Krea 2 自然语言</option></select></label>
          <p id="datasetExportStatus">先在上方手动精选结果图；导出不会改动原图。</p>
          <button id="exportDataset" disabled>导出精选数据集 ZIP</button>
        </div>
        <section class="review-proposal" id="reviewProposal" hidden>
          <div class="review-proposal-head"><h3>本地视觉复盘</h3><span id="reviewModelName"></span></div>
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
          <label>Steps<input id="genSteps" type="number" min="1" max="200" placeholder="28"></label>
          <label>CFG<input id="genCfg" type="number" min="0" max="30" step="0.1" placeholder="5"></label>
          <label>Seed<input id="genSeed" type="text" placeholder="-1"></label>
          <label class="wide">结果图路径或链接（每行一个）<textarea id="genResults" placeholder="Windows 结果图路径、共享目录地址或图片链接"></textarea></label>
          <label class="wide">实测备注<textarea id="creativeNotes" maxlength="6000" placeholder="哪组词有效、哪里需要降低权重、下一轮修改什么……"></textarea></label>
        </div>
      </section>
    </main>
    <aside class="output-rail">
      <p class="section-label" style="color:#b9ae9f">Compiled prompt / 双版本输出</p>
      <div class="output-profile-tabs"><button class="profile-tab active" data-profile="anima">ANIMA</button><button class="profile-tab" data-profile="krea2">KREA 2</button></div>
      <div class="output-block"><header><h3>Positive prompt</h3><button class="output-copy" data-copy-output="positive">COPY</button></header><pre class="output-text" id="creativePositive">先填写一个槽位。</pre></div>
      <div class="output-block"><header><h3>Negative / Avoid</h3><button class="output-copy" data-copy-output="negative">COPY</button></header><pre class="output-text output-negative" id="creativeNegative"></pre></div>
      <ul class="warning-list" id="creativeWarnings"></ul>
      <section class="workflow-dispatch">
        <div class="workflow-dispatch-head"><strong>5060 Ti / 生成工作流</strong><span>ComfyUI</span></div>
        <label for="workflowProfile">当前 Profile 对应工作流</label>
        <select id="workflowProfile"></select>
        <label class="workflow-cost"><input id="workflowLowCost" type="checkbox" checked><span><strong>先做低成本测试</strong><small>跳过脸手精修与放大；确认构图后可关闭</small></span></label>
        <button class="creative-action primary" id="sendWorkflow" disabled>发送到 5060 Ti</button>
        <p id="workflowRunStatus">正在读取本机 Workflow Profile…</p>
        <button class="workflow-task-link" data-view="remote">查看任务队列与回传</button>
      </section>
      <input class="recipe-name" id="recipeName" maxlength="160" placeholder="配方名称（可选）">
      <div class="output-actions"><button class="creative-action primary" id="saveRecipe">保存为配方</button><button class="creative-action" id="exportCreative">导出 Anima + Krea 2 JSON</button><button class="creative-action" data-view="prompts">继续找参考资料</button></div>
      <p class="save-state" id="creativeSaveState">尚未建立项目</p>
      <section class="api-config-section">
        <div class="api-config-head"><h3>外部 API 配置</h3></div>
        
        <label class="api-config-label">BASE URL
          <div class="combobox-wrapper">
            <input id="apiBaseUrl" type="text" class="combobox-input" placeholder="输入 API 服务的基础 URL">
            <button type="button" class="combobox-trigger" id="comboboxTrigger">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
                <path d="M2 4l4 4 4-4z"/>
              </svg>
            </button>
            <div class="combobox-dropdown" id="comboboxDropdown">
              <div class="combobox-option" data-url="https://api.openai.com/v1" data-name="OpenAI">
                <span class="option-name">OpenAI</span>
                <span class="option-url">https://api.openai.com/v1</span>
              </div>
              <div class="combobox-option" data-url="https://api.anthropic.com/v1" data-name="Anthropic">
                <span class="option-name">Anthropic</span>
                <span class="option-url">https://api.anthropic.com/v1</span>
              </div>
              <div class="combobox-option" data-url="https://generativelanguage.googleapis.com/v1beta" data-name="Google Gemini">
                <span class="option-name">Google Gemini</span>
                <span class="option-url">https://generativelanguage.googleapis.com/v1beta</span>
              </div>
              <div class="combobox-option" data-url="https://api.x.ai/v1" data-name="xAI Grok">
                <span class="option-name">xAI Grok</span>
                <span class="option-url">https://api.x.ai/v1</span>
              </div>
              <div class="combobox-option" data-url="https://api.deepseek.com" data-name="DeepSeek">
                <span class="option-name">DeepSeek</span>
                <span class="option-url">https://api.deepseek.com</span>
              </div>
              <div class="combobox-option" data-url="https://open.bigmodel.cn/api/paas/v4" data-name="GLM">
                <span class="option-name">GLM</span>
                <span class="option-url">https://open.bigmodel.cn/api/paas/v4</span>
              </div>
              <div class="combobox-option" data-url="https://api.moonshot.cn/v1" data-name="Kimi">
                <span class="option-name">Kimi</span>
                <span class="option-url">https://api.moonshot.cn/v1</span>
              </div>
              <div class="combobox-option" data-url="https://api.minimax.chat/v1" data-name="MiniMax">
                <span class="option-name">MiniMax</span>
                <span class="option-url">https://api.minimax.chat/v1</span>
              </div>
              <div class="combobox-option" data-url="https://dashscope.aliyuncs.com/compatible-mode/v1" data-name="Qwen">
                <span class="option-name">Qwen</span>
                <span class="option-url">https://dashscope.aliyuncs.com/compatible-mode/v1</span>
              </div>
              <div class="combobox-option combobox-option-custom" data-url="" data-name="自定义">
                <span class="option-name">自定义</span>
                <span class="option-url">输入自定义 Base URL</span>
              </div>
            </div>
          </div>
        </label>
        
        <label class="api-config-label">API Key
          <input id="apiKey" type="password" class="api-config-input" placeholder="sk-...">
        </label>
        
        <div class="api-fetch-row">
          <label class="api-config-label">可用模型</label>
          <button class="api-fetch-models" id="fetchModelsBtn">拉取模型列表</button>
        </div>
        
        <div class="api-model-list" id="apiFetchedModelList">
          <p class="api-empty-hint">点击"拉取模型列表"获取可用模型</p>
        </div>
        
        <button class="api-save-config" id="saveApiConfigBtn">保存配置</button>
      </section>    </aside>
  </div>
</section>
"""
