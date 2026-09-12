    const $ = (selector) => document.querySelector(selector);
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
    const formatNumber = (value) => new Intl.NumberFormat('zh-CN').format(value || 0);
    let currentMode = 'home';
    let currentResults = [];
    let currentCharacters = [];
    let archivePage = 1;
    const archivePageSize = 12;
    let remoteDeviceName = __PROMPT_HUB_DEVICE_NAME_JSON__;
    let tagDisplayLanguage = 'zh';
    const tagLabelCache = new Map();
    let homeMissingSources = [];
    const sourceSetupSkipKey = 'soda-prompt-hub-source-setup-skipped';
    const viewLabels = {home:'首页', creative:'创作台', prompts:'提示词库', discover:'智能检索', characters:'角色库', datasets:'数据集', lora:'LoRA 项目', comfy:'Windows 出图', management:'资料管理', remote:'设备连接'};

    function setPromptHubDeviceName(value) {
      remoteDeviceName = String(value || '').trim() || 'Windows 绘图设备';
      document.querySelectorAll('[data-remote-device-name]').forEach(node => { node.textContent = remoteDeviceName; });
      window.dispatchEvent(new CustomEvent('prompt-hub-device-name-change', {detail:{name:remoteDeviceName}}));
      return remoteDeviceName;
    }
    window.getPromptHubDeviceName = () => remoteDeviceName;
    window.setPromptHubDeviceName = setPromptHubDeviceName;

    function setNavMenu(open) {
      const nav = document.querySelector('.app-nav');
      const toggle = $('#appNavToggle');
      nav.dataset.menuOpen = String(Boolean(open));
      toggle.setAttribute('aria-expanded', String(Boolean(open)));
      toggle.querySelector('small').textContent = open ? '收起菜单' : '打开菜单';
    }

    function displayCanonicalTag(tag) {
      const value = String(tag || '').trim();
      const item = tagLabelCache.get(value.toLowerCase());
      if (!item || tagDisplayLanguage === 'en') return value;
      return item.zh ? `${item.zh} (${item.en})` : item.en;
    }

    async function ensureTagLabels(tags) {
      const values = tags.map(value => String(value || '').trim()).filter(Boolean);
      const canonicalPattern = /^[A-Za-z0-9][A-Za-z0-9_()'./:+\- ]*$/;
      const missing = [...new Set(values)].filter(value => canonicalPattern.test(value) && !tagLabelCache.has(value.toLowerCase()));
      if (!missing.length) return false;
      let changed = false;
      for (let index = 0; index < missing.length; index += 500) {
        const response = await fetch('/api/tags/localize', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({tags:missing.slice(index,index+500), language:'zh'})});
        if (!response.ok) continue;
        const payload = await response.json();
        (payload.items || []).forEach(item => tagLabelCache.set(String(item.en).toLowerCase(), item));
        changed = true;
      }
      return changed;
    }

    function tagValuesFromItem(item) {
      return item.kind === 'tag' ? [item.title, ...String(item.content || '').split(',')] : [];
    }

    const kindLabels = {style:'画风',prompt:'完整提示词',modifier:'修饰词',wildcard:'通配词',caption:'图片说明',tag:'标签',character_reference:'角色参照',artist_reference:'画师参照',copyright_reference:'作品参照'};
    const safetyLabels = {sfw:'普通',suggestive:'轻度成人向',adult:'成人向','explicit-adult':'明确成人向',unrated:'尚未分级'};
    const modelFamilyLabels = {'danbooru-tags':'Booru 标签',anima:'Anima',krea2:'Krea 2'};
    const categoryLabels = {'web-capture':'网页资料','kisega-tag':'服装与物件标签'};

    function tagCardTitle(item) { return item.kind === 'tag' ? displayCanonicalTag(item.title) : item.title; }
    function tagCardContent(item) {
      if (item.kind !== 'tag') return item.content;
      return tagDisplayLanguage === 'zh' ? `标准英文输出：${item.content}` : item.content;
    }

    function setTagDisplayLanguage(language) {
      tagDisplayLanguage = language === 'en' ? 'en' : 'zh';
      $('#tagLanguageToggle').textContent = tagDisplayLanguage === 'zh' ? '标签：中英' : '标签：仅英文';
      window.dispatchEvent(new CustomEvent('tag-language-change', {detail:{language:tagDisplayLanguage}}));
      if (currentMode === 'prompts') searchPrompts().catch(console.error);
    }

    window.displayCanonicalTag = displayCanonicalTag;
    window.ensureTagLabels = ensureTagLabels;
    window.getTagDisplayLanguage = () => tagDisplayLanguage;
    window.toggleTagDisplayLanguage = () => setTagDisplayLanguage(tagDisplayLanguage === 'zh' ? 'en' : 'zh');

    function visualMarkup(item) {
      if (!item.visuals?.length) return '';
      const multiple = item.visuals.length > 1;
      const cards = item.visuals.map((visual, index) => {
        const rawVisualSafety = visual.safety || item.safety || 'unrated';
        const visualSafety = escapeHtml(rawVisualSafety);
        const openLabel = multiple ? `查看第 ${index + 1} 张 ↗` : '查看大图 ↗';
        return `<a class="visual-frame" href="${escapeHtml(visual.original_url)}" target="_blank" rel="noreferrer" aria-label="查看 ${escapeHtml(item.title)} 参照图 ${index + 1}">
          <img src="${escapeHtml(visual.thumbnail_url)}" alt="${escapeHtml(item.title)} 视觉参照 ${index + 1}" loading="lazy" decoding="async">
          <span class="visual-label">${openLabel}</span><span class="visual-safety ${visualSafety}">${escapeHtml(safetyLabels[rawVisualSafety] || '尚未分级')}</span>
        </a>`;
      }).join('');
      return `<div class="visual-gallery ${multiple ? 'multi' : ''}" style="--visual-count:${item.visuals.length}">${cards}</div>`;
    }

    function personalMarkup(item) {
      const rating = Number(item.user_rating || 0);
      const stars = [1, 2, 3, 4, 5].map(value => `<button class="star-button ${value <= rating ? 'active' : ''}" data-personal-action="rating" data-rating="${value}" aria-label="${value} 星" aria-pressed="${value === rating ? 'true' : 'false'}">★</button>`).join('');
      const note = item.user_note || '';
      return `<div class="personal-tools">
        <button class="favorite-button" data-personal-action="favorite" aria-pressed="${item.favorite ? 'true' : 'false'}">${item.favorite ? '★ 已收藏' : '☆ 收藏'}</button>
        <div class="rating-control" aria-label="个人评分">${stars}</div>
        <button class="note-button ${note ? 'has-note' : ''}" data-personal-action="note-toggle">${note ? '备注 ●' : '写备注'}</button>
      </div>
      ${note ? `<p class="note-preview">${escapeHtml(note)}</p>` : ''}
      <div class="note-editor" hidden><textarea maxlength="1200" placeholder="记录适用模型、构图效果或测试想法…">${escapeHtml(note)}</textarea><button class="save-note-button" data-personal-action="note-save">保存备注</button></div>`;
    }

    function characterCard(item, index) {
      const traits = [item.gender, item.age ? `${item.age}岁` : '', item.race, item.identity].filter(Boolean);
      const initial = Array.from(item.name || '?')[0] || '?';
      return `<article class="card character-card" data-character-index="${index}" style="animation-delay:${Math.min(index * 25, 250)}ms">
        <div class="character-mark" data-initial="${escapeHtml(initial)}"><span>OC Manager 本地副本</span><span>${escapeHtml(item.sheet_role === 'npc' ? '非玩家角色' : item.sheet_role === 'pc' ? '玩家角色' : item.sheet_role || '角色')}</span></div>
        <div class="card-meta">
          <span class="badge signal">角色</span>
          ${item.world ? `<span class="badge">${escapeHtml(item.world)}</span>` : ''}
          ${item.faction ? `<span class="badge soft">${escapeHtml(item.faction)}</span>` : ''}
        </div>
        <h3>${escapeHtml(item.name)}</h3>
        <p class="content">${escapeHtml(item.story_excerpt || '暂无故事简介')}</p>
        <div class="character-meta">
          <span><strong>角色资料</strong> ${escapeHtml(traits.join(' / ') || '未填写')}</span>
          <span><strong>提示词</strong> ${formatNumber(item.prompt_count)}</span>
          <span><strong>图片</strong> ${formatNumber(item.gallery_count)}</span>
          <span><strong>更新时间</strong> ${escapeHtml((item.source_updated_at || item.imported_at || '').slice(0, 10))}</span>
        </div>
        <div class="character-actions"><button class="character-create-button" data-character-create>以此角色开始创作</button><button class="detail-button" data-character-action="details" aria-expanded="false">展开角色资料 ↘</button></div>
        <div class="character-detail" hidden></div>
      </article>`;
    }

    function characterDetailMarkup(item) {
      const profile = item.profile || {};
      const prompts = item.prompts || [];
      const modules = Array.isArray(profile.modules) ? profile.modules : [];
      const timeline = Array.isArray(profile.timeline) ? profile.timeline : [];
      const relationships = Array.isArray(profile.relationships) ? profile.relationships : [];
      const gallery = Array.isArray(profile.gallery) ? profile.gallery : [];
      const promptMarkup = prompts.length ? prompts.map(prompt => `<div class="prompt-record"><strong>${escapeHtml(prompt.label || '未命名提示词')}</strong><p>${escapeHtml(prompt.text)}</p></div>`).join('') : '<p>这个角色还没有保存提示词。</p>';
      return `<h4>角色资料</h4>
        <p>${escapeHtml(item.story || '暂无故事内容')}</p>
        <div class="detail-counts"><span>${modules.length} 个模块</span><span>${timeline.length} 条时间线</span><span>${relationships.length} 组关系</span><span>${gallery.length} 张图片</span></div>
        <h4>角色提示词</h4>${promptMarkup}`;
    }

    async function loadStats() {
      const selectedSource = $('#source').value;
      const [stats, sources, version] = await Promise.all([fetch('/api/stats').then(r => r.json()), fetch('/api/sources').then(r => r.json()), fetch('/api/system/version').then(r => r.json())]);
      $('#entryCount').textContent = formatNumber(stats.entries);
      $('#sourceCount').textContent = formatNumber(stats.sources);
      $('#styleCount').textContent = formatNumber(stats.kinds?.style);
      $('#tagCount').textContent = formatNumber(stats.kinds?.tag);
      $('#favoriteCount').textContent = formatNumber(stats.personal?.favorites);
      $('#ocCount').textContent = formatNumber(stats.oc_manager?.characters);
      $('#homeEntryCount').textContent = formatNumber(stats.entries);
      $('#homeSourceCount').textContent = formatNumber(stats.sources);
      $('#homeOcCount').textContent = formatNumber(stats.oc_manager?.characters);
      const product = version.product || {};
      const dataVersion = version.data || {};
      $('#homeProgramVersion').textContent = `${product.version || '无法识别'} · ${product.release_channel_label || '版本未知'}`;
      $('#homeDataVersion').textContent = dataVersion.summary || '尚未初始化';
      $('#homeDataVersion').title = dataVersion.summary || '尚未初始化';
      $('#homeReleaseIdentity').textContent = `Soda Prompt Hub ${product.version || ''}（${product.release_channel_label || '版本未知'}）：`;
      $('#source').innerHTML = '<option value="">全部来源</option>' + sources.map(s => `<option value="${escapeHtml(s.source_id)}">${escapeHtml(s.name)}</option>`).join('');
      if ([...$('#source').options].some(option => option.value === selectedSource)) $('#source').value = selectedSource;
      renderSourceQuickFilters(sources);
      $('#sourceList').innerHTML = '<p class="section-label">资料来源</p>' + sources.map(s => `<div class="source-row"><span>${escapeHtml(s.name)}</span><span>${formatNumber(s.entry_count)}</span></div>`).join('');
    }

    function renderSourceQuickFilters(sources) {
      if (currentMode === 'characters') {
        $('#sourceQuickFilters').innerHTML = '';
        return;
      }
      const selected = $('#source').value;
      const visualSources = sources.filter(item => Number(item.visual_count || 0) > 0);
      $('#sourceQuickFilters').innerHTML = [
        {source_id:'', name:'全部来源'},
        ...visualSources,
      ].map(item => `<button type="button" class="source-quick-filter" data-source-quick="${escapeHtml(item.source_id)}" aria-pressed="${String(selected === item.source_id)}">${escapeHtml(item.name)}</button>`).join('');
      $('#sourceQuickFilters').querySelectorAll('[data-source-quick]').forEach(button => button.addEventListener('click', async () => {
        $('#source').value = button.dataset.sourceQuick;
        await handleSourceChange();
      }));
    }

    async function loadAnimadexFacets() {
      const response = await fetch('/api/sources/animadex/facets');
      if (!response.ok) return;
      const facets = await response.json();
      const optionLabel = value => String(value || '').replaceAll('_', ' ');
      const fill = (selector, label, values) => {
        const selected = $(selector).value;
        $(selector).innerHTML = `<option value="">${label}</option>` + (values || []).map(value => `<option value="${escapeHtml(value)}">${escapeHtml(optionLabel(value))}</option>`).join('');
        if ([...$(selector).options].some(option => option.value === selected)) $(selector).value = selected;
      };
      fill('#animadexCopyright', '全部作品', facets.categories);
      fill('#animadexHair', '全部发色', facets.hair_colors);
      fill('#animadexEyes', '全部瞳色', facets.eye_colors);
    }

    async function handleSourceChange() {
      const isAnimadex = $('#source').value === 'animadex';
      $('#animadexFilters').hidden = !isAnimadex;
      if (isAnimadex) await loadAnimadexFacets();
      else {
        $('#animadexCopyright').value = '';
        $('#animadexHair').value = '';
        $('#animadexEyes').value = '';
      }
      document.querySelectorAll('[data-source-quick]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.sourceQuick === $('#source').value)));
      await searchPrompts();
    }

    function sourceSetupSignature(sources) {
      return sources.map(item => item.source_id).sort().join('|');
    }

    function sourceLicenseLabel(value) {
      if (value === 'unknown') return '许可证待查';
      if (value === 'MIT (code); community prompt text') return '代码 MIT；提示词按上游说明';
      return value;
    }

    function renderHomeSourceSetup(sources) {
      homeMissingSources = sources.filter(item => item.status === 'missing');
      const setup = $('#homeSourceSetup');
      if (!homeMissingSources.length) {
        setup.hidden = true;
        localStorage.removeItem(sourceSetupSkipKey);
        return;
      }
      const signature = sourceSetupSignature(homeMissingSources);
      setup.hidden = localStorage.getItem(sourceSetupSkipKey) === signature;
      $('#homeSourceSetupList').innerHTML = homeMissingSources.map(item => `<span>${escapeHtml(item.name)} · ${escapeHtml(sourceLicenseLabel(item.license))}</span>`).join('');
      $('#homeSourceSetupDescription').textContent = homeMissingSources.some(item => item.source_id === 'kisegaeningyou') ? `还缺 ${homeMissingSources.length} 个推荐资料库。其中视觉参照库图片较多，第一次下载可能需要几分钟。` : `还缺 ${homeMissingSources.length} 个推荐资料库，安装后会自动建立本地检索索引。`;
    }

    async function loadSourceSyncStatus() {
      const labels = {ready:'可以安全更新',dirty:'有本地改动',no_upstream:'没有上游',missing:'本地缺失',not_git:'不是 Git 仓库',cloned:'已拉取',failed:'检查失败'};
      const response = await fetch('/api/sources/sync-status');
      const sources = response.ok ? await response.json() : [];
      renderHomeSourceSetup(sources);
      $('#sourceSyncList').innerHTML = sources.map(item => {
        const action = item.status === 'missing' ? `<button class="source-sync-fetch" data-clone-source="${escapeHtml(item.source_id)}" title="从 ${escapeHtml(item.url)} 拉取到本地">拉取</button>` : '';
        return `<div class="source-sync-row"><strong>${escapeHtml(item.name)}</strong><span class="source-sync-status"><span class="source-sync-state ${escapeHtml(item.status)}">${escapeHtml(labels[item.status] || item.status)}</span>${action}</span><code>${escapeHtml(item.branch || '—')} · ${escapeHtml((item.before || '').slice(0, 10) || '暂无版本')}</code></div>`;
      }).join('');
      $('#sourceSyncList').querySelectorAll('[data-clone-source]').forEach(button => button.addEventListener('click', () => cloneSource(button.dataset.cloneSource, button)));
      const dirty = sources.filter(item => item.status === 'dirty').length;
      const ready = sources.filter(item => item.status === 'ready').length;
      const missing = sources.filter(item => item.status === 'missing').length;
      $('#sourceSyncMessage').textContent = missing ? `${missing} 个预设资料源尚未拉取到本机，点状态旁的“拉取”即可下载；其余 ${ready} 个可以安全更新。` : dirty ? `${dirty} 个资料源有本地改动，会自动跳过；其余 ${ready} 个可以安全更新。` : `${ready} 个资料源可以安全检查更新；只允许 fast-forward，不会覆盖本地修改。`;
    }

    async function loadOcWorlds() {
      const selectedWorld = $('#ocWorld').value;
      const worlds = await fetch('/api/oc-manager/worlds').then(r => r.json());
      $('#ocWorld').innerHTML = '<option value="">全部世界</option>' + worlds.map(world => `<option value="${escapeHtml(world.world_name)}">${escapeHtml(world.world_name)} · ${formatNumber(world.character_count)}</option>`).join('');
      if ([...$('#ocWorld').options].some(option => option.value === selectedWorld)) $('#ocWorld').value = selectedWorld;
    }

    function renderPromptPage() {
      const pageCount = Math.max(1, Math.ceil(currentResults.length / archivePageSize));
      archivePage = Math.min(Math.max(archivePage, 1), pageCount);
      const start = (archivePage - 1) * archivePageSize;
      const pageItems = currentResults.slice(start, start + archivePageSize);
      $('#archivePagination').hidden = currentResults.length <= archivePageSize;
      $('#archivePageStatus').textContent = `第 ${archivePage} / ${pageCount} 页 · 每页 ${archivePageSize} 条`;
      $('#archivePreviousPage').disabled = archivePage <= 1;
      $('#archiveNextPage').disabled = archivePage >= pageCount;
      $('#results').innerHTML = pageItems.map((item, index) => `
        <article class="card ${item.favorite ? 'is-favorite' : ''}" data-result-index="${start + index}" style="animation-delay:${Math.min(index * 25, 250)}ms">
          ${visualMarkup(item)}
          <div class="card-meta">
            <span class="badge signal">${escapeHtml(kindLabels[item.kind] || '资料')}</span>
            <span class="badge">${escapeHtml(safetyLabels[item.safety] || '尚未分级')}</span>
            ${item.model_family ? `<span class="badge soft">${escapeHtml(modelFamilyLabels[item.model_family] || item.model_family)}</span>` : ''}
          </div>
          <h3>${escapeHtml(tagCardTitle(item))}</h3>
          <p class="content">${escapeHtml(tagCardContent(item))}</p>
          <div class="archive-add-tools"><select data-creative-slot aria-label="选择创作槽位"><option value="character">角色</option><option value="outfit">服装</option><option value="action">动作</option><option value="composition">构图</option><option value="scene">场景</option><option value="lighting">灯光</option><option value="style" ${item.kind === 'style' ? 'selected' : ''}>画风</option></select><button class="archive-add-button" data-creative-add>加入创作</button></div>
          ${personalMarkup(item)}
          <footer><span>${escapeHtml(item.source_name)} · ${escapeHtml(categoryLabels[item.category] || item.category || '未分类')}</span>${item.source_url ? `<a href="${escapeHtml(item.source_url)}" target="_blank" rel="noreferrer">查看来源 ↗</a>` : ''}</footer>
        </article>`).join('');
    }

    async function searchPrompts() {
      $('#status').textContent = '正在查找…';
      $('#results').classList.remove('character-results');
      const params = new URLSearchParams({query: $('#query').value, kind: $('#kind').value, safety: $('#safety').value, source_id: $('#source').value, favorites_only: $('#favoritesOnly').getAttribute('aria-pressed'), has_visual: $('#onlyWithVisuals').getAttribute('aria-pressed'), category: $('#animadexCopyright').value, hair_color: $('#animadexHair').value, eye_color: $('#animadexEyes').value, limit: '30'});
      const data = await fetch('/api/search?' + params).then(r => r.json());
      currentResults = data.results;
      archivePage = 1;
      await ensureTagLabels(data.results.flatMap(tagValuesFromItem));
      $('#status').textContent = `找到 ${data.count} 条`;
      if (!data.results.length) {
        $('#archivePagination').hidden = true;
        $('#results').innerHTML = '<div class="empty"><strong>没有找到对应资料</strong><span>换一个词，或放宽类型与内容分级。</span></div>';
        return;
      }
      renderPromptPage();
    }

    async function searchCharacters() {
      $('#status').textContent = '正在查找角色…';
      $('#results').classList.add('character-results');
      const params = new URLSearchParams({query: $('#query').value, world: $('#ocWorld').value, limit: '30'});
      const data = await fetch('/api/oc-manager/characters?' + params).then(r => r.json());
      currentCharacters = data.results;
      $('#archivePagination').hidden = true;
      $('#status').textContent = `找到 ${data.count} 个角色`;
      if (!data.results.length) {
        $('#results').innerHTML = '<div class="empty"><strong>还没有找到角色</strong><span>可以换一个关键词，或选择 OC Manager 导出的 JSON 文件进行导入。</span></div>';
        return;
      }
      $('#results').innerHTML = data.results.map(characterCard).join('');
    }

    function runSearch() {
      return currentMode === 'characters' ? searchCharacters() : searchPrompts();
    }

    async function setMode(mode) {
      currentMode = mode;
      const characterMode = mode === 'characters';
      $('#promptFilters').hidden = characterMode;
      $('#ocFilters').hidden = !characterMode;
      $('#favoritesOnly').hidden = characterMode;
      $('#onlyWithVisuals').hidden = characterMode;
      $('#sourceQuickFilters').hidden = characterMode;
      $('#ocImportPanel').hidden = !characterMode;
      $('#resultsTitle').textContent = characterMode ? '角色结果' : '提示词结果';
      $('#query').placeholder = characterMode ? '角色名、世界、故事或外观' : '例如：哥特连衣裙、兔耳、逆光';
      $('#query').setAttribute('aria-label', characterMode ? '输入角色名、世界、故事或外观' : '输入提示词关键词');
      $('#searchButton').textContent = characterMode ? '查找角色' : '查找提示词';
      $('#searchLabel').textContent = characterMode ? '查找角色' : '查找提示词和视觉参考';
      $('#archiveNotice').innerHTML = characterMode ? '<strong>OC 角色库：</strong>导入 OC Manager JSON 后，可以按角色名、世界、故事和外观查找角色。' : '<strong>提示词与视觉资料库：</strong>输入服装、动作、构图、场景或画风关键词。找到合适内容后可以收藏并记录实测备注。';
      $('#query').value = '';
      if (!characterMode) await handleSourceChange();
      if (characterMode) await loadOcWorlds();
      if (characterMode) await runSearch();
    }

    function preferReducedMotion() {
      return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function playViewEnter(element) {
      if (!element || preferReducedMotion()) return;
      element.classList.remove('view-enter');
      void element.offsetWidth;
      element.classList.add('view-enter');
    }

    async function setView(view) {
      setNavMenu(false);
      $('#appNavCurrent').textContent = `当前：${viewLabels[view] || '首页'}`;
      const archiveMode = view === 'prompts' || view === 'characters';
      const pageByView = {
        home: $('#homePage'),
        creative: $('#creativePage'),
        discover: $('#discoveryPage'),
        datasets: $('#workspacePage'),
        lora: $('#loraPage'),
        comfy: $('#comfyPage'),
        remote: $('#remotePage'),
        management: $('#managementPage'),
      };
      Object.entries(pageByView).forEach(([key, node]) => { if (node) node.hidden = key !== view; });
      $('#archiveWorkspace').hidden = !archiveMode;
      const enterTarget = archiveMode ? $('#archiveWorkspace') : pageByView[view];
      playViewEnter(enterTarget);
      document.querySelectorAll('[data-view]').forEach(button => {
        if (button.classList.contains('app-nav-button')) {
          button.setAttribute('aria-current', button.dataset.view === view ? 'page' : 'false');
        }
      });
      if (archiveMode) {
        await setMode(view);
        $('#query').focus();
      } else if (view === 'creative' && window.ensureCreativeProject) {
        currentMode = view;
        await window.ensureCreativeProject();
      } else if (view === 'discover' && window.ensureHybridSearch) {
        currentMode = view;
        await window.ensureHybridSearch();
      } else if (view === 'datasets' && window.ensureDatasetWorkspace) {
        currentMode = view;
        await window.ensureDatasetWorkspace();
      } else if (view === 'lora' && window.ensureLoraProject) {
        currentMode = view;
        await window.ensureLoraProject();
      } else if (view === 'comfy' && window.ensureComfyResults) {
        currentMode = view;
        await window.ensureComfyResults();
      } else if (view === 'remote' && window.ensureRemoteDevices) {
        currentMode = view;
        await window.ensureRemoteDevices();
      } else if (view === 'management') {
        currentMode = view;
        await Promise.all([loadSourceSyncStatus(), window.ensureSourceCenter ? window.ensureSourceCenter() : Promise.resolve()]);
      } else {
        currentMode = view;
      }
      window.scrollTo({top: 0, behavior: 'smooth'});
    }
    window.setPromptHubView = setView;

    async function openExample() {
      await setView('prompts');
      $('#query').value = 'victorian military uniform';
      await searchPrompts();
    }

    async function importOcFile() {
      const file = $('#ocFile').files[0];
      if (!file) return;
      const button = $('#ocImportButton');
      button.disabled = true;
      button.textContent = '正在导入…';
      $('#ocImportMessage').textContent = '';
      try {
        const response = await fetch('/api/oc-manager/import?filename=' + encodeURIComponent(file.name), {method: 'POST', headers: {'Content-Type': 'application/json'}, body: file});
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || `导入失败: ${response.status}`);
        $('#ocImportMessage').textContent = `已导入 ${formatNumber(result.characters_imported)} 个角色 · ${formatNumber(result.worlds_imported)} 个世界`;
        await Promise.all([loadStats(), loadOcWorlds()]);
        await searchCharacters();
      } catch (error) {
        $('#ocImportMessage').textContent = `导入失败：${error.message}`;
      } finally {
        button.disabled = false;
        button.textContent = '导入到本地角色库';
      }
    }

    async function saveMark(item) {
      const response = await fetch('/api/marks', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({source_id: item.source_id, external_id: item.external_id, favorite: Boolean(item.favorite), rating: item.user_rating || null, note: item.user_note || ''})
      });
      if (!response.ok) throw new Error(`保存失败: ${response.status}`);
      Object.assign(item, await response.json());
      $('#status').textContent = '收藏和备注已保存';
      await loadStats();
      await searchPrompts();
    }

    async function rebuild() {
      const button = $('#importButton');
      const sourceMessage = $('#sourceSyncMessage');
      button.disabled = true;
      button.textContent = '正在重建索引…';
      sourceMessage.textContent = '正在重建本地索引…';
      try {
        const response = await fetch('/api/import', {method: 'POST'});
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || `请求失败：${response.status}`);
        await loadStats();
        await searchPrompts();
        const failed = result.failed || [], skipped = result.skipped || [];
        const rebuilt = Object.keys(result.sources || {}).length;
        let message = `索引已更新，共 ${formatNumber(result.stats.entries)} 条资料`;
        if (rebuilt === 0) message = `没有任何来源被重建，现有 ${formatNumber(result.stats.entries)} 条资料保持不变`;
        if (skipped.length) message += `；${skipped.length} 个来源的本地目录不存在（${skipped.map(item => item.name).join('、')}）`;
        if (failed.length) message += `；${failed.length} 个来源本次失败：${failed.map(item => `${item.name} — ${item.message}`).join('；')}`;
        sourceMessage.textContent = message;
        $('#status').textContent = message;
      } catch (error) {
        sourceMessage.textContent = `重建失败：${error.message}`;
        $('#status').textContent = `重建失败：${error.message}`;
      } finally {
        button.disabled = false;
        button.textContent = '仅重建本地索引';
      }
    }

    async function runSourceSyncJob(body, onProgress = () => {}) {
      const response = await fetch('/api/sources/sync', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `启动更新失败：${response.status}`);
      let job = payload.job;
      while (['queued','running'].includes(job.status)) {
        $('#sourceSyncMessage').textContent = job.progress_message || '等待资料更新任务…';
        onProgress(job);
        await new Promise(resolve => setTimeout(resolve, 500));
        job = await fetch(`/api/jobs/${encodeURIComponent(job.job_id)}`).then(result => result.json());
      }
      onProgress(job);
      if (job.status !== 'completed') throw new Error(job.error || `资料更新${job.status}`);
      return job.result || {};
    }

    async function installRecommendedSources() {
      if (!homeMissingSources.length) return;
      const list = homeMissingSources.map(item => `• ${item.name}（${item.license === 'unknown' ? '上游未明确许可证，仅建议个人研究使用' : sourceLicenseLabel(item.license)}）`).join('\n');
      const visualNote = homeMissingSources.some(item => item.source_id === 'kisegaeningyou') ? '\n\n视觉参照库包含较多图片，下载时间和空间占用会更高。' : '';
      if (!confirm(`将以下公开资料下载到本机，并建立检索索引：\n\n${list}${visualNote}\n\n继续安装吗？`)) return;
      const button = $('#homeSourceInstall'), skip = $('#homeSourceSkip'), panel = $('#homeSourceProgress'), bar = $('#homeSourceProgressBar'), message = $('#homeSourceProgressMessage');
      button.disabled = true;
      skip.disabled = true;
      button.textContent = '正在安装…';
      panel.hidden = false;
      message.textContent = '正在建立后台任务…';
      try {
        const sourceIds = homeMissingSources.map(item => item.source_id);
        const result = await runSourceSyncJob({source_ids: sourceIds, clone_missing: true}, job => {
          bar.max = Math.max(Number(job.progress_total) || 1, 1);
          bar.value = Math.min(Number(job.progress_current) || 0, bar.max);
          message.textContent = job.progress_message || '正在准备资料…';
        });
        await Promise.all([loadStats(), loadSourceSyncStatus(), searchPrompts()]);
        const failed = (result.sources || []).filter(item => item.status === 'failed');
        if (failed.length) {
          message.textContent = `${failed.length} 个资料库没有安装成功：${failed.map(item => item.name).join('、')}。可以稍后重试。`;
        } else {
          message.textContent = `资料准备完成：新安装 ${result.cloned || 0} 个资料库，本地索引已经更新。`;
        }
      } catch (error) {
        message.textContent = `安装没有完成：${error.message}。请检查网络后重试。`;
      } finally {
        button.disabled = false;
        skip.disabled = false;
        button.textContent = '安装推荐资料库';
      }
    }

    function skipRecommendedSources() {
      if (!homeMissingSources.length) return;
      localStorage.setItem(sourceSetupSkipKey, sourceSetupSignature(homeMissingSources));
      $('#homeSourceSetup').hidden = true;
    }

    async function syncPublicSources() {
      const button = $('#sourceSyncButton');
      button.disabled = true;
      button.textContent = '正在检查资料源…';
      try {
        const result = await runSourceSyncJob({source_ids: [], clone_missing: false});
        $('#sourceSyncMessage').textContent = `更新完成：${result.updated || 0} 个有新版本，${result.unchanged || 0} 个已是最新，${result.skipped || 0} 个已安全跳过。`;
        await Promise.all([loadStats(), loadSourceSyncStatus()]);
      } catch (error) {
        $('#sourceSyncMessage').textContent = error.message;
      } finally {
        button.disabled = false;
        button.textContent = '↻ 更新公共提示词库';
      }
    }

    async function cloneSource(sourceId, button) {
      button.disabled = true;
      button.textContent = '拉取中';
      try {
        const result = await runSourceSyncJob({source_ids: [sourceId], clone_missing: true});
        const detail = (result.sources || []).find(item => item.source_id === sourceId) || {};
        if (detail.status === 'failed') throw new Error(detail.message || '拉取失败');
        const indexed = (result.entry_counts || {})[sourceId];
        $('#sourceSyncMessage').textContent = `${detail.name || sourceId} 已拉取到本地${indexed ? `，索引 ${formatNumber(indexed)} 条资料` : ''}。`;
        await Promise.all([loadStats(), loadSourceSyncStatus(), searchPrompts()]);
      } catch (error) {
        $('#sourceSyncMessage').textContent = error.message;
        button.disabled = false;
        button.textContent = '拉取';
      }
    }

    $('#searchButton').addEventListener('click', runSearch);
    $('#query').addEventListener('keydown', event => { if (event.key === 'Enter') runSearch(); });
    $('#kind').addEventListener('change', searchPrompts);
    $('#safety').addEventListener('change', searchPrompts);
    $('#source').addEventListener('change', () => handleSourceChange().catch(error => { $('#status').textContent = error.message; }));
    ['#animadexCopyright', '#animadexHair', '#animadexEyes'].forEach(selector => $(selector).addEventListener('change', searchPrompts));
    $('#ocWorld').addEventListener('change', searchCharacters);
    $('#archivePreviousPage').addEventListener('click', () => { if (archivePage <= 1) return; archivePage -= 1; renderPromptPage(); $('#archivePagination').scrollIntoView({block:'nearest'}); });
    $('#archiveNextPage').addEventListener('click', () => { if (archivePage * archivePageSize >= currentResults.length) return; archivePage += 1; renderPromptPage(); $('#archivePagination').scrollIntoView({block:'nearest'}); });
    $('#appNavToggle').addEventListener('click', event => setNavMenu(event.currentTarget.getAttribute('aria-expanded') !== 'true'));
    document.addEventListener('keydown', event => { if (event.key === 'Escape') setNavMenu(false); });
    document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
    document.querySelectorAll('[data-start]').forEach(button => button.addEventListener('click', () => setView(button.dataset.start)));
    $('#exampleButton').addEventListener('click', openExample);
    $('#ocFile').addEventListener('change', event => {
      const file = event.target.files[0];
      $('#ocFileName').textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KiB` : '尚未选择文件';
      $('#ocImportButton').disabled = !file;
      $('#ocImportMessage').textContent = '';
    });
    $('#ocImportButton').addEventListener('click', importOcFile);
    $('#favoritesOnly').addEventListener('click', event => {
      const active = event.currentTarget.getAttribute('aria-pressed') === 'true';
      event.currentTarget.setAttribute('aria-pressed', String(!active));
      event.currentTarget.textContent = active ? '☆ 只看我的收藏' : '★ 正在只看收藏';
      searchPrompts();
    });
    $('#onlyWithVisuals').addEventListener('click', event => {
      const active = event.currentTarget.getAttribute('aria-pressed') === 'true';
      event.currentTarget.setAttribute('aria-pressed', String(!active));
      event.currentTarget.textContent = active ? '▣ 只看有图片的资料' : '▣ 正在只看有图片的资料';
      searchPrompts();
    });
    $('#results').addEventListener('click', async event => {
      const characterButton = event.target.closest('[data-character-action="details"]');
      if (characterButton) {
        const card = characterButton.closest('.character-card');
        const item = currentCharacters[Number(card.dataset.characterIndex)];
        const detail = card.querySelector('.character-detail');
        const expanded = characterButton.getAttribute('aria-expanded') === 'true';
        if (expanded) {
          detail.hidden = true;
          characterButton.setAttribute('aria-expanded', 'false');
          characterButton.textContent = '展开角色资料 ↘';
          return;
        }
        characterButton.disabled = true;
        characterButton.textContent = '正在读取…';
        try {
          const response = await fetch('/api/oc-manager/characters/' + encodeURIComponent(item.character_id));
          if (!response.ok) throw new Error(`读取失败: ${response.status}`);
          detail.innerHTML = characterDetailMarkup(await response.json());
          detail.hidden = false;
          characterButton.setAttribute('aria-expanded', 'true');
          characterButton.textContent = '收起角色资料 ↗';
        } catch (error) {
          detail.textContent = error.message;
          detail.hidden = false;
          characterButton.textContent = '重新读取角色资料';
        } finally {
          characterButton.disabled = false;
        }
        return;
      }
      const actionButton = event.target.closest('[data-personal-action]');
      if (!actionButton) return;
      const card = actionButton.closest('.card');
      const item = currentResults[Number(card.dataset.resultIndex)];
      const action = actionButton.dataset.personalAction;
      if (action === 'note-toggle') {
        const editor = card.querySelector('.note-editor');
        editor.hidden = !editor.hidden;
        if (!editor.hidden) editor.querySelector('textarea').focus();
        return;
      }
      if (action === 'favorite') item.favorite = !item.favorite;
      if (action === 'rating') {
        const selected = Number(actionButton.dataset.rating);
        item.user_rating = item.user_rating === selected ? null : selected;
      }
      if (action === 'note-save') item.user_note = card.querySelector('textarea').value;
      try { await saveMark(item); } catch (error) { $('#status').textContent = '保存失败，请重试'; console.error(error); await searchPrompts(); }
    });
    $('#importButton').addEventListener('click', rebuild);
    $('#sourceSyncButton').addEventListener('click', syncPublicSources);
    $('#homeSourceInstall').addEventListener('click', installRecommendedSources);
    $('#homeSourceSkip').addEventListener('click', skipRecommendedSources);
    window.loadPromptHubStats = loadStats;
    $('#tagLanguageToggle').addEventListener('click', window.toggleTagDisplayLanguage);
    Promise.all([loadStats(), loadOcWorlds(), loadSourceSyncStatus(), searchPrompts()]).catch(error => { $('#status').textContent = '读取失败，请刷新页面'; console.error(error); });
