(() => {
  "use strict";
  const page=document.querySelector("#studioSettingsPage");
  const section=document.createElement("section");section.className="studio-settings-form";
  section.innerHTML='<h2>本地畫風庫</h2><form id="localStylesSettings"><label>畫風庫目錄<input name="root" placeholder="E:\\个人开发项目\\画风库" required></label><label>Neons 節點目錄<input name="node_root" required></label><div class="workbench-actions"><button type="submit">保存目錄</button><button type="button" id="localStylesSync">同步預覽</button></div><p id="localStylesSettingsStatus" role="status"></p></form>';
  page.querySelector(".studio-settings-layout").appendChild(section);
  async function api(body){const response=await fetch('/api/local-styles/settings',{method:body?'PUT':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});const data=await response.json();if(!response.ok)throw Error(data.detail||'請求失敗');return data;}
  let loaded=false;
  new MutationObserver(async()=>{if(page.hidden||loaded)return;loaded=true;try{const settings=await api();for(const key of ['root','node_root'])document.querySelector('#localStylesSettings').elements[key].value=settings[key]||'';}catch(error){document.querySelector('#localStylesSettingsStatus').textContent=error.message;loaded=false;}}).observe(page,{attributes:true,attributeFilter:['hidden']});
  document.querySelector('#localStylesSettings').addEventListener('submit',async event=>{event.preventDefault();const button=event.submitter;button.disabled=true;try{await api(Object.fromEntries(new FormData(event.currentTarget)));document.querySelector('#localStylesSettingsStatus').textContent='已保存';}catch(error){document.querySelector('#localStylesSettingsStatus').textContent=error.message;}finally{button.disabled=false;}});
  document.querySelector('#localStylesSync').addEventListener('click',async event=>{const button=event.currentTarget;button.disabled=true;try{const response=await fetch('/api/local-styles/sync',{method:'POST'});const result=await response.json();if(!response.ok)throw Error(result.detail||'請求失敗');document.querySelector('#localStylesSettingsStatus').textContent='已同步 '+result.entries+' 条';await window.loadPromptHubStats();}catch(error){document.querySelector('#localStylesSettingsStatus').textContent=error.message;}finally{button.disabled=false;}});
})();
