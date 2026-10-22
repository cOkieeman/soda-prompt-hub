(() => {
  const q = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
  const state = {projects: [], project: null, page: null, version: null, ai: null, translation: null, character: null, tasks: new Map(), busy: false, loadRun: 0, deletePage: false};
  const root = '/api/storyboard';
  const projectId = item => item?.id || item?.project_id || '';
  const pageId = item => item?.id || item?.page_id || '';
  const projectUrl = () => `${root}/projects/${encodeURIComponent(projectId(state.project))}`;
  const pageUrl = () => `${projectUrl()}/pages/${encodeURIComponent(pageId(state.page))}`;
  const recordList = (value, keys = ['results', 'projects', 'pages', 'items']) => Array.isArray(value) ? value : keys.map(key => value?.[key]).find(Array.isArray) || [];
  const pretty = value => JSON.stringify(value, null, 2);

  async function api(url, body, method) {
    const options = body === undefined ? {} : {method: method || 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)};
    if (method) options.method = method;
    return window.fetchJsonWithTimeout(url, options, 120000);
  }
  function message(text) { q('#storyboardStatus').textContent = text; }
  function showJson(selector, value) { const element = q(selector); element.textContent = pretty(value); element.hidden = false; }
  function safeUrl(value, {editor = false} = {}) {
    if (!String(value || '').trim()) return '';
    try {
      const url = new URL(String(value || ''), window.location.origin);
      if (editor) return url.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname) ? url.href : '';
      return url.origin === window.location.origin && ['http:', 'https:'].includes(url.protocol) ? url.href : '';
    } catch { return ''; }
  }
  function sketchUrl(item) {
    const href = safeUrl(item?.preview_url || item?.thumbnail_url || item?.draft_url || `${projectUrl()}/pages/${encodeURIComponent(pageId(item))}/preview.png`);
    if (!href) return '';
    const url = new URL(href);
    if (item?.version) url.searchParams.set('v', String(item.version));
    return url.href;
  }
  function warnings(items) {
    const values = recordList(items, ['warnings', 'errors', 'infos']);
    q('#storyboardWarnings').replaceChildren(...values.map(value => { const p = document.createElement('p'); p.textContent = typeof value === 'string' ? value : pretty(value); return p; }));
  }
  async function perform(action) {
    if (state.busy) return;
    state.busy = true;
    q('#storyboardPage').inert = true;
    q('#storyboardPage').setAttribute('aria-busy', 'true');
    try { await action(); } catch (error) { message(error.message || '操作未完成，请重试。'); if (q('#storyboardDeleteDialog').open) q('#storyboardDeleteStatus').textContent = error.message; }
    finally { state.busy = false; q('#storyboardPage').inert = false; q('#storyboardPage').setAttribute('aria-busy', 'false'); }
  }
  function clearPreviews() {
    state.ai = null; state.translation = null;
    ['#storyboardAiPreview', '#storyboardAiApply', '#storyboardAiCandidateLabel', '#storyboardTranslationPreview', '#storyboardTranslationApply'].forEach(selector => { q(selector).hidden = true; });
    q('#storyboardAiSummary').textContent = '';
  }
  function renderProjects() {
    q('#storyboardProjectList').innerHTML = state.projects.length ? state.projects.map(item => `<button class="storyboard-project-button" type="button" data-storyboard-project="${esc(projectId(item))}" aria-pressed="${projectId(state.project) === projectId(item)}"><strong data-i18n-ignore>${esc(item.name || item.title || item.project?.title || projectId(item))}</strong><small>${esc(item.page_count ?? item.pages?.length ?? 0)} 页</small></button>`).join('') : '<p class="storyboard-note">还没有分镜项目。可以新建，或导入已有分镜包。</p>';
  }
  function renderPages() {
    const pages = recordList(state.project?.pages);
    q('#storyboardPageList').innerHTML = pages.length ? pages.map(item => `<button class="storyboard-page-card" type="button" data-storyboard-page="${esc(pageId(item))}" aria-pressed="${pageId(state.page) === pageId(item)}"><img src="${esc(sketchUrl(item))}" alt="${esc(item.title || item.name || pageId(item))} 分镜草稿" loading="lazy"><strong data-i18n-ignore>${esc(item.title || item.name || pageId(item))}</strong><span>${esc(item.panel_count ?? item.panels?.length ?? '—')} 格</span></button>`).join('') : '<p class="storyboard-note">项目还没有页面。先添加空白页，再打开编辑器或用 AI 拆格。</p>';
  }
  function renderCharacters() {
    const characters = state.project?.characters || {};
    const values = Array.isArray(characters) ? characters : Object.entries(characters).map(([id, character]) => ({id, ...character}));
    q('#storyboardCharacters').textContent = values.length ? `已保存角色：${values.map(item => item.name || item.id).join('、')}` : '尚未保存角色卡。';
  }
  function renderResults(data) {
    const results = recordList(data?.results || data?.renders || data?.production?.renders || []);
    q('#storyboardResults').innerHTML = results.length ? results.map(item => {
      const id = item.result_id || item.render_id || item.id || item.asset_id;
      const image = safeUrl(item.thumbnail_url || item.image_url || item.original_url || (item.asset_id ? `/api/comfy-results/${encodeURIComponent(item.asset_id)}/thumbnail` : ''));
      return `<article class="storyboard-result">${image ? `<a href="${esc(safeUrl(item.image_url || item.original_url) || image)}" target="_blank" rel="noreferrer"><img src="${esc(image)}" alt="分镜候选图" loading="lazy"></a>` : '<p>图片已回收，可到出图页查看。</p>'}<p data-i18n-ignore>${esc(item.filename || item.name || id || '候选图')}</p>${item.selected || item.picked ? '<strong>已选为本页成图</strong>' : id ? `<button class="ui-btn" type="button" data-storyboard-pick="${esc(id)}">选为本页成图</button>` : ''}</article>`;
    }).join('') : '<p>尚无候选图。投递后点击“回收任务结果”，也可到出图页查看任务与复盘。</p>';
  }
  async function loadPage(id) {
    clearPreviews();
    const data = await api(`${projectUrl()}/pages/${encodeURIComponent(id)}`);
    state.page = data.page || data;
    state.version = data.version;
    q('#storyboardPageDetail').hidden = false;
    q('#storyboardPageTitle').textContent = state.page.title || state.page.name || pageId(state.page);
    q('#storyboardPageSketch').src = sketchUrl({...state.page, preview_url: data.preview_url, version: state.version || Date.now()});
    q('#storyboardPageSummary').textContent = `${state.page.canvas_width || 1024} × ${state.page.canvas_height || 1536}，${state.page.panels?.length || 0} 格。${state.page.description || ''}`;
    q('#storyboardStory').value = state.page.description || '';
    q('#storyboardTranslationStatus').textContent = '点击“检查待翻译内容”查看缺失或过期的英文译文。';
    q('#storyboardExportPage').href = `${projectUrl()}/export?page_id=${encodeURIComponent(id)}`;
    q('#storyboardExportProject').href = q('#storyboardExportPage').href;
    q('#storyboardExportProject').setAttribute('aria-disabled', 'false');
    q('#storyboardCompilePreview').textContent = '页面已重新读取，请重新校验或编译。';
    const task = data.task || data.last_task || state.page.production?.hub_task;
    if (task?.task_id) state.tasks.set(`${projectId(state.project)}/${id}`, task);
    const savedTask = state.tasks.get(`${projectId(state.project)}/${id}`);
    q('#storyboardTaskStatus').textContent = savedTask ? `任务已登记：${savedTask.task_id}。完成后回收结果。` : '';
    warnings(data.warnings || []); renderPages(); renderResults(data);
  }
  async function loadProject(id, preferredPage) {
    const data = await api(`${root}/projects/${encodeURIComponent(id)}`);
    state.project = {id, ...data}; state.page = null; state.version = null; state.character = null; clearPreviews();
    q('#storyboardWorkspace').hidden = false; q('#storyboardEmpty').hidden = true; q('#storyboardPageDetail').hidden = true;
    q('#storyboardOcPreview').hidden = true; q('#storyboardOcApply').hidden = true;
    q('#storyboardProjectTitle').textContent = data.name || data.title || data.project?.title || data.project?.name || id;
    q('#storyboardProjectMeta').textContent = `分镜项目，${recordList(data.pages).length} 页。文件保存在 Hub 的个人资料目录。`;
    q('#storyboardExportProject').removeAttribute('href'); q('#storyboardExportProject').setAttribute('aria-disabled', 'true');
    renderProjects(); renderPages(); renderCharacters();
    const pages = recordList(data.pages);
    const target = pages.find(item => pageId(item) === preferredPage) || pages[0];
    if (target) await loadPage(pageId(target));
    message('项目已读取。可以调整页面，或导出分镜包。');
  }
  async function loadProjects(preferredProject, preferredPage) {
    state.projects = recordList(await api(`${root}/projects`)); renderProjects();
    const target = state.projects.find(item => projectId(item) === (preferredProject || projectId(state.project)));
    if (target) await loadProject(projectId(target), preferredPage || pageId(state.page));
    else { state.project = null; state.page = null; q('#storyboardWorkspace').hidden = true; q('#storyboardEmpty').hidden = false; renderProjects(); }
  }
  function populate(selector, items, id, label, emptyText) {
    const element = q(selector), previous = element.value;
    element.replaceChildren(...(items.length ? items.map(item => new Option(label(item), id(item))) : [new Option(emptyText, '')]));
    if (items.some(item => String(id(item)) === previous)) element.value = previous;
  }
  async function loadResources() {
    const resources = await Promise.allSettled([api('/api/caption-assist'), api('/api/remote-nodes'), api('/api/oc-manager/characters?limit=50')]);
    const [models, nodes, characters] = resources;
    populate('#storyboardAiModel', models.status === 'fulfilled' ? recordList(models.value.options) : [], item => item.id, item => item.name || item.label || item.id, '先到设备连接启用模型');
    populate('#storyboardOcModel', [{id: '', name: '仅映射已有资料'}, ...(models.status === 'fulfilled' ? recordList(models.value.options) : [])], item => item.id, item => item.name || item.label || item.id, '仅映射已有资料');
    if (models.status === 'fulfilled' && models.value.connection_id) q('#storyboardAiModel').value = models.value.connection_id;
    populate('#storyboardNode', nodes.status === 'fulfilled' ? recordList(nodes.value).filter(item => item.enabled !== false) : [], item => item.node_id || item.id, item => item.label || item.node_id || item.id, '先到设备连接配置 Worker');
    populate('#storyboardOc', characters.status === 'fulfilled' ? recordList(characters.value) : [], item => item.character_id || item.id, item => item.name || item.character_id, '先在角色库导入 OC');
    const failed = resources.filter(item => item.status === 'rejected');
    if (failed.length) message('项目已读取；部分模型、设备或角色选项暂不可用，可点击“刷新项目”重试。');
  }
  function connectionId() { const value = q('#storyboardAiModel').value; if (!value) throw new Error('请先在“设备连接 → 模型服务”启用一个模型。'); return value; }
  function pageRequired() { if (!state.page) throw new Error('请先添加并选择一个分镜页。'); }
  function bind(selector, action, event = 'click') { q(selector).addEventListener(event, evt => { evt.preventDefault(); perform(() => action(evt)); }); }

  bind('#storyboardRefresh', async () => { await loadProjects(); await loadResources(); });
  bind('#storyboardCreateForm', async () => { const data = await api(`${root}/projects`, {name: q('#storyboardProjectName').value.trim()}); q('#storyboardCreateForm').reset(); await loadProjects(projectId(data)); }, 'submit');
  bind('#storyboardCreatePageForm', async () => { const name = q('#storyboardPageName').value.trim(); const data = await api(`${projectUrl()}/pages`, {name, title: name}); q('#storyboardCreatePageForm').reset(); await loadProjects(projectId(state.project), pageId(data.page || data)); }, 'submit');
  bind('#storyboardImportForm', async () => {
    const file = q('#storyboardImportFile').files[0]; if (!file) return;
    if (file.size > 16 * 1024 * 1024) throw new Error('分镜文件不能超过 16 MiB。');
    const text = await file.text();
    let content = text;
    if (/\.json$/i.test(file.name)) { try { content = JSON.parse(text); } catch { throw new Error('JSON 文件无法读取，请检查文件格式。'); } }
    const existing = q('#storyboardImportTarget').value === 'current';
    if (existing && !state.project) throw new Error('请先选择要导入的项目。');
    const targetProject = projectId(state.project);
    const data = await api(existing ? `${projectUrl()}/import` : `${root}/import`, existing ? {content} : {content, name: file.name.replace(/\.(storyboard\.)?(json|md|txt)$/i, '').slice(0, 160)});
    await loadProjects(existing ? targetProject : projectId(data), data.page_id || pageId(data.page)); message('分镜已导入。请检查草稿、角色与导入报告。');
    if (data.import_report || data.report || data.warnings) { showJson('#storyboardCompilePreview', data.import_report || data.report || data.warnings); q('#storyboardCompilePanel').open = true; }
  }, 'submit');
  q('#storyboardProjectList').addEventListener('click', evt => { const button = evt.target.closest('[data-storyboard-project]'); if (button) perform(() => loadProject(button.dataset.storyboardProject)); });
  q('#storyboardPageList').addEventListener('click', evt => { const button = evt.target.closest('[data-storyboard-page]'); if (button) perform(() => loadPage(button.dataset.storyboardPage)); });
  bind('#storyboardReloadPage', async () => { pageRequired(); await loadProject(projectId(state.project), pageId(state.page)); });
  bind('#storyboardValidate', async () => { pageRequired(); const result = await api(`${pageUrl()}/validate`, {}); showJson('#storyboardCompilePreview', result); q('#storyboardCompilePanel').open = true; warnings([...(result.errors || []), ...(result.warnings || [])]); message(result.valid === false || result.errors?.length ? '校验发现问题，请检查下方结果。' : '页面校验完成，请检查提醒。'); });
  bind('#storyboardCompile', async () => { pageRequired(); const result = await api(`${pageUrl()}/compile`, {}); showJson('#storyboardCompilePreview', result); q('#storyboardCompilePanel').open = true; warnings(result.warnings || []); message('已编译 MOSS JSON。请检查译文提醒与单 LoRA 选择。'); });
  bind('#storyboardEditorStart', async () => {
    pageRequired();
    const popup = window.open('about:blank', '_blank');
    if (popup) popup.opener = null;
    try {
      const result = await api(`${pageUrl()}/editor/start`, {}), url = safeUrl(result.url || result.editor_url, {editor: true});
      if (!url) throw new Error('编辑器没有返回有效的本机地址。');
      if (popup) popup.location.replace(url);
      else { message('编辑器已启动。浏览器拦截了新窗口，请允许弹出窗口后再次打开。'); return; }
      message('编辑器已在新窗口打开。保存后回到 Hub 重新读取页面。');
    } catch (error) { popup?.close(); throw error; }
  });
  bind('#storyboardEditorStop', async () => { pageRequired(); await api(`${pageUrl()}/editor/stop`, {}); message('当前项目的网页编辑器已停止。'); });
  bind('#storyboardAiForm', async () => {
    pageRequired(); state.ai = null; q('#storyboardAiApply').hidden = true;
    const version = state.version;
    const data = await api(`${pageUrl()}/ai/preview`, {story: q('#storyboardStory').value, connection_id: connectionId(), panel_count: Number(q('#storyboardPanelCount').value)});
    state.ai = {...data, expected_version: version}; showJson('#storyboardAiPreview', data.page || data);
    const candidates = data.candidates || [];
    q('#storyboardAiCandidateLabel').hidden = !candidates.length;
    populate('#storyboardAiCandidate', candidates.map((item, index) => ({...item, index})), item => item.index, item => typeof item.layout === 'string' ? item.layout : item.layout?.name || item.layout?.id || `方案 ${item.index + 1}`, '默认方案');
    q('#storyboardAiCandidate').value = '0';
    const panels = data.page?.panels || []; q('#storyboardAiSummary').textContent = `${panels.length} 格方案，仅供预览，尚未写入。${(data.warnings || []).join('；')}`;
    q('#storyboardAiApply').hidden = !data.preview_id; message('拆格方案已生成，检查后点击“确认写入分镜页”。');
  }, 'submit');
  bind('#storyboardAiApply', async () => {
    if (!state.ai) return;
    await api(`${pageUrl()}/ai/apply`, {preview_id: state.ai.preview_id, confirmed: true, expected_version: state.ai.expected_version, candidate_index: Number(q('#storyboardAiCandidate').value || 0)});
    await loadProject(projectId(state.project), pageId(state.page)); message('已确认写入分镜页。可以打开网页编辑器调整。');
  });
  q('#storyboardAiCandidate').addEventListener('change', () => {
    const candidate = state.ai?.candidates?.[Number(q('#storyboardAiCandidate').value)];
    if (candidate) showJson('#storyboardAiPreview', {page: candidate.page, validation: candidate.validation});
  });
  bind('#storyboardTranslationTodo', async () => {
    pageRequired(); state.translation = null; q('#storyboardTranslationApply').hidden = true;
    const data = await api(`${pageUrl()}/translations/todo`); showJson('#storyboardTranslationPreview', data);
    const count = recordList(data, ['todo', 'items', 'panels', 'results']).length;
    q('#storyboardTranslationStatus').textContent = count ? `有 ${count} 项待翻译，查看英文翻译清单。` : '翻译清单已检查，详见下方结果。';
  });
  bind('#storyboardTranslationGenerate', async () => {
    pageRequired(); state.translation = null; q('#storyboardTranslationApply').hidden = true; const version = state.version;
    const data = await api(`${pageUrl()}/translations/preview`, {connection_id: connectionId()});
    state.translation = {...data, expected_version: version}; showJson('#storyboardTranslationPreview', data.translations || data);
    q('#storyboardTranslationApply').hidden = !data.preview_id; message('英文译文仅供预览，确认后才应用。');
  });
  bind('#storyboardTranslationApply', async () => {
    if (!state.translation) return;
    await api(`${pageUrl()}/translations/apply`, {preview_id: state.translation.preview_id, confirmed: true, expected_version: state.translation.expected_version});
    await loadPage(pageId(state.page)); message('已确认应用译文，请重新编译。');
  });
  bind('#storyboardOcForm', async () => {
    state.character = null; q('#storyboardOcApply').hidden = true;
    const oc = q('#storyboardOc').value; if (!oc) throw new Error('请先在角色库导入 OC。');
    const payload = {oc_id: oc};
    if (q('#storyboardOcModel').value) payload.connection_id = q('#storyboardOcModel').value;
    [['appearance_zh', '#storyboardAppearanceZh'], ['appearance_en', '#storyboardAppearanceEn'], ['outfit_zh', '#storyboardOutfitZh'], ['outfit_en', '#storyboardOutfitEn']].forEach(([key, selector]) => { if (q(selector).value.trim()) payload[key] = q(selector).value.trim(); });
    if (q('#storyboardOcLora').value.trim()) payload.lora = {path: q('#storyboardOcLora').value.trim(), strength: 1};
    const data = await api(`${projectUrl()}/characters/preview`, payload); state.character = data;
    showJson('#storyboardOcPreview', {character: data.character, warnings: data.warnings || []}); q('#storyboardOcApply').hidden = !data.preview_id;
    message('角色卡尚未保存。核对中英文外观和服装颜色后确认。');
  }, 'submit');
  bind('#storyboardOcApply', async () => { if (!state.character) return; await api(`${projectUrl()}/characters/apply`, {preview_id: state.character.preview_id, confirmed: true}); await loadProject(projectId(state.project), pageId(state.page)); message('已保存分镜角色卡。'); });
  bind('#storyboardWorkflowForm', async () => {
    q('#storyboardWorkflowStatus').textContent = '';
    const file = q('#storyboardWorkflowFile').files[0]; if (!file) return;
    if (!file.size || file.size > 2 * 1024 * 1024) throw new Error('API 工作流文件须为 1 字节到 2 MiB 的 JSON。');
    const text = await file.text();
    try { JSON.parse(text); } catch { throw new Error('API 工作流 JSON 无法读取，请检查导出格式。'); }
    const params = new URLSearchParams({label: q('#storyboardWorkflowName').value.trim(), filename: file.name.slice(0, 180)});
    if (q('#storyboardWorkflowReplace').checked) params.set('replace', 'true');
    q('#storyboardWorkflowStatus').textContent = '正在校验并登记 API 工作流…';
    try {
      await window.fetchJsonWithTimeout(`/api/workflow-profiles/moss-soda-v2/import?${params}`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: text}, 30000);
      q('#storyboardWorkflowStatus').textContent = 'Soda-MOSS-v2 API 工作流已登记。可以在下方选择该工作流出图。';
      q('#storyboardBackend').value = 'moss-soda-v2';
      message('API 工作流已登记，尚未投递任何生成任务。');
    } catch (error) { q('#storyboardWorkflowStatus').textContent = error.message; throw error; }
  }, 'submit');
  bind('#storyboardGenerateForm', async () => {
    pageRequired(); const nodeId = q('#storyboardNode').value; if (!nodeId) throw new Error('请先配置一个 Worker 设备。');
    const payload = {node_id: nodeId, backend: q('#storyboardBackend').value, preset: q('#storyboardPreset').value, seed: Number(q('#storyboardSeed').value), negative: q('#storyboardNegative').value};
    if (q('#storyboardModel').value.trim()) payload.model = q('#storyboardModel').value.trim();
    const overrides = {};
    [['diffusion_model', '#storyboardDiffusionModel'], ['text_encoder', '#storyboardClip'], ['vae', '#storyboardVae']].forEach(([key, selector]) => { if (q(selector).value.trim()) overrides[key] = q(selector).value.trim(); });
    if (Object.keys(overrides).length) payload.model_overrides = overrides;
    const data = await api(`${pageUrl()}/generate`, payload), task = data.task || data;
    const taskId = task.task_id || data.task_id;
    if (taskId) state.tasks.set(`${projectId(state.project)}/${pageId(state.page)}`, {node_id: nodeId, task_id: taskId});
    q('#storyboardTaskStatus').textContent = taskId ? `任务已投递：${taskId}。Worker 完成后点击“回收任务结果”。` : '任务已投递，可到出图页查看。';
    message('出图任务已交给 Worker。');
  }, 'submit');
  bind('#storyboardRefreshResults', async () => {
    pageRequired(); const task = state.tasks.get(`${projectId(state.project)}/${pageId(state.page)}`);
    if (!task) { await loadPage(pageId(state.page)); message('页面已刷新。若任务在出图页回收，可在此查看结果。'); return; }
    const data = await api(`${pageUrl()}/results/refresh`, task);
    await loadPage(pageId(state.page));
    message(data.message || '任务状态与候选图已刷新。');
  });
  q('#storyboardResults').addEventListener('click', evt => { const button = evt.target.closest('[data-storyboard-pick]'); if (button) perform(async () => { await api(`${pageUrl()}/results/pick`, {result_id: button.dataset.storyboardPick}); await loadPage(pageId(state.page)); message('已选为本页成图，并写入分镜 production。'); }); });
  bind('#storyboardOpenResults', () => window.setPromptHubView('comfy'));
  function confirmDelete(page) {
    if (state.busy || !state.project || (page && !state.page)) return;
    state.deletePage = page;
    q('#storyboardDeleteTitle').textContent = page ? '将当前分镜页移入回收站？' : '将分镜项目移入回收站？';
    q('#storyboardDeleteName').textContent = q(page ? '#storyboardPageTitle' : '#storyboardProjectTitle').textContent;
    q('#storyboardDeleteStatus').textContent = ''; q('#storyboardDeleteDialog').showModal();
  }
  q('#storyboardDeleteProject').addEventListener('click', () => confirmDelete(false));
  q('#storyboardDeletePage').addEventListener('click', () => confirmDelete(true));
  q('#storyboardDeleteCancel').addEventListener('click', () => q('#storyboardDeleteDialog').close());
  bind('#storyboardDeleteConfirm', async () => { const id = projectId(state.project), page = state.deletePage; await api(page ? pageUrl() : projectUrl(), undefined, 'DELETE'); q('#storyboardDeleteDialog').close(); state.project = null; state.page = null; await loadProjects(page ? id : undefined); message(page ? '分镜页已移入回收站。' : '分镜项目已移入回收站。'); });

  window.ensureStoryboardProjects = async () => {
    const run = ++state.loadRun;
    if (state.busy) return;
    await perform(async () => { await loadProjects(); if (run === state.loadRun) await loadResources(); });
  };
})();
