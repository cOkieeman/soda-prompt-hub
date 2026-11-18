(() => {
  "use strict";
  const $=selector=>document.querySelector(selector);
  const mediaUrl = url => "/api/online-gallery/media?url=" + encodeURIComponent(url);
  const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const host=document.createElement("section");host.id="onlineGalleryHost";host.hidden=true;
  host.innerHTML='<form id="onlineGalleryForm" class="online-gallery-toolbar"><label>來源<select id="onlineSource"><option value="danbooru">Danbooru</option><option value="safebooru">Safebooru</option><option value="gelbooru">Gelbooru</option><option value="aitag">AI TAG</option><option value="quicktagcloud" selected>QuickTagCloud</option></select></label><label>瀏覽方式<select id="onlineFeed"><option value="search">搜尋</option><option value="popular">熱門</option><option value="random">隨機</option><option value="favorites">本地收藏</option><option value="remote_favorites">遠端收藏</option></select></label><label id="onlineQueryField">關鍵詞<input id="onlineQuery" type="search" placeholder="標籤或提示詞" maxlength="1000"></label><label id="onlineRemoteUserField" hidden>使用者名稱或 ID<input id="onlineRemoteUser" maxlength="160" autocomplete="off"></label><label id="onlinePeriodField">榜單<select id="onlinePeriod"><option value="day">每日</option><option value="week">每週</option><option value="month">每月</option></select></label><label id="onlineDateField">日期<input type="date" id="onlineDate"></label><label id="onlineCodexField" hidden>詞典<select id="onlineCodex"><option value="">全部詞典</option></select></label><button type="submit" class="gallery-primary">載入</button></form><details id="onlineAccountPanel"><summary>Danbooru 帳號</summary><form id="onlineAccountForm" class="online-gallery-toolbar"><label>使用者名稱<input id="onlineAccountUser" maxlength="160" autocomplete="username"></label><label>API Key<input id="onlineAccountKey" type="password" maxlength="12000" autocomplete="new-password" placeholder="留空沿用已保存的 Key"></label><button type="submit">驗證並保存</button><button type="button" id="onlineClearAccount">移除帳號</button></form><p id="onlineAccountStatus" role="status"></p></details><p id="onlineStatus" role="status"></p><div id="onlineGrid" class="gallery-grid"></div><nav class="gallery-pagination"><button type="button" id="onlinePrevious">上一頁</button><span id="onlinePage"></span><button type="button" id="onlineNext">下一頁</button></nav>';
  $("#galleryPage").appendChild(host);
  const dialog=document.createElement("dialog");dialog.className="online-detail-dialog";
  dialog.innerHTML='<header class="workbench-heading"><h2 id="onlineTitle"></h2><button type="button" id="onlineClose">關閉</button></header><div class="online-detail-layout"><div><img id="onlineImage" alt=""><div id="onlineMediaChoices" class="workbench-actions"></div></div><div><a id="onlineSourceLink" target="_blank" rel="noreferrer">開啟來源</a><pre id="onlinePrompt" data-i18n-ignore></pre><div class="workbench-actions"><button type="button" id="onlineFavorite">收藏</button><button type="button" id="onlineRemoteFavorite" hidden>加入遠端收藏</button><button type="button" id="onlineSendPrompt">提示詞送到創作台</button><button type="button" id="onlineSave">保存到畫廊</button><button type="button" id="onlineDataset">加入資料集</button></div><details><summary>來源參數</summary><pre id="onlineMetadata" data-i18n-ignore></pre></details><p id="onlineDetailStatus" role="status"></p></div></div>';
  document.body.appendChild(dialog);
  const state={run:0,detailRun:0,items:[],page:1,seed:Math.floor(Math.random()*2**31),active:null,saved:null,loaded:false,account:null};
  async function api(path,body,method="POST",signal){const response=await fetch("/api/online-gallery"+path,{method:body===undefined?"GET":method,headers:{"Content-Type":"application/json"},body:body===undefined?undefined:JSON.stringify(body),signal});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"請求失敗");return data;}
  function persist(){localStorage.setItem("soda-online-gallery",JSON.stringify({source:$("#onlineSource").value,feed:$("#onlineFeed").value,q:$("#onlineQuery").value,page:state.page,seed:state.seed,codex:$("#onlineCodex").value,period:$("#onlinePeriod").value,date:$("#onlineDate").value,username:$("#onlineRemoteUser").value}));}
  try{const saved=JSON.parse(localStorage.getItem("soda-online-gallery")||"{}");for(const [key,id]of Object.entries({source:"onlineSource",feed:"onlineFeed",q:"onlineQuery",period:"onlinePeriod",date:"onlineDate",username:"onlineRemoteUser"})){if(saved[key]!==undefined)$("#"+id).value=saved[key];}state.page=saved.page||1;state.seed=saved.seed||state.seed;state.codex=saved.codex||"";}catch{}
  function capabilities(){
    const source=$("#onlineSource").value;
    const supportsAccount=["danbooru","safebooru"].includes(source);
    $("#onlineAccountPanel").hidden=!supportsAccount;
    $("#onlineFeed option[value='remote_favorites']").disabled=!supportsAccount;
    $("#onlineFeed option[value='popular']").disabled=["gelbooru","quicktagcloud"].includes(source);
    if($("#onlineFeed").selectedOptions[0]?.disabled)$("#onlineFeed").value="search";
    const remote=$("#onlineFeed").value==="remote_favorites";
    $("#onlineRemoteUserField").hidden=!remote;
    $("#onlineQueryField").hidden=remote;
    const popular=$("#onlineFeed").value==="popular";
    $("#onlinePeriodField").hidden=!popular;
    $("#onlineDateField").hidden=!popular||source==="aitag";
    $("#onlineCodexField").hidden=source!=="quicktagcloud";
  }
  async function search(){
    capabilities();persist();const run=++state.run;
    state.controller?.abort();state.controller=new AbortController();
    $("#onlineStatus").textContent="正在讀取線上畫廊…";$("#onlineGrid").setAttribute("aria-busy","true");
    const params=new URLSearchParams({source:$("#onlineSource").value,feed:$("#onlineFeed").value,q:$("#onlineQuery").value,page:state.page,seed:state.seed,period:$("#onlinePeriod").value,date:$("#onlineDate").value,codex:$("#onlineCodex").value||state.codex||"",username:$("#onlineRemoteUser").value});
    try{const result=await api("/search?"+params,undefined,"GET",state.controller.signal);if(run!==state.run)return;
      state.items=result.items;state.loaded=true;
      if(result.catalogs){$("#onlineCodex").innerHTML=result.catalogs.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.title)+'</option>').join("");$("#onlineCodex").value=result.codex;state.codex=result.codex;persist();}
      $("#onlineGrid").innerHTML=result.items.map((item,index)=>'<article class="gallery-card"><button type="button" class="gallery-image-button" data-online-open="'+index+'">'+(item.thumbnail_url?'<img loading="lazy" src="'+esc(mediaUrl(item.thumbnail_url))+'" alt="'+esc(item.title)+'">':'<span class="gallery-no-image">'+(item.pending?'點擊載入圖片':'暫無預覽')+'</span>')+'</button><div class="gallery-card-body"><strong data-i18n-ignore>'+esc(item.title)+'</strong><small>'+esc(item.source)+'</small><button type="button" data-online-open="'+index+'">查看</button></div></article>').join("")||'<p class="gallery-empty">沒有符合條件的圖片</p>';
      $("#onlineStatus").textContent=result.notice||"";$("#onlinePage").textContent=String(state.page);$("#onlinePrevious").disabled=state.page===1;$("#onlineNext").disabled=!result.has_more;
      hydratePreviews(run);
    }catch(error){if(run===state.run&&error.name!=="AbortError"){$("#onlineStatus").textContent=error.message;$("#onlineGrid").innerHTML="";}}
    finally{if(run===state.run)$("#onlineGrid").removeAttribute("aria-busy");}
  }
  async function hydratePreviews(run){
    const pending=state.items.map((item,index)=>({item,index})).filter(row=>row.item.pending);
    let cursor=0;
    await Promise.all(Array.from({length:Math.min(4,pending.length)},async()=>{while(cursor<pending.length&&run===state.run&&!host.hidden){const {item,index}=pending[cursor++];try{const detail=await api('/detail/'+item.source+'/'+encodeURIComponent(item.id),undefined,'GET',state.controller.signal);if(run!==state.run||host.hidden)return;state.items[index]={...detail,favorite:item.favorite};const button=host.querySelector('[data-online-open="'+index+'"]');if(button&&detail.thumbnail_url)button.innerHTML='<img loading="lazy" src="'+esc(mediaUrl(detail.thumbnail_url))+'" alt="'+esc(detail.title)+'">';}catch(error){if(error.name==='AbortError')return;}}}));
  }
  async function inspect(item){const run=++state.detailRun;state.active=item;state.saved=null;$("#onlineTitle").textContent=item.title;$("#onlineImage").removeAttribute("src");$("#onlinePrompt").textContent=item.prompt||"";$("#onlineDetailStatus").textContent="正在載入詳情…";window.SodaOnlineViewer?.loading();if(!dialog.open)dialog.showModal();
    try{const detail=await api("/detail/"+item.source+"/"+encodeURIComponent(item.id));if(run!==state.detailRun)return;state.active={...detail,favorite:item.favorite};$("#onlineImage").src=mediaUrl(detail.original_url||detail.thumbnail_url||"");$("#onlineImage").alt=detail.title;$("#onlineSourceLink").href=detail.source_url;$("#onlinePrompt").textContent=detail.prompt||"";$("#onlineMetadata").textContent=JSON.stringify(detail.metadata,null,2);$("#onlineFavorite").textContent=item.favorite?"取消收藏":"收藏";$("#onlineSendPrompt").disabled=!detail.prompt;$("#onlineSave").disabled=!detail.original_url;$("#onlineDataset").disabled=!detail.original_url;$("#onlineDetailStatus").textContent="";$("#onlineMediaChoices").innerHTML=(detail.media||[]).map((media,index)=>'<button type="button" data-online-media="'+index+'">'+(index+1)+'</button>').join("");window.SodaOnlineViewer?.show(state.active);await refreshRemoteFavorite(run);}
    catch(error){if(run===state.detailRun){$("#onlineDetailStatus").textContent=error.message;window.SodaOnlineViewer?.loading(error.message);dialog.removeAttribute("aria-busy");}}
  }
  async function loadAccount() {
    state.account=await api("/account");
    $("#onlineAccountUser").value=state.account.username;
    $("#onlineAccountStatus").textContent=state.account.has_api_key?"帳號已連接":"可查看公開收藏；同步收藏需要帳號 API Key。";
  }
  async function refreshRemoteFavorite(run) {
    const button=$("#onlineRemoteFavorite");
    button.hidden=!["danbooru","safebooru"].includes(state.active.source);
    button.disabled=!state.account?.has_api_key;
    button.textContent="加入遠端收藏";
    if(button.hidden||button.disabled)return;
    try {
      const result=await api("/remote-favorite/"+encodeURIComponent(state.active.id));
      if(run!==state.detailRun)return;
      state.active.remoteFavorite=result.favorite;
      button.textContent=result.favorite?"移除遠端收藏":"加入遠端收藏";
    } catch(error) { if(run===state.detailRun)$("#onlineDetailStatus").textContent=error.message; }
  }
  $("#onlineAccountForm").addEventListener("submit",async event=>{
    event.preventDefault();const button=event.submitter;button.disabled=true;
    try {
      const submitted={username:$("#onlineAccountUser").value,api_key:$("#onlineAccountKey").value};
      state.account=await api("/account",submitted,"PUT");
      if($("#onlineAccountKey").value===submitted.api_key)$("#onlineAccountKey").value="";$("#onlineAccountStatus").textContent="帳號已連接";
    }catch(error){$("#onlineAccountStatus").textContent=error.message;}finally{button.disabled=false;}
  });
  $("#onlineClearAccount").addEventListener("click",async()=>{
    try{await api("/account",{},"DELETE");await loadAccount();}catch(error){$("#onlineAccountStatus").textContent=error.message;}
  });
  $("#onlineRemoteFavorite").addEventListener("click",event=>action(event.currentTarget,async()=>{
    const active=state.active;const run=state.detailRun;
    const result=await api("/remote-favorite/"+encodeURIComponent(active.id),{favorite:!active.remoteFavorite},"PUT");
    if(run!==state.detailRun)return;
    active.remoteFavorite=result.favorite;$("#onlineRemoteFavorite").textContent=result.favorite?"移除遠端收藏":"加入遠端收藏";
  }));
  async function action(button,callback){button.disabled=true;try{await callback();}catch(error){$("#onlineDetailStatus").textContent=error.message;}finally{button.disabled=false;}}
  async function save(){if(!state.saved)state.saved=await api("/save",{source:state.active.source,id:state.active.id,media_index:state.active.media_index||0});$("#onlineDetailStatus").textContent="已保存到本地畫廊";return state.saved;}
  $("#onlineGalleryForm").addEventListener("submit",event=>{event.preventDefault();state.page=1;if($("#onlineFeed").value==="random")state.seed=Math.floor(Math.random()*2**31);search();});
  $("#onlineSource").addEventListener("change",()=>{state.page=1;state.codex="";$("#onlineCodex").innerHTML='<option value="">全部詞典</option>';capabilities();search();});
  $("#onlineFeed").addEventListener("change",()=>{state.page=1;capabilities();if($("#onlineFeed").value==="remote_favorites"&&!$("#onlineRemoteUser").value){$("#onlineStatus").textContent="填寫使用者名稱後載入遠端收藏。";return;}search();});
  $("#onlineCodex").addEventListener("change",()=>{state.page=1;state.codex=$("#onlineCodex").value;search();});
  $("#onlinePrevious").addEventListener("click",()=>{state.page=Math.max(1,state.page-1);search();});$("#onlineNext").addEventListener("click",()=>{state.page++;search();});
  $("#onlineGrid").addEventListener("click",event=>{const button=event.target.closest("[data-online-open]");if(button)inspect(state.items[Number(button.dataset.onlineOpen)]);});
  $("#onlineClose").addEventListener("click",()=>{state.detailRun++;dialog.close();});dialog.addEventListener("cancel",()=>{state.detailRun++;});
  $("#onlineMediaChoices").addEventListener("click",event=>{const button=event.target.closest("[data-online-media]");if(!button)return;const media=state.active.media[Number(button.dataset.onlineMedia)];$("#onlineImage").src=mediaUrl(media.url);$("#onlinePrompt").textContent=media.prompt||"";state.active.prompt=media.prompt||"";state.active.media_index=Number(button.dataset.onlineMedia);state.saved=null;window.SodaOnlineViewer?.show(state.active);});
  $("#onlineFavorite").addEventListener("click",event=>action(event.currentTarget,async()=>{const item=state.active;await api("/favorite",{source:item.source,id:item.id,favorite:!item.favorite},"PUT");item.favorite=!item.favorite;$("#onlineFavorite").textContent=item.favorite?"取消收藏":"收藏";window.SodaOnlineViewer?.favorite();}));
  $("#onlineSendPrompt").addEventListener("click",event=>action(event.currentTarget,async()=>{const prompt=state.active.prompt;dialog.close();await window.SodaWorkbench.applySlots({body:prompt});}));
  $("#onlineSave").addEventListener("click",event=>action(event.currentTarget,save));
  $("#onlineDataset").addEventListener("click",event=>action(event.currentTarget,async()=>{const asset=await save();dialog.close();await window.SodaWorkbench.addToDataset([asset.asset_id]);}));
  document.querySelectorAll("[data-gallery-tab]").forEach(button=>button.addEventListener("click",()=>window.setPromptHubView("gallery",{route:{view:"gallery",tab:button.dataset.galleryTab}})));
  capabilities();
  window.SodaOnlineGallery={reverse:async()=>{const asset=await save();dialog.close();await window.SodaWorkbench.repair(asset.asset_id);const section=document.querySelector("#creationReverse");if(section)section.open=true;},open:async mode=>{host.hidden=mode!=="online";$("#galleryLocalHost").hidden=mode==="online";document.querySelectorAll("[data-gallery-tab]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.galleryTab===(mode==="online"?"online":"local"))));if(mode==="online"&&!state.account)await loadAccount();if(mode==="online"&&!state.loaded)await search();}};
})();
