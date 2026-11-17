(() => {
  "use strict";
  const frames=new Map();
  let current={packages:[],selected:[],projections:[],pending:false};
  function update(frame,packageInfo){
    const style=getComputedStyle(document.querySelector("#agentComposer"));
    const projection=current.projections.find(item=>item.package_id===packageInfo.id||item.title===packageInfo.title);
    frame.contentWindow?.postMessage({source:"soda-agent-host",projections:projection?.projections||packageInfo.initial_projections||{},
      pending:current.pending,sessionId:current.sessionId,theme:document.documentElement.dataset.theme||"dark",
      color:style.color,font:style.fontFamily,accent:style.getPropertyValue("--accent")||"#d6e74a"},"*");
  }
  function render(values){
    current=values;
    let host=document.querySelector("#agentClientPanels");
    if(!host){host=document.createElement("div");host.id="agentClientPanels";document.querySelector("#agentComposer").before(host);}
    const selected=values.packages.filter(item=>item.has_client&&item.status==="ready"&&values.selected.includes(item.id));
    for(const [id,entry] of frames)if(!selected.some(item=>item.id===id)){entry.frame.remove();frames.delete(id);}
    for(const item of selected){
      if(!frames.has(item.id)){
        const frame=document.createElement("iframe");frame.title=item.title;frame.className="agent-client-panel";
        frame.sandbox="allow-scripts";frame.src="/api/agent/packages/"+encodeURIComponent(item.id)+"/client";
        frames.set(item.id,{frame,item});host.append(frame);
      }
      update(frames.get(item.id).frame,item);
    }
  }
  addEventListener("message",event=>{
    if(event.data?.source!=="soda-agent-client")return;
    const entry=[...frames.values()].find(item=>item.frame.contentWindow===event.source);
    if(!entry)return;
    if(event.data.type==="ready")update(entry.frame,entry.item);
    if(event.data.type==="height"&&Number.isFinite(event.data.height))entry.frame.style.height=Math.max(28,Math.min(480,event.data.height))+"px";
    if(event.data.type==="error")entry.frame.setAttribute("aria-label",entry.item.title+" · "+event.data.message);
  });
  new MutationObserver(()=>{for(const {frame,item} of frames.values())update(frame,item);}).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
  window.SodaAgentClients={render};
})();
