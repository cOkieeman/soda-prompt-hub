(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const escape = value => String(value ?? "").replace(/[&<>"']/g,c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const root = $("#workbenchPage");
  $(".shell").appendChild(root);
  const studio = $("#studioPage");
  const workspace = $("#workspacePage");
  const candidateUpload = $("#studioCandidateFiles").closest("label");
  const taggerImportHost = $("#studioProjectTaggerActions");
  const candidateUploadPlaceholder = document.createComment("dataset candidate upload position");
  candidateUpload.before(candidateUploadPlaceholder);
  const captionSettings = studio.querySelector(".tagger-run-settings");
  const captionSettingsPlaceholder = document.createComment("caption settings position");
  captionSettings.before(captionSettingsPlaceholder);
  const captionBatchButton = $("#studioCaptionBatch");
  const captionBatchPlaceholder = document.createComment("caption batch button position");
  captionBatchButton.before(captionBatchPlaceholder);
  const taggerRunSettingsHost = $("#taggerRunSettingsHost");
  const datasetMore=document.createElement('details');datasetMore.className='workbench-dataset-more';datasetMore.innerHTML='<summary>資料集操作</summary><div class="workbench-actions"></div>';
  $('#workbenchDatasetTools > .workbench-actions').appendChild(datasetMore);
  ['workbenchDatasetRename','workbenchDatasetGallery','workbenchDatasetGenerate'].forEach(id=>datasetMore.querySelector('div').appendChild($('#'+id)));
  const compactDatasetMenu=matchMedia('(max-width:760px)');
  const adaptDatasetMenu=()=>{datasetMore.open=!compactDatasetMenu.matches;};compactDatasetMenu.addEventListener('change',adaptDatasetMenu);adaptDatasetMenu();
  const referencePanel = studio.querySelector('[data-studio-panel="references"]');
  const referencePlaceholder = document.createComment("studio reference position");
  referencePanel.before(referencePlaceholder);
  const referenceDetails = document.createElement("details");
  referenceDetails.innerHTML = "<summary>參考圖片與用途</summary>";
  referenceDetails.className = "workbench-references";
  studio.querySelector(".studio-editor").appendChild(referenceDetails);
  const canvas = document.createElement("section");
  canvas.className = "workbench-canvas";
  canvas.innerHTML = '<div class="workbench-canvas-image"><p id="workbenchCanvasEmpty">生成結果預覽</p><img id="workbenchCanvasImage" alt="生成圖片" hidden></div><div class="workbench-actions"><button type="button" id="workbenchOpenGallery">前往畫廊</button><button type="button" id="workbenchCanvasEnlarge">查看大圖</button></div>';
  studio.querySelector(".studio-editor").after(canvas);
  const jobsHome = document.createComment("studio jobs position");
  $("#studioJobs").before(jobsHome);
  const state = {serial:0,engine:localStorage.getItem("soda-generation-engine") || "comfyui",datasets:[],selectedAssets:new Set(),addAssets:[],dataset:"",returnToTagger:false};
  async function api(path, values, method="POST") {
    const response = await fetch(path,{method:values === undefined ? "GET" : method,headers:{"Content-Type":"application/json"},body:values === undefined ? undefined : JSON.stringify(values)});
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "請求失敗");
    return result;
  }
  function message(text,error=false) { $("#workbenchStatus").hidden=false; $("#workbenchStatus").textContent=text; $("#workbenchStatus").dataset.error=String(error); }
  async function saveBeforeNavigation(run = ++state.serial) {
    try {
      await window.SodaStudio.save();
      return run === state.serial;
    }
    catch(error) {
      if (run === state.serial) { root.hidden=false; message(error.message,true); }
      return false;
    }
  }
  function hideScreens() {
    ["homePage","creativePage","galleryPage","discoveryPage","workspacePage","loraPage","comfyPage","remotePage","managementPage","archiveWorkspace","studioPage","studioProjectsPage","studioSettingsPage","workbenchTagger"].forEach(id => { $("#" + id).hidden=true; });
    root.hidden=false;
  }
  function updateNavigation(view) {
    document.body.dataset.appView=view;
    document.querySelector(".app-nav").dataset.menuOpen="false";
    $("#appNavToggle").setAttribute("aria-expanded","false");
    $("#appNavCurrent").textContent={creative:"創作台",gallery:"畫廊",datasets:"資料集",tagger:"打標器"}[view];
    document.querySelectorAll(".app-nav-button[data-view]").forEach(button => button.setAttribute("aria-current",button.dataset.view===view?"page":"false"));
    document.querySelectorAll(".app-settings-menu").forEach(menu => { menu.open=false; });
  }
  function updateCanvas() {
    const current=window.SodaStudio.current();
    const images=current.images.filter(item=>item.kind==="candidate");
    const image=images[images.length-1];
    $("#workbenchCanvasImage").hidden=!image;
    $("#workbenchCanvasEmpty").hidden=Boolean(image);
    $("#workbenchCanvasEnlarge").disabled=!image;
    if (image) $("#workbenchCanvasImage").src=image.image_url || image.thumbnail_url;
  }
  async function datasetList() {
    state.datasets=await api("/api/workbench/datasets");
    $("#workbenchDatasetList").innerHTML=state.datasets.length ? state.datasets.map(item=>'<article class="workbench-dataset-row"><div><h2 data-i18n-ignore>'+escape(item.name)+'</h2><p>'+escape(item.image_count)+' · '+escape(item.target || item.source_path || "")+'</p></div><div class="workbench-actions"><button type="button" data-workbench-dataset="'+escape(item.id)+'" data-dataset-kind="'+escape(item.kind)+'">開啟</button>'+(item.kind==="directory"?'<label>訓練目標<select data-import-target><option value="moss">MOSS</option><option value="anima">Anima</option><option value="krea2">Krea2</option><option value="h3">MiniMax H3 Image</option></select></label><button type="button" data-workbench-import="'+escape(item.id)+'">加入統一工作區</button>':'')+'</div></article>').join("") : '<p class="studio-empty">建立資料集，或從畫廊選圖加入。</p>';
  }
  async function taggingProjectList() {
    state.datasets=await api("/api/workbench/datasets");
    const projects=state.datasets.filter(item=>item.kind==="project");
    $("#workbenchTaggerList").innerHTML=projects.length ? projects.map(item=>'<article class="workbench-dataset-row"><div><h2 data-i18n-ignore>'+escape(item.name)+'</h2><p><span data-i18n-ignore>'+escape(item.image_count)+'</span> <span>圖片</span> · <span data-i18n-ignore>'+escape(item.target)+'</span></p></div><div class="workbench-actions"><button type="button" data-workbench-tagger="'+escape(item.id)+'">打开打标器</button></div></article>').join("") : '<p class="studio-empty">还没有数据集项目。</p>';
  }
  function positionCandidateUpload(inTagger) {
    if (inTagger) {
      taggerImportHost.append(candidateUpload, captionBatchButton);
      taggerRunSettingsHost.appendChild(captionSettings);
      return;
    }
    candidateUploadPlaceholder.after(candidateUpload);
    captionBatchPlaceholder.after(captionBatchButton);
    captionSettingsPlaceholder.after(captionSettings);
  }
  function updateTaggerFlow() {
    const descriptions={
      vision:"視覺模型 API 根據圖片生成描述草稿。",
      wd14:"WD14 在本機 CPU 生成標籤草稿。",
      pixai:"PixAI 依標籤信心值生成 Danbooru 標籤。",
      gbc:"KohakuGBC 使用視覺模型描述場景並建立關係圖。",
      pixai_gbc:"PixAI 標籤與視覺描述送入 KohakuGBC，使用設定的偵測模型及視覺模型建立關係圖，最多擴展兩輪。",
    };
    $("#workbenchTaggerFlow").textContent=descriptions[$("#studioCaptionMethod").value] || descriptions.vision;
  }
  async function open(view,options={}) {
    const run=++state.serial;
    if (!await saveBeforeNavigation(run) || run!==state.serial) return;
    const incoming=options.route || {view};
    const route={...incoming,view:["projects","studio"].includes(view)?"datasets":view==="comfy"?"gallery":view};
    if (view==="studio") route.step=incoming.step || "review";
    if (view==="projects") route.project="";
    if (route.view!=="gallery") state.returnToTagger=false;
    positionCandidateUpload(route.view==="tagger");
    hideScreens(); updateNavigation(route.view);
    $("#appNavToggle small").textContent="打開選單";
    $("#workbenchCreation").hidden=route.view!=="creative";
    $("#workbenchDatasets").hidden=route.view!=="datasets";
    $("#workbenchTagger").hidden=route.view!=="tagger";
    taggerImportHost.hidden=route.view!=="tagger";
    $("#studioTaggerJobs").hidden=route.view!=="tagger";
    $("#studioTaggerSelection").hidden=route.view!=="tagger";
    $("#workbenchStatus").hidden=true;
    try {
      if (route.view==="creative") {
        state.engine=route.engine || state.engine;
        route.engine=state.engine;
        localStorage.setItem("soda-generation-engine",state.engine);
        document.querySelectorAll("[data-generation-engine]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.generationEngine===state.engine)));
        $("#workbenchGenerationHost").hidden=true;
        $("#workbenchAgentHost").hidden=true;
        $("#creationParameterShortcut").hidden=true;
        message("正在載入創作台…");
        if (state.engine==="agent") {
          window.PromptHubNavigation.commit(route,options.historyMode || "push");
          await window.SodaAgent?.open();
          if (run!==state.serial) return;
          $("#workbenchAgentHost").hidden=false;
        } else {
          const draft=await api("/api/workbench/drafts/"+state.engine,{});
          if (run!==state.serial) return;
          const current=window.SodaStudio.current();
          if(current.project?.project_id===draft.project_id&&current.project.revision!==draft.revision)current.project=null;
          route.project=draft.project_id;
          window.PromptHubNavigation.commit(route,options.historyMode || "push");
          $("#workbenchGenerationHost").appendChild(studio); studio.hidden=false;
          jobsHome.after($("#studioJobs"));
          await window.ensureDatasetStudio({...route,step:"generate"});
          if (run!==state.serial) return;
          referenceDetails.appendChild(referencePanel); referencePanel.hidden=false;
          canvas.hidden=false;
          if (window.SodaStudio.current().project.studio.backend!==state.engine) window.SodaStudio.setFields({backend:state.engine});
          updateCanvas();
          $("#workbenchGenerationHost").hidden=false;
          $("#creationParameterShortcut").hidden=state.engine!=="novelai";
          window.dispatchEvent(new Event("soda-studio-populated"));
        }
        $("#workbenchStatus").hidden=true;
      } else if (route.view==="tagger") {
        window.PromptHubNavigation.commit(route,options.historyMode || "push");
        $("#workbenchTaggerProjects").hidden=Boolean(route.project);
        $("#workbenchTaggerEditor").hidden=!route.project;
        if (route.project) {
          state.dataset=route.project;
          $("#workbenchTaggerStudioHost").appendChild(studio); studio.hidden=false;
          $("#studioTaggerJobs").appendChild($("#studioJobs"));
          await window.ensureDatasetStudio({...route,step:"caption"});
          updateTaggerFlow();
        } else {
          state.dataset="";
          await taggingProjectList();
        }
      } else if (route.view==="datasets") {
        root.dataset.datasetOpen=String(Boolean(route.project));
        window.PromptHubNavigation.commit(route,options.historyMode || "push");
        $("#workbenchDatasetList").hidden=Boolean(route.project || route.tab==="import");
        $("#workbenchDatasetTools").hidden=!route.project;
        $("#workbenchDatasetJobs").hidden=route.tab!=="jobs";
        $("#workbenchDirectoryHost").hidden=!(route.tab==="directory" || route.tab==="import");
        $("#workbenchDatasetHost").hidden=!route.project || route.tab==="directory" || route.tab==="jobs";
        if (route.tab==="directory" || route.tab==="import") {
          $("#workbenchDirectoryHost").appendChild(workspace); workspace.hidden=false;
          if (route.project) await window.openDatasetWorkspace(route.project);
          else await window.ensureDatasetWorkspace();
        } else if (route.project) {
          state.dataset=route.project;
          $("#workbenchDatasetHost").appendChild(studio); studio.hidden=false;
          referencePlaceholder.after(referencePanel);
          canvas.hidden=true;
          const step=["review","caption","export"].includes(route.step)?route.step:"review";
          await window.ensureDatasetStudio({...route,step});
          document.querySelectorAll("[data-dataset-section]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.datasetSection===(route.tab==="jobs"?"jobs":step))));
          if (route.tab==="jobs") $("#workbenchDatasetJobs").appendChild($("#studioJobs"));
          else jobsHome.after($("#studioJobs"));
        } else await datasetList();
      } else {
        window.PromptHubNavigation.commit(route,options.historyMode || "push");
        root.hidden=true; $("#galleryPage").hidden=false;
        if(route.tab!=="online") await window.loadGallery();
        if(run!==state.serial)return;
        await window.SodaOnlineGallery?.open(route.tab || "local");
        if(run!==state.serial)return;
        if (route.asset) await window.SodaGallery?.open(route.asset);
      }
      if (run===state.serial) window.PromptHubNavigation.restore(route);
    } catch(error) { message(error.message,true); window.PromptHubNavigation.restore(route); }
  }
  async function applySlots(fields, options = {}) {
    const engine = options.engine || (state.engine === "agent" ? "comfyui" : state.engine);
    await open("creative",{route:{view:"creative",engine}});
    const recipe=window.SodaStudio.current().project.studio;
    window.SodaStudio.setFields(Object.fromEntries(Object.entries(fields).map(([name,value])=>[name,options.replace ? value : [recipe[name],value].filter(Boolean).join("\n")])));
    await window.SodaStudio.save();
  }
  async function repair(assetId) {
    const asset=await api('/api/gallery/assets/'+encodeURIComponent(assetId));
    if(state.engine==='agent'){
      await open('creative',{route:{view:'creative',engine:'agent'}});
      window.SodaAgent.attach(asset);return;
    }
    const engine=state.engine==='novelai'?'novelai':'comfyui';
    const draft=await api('/api/workbench/drafts/'+engine,{});
    await api('/api/workbench/datasets/'+draft.project_id+'/assets',{asset_ids:[assetId],kind:'reference',role:'identity'});
    const result=await api('/api/studio/projects/'+draft.project_id);
    if(engine==='novelai'){
      for(const image of result.images.filter(i=>i.kind==='reference'&&i.asset_id!==assetId&&i.review!=='excluded'))await api('/api/studio/projects/'+draft.project_id+'/images/'+image.item_id,{review:'excluded'},'PUT');
    }
    const source=result.images.find(i=>i.kind==='reference'&&i.asset_id===assetId);
    if(source?.review==='excluded')await api('/api/studio/projects/'+draft.project_id+'/images/'+source.item_id,{review:'pending'},'PUT');
    await api('/api/studio/projects/'+draft.project_id,{studio:{...result.project.studio,count:1,repair_parent_asset:assetId,...(engine==='novelai'?{novelai_mode:'img2img'}:{})},expected_revision:result.project.revision},'PUT');
    await open('creative',{route:{view:'creative',engine}});
    await window.SodaStudio.refresh();referenceDetails.open=true;
    $('#studioStatus').textContent='已將圖片加入參考素材，可修改提示詞並生成修正版。ComfyUI 請設定參考圖輸入。';
  }
  async function addToDataset(assetIds) {
    state.addAssets=[...new Set(assetIds)];
    const projects=(await api("/api/workbench/datasets")).filter(item=>item.kind==="project");
    $("#workbenchTargetDataset").innerHTML=projects.map(item=>'<option value="'+escape(item.id)+'">'+escape(item.name)+'</option>').join("");
    if (state.dataset && projects.some(item=>item.id===state.dataset)) $("#workbenchTargetDataset").value=state.dataset;
    $("#workbenchAddCount").textContent=state.addAssets.length+" 張圖片";
    $("#workbenchAddStatus").textContent="";
    $("#workbenchOpenAdded").hidden=true;
    $("#workbenchDatasetDialog").showModal();
  }
  document.querySelectorAll("[data-generation-engine]").forEach(button=>button.addEventListener("click",()=>open("creative",{route:{view:"creative",engine:button.dataset.generationEngine}})));
  $("#workbenchTaggerNew").addEventListener("click",()=>{ $("#workbenchTaggerCreate").hidden=false; $("#workbenchTaggerCreate").elements.title.focus(); });
  $("#workbenchTaggerCancel").addEventListener("click",()=>{ $("#workbenchTaggerCreate").hidden=true; $("#workbenchTaggerCreate").reset(); });
  $("#workbenchTaggerCreate").addEventListener("submit",async event=>{
    event.preventDefault(); const form=event.currentTarget,button=event.submitter || form.querySelector('[type="submit"]'); button.disabled=true;
    try { const project=await api("/api/studio/projects",{title:form.elements.title.value.trim(),target:form.elements.target.value}); form.reset(); form.hidden=true; await open("tagger",{route:{view:"tagger",project:project.project_id}}); }
    catch(error) { message(error.message,true); } finally { button.disabled=false; }
  });
  $("#workbenchTaggerList").addEventListener("click",event=>{const button=event.target.closest("[data-workbench-tagger]");if(button)open("tagger",{route:{view:"tagger",project:button.dataset.workbenchTagger}});});
  $("#workbenchTaggerBack").addEventListener("click",()=>open("tagger"));
  $("#workbenchTaggerGallery").addEventListener("click",()=>{state.returnToTagger=true;open("gallery",{route:{view:"gallery",project:state.dataset,tab:"local"}});});
  $("#studioCaptionMethod").addEventListener("change",updateTaggerFlow);
  $("#workbenchNewDataset").addEventListener("click",()=>{ $("#workbenchCreateDataset").hidden=false; $("#workbenchCreateDataset").elements.title.focus(); });
  $("#workbenchCancelDataset").addEventListener("click",()=>{ $("#workbenchCreateDataset").hidden=true; });
  $("#workbenchCreateDataset").addEventListener("submit",async event=>{
    event.preventDefault(); const form=event.currentTarget,button=event.submitter || form.querySelector('[type="submit"]'); button.disabled=true;
    try { const project=await api("/api/studio/projects",Object.fromEntries(new FormData(form))); form.hidden=true; form.reset(); await open("datasets",{route:{view:"datasets",project:project.project_id,step:"review"}}); }
    catch(error) { message(error.message,true); } finally { button.disabled=false; }
  });
  $("#workbenchDatasetList").addEventListener("click",event=>{const button=event.target.closest("[data-workbench-dataset]");if(button)open("datasets",{route:{view:"datasets",project:button.dataset.workbenchDataset,step:"review",tab:button.dataset.datasetKind==="directory"?"directory":""}});});
  $("#workbenchDatasetList").addEventListener("click",async event=>{const button=event.target.closest("[data-workbench-import]");if(!button)return;button.disabled=true;message("正在匯入圖片與既有標注，原始檔案會保留。");try{const result=await api('/api/workbench/workspaces/'+encodeURIComponent(button.dataset.workbenchImport)+'/import',{target:button.closest('article').querySelector('[data-import-target]').value});await open('datasets',{route:{view:'datasets',project:result.project_id,step:'review'}});if(result.errors.length)message(JSON.stringify(result.errors),true);}catch(error){message(error.message,true);}finally{button.disabled=false;}});
  $("#workbenchDatasetBack").addEventListener("click",()=>open("datasets"));
  $("#workbenchImportDataset").addEventListener("click",()=>open("datasets",{route:{view:"datasets",tab:"import"}}));
  $("#workbenchDatasetGallery").addEventListener("click",()=>{state.returnToTagger=false;open("gallery")});
  $("#workbenchDatasetGenerate").addEventListener("click",()=>open("creative"));
  $("#workbenchDatasetRename").addEventListener("click",async()=>{
    const current=window.SodaStudio.current().project;
    const title=window.prompt("資料集名稱",current.title);
    if (!title?.trim()) return;
    try { const saved=await api("/api/studio/projects/"+current.project_id,{title:title.trim(),expected_revision:current.revision},"PUT"); current.title=saved.title;current.revision=saved.revision; $("#studioProjectTitle").textContent=current.title; }
    catch(error) { message(error.message,true); }
  });
  document.querySelectorAll("[data-dataset-section]").forEach(button=>button.addEventListener("click",()=>open("datasets",{route:{view:"datasets",project:state.dataset,step:button.dataset.datasetSection==="jobs"?"review":button.dataset.datasetSection,tab:button.dataset.datasetSection==="jobs"?"jobs":""}})));
  $("#workbenchOpenGallery").addEventListener("click",()=>open("gallery"));
  $("#workbenchCanvasEnlarge").addEventListener("click",()=>{
    const images=window.SodaStudio.current().images.filter(item=>item.kind==="candidate");
    const image=images[images.length-1];
    if(image) window.SodaGallery?.open(image.asset_id);
  });
  $("#workbenchCloseAdd").addEventListener("click",()=>$("#workbenchDatasetDialog").close());
  $("#workbenchAddImages").addEventListener("submit",async event=>{
    event.preventDefault();const form=event.currentTarget,button=event.submitter || form.querySelector('[type="submit"]');button.disabled=true;
    try {
      let project=form.elements.project.value;
      if (form.elements.new_title.value.trim()) {
        const created=await api("/api/studio/projects",{title:form.elements.new_title.value.trim(),target:form.elements.target.value});
        project=created.project_id;
        const option=document.createElement("option");option.value=project;option.textContent=created.title;form.elements.project.appendChild(option);form.elements.project.value=project;
        form.elements.new_title.value="";
      }
      if (!project) throw new Error("請選擇資料集或填寫新名稱");
      const result=await api("/api/workbench/datasets/"+encodeURIComponent(project)+"/assets",{asset_ids:state.addAssets});
      state.dataset=project;
      $("#workbenchOpenAdded").hidden=false;
      $("#workbenchAddStatus").textContent="已加入 "+result.added+" 張，重複圖片已略過。";
      form.elements.new_title.value="";
    } catch(error) { $("#workbenchAddStatus").textContent=error.message; } finally { button.disabled=false; }
  });
  $("#workbenchOpenAdded").addEventListener("click",async()=>{$("#workbenchDatasetDialog").close();const view=state.returnToTagger?"tagger":"datasets";state.returnToTagger=false;await open(view,{route:view==="tagger"?{view,project:state.dataset}:{view,project:state.dataset,step:"review"}});});
  new MutationObserver(updateCanvas).observe($("#studioRecentImages"),{childList:true});
  window.SodaWorkbench={handles:view=>["creative","gallery","datasets","tagger","projects","studio","comfy"].includes(view),open,hide:()=>{state.serial++;root.hidden=true;},saveBeforeNavigation,applySlots,addToDataset,repair};
})();
