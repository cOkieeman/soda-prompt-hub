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
        <p class="lm-status" id="lmStatus">正在检查 LM Studio…</p>
        <select class="assist-select" id="lmModel"></select>
        <button class="rail-button" id="assistCreative" style="margin-top:7px">整理未锁定槽位</button>
        <div class="assist-proposal" id="assistProposal" hidden>
          <strong>建议预览（尚未写入）</strong><pre id="assistPreview"></pre>
          <div class="assist-proposal-actions"><button class="rail-button primary" id="applyAssist">确认应用</button><button class="rail-button" id="cancelAssist">取消</button></div>
        </div>
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
        <p class="result-review-status" id="resultModelHint">正在读取 LM Studio 的视觉模型状态…</p>
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
      <input class="recipe-name" id="recipeName" maxlength="160" placeholder="配方名称（可选）">
      <div class="output-actions"><button class="creative-action primary" id="saveRecipe">保存为配方</button><button class="creative-action" id="exportCreative">导出 Anima + Krea 2 JSON</button><button class="creative-action" data-view="prompts">继续找参考资料</button></div>
      <p class="save-state" id="creativeSaveState">尚未建立项目</p>
    </aside>
  </div>
</section>
"""
