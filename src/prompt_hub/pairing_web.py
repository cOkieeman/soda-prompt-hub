"""In-app pairing guide; credentials stay in the operating system."""

# ruff: noqa: RUF001, E501 -- embedded HTML/CSS/JavaScript, like remote_web.py

PAIRING_HTML = r"""
<section class="pairing-entry" id="pairingEntry" hidden>
  <div><span class="eyebrow">FIRST CONNECTION / 首次连接</span><h2>让两台设备一起工作。</h2><p>从 Windows 准备，到 Mac 登录，再到逐项验收。每一步都在这里。</p></div>
  <button type="button" id="pairingOpen">开始配对引导 →</button>
</section>
<dialog id="pairingDialog" class="pairing-dialog" aria-labelledby="pairingTitle">
  <header><div><span class="eyebrow">MAC → WINDOWS</span><h2 id="pairingTitle">连接你的 Windows</h2></div><button type="button" id="pairingClose" aria-label="关闭配对引导">×</button></header>
  <ol class="pairing-track" aria-label="配对进度"><li>01 连接信息</li><li>02 系统授权</li><li>03 验收</li></ol>
  <section data-pairing-step="0">
    <h3 tabindex="-1">先在 Windows 打开 Worker</h3><p>点击 Worker 的「首次使用引导」，准备共享文件夹，再将它显示的连接地址粘贴到这里。两台设备应处于同一可信局域网。</p>
    <form id="pairingForm">
      <label>Windows 连接地址<input id="pairingUrl" placeholder="smb://192.168.1.10/PromptHub-5060Ti" maxlength="1024" required autocomplete="off" spellcheck="false"></label>
      <label>设备名称<input id="pairingLabel" maxlength="160" placeholder="我的 Windows"></label>
      <label><span><input id="pairingEnabled" type="checkbox" checked style="width:auto"> 启用这台设备</span></label>
      <details><summary>高级：Mac 已挂载的路径</summary><p>通常自动使用 /Volumes/共享名称；同名卷被系统添加后缀时，可在 Finder 核对后修改。</p><input id="pairingMount" aria-label="Mac 挂载路径" placeholder="留空自动填写"></details>
      <p id="pairingExisting">保存前不会修改已有设备。</p><button type="submit">保存连接信息并继续 →</button>
    </form>
  </section>
  <section data-pairing-step="1" hidden>
    <h3 tabindex="-1">在系统窗口完成一次登录</h3><p>使用有此共享文件夹读写权限的 Windows 账号密码，不是 Windows Hello PIN。可在系统窗口选择记住密码；Prompt Hub 不读取或保存密码。</p>
    <button type="button" id="pairingConnect">打开系统登录窗口</button>
    <p>若没有弹出登录窗口，可能已经连接。点击下方检查即可。取消登录也不会丢失已保存的设备。</p>
    <button type="button" id="pairingVerify">我已完成登录，检查连接 →</button>
  </section>
  <section data-pairing-step="2" hidden>
    <h3 tabindex="-1">逐项检查，不靠猜测</h3><ul class="pairing-checks" id="pairingChecks" aria-live="polite"></ul>
    <p id="pairingAdvice">点击检查，读取共享与实时 Worker 心跳。</p>
    <button type="button" id="pairingPrepare" hidden>创建任务目录并重新检查</button>
    <button type="button" id="pairingRecheck">重新检查</button><button type="button" id="pairingDone" hidden>完成，开始使用</button>
    <details><summary>连接遇到问题？</summary><p>共享不可达：确认同一局域网、Windows 已开启且共享名称正确。权限不足：在 Windows 文件夹的共享权限与「安全」页，为指定账号设置读写权限；不要开放整个磁盘或关闭防火墙。Worker 离线：在 Windows 打开 Worker。ComfyUI 离线：启动 ComfyUI 并在 Worker 设置中核对地址。</p></details>
  </section>
  <footer><button type="button" id="pairingBack" hidden>← 上一步</button><p id="pairingNotice" role="status">不会修改系统共享或防火墙设置。</p></footer>
</dialog>
"""

PAIRING_STYLES = r"""
<style>
.pairing-entry{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:24px 30px;border-bottom:1px solid var(--line);background:#efefdf}
.pairing-entry[hidden],.pairing-dialog [hidden]{display:none!important}
.pairing-entry h2{margin:8px 0;font-size:24px}.pairing-entry p{margin:0}
.pairing-dialog{width:min(660px,calc(100vw - 32px));max-height:85vh;box-sizing:border-box;border:1px solid #282822;background:#f6f3eb;color:#272922;padding:28px;overflow:auto}
.pairing-dialog::backdrop{background:#20251f75;backdrop-filter:blur(4px)}
.pairing-dialog header{display:flex;justify-content:space-between;align-items:start;gap:20px}.pairing-dialog h2{margin:8px 0 20px;font-size:30px}.pairing-dialog h3{font-size:22px;margin:24px 0 12px}
.pairing-dialog p{font-size:14px;line-height:1.8}.pairing-dialog label{display:grid;gap:8px;margin:16px 0;font-size:14px}.pairing-dialog input{width:100%;box-sizing:border-box;padding:12px;background:#fffdf6;border:1px solid #a3a493;color:inherit;font:inherit}
.pairing-dialog button,.pairing-entry button{appearance:none;border:1px solid #272922;background:transparent;color:inherit;font:inherit;padding:11px 16px;cursor:pointer}.pairing-dialog button:disabled{opacity:.5;cursor:wait}.pairing-dialog button:hover:not(:disabled),.pairing-entry button:hover{background:#d8ee87}.pairing-dialog button:focus-visible{outline:3px solid #768d34;outline-offset:3px}
.pairing-track{display:flex;list-style:none;margin:0;padding:0;border-block:1px solid #b4b6a5;font-size:12px}.pairing-track li{flex:1;padding:12px 5px;color:#747868}.pairing-track [aria-current]{color:#20251f;background:#d8ee87}
.pairing-checks{list-style:none;padding:0}.pairing-checks li{display:flex;gap:16px;justify-content:space-between;padding:13px 0;border-bottom:1px solid #c3c4b5}.pairing-checks [data-ok="true"] strong{color:#466612}.pairing-checks strong{font-size:13px}.pairing-dialog footer{border-top:1px solid #c3c4b5;margin-top:22px;padding-top:16px}.pairing-dialog details{margin:18px 0}.pairing-dialog summary{cursor:pointer;font-size:14px}.pairing-dialog section:not([hidden]){animation:pairing-in .22s ease-out}
@keyframes pairing-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){.pairing-dialog section:not([hidden]){animation:none}}
@media(max-width:620px){.pairing-entry{align-items:start;flex-direction:column;padding:22px}.pairing-dialog{padding:20px}.pairing-track{font-size:11px}}
</style>
"""

PAIRING_SCRIPT = r"""
<script>
(() => {
  const $ = selector => document.querySelector(selector), dialog = $('#pairingDialog');
  let step = 0, busy = false, saved = null, loaded = false, nodeId = 'compute-5060ti', returnFocus;
  const defaultCapabilities=['comfyui_generate','workflow_test','result_metadata','wd14_batch','embedding_batch','vlm_caption_batch','lora_catalog_snapshot','model_catalog_snapshot','lora_train','checkpoint_test'];
  async function api(path, options={}) {
    const response = await fetch(path, {...options, signal:AbortSignal.timeout(15000)});
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail==='string'?data.detail:'操作未完成，请检查连接后重试。');
    return data;
  }
  function showStep(value) {
    step = value;
    dialog.querySelectorAll('[data-pairing-step]').forEach(el=>el.hidden=Number(el.dataset.pairingStep)!==step);
    dialog.querySelectorAll('.pairing-track li').forEach((el,index)=>{if(index===step)el.setAttribute('aria-current','step');else el.removeAttribute('aria-current');});
    $('#pairingBack').hidden=step===0;
    dialog.querySelector(`[data-pairing-step="${step}"] h3`)?.focus();
  }
  async function run(action) {
    if(busy)return;
    busy=true;
    const controls=[...dialog.querySelectorAll('button,input')];
    controls.forEach(el=>el.disabled=true);
    $('#pairingNotice').textContent='正在处理，请稍候…';
    try { await action(); }
    catch(error) { $('#pairingNotice').textContent=['TimeoutError','AbortError'].includes(error.name)?'请求超时。保存或目录创建可能已完成，请重新检查；不要反复提交。':error.message; }
    finally { busy=false;controls.forEach(el=>el.disabled=false); }
  }
  async function openGuide() {
    loaded=false;
    returnFocus=document.activeElement;dialog.showModal();showStep(0);
    await run(async()=>{
      const nodes=await api('/api/remote-nodes');
      saved=nodes.find(n=>n.node_id==='compute-5060ti')||nodes.find(n=>n.role==='compute_5060ti')||null;
      loaded=true;
      nodeId=saved?.node_id||'compute-5060ti';
      const share=saved?.smb_share||saved?.smb_mount?.split('/').at(-1)||'';
      $('#pairingUrl').value=saved?.host&&share?`smb://${saved.host}/${encodeURIComponent(share)}`:'';
      $('#pairingLabel').value=saved?.label||'';$('#pairingMount').value=saved?.smb_mount||'';
      $('#pairingEnabled').checked=saved?.enabled??true;
      $('#pairingExisting').textContent=saved?'正在编辑已有设备；只有点击保存才会更新，其他配置保留。':'新设备：先从 Windows Worker 复制连接地址。';
      $('#pairingNotice').textContent='准备好连接信息后继续；密码只在系统窗口输入。';
    });
  }
  function parseAddress(value) {
    if(!/^smb:\/\/[^/]+\/[^/]+$/i.test(value.trim()))throw new Error('连接地址只能包含主机和一个共享名称，不能包含子文件夹。');
    const url=new URL(value.trim());
    const share=decodeURIComponent(url.pathname.slice(1));
    if(url.protocol!=='smb:'||url.username||url.password||url.port||url.search||url.hash||! /^[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}$/.test(url.hostname)||!share||share==='.'||share==='..'||/[\/\\\x00]/.test(share)) throw new Error('请填写 smb://主机/共享名称，不要包含账号、密码或子文件夹。');
    return {host:url.hostname,smb_share:share};
  }
  async function verify() {
    showStep(2);$('#pairingDone').hidden=true;$('#pairingPrepare').hidden=true;
    $('#pairingChecks').textContent='正在读取实时状态…';
    const base=`/api/remote-nodes/${encodeURIComponent(nodeId)}`;
    const [diagnostic,summary]=await Promise.all([api(base+'/diagnostics'),api(base+'/connection')]);
    const checks=[['共享文件夹',diagnostic.mount_exists,'尚未挂载'],['任务目录读写',diagnostic.bridge_prepared&&diagnostic.bridge_writable,'需要准备或授权'],['Windows Worker',summary.worker_online,'等待实时心跳'],['ComfyUI',summary.can_compute,'尚未就绪']];
    $('#pairingChecks').replaceChildren(...checks.map(([name,ok,waiting])=>{const row=document.createElement('li'),label=document.createElement('span'),status=document.createElement('strong');label.textContent=name;status.textContent=ok?'已通过':waiting;row.dataset.ok=String(Boolean(ok));row.append(label,status);return row;}));
    $('#pairingPrepare').hidden=diagnostic.state!=='mount_ready_bridge_unprepared';
    const ready=checks.every(([,ok])=>ok);
    $('#pairingDone').hidden=!ready;
    $('#pairingAdvice').textContent=summary.detail;
    $('#pairingNotice').textContent=ready?'全部检查通过，可以开始使用。':`检查完成 · ${summary.label}。修复后点击重新检查。`;
  }
  $('#pairingOpen').addEventListener('click',openGuide);
  $('#pairingClose').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
  dialog.addEventListener('close',()=>returnFocus?.focus());
  $('#pairingBack').addEventListener('click',()=>showStep(step-1));
  $('#pairingForm').addEventListener('submit',event=>{event.preventDefault();run(async()=>{
    if(!loaded)throw new Error('未能读取已有设备，暂不保存。请关闭并重新打开向导后重试。');
    const address=parseAddress($('#pairingUrl').value), mount=$('#pairingMount').value.trim()||`/Volumes/${address.smb_share}`;
    if(!mount.startsWith('/'))throw new Error('Mac 挂载路径需要以 / 开头。');
    const fields={label:$('#pairingLabel').value.trim()||'我的 Windows',role:'compute_5060ti',host:address.host,smb_share:address.smb_share,smb_mount:mount,enabled:$('#pairingEnabled').checked,capabilities:saved?.capabilities||defaultCapabilities,notes:saved?.notes||''};
    saved=await api(`/api/remote-nodes/${encodeURIComponent(nodeId)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(fields)});
    window.dispatchEvent(new Event('prompt-hub-pairing-saved'));showStep(1);$('#pairingNotice').textContent='设备信息已保存，尚未确认连接。';
  });});
  $('#pairingConnect').addEventListener('click',()=>run(async()=>{const result=await api(`/api/remote-nodes/${encodeURIComponent(nodeId)}/connect`,{method:'POST'});$('#pairingNotice').textContent=result.message;}));
  $('#pairingVerify').addEventListener('click',()=>run(verify));
  $('#pairingRecheck').addEventListener('click',()=>run(verify));
  $('#pairingPrepare').addEventListener('click',()=>run(async()=>{await api(`/api/remote-nodes/${encodeURIComponent(nodeId)}/prepare`,{method:'POST'});await verify();}));
  $('#pairingDone').addEventListener('click',()=>dialog.close());
  $('#pairingUrl').addEventListener('input',()=>{$('#pairingMount').value='';$('#pairingNotice').textContent='连接地址已修改，挂载路径将按新共享名生成；自定义路径可在高级选项中填写。';});
  api('/api/desktop/connection').then(summary=>{ $('#pairingEntry').hidden=['windows_local','linux_local'].includes(summary.mode); }).catch(()=>{});
})();
</script>
"""
