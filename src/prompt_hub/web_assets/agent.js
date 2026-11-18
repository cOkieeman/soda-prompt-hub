(() => {
  "use strict";
  const $=selector=>document.querySelector(selector);
  const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
  const host=$("#workbenchAgentHost");
  host.innerHTML='<div class="agent-layout"><aside class="agent-sidebar"><header class="workbench-heading"><h2>對話</h2><button type="button" id="agentNewChat">新對話</button></header><div id="agentChats"></div><details open><summary>預設與插件</summary><label class="studio-upload-button">安裝預設／Skill<input type="file" id="agentPackageFile" accept=".zip,.md,.txt,.json,.js,.mjs"></label><details><summary>推薦預設</summary><div id="agentCatalog"></div></details><div id="agentPackages"></div><div id="agentPluginStates"></div><p class="agent-help">勾選預設後，Agent 可讀取指南並調用附帶工具。</p></details></aside><section class="agent-conversation"><div class="agent-controls"><label>聊天模型<select id="agentModel"></select></label><label>生圖工具<select id="agentImageProvider"></select></label><button type="button" id="agentConnections">管理連線</button></div><div id="agentMessages" class="agent-messages" aria-live="polite"></div><form id="agentComposer"><label class="sr-only" for="agentInput">訊息</label><textarea id="agentInput" rows="4" placeholder="描述想要的畫面，或加入圖片反推提示詞。"></textarea><div id="agentAttachments" class="workbench-actions"></div><div class="workbench-actions"><label class="studio-upload-button">加入圖片<input type="file" id="agentAttachmentFile" accept="image/png,image/jpeg,image/webp"></label><button type="submit" id="agentSend" class="studio-primary">發送</button><button type="button" id="agentRetry" hidden>重試上一則</button></div></form><p id="agentStatus" role="status"></p></section></div>';
  const state={bootstrap:null,chat:null,busy:false,loading:false,run:0,assets:[],polls:new Map()};
  async function api(path,body,method="POST",raw=false){const response=await fetch(path,{method:body===undefined?"GET":method,headers:raw?{"Content-Type":"application/octet-stream"}:{"Content-Type":"application/json"},body:body===undefined?undefined:raw?body:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw Error(typeof data.detail==="string"?data.detail:"請求失敗");return data;}
  function status(value){$("#agentStatus").textContent=value;}
  function draftKey(){return "soda-agent-input-"+(state.chat?.id||"new");}
  function renderProposal(proposal, messageIndex, proposalIndex) {
    const key = messageIndex + ":" + proposalIndex;
    const queued = proposal.job_ids?.length > 0;
    return '<section class="agent-image-proposal"><pre data-i18n-ignore>' + esc(proposal.prompt)
      + '</pre><button type="button" data-agent-generate="' + key + '"' + (queued ? ' disabled' : '') + '>'
      + (queued ? '已加入生成佇列' : '執行生圖') + '</button><div class="agent-job-progress" data-agent-job="' + key + '"'
      + (queued ? '' : ' hidden') + '><progress max="100" aria-label="生成進度"></progress>'
      + '<span class="agent-job-progress-message"></span></div></section>';
  }
  function renderMessage(message, index) {
    const actionButtons = message.role === "assistant"
      ? '<div class="workbench-actions"><button type="button" data-agent-copy="' + index
        + '">複製</button><button type="button" data-agent-apply="' + index
        + '" data-agent-engine="novelai">套用至 NovelAI</button><button type="button" data-agent-apply="' + index
        + '" data-agent-engine="comfyui">套用至 ComfyUI</button><button type="button" data-agent-save="' + index
        + '">保存至詞庫</button></div>'
      : "";
    const attachments = (message.assets || []).map(id => '<img class="agent-attachment-preview" src="/api/gallery/assets/'
      + esc(id) + '/media/thumbnail" alt="">').join("");
    const tools = message.tools?.length
      ? '<details><summary>' + (window.t?.("工具執行記錄") || "工具執行記錄") + ' (' + message.tools.length
        + ')</summary><pre data-agent-tool-result data-i18n-ignore>'
        + esc(message.tools.map(tool => tool.name + '\n' + JSON.stringify(tool.result, null, 2)).join('\n\n'))
        + '</pre></details>'
      : "";
    const proposals = (message.proposals || []).map((proposal, proposalIndex) =>
      renderProposal(proposal, index, proposalIndex)).join("");
    return '<article class="agent-message agent-message-' + message.role + '"><strong>'
      + (message.role === "user" ? "你" : "Agent") + '</strong><div class="agent-message-text" data-i18n-ignore>'
      + esc(message.content) + '</div>' + attachments + actionButtons + tools + proposals + '</article>';
  }
  function render(){
    const messages = state.chat?.messages || [];
    $("#agentMessages").innerHTML = messages.length
      ? messages.map(renderMessage).join("")
      : '<div class="agent-empty"><h2>從一句想法開始</h2><p>寫提示詞、看圖反推，或調用生圖工具。</p></div>';
    $("#agentPluginStates").innerHTML = (state.chat?.plugin_states || []).map(plugin =>
      '<details class="agent-plugin-state"><summary data-i18n-ignore>' + esc(plugin.title) + '</summary><pre data-i18n-ignore>'
      + esc(JSON.stringify(plugin.projections || {error: plugin.error}, null, 2)) + '</pre></details>').join("");
    $("#agentRetry").hidden=!state.chat?.error;
    renderClients();
    $("#agentSend").disabled=state.busy||state.loading;
    $("#agentInput").disabled=state.loading;
    $("#agentNewChat").disabled=state.busy||state.loading;
    (state.chat?.messages||[]).forEach((message,index)=>(message.proposals||[]).forEach((proposal,p)=>{if(proposal.job_ids?.length)pollJob(proposal.job_ids[0],index+":"+p);}));
    $("#agentChats").innerHTML=(state.bootstrap?.chats||[]).map(chat=>'<button type="button" data-agent-chat="'+esc(chat.id)+'" aria-pressed="'+(chat.id===state.chat?.id)+'" data-i18n-ignore>'+esc(chat.title==='新對話'?(window.t?.('新對話')||chat.title):chat.title)+'</button>').join("");
  }
  function renderClients(){window.SodaAgentClients?.render({packages:state.bootstrap?.packages||[],
    selected:[...$("#agentPackages").querySelectorAll("input:checked")].map(input=>input.value),
    projections:state.chat?.plugin_states||[],pending:state.busy,sessionId:state.chat?.id});}
  $("#agentPackages").addEventListener("change",renderClients);
  async function openChat(id) {
    if (state.busy) return;
    const run = ++state.run;
    state.loading = true;
    render();
    try {
    const chat = await api("/api/agent/chats/" + id);
    if (run !== state.run) return;
    state.polls.forEach(timer => clearTimeout(timer));
    state.polls.clear();
    state.chat = chat;
    localStorage.setItem("soda-agent-chat", id);
    $("#agentInput").value = localStorage.getItem(draftKey()) || "";
    $("#agentModel").value = state.chat.model || $("#agentModel").value;
    $("#agentPackages").querySelectorAll("[data-agent-package]").forEach(input => {
      input.checked = (state.chat.packages || []).includes(input.value);
    });
    state.assets = JSON.parse(localStorage.getItem(draftKey() + "-assets") || "[]");
    renderAttachments();
    render();
    status(state.chat.error || "");
    if (state.chat.pending) {
      state.busy = true;
      render();
      pollChat(state.chat.id);
    }
    } finally { if(run===state.run){state.loading=false;render();} }
  }
  async function pollChat(id){try{const chat=await api("/api/agent/chats/"+id);if(state.chat?.id!==id)return;state.chat=chat;if(chat.pending){setTimeout(()=>pollChat(id),1200);return;}state.busy=false;render();status(chat.error||"");}catch(error){state.busy=false;status(error.message);render();}}
  async function bootstrap() {
    state.bootstrap = await api("/api/agent/bootstrap");
    const current = $("#agentModel").value;
    const imageProvider = $("#agentImageProvider").value
      || localStorage.getItem("soda-agent-image-provider") || "";
    $("#agentModel").innerHTML = state.bootstrap.models.length
      ? state.bootstrap.models.map(model => '<option value="' + esc(model.id) + '">'
        + esc(model.name) + '</option>').join("")
      : '<option value="">請先接入聊天模型</option>';
    if (state.bootstrap.models.some(model => model.id === current)) {
      $("#agentModel").value = current;
    }
    $("#agentImageProvider").innerHTML = state.bootstrap.providers.length
      ? state.bootstrap.providers.map(provider => '<option value="' + esc(provider.id) + '">'
        + esc(provider.label) + ' · ' + esc(provider.model) + '</option>').join("")
      : '<option value="">請先接入圖片 API</option>';
    if (state.bootstrap.providers.some(provider => provider.id === imageProvider)) {
      $("#agentImageProvider").value = imageProvider;
    }
    $("#agentPackages").innerHTML = state.bootstrap.packages.map(packageInfo => {
      const selection = packageInfo.status !== "ready" ? ' disabled'
        : (state.chat?.packages || []).includes(packageInfo.id) ? ' checked' : '';
      const type = {preset: '提示詞預設', skill: 'SKILL 指南', dsh: 'DSH 插件'}[packageInfo.kind] || '提示詞預設';
      const availability = packageInfo.status === "ready" ? '已載入' : '工具環境需要處理';
      const count = packageInfo.kind === "dsh" ? (packageInfo.tools || []).length : (packageInfo.tool_files || []).length;
      const capability = packageInfo.kind === "dsh" ? '已註冊工具' : '附帶腳本';
      const tools = count ? ' · '+(window.t?.(capability)||capability)+' '+count : '';
      return '<label class="agent-package"><input type="checkbox" data-agent-package value="'
        + esc(packageInfo.id) + '"' + selection + '><span data-i18n-ignore>'
        + esc(packageInfo.title) + '</span><small>' + (window.t?.(type)||type) + ' · ' + (window.t?.(availability)||availability) + tools + '</small>' + (packageInfo.runtime_error ? '<small data-i18n-ignore>'+esc(packageInfo.runtime_error)+'</small>' : '') + '</label>';
    }).join("") || '<p>尚未安裝預設</p>';
    $("#agentCatalog").innerHTML = (state.bootstrap.catalog || []).map(item =>
      '<button type="button" data-agent-catalog="' + esc(item.id) + '"><span>' + (window.t?.("安裝") || "安裝") + '</span> <span data-i18n-ignore>' + esc(item.title) + '</span></button>').join("");
    render();
  }
  async function send(retry=false){if(state.busy||state.loading||!state.chat)return;const text=retry?state.chat.messages.filter(m=>m.role==="user").at(-1)?.content:$("#agentInput").value.trim();if(!text)return;state.busy=true;render();status("正在等待模型回覆…");
    try{const chat=await api("/api/agent/chats/"+state.chat.id+"/messages",{text,model:$("#agentModel").value,packages:[...$("#agentPackages").querySelectorAll("input:checked")].map(i=>i.value),assets:state.assets.map(a=>a.asset_id),retry});state.chat=chat;$("#agentInput").value="";localStorage.removeItem(draftKey());state.assets=[];renderAttachments();await bootstrap();status("");}
    catch(error){status(error.message);state.chat=await api("/api/agent/chats/"+state.chat.id).catch(()=>state.chat);}
    finally{state.busy=false;render();}}
  function renderAttachments(){localStorage.setItem(draftKey()+"-assets",JSON.stringify(state.assets));$("#agentAttachments").innerHTML=state.assets.map((asset,index)=>'<span><img class="agent-attachment-preview" src="'+esc(asset.thumbnail_url)+'" alt=""><button type="button" data-agent-remove="'+index+'">移除</button></span>').join("");}
  $("#agentComposer").addEventListener("submit",event=>{event.preventDefault();send();});$("#agentRetry").addEventListener("click",()=>send(true));
  $("#agentInput").addEventListener("keydown",event=>{if(event.key!=="Enter"||event.shiftKey||event.isComposing||event.keyCode===229)return;event.preventDefault();$("#agentComposer").requestSubmit();});
  $("#agentInput").addEventListener("input",()=>localStorage.setItem(draftKey(),$("#agentInput").value));
  $("#agentNewChat").addEventListener("click",async()=>{
    if(state.busy||state.loading)return;
    state.loading=true;render();
    try{const chat=await api("/api/agent/chats",{});await bootstrap();await openChat(chat.id);}
    catch(error){status(error.message);}
    finally{state.loading=false;render();}
  });
  $("#agentConnections").addEventListener("click",()=>window.openModelEndpoints());
  $("#agentImageProvider").addEventListener("change",()=>localStorage.setItem("soda-agent-image-provider",$("#agentImageProvider").value));
  $("#agentChats").addEventListener("click",event=>{const button=event.target.closest("[data-agent-chat]");if(button)openChat(button.dataset.agentChat).catch(error=>status(error.message));});
  $("#agentCatalog").addEventListener("click", async event => {
    const button = event.target.closest("[data-agent-catalog]");
    if (!button || button.disabled) return;
    button.disabled = true;
    try {
      status("正在安裝…");
      await api("/api/agent/packages/catalog/" + button.dataset.agentCatalog, {});
      await bootstrap();
      status("已安裝，勾選後用於下一則訊息。");
    } catch (error) { status(error.message); }
    finally { button.disabled = false; }
  });
  $("#agentPackageFile").addEventListener("change",async event=>{const file=event.target.files[0];if(!file)return;try{status("正在安裝…");await api("/api/agent/packages?filename="+encodeURIComponent(file.name),file,"POST",true);await bootstrap();status("已安裝，勾選後用於下一則訊息。");}catch(error){status(error.message);}event.target.value="";});
  $("#agentAttachmentFile").addEventListener("change",async event=>{const file=event.target.files[0];if(!file)return;try{if(state.assets.length>=4)throw Error("每次最多加入四張圖片");const asset=await api("/api/gallery/import?kind=reference&filename="+encodeURIComponent(file.name),file,"POST",true);state.assets.push(asset);renderAttachments();}catch(error){status(error.message);}event.target.value="";});
  $("#agentAttachments").addEventListener("click",event=>{const button=event.target.closest("[data-agent-remove]");if(button){state.assets.splice(Number(button.dataset.agentRemove),1);renderAttachments();}});
  $("#agentMessages").addEventListener("click",async event=>{const button=event.target.closest("button");if(!button)return;
    const chatId = state.chat?.id;
    try{
      if(button.dataset.agentCopy!==undefined)await navigator.clipboard.writeText(state.chat.messages[Number(button.dataset.agentCopy)].content);
      if (button.dataset.agentApply !== undefined) {
        const content = state.chat.messages[Number(button.dataset.agentApply)].content;
        await window.SodaWorkbench.open("creative", {route: {view: "creative", engine: button.dataset.agentEngine}});
        await window.SodaWorkbench.applySlots({body: content});
      }
      if (button.dataset.agentSave !== undefined) {
        button.disabled = true;
        const index = Number(button.dataset.agentSave);
        const name = "agent-" + state.chat.id + "-" + index;
        await api("/api/studio/wordlists", {name, content: state.chat.messages[index].content}, "PUT");
        status("已保存至詞庫，可在管理隨機詞庫中查看。");
        button.disabled = false;
      }
      if(button.dataset.agentGenerate!==undefined){
        button.disabled=true;
        const [index,p]=button.dataset.agentGenerate.split(":").map(Number);
        const chatId = state.chat.id;
        const queued=await api("/api/agent/chats/"+chatId+"/generate",{message_index:index,proposal_index:p,provider_id:$("#agentImageProvider").value});
        if (state.chat?.id !== chatId) return;
        state.chat.messages[index].proposals[p].job_ids=queued.job_ids;
        button.textContent="已加入生成佇列";
        status("任務已提交，可到畫廊查看結果。");
        pollJob(queued.job_ids[0],button.dataset.agentGenerate);
      }
    }catch(error){if(state.chat?.id===chatId)status(error.message);button.disabled=false;}});
  async function pollJob(id, key, chatId = state.chat?.id) {
    clearTimeout(state.polls.get(id));
    try {
      const job = await api("/api/jobs/" + id);
      if (state.chat?.id !== chatId) return;
      const element = host.querySelector('[data-agent-job="' + key + '"]');
      if (element) {
        const progress = element.querySelector("progress");
        const message = element.querySelector(".agent-job-progress-message");
        element.hidden = false;
        element.dataset.state = job.status;
        if (job.status === "completed") progress.value = 100;
        else if (job.status === "running" && !job.progress_current) progress.removeAttribute("value");
        else if (job.progress_total > 0) progress.value = Math.round(job.progress_current / job.progress_total * 100);
        else progress.value = 0;
        message.textContent = job.status === "queued" ? (window.t?.("排隊中，尚未出圖") || "排隊中，尚未出圖")
          : job.status === "completed" ? (window.t?.("已出圖") || "已出圖")
          : job.status === "failed" ? (window.t?.("出圖失敗") || "出圖失敗")
          : job.status === "canceled" ? (window.t?.("生成已取消") || "生成已取消")
          : job.progress_message || (window.t?.("正在出圖") || "正在出圖");
        if (job.status === "completed") {
          if (!element.querySelector("[data-agent-gallery]")) {
            const button = document.createElement("button");
            button.type = "button";
            button.dataset.agentGallery = "";
            button.textContent = window.t?.("前往畫廊") || "前往畫廊";
            element.append(button);
          }
        }
        if (job.error) message.textContent = job.error;
      }
      clearTimeout(state.polls.get(id));
      state.polls.delete(id);
      if (["queued", "running"].includes(job.status)) {
        state.polls.set(id, setTimeout(() => pollJob(id, key, chatId), 1800));
      }
    } catch (error) {
      if (state.chat?.id === chatId) status(error.message);
    }
  }
  host.addEventListener("click",event=>{if(event.target.closest("[data-agent-gallery]"))window.setPromptHubView("gallery");});
  window.SodaAgent={attach:asset=>{if(!state.assets.some(a=>a.asset_id===asset.asset_id))state.assets.push(asset);renderAttachments();},open:async()=>{await bootstrap();if(!state.chat){const id=localStorage.getItem("soda-agent-chat");if(id&&state.bootstrap.chats.some(c=>c.id===id))await openChat(id);else{const chat=await api("/api/agent/chats",{});await bootstrap();await openChat(chat.id);}}}};
})();
