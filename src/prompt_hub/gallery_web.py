from __future__ import annotations

from prompt_hub.web_resources import read_web_asset

GALLERY_STYLES = f"<style>{read_web_asset('gallery.css')}</style>"
GALLERY_SCRIPT = f"<script>{read_web_asset('gallery.js')}</script>"

GALLERY_HTML = r"""
<section class="gallery-page" id="galleryPage" hidden aria-labelledby="galleryTitle">
  <header class="gallery-heading"><div><span class="eyebrow">作品与参考</span><h1 id="galleryTitle">本地画廊</h1></div><p>留住自己的作品，也整理值得研究的图片。选好参考用途，让它帮助下一次场景设计和画风搭配。</p></header>
  <div class="gallery-toolbar">
    <div class="gallery-kind-tabs" role="group" aria-label="图片分类"><button type="button" data-gallery-kind="all" aria-pressed="true">全部</button><button type="button" data-gallery-kind="work" aria-pressed="false">我的作品</button><button type="button" data-gallery-kind="reference" aria-pressed="false">收集参考</button></div>
    <button id="galleryRefresh" type="button">刷新</button>
  </div>
  <form id="gallerySearchForm" class="gallery-search"><label><span class="sr-only">搜索画廊</span><input id="galleryQuery" type="search" maxlength="500" placeholder="搜索名称、标签、作者或备注"></label><label><span class="sr-only">图集</span><select id="galleryAlbum"><option value="">全部图集</option></select></label><label><span class="sr-only">按底模筛选</span><select id="galleryModelFilter"><option value="">全部底模</option></select></label><label><span class="sr-only">按 LoRA 筛选</span><select id="galleryLoraFilter"><option value="">全部 LoRA</option></select></label><label class="gallery-check"><input id="galleryFavoriteOnly" type="checkbox">只看收藏</label><button type="submit">搜索</button></form>
  <details class="gallery-import-panel" id="galleryImportPanel"><summary>添加图片与目录</summary><div class="gallery-import-grid">
    <form id="galleryRootForm"><h2>映射已有目录</h2><p>原图留在原目录，不会复制、移动或修改。Hub 只保存缩略图、索引和你确认的分析。</p><label>目录路径<input id="galleryRootPath" required maxlength="2000" placeholder="当前电脑可访问的绝对目录或已挂载共享目录"></label><div class="gallery-form-pair"><label>显示名称<input id="galleryRootLabel" maxlength="160" placeholder="例如：我的 Krea 2 作品"></label><label>默认分类<select id="galleryRootKind"><option value="work">我的作品</option><option value="reference">收集参考</option></select></label></div><label class="gallery-check"><input id="galleryRootRecursive" type="checkbox" checked>包含子目录</label><button type="submit" class="gallery-primary">登记并扫描</button></form>
    <form id="galleryUploadForm"><h2>添加选中的图片</h2><p>选择少量图片加入画廊，方便收藏、备注和用于创作参考。</p><label>选择图片<input id="galleryUploadFiles" type="file" accept="image/png,image/jpeg,image/webp" multiple required></label><label>分类<select id="galleryUploadKind"><option value="reference">收集参考</option><option value="work">我的作品</option></select></label><button type="submit">添加图片</button></form>
  </div><div class="gallery-root-list" id="galleryRoots"></div><div class="gallery-job-list" id="galleryJobs"></div></details>
  <p class="gallery-status" id="galleryStatus" role="status" aria-live="polite">正在读取本地画廊…</p>
  <div class="gallery-grid" id="galleryGrid"></div>
  <nav class="gallery-pagination" aria-label="画廊分页"><button id="galleryPrevious" type="button" disabled>上一页</button><span id="galleryPageCount">0 张</span><button id="galleryNext" type="button" disabled>下一页</button></nav>
</section>
<dialog class="gallery-detail-dialog" id="galleryDetailDialog" aria-labelledby="galleryDetailTitle">
  <div class="gallery-detail-head"><div><span class="eyebrow" id="galleryDetailKind">图片</span><h2 id="galleryDetailTitle">图片详情</h2></div><div class="gallery-inline-actions"><button type="button" id="galleryDelete">删除图片</button><button id="galleryDetailClose" type="button" aria-label="关闭图片详情">×</button></div></div>
  <div class="gallery-detail-layout"><div class="gallery-detail-image"><img id="galleryDetailImage" alt="画廊图片"><p id="galleryDetailAvailability"></p><a id="galleryOpenOriginal" target="_blank" rel="noreferrer">打开原图 ↗</a></div>
    <div class="gallery-detail-fields">
      <section class="gallery-generation-panel" aria-labelledby="galleryGenerationTitle"><h3 id="galleryGenerationTitle">生成信息</h3><p class="gallery-note" id="galleryEvidenceScope"></p><div id="galleryGenerationContent"></div><ul id="galleryEvidenceWarnings" class="gallery-evidence-warnings"></ul><details id="galleryProjectSnapshot" hidden><summary>关联项目的计划设置</summary><p class="gallery-note">这是项目保存的计划，不代表这张图实际执行了这些参数。</p><pre id="galleryProjectSnapshotData"></pre></details></section>
      <form id="galleryAssetForm"><div class="gallery-form-pair"><label>名称<input id="galleryAssetTitle" maxlength="300"></label><label>分类<select id="galleryAssetKind"><option value="work">我的作品</option><option value="reference">收集参考</option></select></label></div><label class="gallery-check"><input id="galleryAssetFavorite" type="checkbox">收藏这张图</label><div class="gallery-form-pair"><label>作者<input id="galleryAssetAuthor" maxlength="300"></label><label>来源链接<input id="galleryAssetSource" type="url" maxlength="2000" placeholder="https://…"></label></div><label>标签<input id="galleryAssetTags" maxlength="3000" placeholder="逗号分隔，例如：雨夜、门框构图、暖光"></label><label>所属图集<input id="galleryAssetAlbums" maxlength="2000" placeholder="逗号分隔，可填写新图集名称"></label><label>喜欢什么 / 实测备注<textarea id="galleryAssetNote" maxlength="6000" rows="3" placeholder="记录值得参考的镜头、动作、光线，或这次搭配的效果"></textarea></label><label>关联绘图项目<select id="galleryAssetProject"><option value="">暂不关联</option></select></label><button type="submit" class="gallery-primary">保存整理</button></form>
      <section class="gallery-reference-panel"><h3>作为创作参考</h3><label>加入哪个项目<select id="galleryReferenceProject"></select></label><label>参考什么<select id="galleryReferencePurpose"><option value="style">画风</option><option value="composition">镜头与构图</option><option value="action">动作与互动</option><option value="lighting">光线</option><option value="scene">场景与空间</option><option value="all">整体参考</option></select></label><div class="gallery-inline-actions"><button type="button" id="galleryAddReference">加入参考</button><button type="button" id="galleryOpenProject">进入所选项目 →</button></div></section>
      <section class="gallery-analysis-panel"><h3>AI 拆解这张图</h3><label>看图模型<select id="galleryVisionModel"></select></label><p class="gallery-note">图片会发送给所选模型。分析先预览，确认后才保存；没有生成信息时不猜底模或 LoRA。</p><button id="galleryAnalyze" type="button">按参考用途分析</button><div id="galleryAnalysisContent"></div><button id="gallerySaveAnalysis" type="button" class="gallery-primary" hidden>确认保存这次分析</button></section>
      <details class="gallery-metadata"><summary>原始元数据与文件记录</summary><pre id="galleryMetadata"></pre></details>
    </div>
  </div><p class="gallery-status" id="galleryDetailStatus" role="status" aria-live="polite"></p>
</dialog>
<dialog class="gallery-confirm-dialog" id="galleryDeleteDialog" aria-labelledby="galleryDeleteTitle" aria-describedby="galleryDeleteDescription">
  <h2 id="galleryDeleteTitle">从 Hub 删除这张图片？</h2>
  <p id="galleryDeleteName" data-i18n-ignore></p>
  <p id="galleryDeleteDescription">将删除这张图在 Hub 中的记录、收藏、备注和分析。源文件保留；目录重扫不会重新添加，仍可手动添加。</p>
  <p class="gallery-status" id="galleryDeleteStatus" role="status" aria-live="polite"></p>
  <div class="gallery-inline-actions"><button type="button" id="galleryDeleteCancel" autofocus>取消</button><button type="button" id="galleryDeleteConfirm" class="gallery-primary">确认删除</button></div>
</dialog>
"""
