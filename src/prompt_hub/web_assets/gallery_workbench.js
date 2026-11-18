(() => {
  "use strict";
  const $=selector=>document.querySelector(selector);
  const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const page=$("#galleryPage"), heading=page.querySelector("header");
  heading.querySelector("h1").textContent="畫廊";
  heading.querySelector(".eyebrow")?.remove();
  heading.querySelector("p").textContent="整理作品與參考，查看提示詞，選入資料集。";
  const local=document.createElement("div");local.id="galleryLocalHost";
  [...page.children].filter(child=>child!==heading).forEach(child=>local.appendChild(child));
  const tabs=document.createElement("nav");tabs.className="workbench-gallery-tabs";
  tabs.innerHTML='<button type="button" data-gallery-tab="local" aria-pressed="true">本地畫廊</button><button type="button" data-gallery-tab="online" aria-pressed="false">線上畫廊</button>';
  page.append(tabs,local);
  const backend=document.createElement("label");backend.innerHTML='<span class="sr-only">生成來源</span><select id="galleryBackend"><option value="">全部生成來源</option><option value="comfyui">ComfyUI</option><option value="novelai">NovelAI</option><option value="agent">Agent</option><option value="openai">圖片 API</option></select>';
  $("#gallerySearchForm").appendChild(backend);
  backend.addEventListener("change",()=>$("#gallerySearchForm").requestSubmit());
  let selected=new Set();try{selected=new Set(JSON.parse(sessionStorage.getItem("soda-gallery-selection")||"[]"));}catch{}
  const bulk=document.createElement("div");bulk.className="workbench-gallery-bulk";
  bulk.innerHTML='<label><input type="checkbox" id="gallerySelectPage">選取本頁</label><span id="gallerySelectionCount"></span><button type="button" id="galleryAddSelected">加入資料集</button><button type="button" id="galleryClearSelection">清除選取</button>';
  $("#galleryGrid").before(bulk);
  function renderSelection(){
    $("#gallerySelectionCount").textContent=(window.t?.("已選取")||"已選取")+" "+selected.size;
    $("#galleryAddSelected").disabled=!selected.size;
    document.querySelectorAll("[data-gallery-select]").forEach(input=>{input.checked=selected.has(input.dataset.gallerySelect);});
    const ids=window.SodaGallery.items().map(item=>item.asset_id);
    $("#gallerySelectPage").checked=ids.length>0&&ids.every(id=>selected.has(id));
    $("#gallerySelectPage").indeterminate=ids.some(id=>selected.has(id))&&!ids.every(id=>selected.has(id));
    sessionStorage.setItem("soda-gallery-selection",JSON.stringify([...selected]));
  }
  window.addEventListener("soda-gallery-rendered",event=>{
    document.querySelectorAll("#galleryGrid .gallery-card").forEach((card,index)=>{
      const label=document.createElement("label");label.className="workbench-gallery-select";
      label.innerHTML='<input type="checkbox" data-gallery-select="'+esc(event.detail.items[index].asset_id)+'">選取';
      card.appendChild(label);
      const item=event.detail.items[index];
      if(item.hub_generation){const source=document.createElement('small');source.textContent=item.hub_generation.recipe?.creation_origin==='agent'?'Agent':item.hub_generation.backend;card.querySelector('.gallery-card-body').prepend(source);}
    });renderSelection();
  });
  $("#galleryGrid").addEventListener("change",event=>{const id=event.target.dataset.gallerySelect;if(!id)return;event.target.checked?selected.add(id):selected.delete(id);renderSelection();});
  $("#gallerySelectPage").addEventListener("change",event=>{window.SodaGallery.items().forEach(item=>event.target.checked?selected.add(item.asset_id):selected.delete(item.asset_id));renderSelection();});
  $("#galleryClearSelection").addEventListener("click",()=>{selected.clear();renderSelection();});
  $("#galleryAddSelected").addEventListener("click",()=>window.SodaWorkbench.addToDataset([...selected]).catch(error=>{$("#galleryStatus").textContent=error.message;}));
  const detail=document.createElement("section");detail.id="galleryHubGeneration";
  $("#galleryGenerationContent").before(detail);
  const actions=document.createElement("div");actions.className="workbench-actions";
  actions.innerHTML='<button type="button" id="gallerySendDataset">加入資料集</button><button type="button" id="galleryReusePrompt">送到創作台</button>';
  $("#galleryDetailDialog .gallery-detail-fields").prepend(actions);
  let active=null;
  window.addEventListener("soda-gallery-opened",event=>{
    active=event.detail;const record=active.hub_generation;
    window.SodaGallery.renderGeneration(active);
    const route=window.PromptHubNavigation.current();
    if(route?.view==="gallery")window.PromptHubNavigation.commit({...route,asset:active.asset_id},"replace",{preserveScroll:true});
    detail.hidden=!record;
    $("#galleryReusePrompt").disabled=!record?.prompt?.positive;
    $("#gallerySendDataset").disabled=active.availability==="offline";
    if(record)detail.innerHTML='<h3>創作記錄</h3><p>'+esc(record.recipe?.creation_origin==="agent"?"Agent":record.backend)+'</p>'+["prefix","body","negative","suffix"].map((field,index)=>'<details'+(field==="body"?' open':'')+'><summary>'+["主題與風格","正文","負面詞","後綴與簽名"][index]+'</summary><pre data-i18n-ignore>'+esc(record.prompt?.[field]||"")+'</pre></details>').join("")+'<details><summary>實際請求與參考記錄</summary><pre data-i18n-ignore>'+esc(JSON.stringify({request:record.request,references:record.references,job_id:record.job_id,seed:record.prompt?.seed,text_seed:record.prompt?.text_seed},null,2))+'</pre></details>';
    const records=active.hub_generations||[];
    if(records.length>1){const label=document.createElement('label');label.textContent=window.t?.('生成版本')||'生成版本';const select=document.createElement('select');select.innerHTML=records.map((entry,index)=>'<option value="'+index+'">'+esc(entry.recipe?.creation_origin==='agent'?'Agent':entry.backend)+' · '+esc(entry.created_at?new Date(entry.created_at).toLocaleString():String(index+1))+'</option>').join('');select.value=String(records.findIndex(entry=>entry.job_id===record?.job_id));select.addEventListener('change',()=>{const selected=records[Number(select.value)];window.dispatchEvent(new CustomEvent('soda-gallery-opened',{detail:{...active,hub_generation:selected}}));});label.appendChild(select);detail.prepend(label);}
    if(record?.references?.some(ref=>ref.asset_id)){const references=document.createElement('div');references.className='gallery-hub-references';references.innerHTML=record.references.filter(ref=>ref.asset_id).map(ref=>'<a href="/api/gallery/assets/'+esc(ref.asset_id)+'/media/original" target="_blank" rel="noreferrer"><img src="/api/gallery/assets/'+esc(ref.asset_id)+'/media/thumbnail" alt="'+esc(ref.role)+'" loading="lazy"></a>').join('');detail.appendChild(references);}

  });
  window.addEventListener("soda-gallery-closed",()=>{const route=window.PromptHubNavigation.current();if(route?.view==="gallery"&&route.asset){const next={...route};delete next.asset;window.PromptHubNavigation.commit(next,"replace",{preserveScroll:true});}});
  $("#gallerySendDataset").addEventListener("click",async()=>{if(!active)return;const id=active.asset_id;window.SodaGallery.close();await window.SodaWorkbench.addToDataset([id]);});
  $("#galleryReusePrompt").addEventListener("click", async () => {
    const record = active?.hub_generation;
    if (!record) return;
    const fields = Object.fromEntries(["prefix", "body", "negative", "suffix"].map(field => [field, record.prompt[field] || ""]));
    if (record.backend === "novelai") {
      fields.characters = structuredClone(record.recipe?.characters || []);
      fields.character_position_mode = record.recipe?.character_position_mode || "ai";
      fields.nai_quality = record.recipe?.nai_quality || "";
      fields.nai_quality_text = record.recipe?.nai_quality_text || "";
      fields.nai_uc = record.recipe?.nai_uc || "none";
      fields.nai_uc_text = record.recipe?.nai_uc_text || "";
    }
    window.SodaGallery.close();
    await window.SodaWorkbench.applySlots(fields, {replace: true, engine: record.backend === "novelai" ? "novelai" : "comfyui"});
    const status = document.querySelector("#studioStatus");
    if (status) status.textContent = "已用畫廊提示詞替換目前內容。";
  });
  const filterIds=["galleryQuery","galleryAlbum","galleryModelFilter","galleryLoraFilter","galleryFavoriteOnly","galleryBackend"];
  try{const saved=JSON.parse(sessionStorage.getItem("soda-gallery-filters")||"{}");filterIds.forEach(id=>{if(saved[id]!==undefined){if($("#"+id).type==="checkbox")$("#"+id).checked=saved[id];else $("#"+id).value=saved[id];}});}catch{}
  $("#gallerySearchForm").addEventListener("change",saveFilters);$("#gallerySearchForm").addEventListener("submit",saveFilters);
  function saveFilters(){sessionStorage.setItem("soda-gallery-filters",JSON.stringify(Object.fromEntries(filterIds.map(id=>[id,$("#"+id).type==="checkbox"?$("#"+id).checked:$("#"+id).value]))));}
})();
