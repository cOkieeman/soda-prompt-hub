(() => {
  const q=selector=>document.querySelector(selector);
  const esc=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
  const state={kind:'all',offset:0,limit:36,total:0,items:[],roots:[],jobs:[],projects:[],models:[],facets:{models:[],loras:[]},active:null,analysis:null,evidence:null,run:0,detailRun:0,jobTimer:null,opener:null,deleteTarget:null,deleteBusy:false};
  const kindLabel=kind=>kind==='work'?'我的作品':'收集参考';
  const assetOffline=asset=>asset?.availability==='offline'||asset?.offline===true;
  const activeJob=job=>['queued','running'].includes(job.status);

  async function api(url,options={}) {
    const response=await fetch(url,options),data=await response.json().catch(()=>({}));
    if(!response.ok) throw new Error(window.promptHubErrorMessage?.(data,response.status)||(typeof data.detail==='string'?data.detail:`操作失败（${response.status}）`));
    return data;
  }
  function send(url,body,method='POST') { return api(url,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); }
  function message(text,detail=false) { q(detail?'#galleryDetailStatus':'#galleryStatus').textContent=text; }
  function error(error,detail=false) { message(error.message,detail); }
  function safeLink(value) { const text=String(value||'').trim(); if(!text) return ''; try { const url=new URL(text); return ['https:','http:'].includes(url.protocol)?url.href:''; } catch { return ''; } }
  function commaList(value) { return [...new Set(String(value||'').split(/[,，\n]/).map(item=>item.trim()).filter(Boolean))]; }
  function records(value) { return Array.isArray(value)?value:typeof value==='object'&&value!==null?[value]:value?[value]:[]; }
  function promptRecordText(evidence,kind) {
    const text=evidence?.prompts?.[kind]?.text;
    return typeof text==='string'?text:null;
  }
  function resourceName(item) { return typeof item==='string'?item:String(item?.name||item?.model_name||item?.ckpt_name||item?.lora_name||item?.filename||''); }
  function groupLoraRecords(items) {
    const groups=new Map();
    for(const item of items) { const name=resourceName(item); if(!groups.has(name)) groups.set(name,{name,records:[]}); groups.get(name).records.push(item); }
    return [...groups.values()];
  }
  function generationEvidence(asset) {
    const metadata=asset.metadata||{},record=metadata.generation_evidence;
    const structured=Boolean(record&&typeof record==='object'&&!Array.isArray(record)),data=structured?record:{};
    const final=data.extractor_version>=3&&data.final_generation&&typeof data.final_generation==='object'&&!Array.isArray(data.final_generation)?data.final_generation:{};
    const confirmed=['resolved','partial'].includes(final.status);
    const loraSource=data.extractor_version>=4&&final.lora_source?.kind==='saved_image_metadata'?final.lora_source:{};
    const loraSourceStatus=loraSource.status||'missing';
    const models=confirmed?records(final.models).filter(resourceName):[],loras=['recorded','partial'].includes(loraSourceStatus)?records(final.loras).filter(resourceName):[];
    const prompts=Object.fromEntries(['positive','negative'].map(kind=>{
      const exact=final[kind],saved=final.saved_export_prompts?.[kind];
      if(exact?.status==='exact'&&typeof exact.text==='string') return [kind,{text:exact.text,savedExport:false}];
      if(saved?.status==='saved_export'&&typeof saved.text==='string') return [kind,{text:saved.text,savedExport:true}];
      return [kind,{text:null,savedExport:false}];
    }));
    const sampling=confirmed&&final.sampler&&typeof final.sampler==='object'&&!Array.isArray(final.sampler)?[final.sampler]:[];
    return {structured,status:final.status||'unavailable',scope:data.scope||'',models,loras,prompts,sampling,loraSourceStatus,
      unconfirmed:!['recorded','recorded_empty','partial'].includes(loraSourceStatus)};
  }
  function compactEvidence(asset) {
    const evidence=generationEvidence(asset),model=evidence.models.find(item=>['checkpoint','diffusion','unet','diffusion_model'].includes(item.kind||item.asset_type||item.type||item.role)),loras=groupLoraRecords(evidence.loras),lora=loras[0];
    if(!model&&!lora) return '';
    const basename=value=>resourceName(value).replaceAll('\\','/').split('/').pop();
    return `<div class="gallery-card-evidence">${model?`<span title="${esc(resourceName(model))}" data-i18n-ignore>${esc(basename(model))}</span>`:''}${lora?`<span title="${esc(resourceName(lora))}" data-i18n-ignore>LoRA · ${esc(basename(lora))}${loras.length>1?` +${loras.length-1}`:''}</span>`:''}</div>`;
  }
  function renderGeneration(asset) {
    const evidence=generationEvidence(asset); state.evidence=evidence;
    q('#galleryEvidenceScope').textContent='Prompt 只显示主生成阶段；LoRA 来自图片保存的记录。';
    const modelTypeLabels={checkpoint:'底模',diffusion:'扩散底模',diffusion_model:'扩散底模',unet:'扩散底模',text_encoder:'文本编码器',clip:'文本编码器',vae:'VAE',upscaler:'放大模型',upscale_model:'放大模型'};
    const modelHtml=evidence.models.length?`<ul class="gallery-resource-list">${evidence.models.map(item=>`<li><span>${esc(modelTypeLabels[item.kind||item.asset_type||item.type||item.role]||'模型记录')}</span><strong data-i18n-ignore>${esc(resourceName(item))}</strong></li>`).join('')}</ul>`:'<p class="gallery-note">未记录</p>';
    const valueMarkup=value=>value===null||value===undefined||value===''?'<span>未记录</span>':`<b data-i18n-ignore>${esc(value)}</b>`;
    const loraWeights=item=>{
      const model=item.strength_model??item.model_strength??item.strength??item.weight,clip=item.strength_clip??item.clip_strength;
      return [model,clip].every(value=>value===null||value===undefined||value==='')?'':`<span>Model ${valueMarkup(model)} · CLIP ${valueMarkup(clip)}</span>`;
    };
    const loraHtml=evidence.loras.length?`<ul class="gallery-resource-list">${groupLoraRecords(evidence.loras).map(group=>`<li><strong data-i18n-ignore>${esc(group.name)}</strong>${group.records.length===1?loraWeights(group.records[0]):''}</li>`).join('')}</ul>`:`<p class="gallery-note">${evidence.loraSourceStatus==='recorded_empty'?'图片保存的记录为空，未记录使用 LoRA。':'无法确认已使用的 LoRA'}</p>`;
    const loraNotice=evidence.loraSourceStatus==='partial'?'<p class="gallery-note">保存记录不完整，仅展示已识别的 LoRA。</p>':'';
    const promptHtml=Object.entries({positive:'最终正向 Prompt',negative:'最终负向 Prompt'}).map(([kind,label])=>{
      const prompt=evidence.prompts[kind],text=prompt.text;
      const content=text===null?'<p class="gallery-note">无法确认最终 Prompt</p>':text===''?'<p class="gallery-note">已记录为空</p>':`<pre>${esc(text)}</pre>`;
      return `<section class="gallery-prompt-record"><div><h4>${label}</h4><button type="button" data-gallery-copy-prompt="${kind}" ${text===null?'disabled':''}>复制</button></div>${prompt.savedExport?'<p class="gallery-note">图片保存的 Prompt（无法核对编码输入）</p>':''}${content}</section>`;
    }).join('');
    const sampleFields=[['seed','Seed'],['steps','Steps'],['cfg','CFG'],['sampler','Sampler'],['scheduler','Scheduler'],['denoise','Denoise']];
    const samplingHtml=evidence.sampling.length?evidence.sampling.map((sample,index)=>`<article class="gallery-sampling-record">${evidence.sampling.length>1?`<h4>采样记录 ${index+1}</h4>`:''}<dl><div><dt>${evidence.structured?'基础生成尺寸':'元数据尺寸（未核对）'}</dt><dd>${valueMarkup(sample.width&&sample.height?`${sample.width} × ${sample.height}`:null)}</dd></div>${sampleFields.map(([key,label])=>`<div><dt>${label}</dt><dd>${valueMarkup(sample[key]??(key==='sampler'?sample.sampler_name:undefined))}</dd></div>`).join('')}</dl></article>`).join(''):'<p class="gallery-note">未记录采样参数</p>';
    q('#galleryGenerationContent').innerHTML=`${promptHtml}<section><h4>已使用 LoRA</h4><p class="gallery-note"><strong>图片保存的 LoRA 记录</strong></p>${loraNotice}${loraHtml}</section>${evidence.models.length?`<section><h4>最终阶段模型</h4>${modelHtml}</section>`:''}${evidence.sampling.length?`<section><h4>最终阶段采样参数</h4>${samplingHtml}</section>`:''}`;
    q('#galleryEvidenceWarnings').innerHTML='';
    q('#galleryEvidenceWarnings').hidden=true;
    const snapshot=asset.project_snapshot||asset.metadata?.project_snapshot;
    q('#galleryProjectSnapshot').hidden=!snapshot||!Object.keys(snapshot).length; q('#galleryProjectSnapshotData').textContent=snapshot?JSON.stringify(snapshot,null,2):'';
  }

  function renderGrid() {
    q('#galleryGrid').innerHTML=state.items.length?state.items.map(asset=>`<article class="gallery-card ${asset.availability==='offline'?'is-offline':''}"><button type="button" class="gallery-image-button" data-gallery-open="${esc(asset.asset_id)}" aria-label="查看 ${esc(asset.title||asset.filename)}">${asset.thumbnail_url?`<img src="${esc(asset.thumbnail_url)}" alt="${esc(asset.title||asset.filename)}" loading="lazy">`:'<span class="gallery-no-image">暂无缩略图</span>'}${asset.availability==='offline'?'<span class="gallery-offline-badge">原目录未连接</span>':''}</button><div class="gallery-card-body"><strong>${esc(asset.title||asset.filename||'未命名图片')}</strong><span>${kindLabel(asset.kind)} · ${Number(asset.width)||'?'} × ${Number(asset.height)||'?'}</span>${compactEvidence(asset)}${asset.albums?.length?`<small>${asset.albums.map(esc).join(' · ')}</small>`:''}<div class="gallery-card-actions"><button type="button" data-gallery-favorite="${esc(asset.asset_id)}" aria-pressed="${Boolean(asset.favorite)}" title="${asset.favorite?'取消收藏':'收藏'}" aria-label="${asset.favorite?'取消收藏':'收藏'}"><span aria-hidden="true">${asset.favorite?'♥':'♡'}</span></button><button type="button" data-gallery-open="${esc(asset.asset_id)}">查看</button><button type="button" class="gallery-card-delete" data-gallery-delete="${esc(asset.asset_id)}" aria-label="删除图片" title="删除图片"><svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7"/></svg></button></div></div></article>`).join(''):'<div class="gallery-empty"><h2>把值得留下的画面放在一起</h2><p>这里可以整理自己的作品与收集参考。展开“添加图片与目录”，映射已有图库或选择图片。</p></div>';
    const from=state.total?state.offset+1:0,to=Math.min(state.offset+state.items.length,state.total);
    q('#galleryPageCount').textContent=`${from}–${to} / ${state.total} 张`;
    q('#galleryPrevious').disabled=state.offset===0; q('#galleryNext').disabled=state.offset+state.limit>=state.total;
    document.querySelectorAll('[data-gallery-kind]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.galleryKind===state.kind)));
  }
  async function loadAssets() {
    const run=++state.run;
    const params=new URLSearchParams({kind:state.kind,q:q('#galleryQuery').value.trim(),album:q('#galleryAlbum').value,model:q('#galleryModelFilter').value,lora:q('#galleryLoraFilter').value,favorite:String(q('#galleryFavoriteOnly').checked),offset:String(state.offset),limit:String(state.limit)});
    const result=await api(`/api/gallery/assets?${params}`);
    if(run!==state.run) return;
    state.items=result.items||[]; state.total=Number(result.total)||0;
    if(state.offset>=state.total&&state.offset>0) { state.offset=Math.max(0,Math.floor(Math.max(0,state.total-1)/state.limit)*state.limit); return loadAssets(); }
    renderGrid(); message(`共 ${state.total} 张；点击图片可以整理、分析或加入创作参考。`);
  }
  async function loadAlbums() {
    const current=q('#galleryAlbum').value,albums=await api('/api/gallery/albums');
    q('#galleryAlbum').innerHTML='<option value="">全部图集</option>'+(albums||[]).map(album=>`<option value="${esc(album)}">${esc(album)}</option>`).join('');
    if(albums.includes(current)) q('#galleryAlbum').value=current;
  }
  async function loadFacets() {
    state.facets=await api('/api/gallery/facets');
    for(const [key,selector,label] of [['models','#galleryModelFilter','全部底模'],['loras','#galleryLoraFilter','全部 LoRA']]) {
      const select=q(selector),current=select.value,items=state.facets[key]||[];
      select.innerHTML=`<option value="">${label}</option>`+items.map(item=>{ const name=typeof item==='string'?item:item.name||item.value||''; return `<option value="${esc(name)}" data-i18n-ignore>${esc(name)}${item.count?` (${Number(item.count)})`:''}</option>`; }).join('');
      if([...select.options].some(option=>option.value===current)) select.value=current;
    }
  }
  function renderRoots() {
    q('#galleryRoots').innerHTML=state.roots.length?`<h3>已登记的目录</h3>${state.roots.map(root=>{ const busy=state.jobs.some(job=>job.payload?.root_id===root.root_id&&activeJob(job)); return `<article class="gallery-root"><div><strong>${esc(root.label||root.path)}</strong><small>${esc(root.path)} · ${kindLabel(root.kind)}${root.recursive?' · 含子目录':''}</small></div><button type="button" data-gallery-scan="${esc(root.root_id)}" ${busy?'disabled':''}>${busy?'扫描中…':'重新扫描'}</button></article>`; }).join('')}`:'';
  }
  function renderJobs() {
    const labels={queued:'等待扫描',running:'正在扫描',completed:'已完成',failed:'扫描失败',canceled:'已暂停',cancelled:'已暂停'};
    q('#galleryJobs').innerHTML=state.jobs.slice(0,6).map(job=>{ const progress=job.progress||{},current=Number(progress.current??job.progress_current)||0,total=Number(progress.total??job.progress_total)||0,result=job.result||{}; return `<article class="gallery-job"><div><strong>${esc(labels[job.status]||job.status)}</strong><p>${esc(job.message||progress.message||job.progress_message||'')}${total?` · ${current} / ${total}`:''}</p>${job.status==='completed'?`<p>新增或更新 ${Number(result.indexed??result.imported??result.scanned)||0} 张${result.skipped_unchanged?`，复用 ${Number(result.skipped_unchanged)} 张`:''}</p>`:''}${job.error?`<p>${esc(job.error)}</p>`:''}</div>${activeJob(job)?`<button type="button" data-gallery-job="cancel" data-job-id="${esc(job.job_id)}">暂停</button>`:['failed','canceled','cancelled'].includes(job.status)?`<button type="button" data-gallery-job="retry" data-job-id="${esc(job.job_id)}">继续</button>`:''}</article>`; }).join('');
    renderRoots();
  }
  async function loadRoots() { state.roots=await api('/api/gallery/roots'); renderRoots(); }
  function scheduleJobs(delay=1200) {
    clearTimeout(state.jobTimer);
    if(q('#galleryPage').hidden) return;
    state.jobTimer=setTimeout(()=>refreshJobs().catch(err=>{ message(`扫描状态暂时不可用：${err.message}`); scheduleJobs(3000); }),delay);
  }
  async function refreshJobs() {
    const previous=state.jobs;
    state.jobs=(await api('/api/jobs?limit=100')).filter(job=>job.job_type==='gallery_scan'); renderJobs();
    if(state.jobs.some(job=>job.status==='completed'&&previous.find(old=>old.job_id===job.job_id)?.status!=='completed')) await Promise.all([loadAssets(),loadAlbums(),loadRoots(),loadFacets()]);
    if(state.jobs.some(activeJob)) scheduleJobs(); else clearTimeout(state.jobTimer);
  }
  async function scanRoot(rootId) {
    const job=await send(`/api/gallery/roots/${encodeURIComponent(rootId)}/scan`,{});
    state.jobs=[job,...state.jobs.filter(old=>old.job_id!==job.job_id)]; renderJobs(); scheduleJobs();
    message('目录扫描已开始，可以继续浏览；只会读取原图并建立画廊索引。');
  }
  async function loadModelsAndProjects() {
    const results=await Promise.allSettled([api('/api/creative/projects'),api('/api/models')]);
    if(results[0].status==='fulfilled') state.projects=results[0].value;
    if(results[1].status==='fulfilled') state.models=(results[1].value.models||[]).filter(model=>model.vision);
    const previous=q('#galleryVisionModel').value,preferred=state.models.find(model=>model.loaded)||state.models[0];
    q('#galleryVisionModel').innerHTML=state.models.length?state.models.map(model=>`<option value="${esc(model.id)}">${esc(model.name||model.id)}${model.loaded?' · 已加载':''}</option>`).join(''):'<option value="">暂无可用看图模型</option>';
    if(state.models.some(model=>model.id===previous)) q('#galleryVisionModel').value=previous; else if(preferred) q('#galleryVisionModel').value=preferred.id;
    q('#galleryVisionModel').disabled=!state.models.length; q('#galleryAnalyze').disabled=!state.models.length||assetOffline(state.active);
    const options=state.projects.map(project=>`<option value="${esc(project.project_id)}">${esc(project.title)} · 第 ${Number(project.lineage?.iteration)||1} 版</option>`).join('');
    q('#galleryAssetProject').innerHTML='<option value="">暂不关联</option>'+options;
    q('#galleryReferenceProject').innerHTML=options||'<option value="">先在绘图创作建立项目</option>';
    const current=state.active?.project_id||window.getCreativeProjectId?.();
    if(state.projects.some(project=>project.project_id===state.active?.project_id)) q('#galleryAssetProject').value=state.active.project_id;
    if(state.projects.some(project=>project.project_id===current)) q('#galleryReferenceProject').value=current;
    q('#galleryAddReference').disabled=!state.projects.length||assetOffline(state.active); q('#galleryOpenProject').disabled=!state.projects.length;
  }
  const analysisLabels={summary_zh:'画面摘要',style_zh:'画风',composition_zh:'镜头与构图',camera_zh:'镜头位置',action_zh:'动作与互动',lighting_zh:'光线',scene_zh:'场景与空间',intent_zh:'情绪与主题',clues_zh:'故事线索',visual_clues:'视觉线索',strengths:'值得保留',issues:'观察到的问题',improvements:'可尝试的变化',warnings:'需要注意',notes_zh:'分析说明',observed_slots:'实际观察',suggested_slots:'参考建议',character:'角色',outfit:'服装',action:'动作',composition:'构图',scene:'场景',lighting:'光线',style:'画风',model:'分析模型',purpose:'参考用途',safety_warning:'内容提示'};
  function analysisMarkup(value,depth=0) {
    if(value===null||value===undefined) return '';
    if(typeof value!=='object') return `<p>${esc(value)}</p>`;
    if(depth>3) return `<pre>${esc(JSON.stringify(value,null,2))}</pre>`;
    if(Array.isArray(value)) return `<ul>${value.map(item=>`<li>${analysisMarkup(item,depth+1)}</li>`).join('')}</ul>`;
    return Object.entries(value).filter(([key])=>!['image_path','created_at','asset_id','raw_response'].includes(key)).map(([key,item])=>`<section><strong>${esc(analysisLabels[key]||key)}</strong>${analysisMarkup(item,depth+1)}</section>`).join('');
  }
  function renderAnalysis(analysis,pending=false) {
    const exists=analysis&&Object.keys(analysis).length>0;
    const purposeLabels={style:'画风',composition:'镜头与构图',action:'动作与互动',lighting:'光线',scene:'场景与空间',all:'整体参考'};
    const visible=exists?Object.fromEntries(['summary_zh','observed_slots','strengths','issues','improvements','warnings'].filter(key=>analysis[key]!==undefined).map(key=>[key,analysis[key]])):{};
    if(exists&&analysis.safety_warning) visible.safety_warning=analysis.safety_warning;
    const prompts=exists?analysis.reconstructed_prompts:null;
    q('#galleryAnalysisContent').innerHTML=exists?`<p class="gallery-analysis-state">${pending?'分析预览 · 尚未保存':analysis.stale?'已保存的分析已过期，请连接原目录后重新分析':'已确认的分析'}</p><div class="gallery-analysis-meta">${analysis.purpose?`<span>${esc(purposeLabels[analysis.purpose]||'参考用途')}</span>`:''}${analysis.model?`<span data-i18n-ignore>${esc(analysis.model)}</span>`:''}</div>${analysisMarkup(visible)}${prompts&&Object.keys(prompts).length?`<details><summary>反推的 Prompt（模型建议）</summary><pre>${esc(JSON.stringify(prompts,null,2))}</pre></details>`:''}<details><summary>原始分析记录</summary><pre>${esc(JSON.stringify(analysis,null,2))}</pre></details>`:'<p class="gallery-note">还没有保存分析。先选参考用途，再按需拆解。</p>';
    q('#gallerySaveAnalysis').hidden=!pending;
  }
  async function openAsset(assetId,opener) {
    if(!state.items.some(item=>item.asset_id===assetId)) return;
    const run=++state.detailRun; state.opener=opener||document.activeElement;
    let asset;
    try { asset=await api(`/api/gallery/assets/${encodeURIComponent(assetId)}`); }
    catch(err) { if(run===state.detailRun) message(`读取图片详情失败：${err.message}`); throw err; }
    if(run!==state.detailRun) return;
    state.active=asset; state.analysis=null;
    q('#galleryDetailTitle').textContent=asset.title||asset.filename||'图片详情'; q('#galleryDetailKind').textContent=kindLabel(asset.kind);
    q('#galleryDetailImage').dataset.fallbackUsed=assetOffline(asset)?'true':'';
    q('#galleryDetailImage').src=(assetOffline(asset)?asset.thumbnail_url:asset.original_url)||asset.thumbnail_url||''; q('#galleryDetailImage').alt=asset.title||asset.filename||'画廊图片';
    q('#galleryDetailAvailability').textContent=assetOffline(asset)?'原目录当前未连接；这里展示已保存的缩略图。重新连接后可查看原图、分析和加入参考。':`${Number(asset.width)||'?'} × ${Number(asset.height)||'?'} · ${asset.filename||''}`;
    q('#galleryOpenOriginal').href=asset.original_url||''; q('#galleryOpenOriginal').hidden=!asset.original_url||assetOffline(asset);
    q('#galleryAssetTitle').value=asset.title||asset.filename||''; q('#galleryAssetKind').value=asset.kind; q('#galleryAssetFavorite').checked=Boolean(asset.favorite);
    q('#galleryAssetAuthor').value=asset.author||''; q('#galleryAssetSource').value=safeLink(asset.source_url)||''; q('#galleryAssetTags').value=(asset.tags||[]).join('，'); q('#galleryAssetAlbums').value=(asset.albums||[]).join('，'); q('#galleryAssetNote').value=asset.note||'';
    const metadata=asset.metadata||{}; q('#galleryMetadata').textContent=Object.keys(metadata).length?JSON.stringify(metadata,null,2):'无生成元数据。'; renderGeneration(asset);
    renderAnalysis(asset.analysis); message(asset.analysis_stale||asset.analysis?.stale?'旧分析已过期，不会用于 AI 场景与画风建议。请连接原目录，重新分析并确认保存。':'',true); q('#galleryDetailDialog').showModal(); await loadModelsAndProjects();
  }
  function closeAsset() { if(state.deleteBusy) return; cancelDelete(); state.detailRun++; state.active=null; state.analysis=null; q('#galleryDetailDialog').close(); if(state.opener?.isConnected) state.opener.focus(); else q('#galleryRefresh').focus(); }
  function requestDelete(asset=state.active,opener=null) {
    if(!asset?.asset_id||state.deleteBusy) return;
    state.deleteTarget=asset.asset_id; state.deleteOpener=opener;
    state.deleteDetailRun=asset===state.active?state.detailRun:null;
    q('#galleryDeleteName').textContent=asset.title||asset.filename||'';
    q('#galleryDeleteStatus').textContent='';
    q('#galleryDeleteDialog').showModal();
  }
  function cancelDelete() {
    if(state.deleteBusy) return;
    state.deleteTarget=null; q('#galleryDeleteDialog').close();
    if(state.deleteOpener?.isConnected) state.deleteOpener.focus();
    state.deleteOpener=null;
  }
  async function confirmDelete() {
    const assetId=state.deleteTarget;
    if(!assetId||state.deleteBusy) return;
    if(state.deleteDetailRun!==null&&(state.active?.asset_id!==assetId||state.detailRun!==state.deleteDetailRun)) return;
    state.deleteBusy=true;
    q('#galleryDeleteConfirm').disabled=true; q('#galleryDeleteCancel').disabled=true;
    try {
      await api(`/api/gallery/assets/${encodeURIComponent(assetId)}`,{method:'DELETE'});
    } catch(err) {
      q('#galleryDeleteStatus').textContent=err.message; return;
    } finally {
      state.deleteBusy=false;
      q('#galleryDeleteConfirm').disabled=false; q('#galleryDeleteCancel').disabled=false;
    }
    if(state.active?.asset_id===assetId) closeAsset(); else cancelDelete();
    try { await Promise.all([loadAlbums(),loadFacets()]); await loadAssets(); message('已从 Hub 删除图片，源文件保留。'); q('#galleryRefresh').focus(); }
    catch(err) { message(`图片已从 Hub 删除，刷新列表失败：${err.message}`); }
  }
  async function updateActive(body) {
    const assetId=state.active?.asset_id; if(!assetId) return;
    const asset=await send(`/api/gallery/assets/${encodeURIComponent(assetId)}`,body,'PUT');
    const index=state.items.findIndex(item=>item.asset_id===assetId); if(index>=0) state.items[index]=asset;
    if(state.active?.asset_id===assetId) state.active=asset;
    renderGrid(); return asset;
  }
  async function analyzeActive() {
    const assetId=state.active?.asset_id,model=q('#galleryVisionModel').value;
    if(!assetId||!model) throw new Error('请先选择可用的看图模型');
    const run=state.detailRun,button=q('#galleryAnalyze'); button.disabled=true;
    message('正在分析画面；本地模型可能需要几分钟，分析返回后先预览。',true);
    try {
      const result=await send(`/api/gallery/assets/${encodeURIComponent(assetId)}/analyze`,{model,purpose:q('#galleryReferencePurpose').value});
      if(run!==state.detailRun||state.active?.asset_id!==assetId) return;
      state.analysis=result.analysis||result; renderAnalysis(state.analysis,true); message('分析已返回。请检查内容，再确认是否保存。',true);
    } finally { button.disabled=!state.models.length||assetOffline(state.active); }
  }
  async function saveAnalysis() {
    const assetId=state.active?.asset_id,analysis=state.analysis; if(!assetId||!analysis) return;
    const run=state.detailRun;
    const result=await send(`/api/gallery/assets/${encodeURIComponent(assetId)}/analysis`,{analysis},'PUT');
    if(state.active?.asset_id!==assetId||run!==state.detailRun||state.analysis!==analysis) return;
    state.active.analysis=result.analysis||analysis; state.analysis=null; renderAnalysis(state.active.analysis); message('分析已保存，可用于场景设计与画风搭配。',true);
  }
  async function addReference() {
    const assetId=state.active?.asset_id,projectId=q('#galleryReferenceProject').value;
    if(!assetId||!projectId) throw new Error('请先选择一个绘图项目');
    if(assetOffline(state.active)) throw new Error('请先重新连接原目录，再把图片加入创作参考');
    const run=state.detailRun;
    if(window.addGalleryReference) await window.addGalleryReference(assetId,q('#galleryReferencePurpose').value,projectId);
    else await send(`/api/gallery/assets/${encodeURIComponent(assetId)}/reference/${encodeURIComponent(projectId)}`,{purpose:q('#galleryReferencePurpose').value});
    if(run!==state.detailRun||state.active?.asset_id!==assetId) return;
    message(state.active?.analysis_stale||state.active?.analysis?.stale?'图片已加入参考；旧分析已过期，不会用于 AI 建议，请重新分析并确认保存。':state.active?.analysis&&Object.keys(state.active.analysis).length?'已按所选用途加入参考；可以进入项目继续设计场景。':'图片已加入参考。尚未确认图像分析，AI 设计时先参考备注与标签；可在这里分析并保存。',true);
  }
  window.loadGallery=async function() { await Promise.all([loadAlbums(),loadFacets(),loadRoots(),refreshJobs()]); await loadAssets(); };

  q('#gallerySearchForm').addEventListener('submit',event=>{ event.preventDefault(); state.offset=0; loadAssets().catch(error); });
  q('#galleryAlbum').addEventListener('change',()=>{ state.offset=0; loadAssets().catch(error); });
  q('#galleryModelFilter').addEventListener('change',()=>{ state.offset=0; loadAssets().catch(error); });
  q('#galleryLoraFilter').addEventListener('change',()=>{ state.offset=0; loadAssets().catch(error); });
  q('#galleryFavoriteOnly').addEventListener('change',()=>{ state.offset=0; loadAssets().catch(error); });
  q('#galleryRefresh').addEventListener('click',()=>window.loadGallery().catch(error));
  document.querySelectorAll('[data-gallery-kind]').forEach(button=>button.addEventListener('click',()=>{ state.kind=button.dataset.galleryKind; state.offset=0; loadAssets().catch(error); }));
  q('#galleryPrevious').addEventListener('click',()=>{ state.offset=Math.max(0,state.offset-state.limit); loadAssets().catch(error); });
  q('#galleryNext').addEventListener('click',()=>{ state.offset+=state.limit; loadAssets().catch(error); });
  q('#galleryGrid').addEventListener('click',async event=>{
    const remove=event.target.closest('[data-gallery-delete]'); if(remove) { const asset=state.items.find(item=>item.asset_id===remove.dataset.galleryDelete); if(asset) requestDelete(asset,remove); return; }
    const open=event.target.closest('[data-gallery-open]'); if(open) { openAsset(open.dataset.galleryOpen,open).catch(err=>error(err,true)); return; }
    const favorite=event.target.closest('[data-gallery-favorite]'); if(!favorite) return;
    const asset=state.items.find(item=>item.asset_id===favorite.dataset.galleryFavorite); if(!asset) return;
    favorite.disabled=true; try { await send(`/api/gallery/assets/${encodeURIComponent(asset.asset_id)}`,{favorite:!asset.favorite},'PUT'); await loadAssets(); } catch(err) { error(err); } finally { favorite.disabled=false; }
  });
  q('#galleryRootForm').addEventListener('submit',async event=>{
    event.preventDefault(); const button=event.currentTarget.querySelector('button'); button.disabled=true;
    try { const root=await send('/api/gallery/roots',{path:q('#galleryRootPath').value.trim(),label:q('#galleryRootLabel').value.trim(),kind:q('#galleryRootKind').value,recursive:q('#galleryRootRecursive').checked}); await loadRoots(); await scanRoot(root.root_id); } catch(err) { error(err); } finally { button.disabled=false; }
  });
  q('#galleryRoots').addEventListener('click',event=>{ const button=event.target.closest('[data-gallery-scan]'); if(button) scanRoot(button.dataset.galleryScan).catch(error); });
  q('#galleryJobs').addEventListener('click',async event=>{ const button=event.target.closest('[data-gallery-job]'); if(!button) return; button.disabled=true; try { await api(`/api/jobs/${encodeURIComponent(button.dataset.jobId)}/${button.dataset.galleryJob}`,{method:'POST'}); await refreshJobs(); } catch(err) { error(err); button.disabled=false; } });
  q('#galleryUploadForm').addEventListener('submit',async event=>{
    event.preventDefault(); const files=[...q('#galleryUploadFiles').files],kind=q('#galleryUploadKind').value,button=event.currentTarget.querySelector('button'); button.disabled=true;
    try { for(let index=0;index<files.length;index++) { const file=files[index]; message(`正在添加 ${index+1} / ${files.length}：${file.name}`); await api(`/api/gallery/import?${new URLSearchParams({filename:file.name,kind})}`,{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream'},body:file}); } q('#galleryUploadFiles').value=''; state.offset=0; await Promise.all([loadAssets(),loadFacets()]); } catch(err) { error(err); } finally { button.disabled=false; }
  });
  q('#galleryDetailClose').addEventListener('click',closeAsset);
  q('#galleryDelete').addEventListener('click',()=>requestDelete());
  q('#galleryDeleteCancel').addEventListener('click',cancelDelete);
  q('#galleryDeleteConfirm').addEventListener('click',confirmDelete);
  q('#galleryDeleteDialog').addEventListener('cancel',event=>{ event.preventDefault(); cancelDelete(); });
  q('#galleryDetailImage').addEventListener('error',event=>{ const image=event.currentTarget; if(!image.dataset.fallbackUsed&&state.active?.thumbnail_url) { image.dataset.fallbackUsed='true'; image.src=state.active.thumbnail_url; q('#galleryDetailAvailability').textContent='原图暂时无法读取，这里展示已保存的缩略图。请检查原目录连接。'; } });
  q('#galleryDetailDialog').addEventListener('cancel',event=>{ event.preventDefault(); closeAsset(); });
  q('#galleryDetailDialog').addEventListener('click',event=>{ if(event.target===q('#galleryDetailDialog')) { const rect=event.target.getBoundingClientRect(); if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom) closeAsset(); } });
  q('#galleryAssetForm').addEventListener('submit',async event=>{
    event.preventDefault(); const button=event.currentTarget.querySelector('button'); button.disabled=true;
    try { const source=q('#galleryAssetSource').value.trim(),sourceUrl=safeLink(source); if(source&&!sourceUrl) throw new Error('来源链接请填写完整的 http:// 或 https:// 地址'); const asset=await updateActive({title:q('#galleryAssetTitle').value.trim(),kind:q('#galleryAssetKind').value,favorite:q('#galleryAssetFavorite').checked,author:q('#galleryAssetAuthor').value.trim(),source_url:sourceUrl,tags:commaList(q('#galleryAssetTags').value),albums:commaList(q('#galleryAssetAlbums').value),note:q('#galleryAssetNote').value.trim(),project_id:q('#galleryAssetProject').value}); q('#galleryDetailTitle').textContent=asset.title||asset.filename; await loadAlbums(); message('整理已保存。',true); } catch(err) { error(err,true); } finally { button.disabled=false; }
  });
  q('#galleryAnalyze').addEventListener('click',()=>analyzeActive().catch(err=>error(err,true)));
  q('#galleryGenerationContent').addEventListener('click',async event=>{ const button=event.target.closest('[data-gallery-copy-prompt]'); if(!button) return; const text=promptRecordText(state.evidence,button.dataset.galleryCopyPrompt); if(text===null) return; try { await navigator.clipboard.writeText(text); message('Prompt 已复制。',true); } catch(err) { error(err,true); } });
  q('#gallerySaveAnalysis').addEventListener('click',()=>saveAnalysis().catch(err=>error(err,true)));
  q('#galleryAddReference').addEventListener('click',()=>addReference().catch(err=>error(err,true)));
  q('#galleryOpenProject').addEventListener('click',()=>{ const projectId=q('#galleryReferenceProject').value; if(!projectId) return; closeAsset(); window.openCreativeProject?.(projectId).catch(error); });
})();
