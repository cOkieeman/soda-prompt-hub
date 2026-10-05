from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from prompt_hub.workspace_web import WORKSPACE_SCRIPT

ASSETS = Path(__file__).resolve().parents[1] / "src/prompt_hub/web_assets"
CREATIVE = (ASSETS / "creative.js").read_text()
BASE = (ASSETS / "base.js").read_text()
GALLERY = (ASSETS / "gallery.js").read_text()


def snippet(source: str, start: str, end: str) -> str:
    return source[source.index(start) : source.index(end, source.index(start))]


def run_js(script: str) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for UI behavior tests")
    subprocess.run([node, "-e", script], check=True)  # noqa: S603


def gallery_behavior_script() -> str:
    return (
        "const assert=require('node:assert/strict'),fields={};"
        "const document={querySelector:s=>fields[s]||(fields[s]={})};"
        + snippet(GALLERY, "  const q=", "  function renderGrid()")
    )


def test_gallery_saved_lora_rows_ignore_graph_active_choices() -> None:
    run_js(
        gallery_behavior_script()
        + r"""
const rows=Array.from({length:22},(_,i)=>({name:`style-${i%16}.safetensors`,
 strength_model:i===16?-0.25:i/100,strength_clip:i===16?0:0.4,node_id:`node-${i}`}));
const saved=Array.from({length:4},(_,i)=>({name:`saved-${i}`,hash:`abcd000${i}`,
 strength_model:null,strength_clip:null}));
const asset={metadata:{generation_evidence:{extractor_version:4,
 scope:'output_connected',loras:rows,
 final_generation:{status:'resolved',loras:saved,
 lora_source:{status:'recorded',kind:'saved_image_metadata',fields:['Lora hashes']}}}}};
const chip=compactEvidence(asset);
assert.ok(chip.includes(' +3'),chip);assert.ok(!chip.includes(' +15'));
renderGeneration(asset);const html=fields['#galleryGenerationContent'].innerHTML;
assert.ok(html.includes('<h4>已使用 LoRA</h4>'));
assert.ok(html.includes('图片保存的 LoRA 记录'));
assert.equal((html.match(/<strong data-i18n-ignore>saved-/g)||[]).length,4);
assert.ok(!html.includes('style-0'));assert.ok(!html.includes('Model '));
assert.ok(!html.includes('叠加记录'));assert.ok(!html.includes('node-0'));
assert.ok(!html.includes('node-16'));assert.ok(!html.includes('earlier-stage'));
assert.equal(state.evidence.loras.length,4);assert.deepEqual(state.evidence.loras,saved);
assert.equal(asset.metadata.generation_evidence.loras.length,22);
assert.equal(asset.metadata.generation_evidence.loras[16].strength_model,-0.25);
"""
    )


def test_gallery_civitai_saved_names_do_not_inherit_graph_weights_or_family() -> None:
    run_js(
        gallery_behavior_script()
        + r"""
const saved=Array.from({length:4},(_,i)=>({name:`civitai-${i}`,
 air:`urn:air:${i===3?'anima':'flux'}:lora:civitai:${i}@1`,
 strength_model:null,strength_clip:null,weight:i===3?0:0.3}));
const asset={metadata:{generation_evidence:{extractor_version:4,
 final_generation:{status:'resolved',model_family:'krea2',loras:saved,
 lora_source:{status:'recorded',kind:'saved_image_metadata',fields:['Civitai resources']}},
 loras:Array.from({length:22},(_,i)=>({name:`graph-${i}`,strength_model:1}))}}};
renderGeneration(asset);const html=fields['#galleryGenerationContent'].innerHTML;
assert.equal(state.evidence.loras.length,4);assert.ok(compactEvidence(asset).includes(' +3'));
assert.ok(html.includes('civitai-3'));assert.ok(!html.includes('graph-'));
assert.ok(html.includes('<b data-i18n-ignore>0</b>'));assert.ok(!html.includes('>1</b>'));
assert.ok(html.includes('图片保存的 LoRA 记录'));
assert.deepEqual(state.evidence.loras,saved);
"""
    )


@pytest.mark.parametrize(
    "evidence",
    [
        {"scope": "output_connected"},
        {"scope": "output_connected", "extractor_version": 1},
        {"scope": "saved_nodes", "extractor_version": 2},
    ],
)
def test_gallery_unverified_loras_never_appear_as_used(evidence) -> None:
    run_js(
        gallery_behavior_script()
        + f"const evidence={json.dumps(evidence)};"
        + r"""
evidence.loras=[{name:'unverified.safetensors',strength_model:0.5}];
const asset={metadata:{generation_evidence:evidence}};
assert.equal(generationEvidence(asset).loras.length,0);
assert.ok(!compactEvidence(asset).includes('LoRA ·'));
renderGeneration(asset);const html=fields['#galleryGenerationContent'].innerHTML;
assert.ok(html.includes('无法确认'));assert.ok(!html.includes('待核对的工作流记录'));
assert.ok(!html.includes('unverified.safetensors'));
assert.equal(asset.metadata.generation_evidence.loras[0].name,'unverified.safetensors');
"""
    )


def test_gallery_lora_full_paths_candidates_and_text_are_preserved_safely() -> None:
    run_js(
        gallery_behavior_script()
        + r"""
const asset={metadata:{generation_evidence:{extractor_version:4,scope:'output_connected',
 final_generation:{status:'resolved',
 lora_source:{status:'recorded',kind:'saved_image_metadata',fields:['resources_json']},
 loras:[{name:'folder-a/same.safetensors',strength_model:0,strength_clip:-0.2},
 {name:'folder-b/same.safetensors',strength_model:0.4,strength_clip:0},
 {name:'<img src=x onerror=alert(1)>',strength_model:0.4,strength_clip:0}],
 positive:{text:'<script>final prompt</script>',status:'exact'}},
 candidate_loras:[{name:'<img src=x onerror=alert(1)>',strength_model:null,
 node_id:'<node>',reason:'<script>unknown</script>'}],unknown_lora_nodes:[{node_id:'unknown'}]}}};
assert.ok(compactEvidence(asset).includes(' +2'));
renderGeneration(asset);const html=fields['#galleryGenerationContent'].innerHTML;
assert.ok(html.includes('folder-a/same.safetensors'));assert.ok(html.includes('folder-b/same.safetensors'));
assert.ok(html.includes('-0.2'));assert.ok(!html.includes('待核对的工作流记录'));
assert.ok(html.includes('&lt;img'));assert.ok(html.includes('&lt;script&gt;'));
assert.ok(!html.includes('<img'));assert.ok(!html.includes('<script>'));
assert.ok(!html.includes('unknown</script>'));
const legacy={metadata:{source:'parameters',loras:[{name:'legacy.safetensors',strength:0.3}]}};
assert.equal(generationEvidence(legacy).loras.length,0);assert.equal(compactEvidence(legacy),'');
renderGeneration({metadata:{generation_evidence:{extractor_version:2,scope:'output_connected',
 unknown_lora_nodes:[{node_id:'unknown'}],loras:[]}}});
assert.ok(fields['#galleryGenerationContent'].innerHTML.includes('无法确认'));
"""
    )


def test_gallery_final_prompts_and_sampler_exclude_intermediate_components() -> None:
    run_js(
        gallery_behavior_script()
        + r"""
const final={status:'resolved',models:[{name:'final-base',kind:'diffusion_model'}],
 sampler:{seed:'18446744073709551615',steps:20,cfg:3.1,sampler_name:'euler'},
 loras:[{name:'final-style',strength_model:0.4,strength_clip:0}],
 positive:{text:'exact final positive',status:'exact'},negative:{text:'',status:'exact'}};
const asset={metadata:{generation_evidence:{extractor_version:3,scope:'output_connected',
 final_generation:final,models:[{name:'old-base',kind:'diffusion_model'}],
 sampling:[{seed:'old-seed',steps:99}],
 prompts:[{polarity:'positive',text:'record one'},{polarity:'positive',text:'record two'}]}}};
renderGeneration(asset);const html=fields['#galleryGenerationContent'].innerHTML;
assert.equal((html.match(/data-gallery-copy-prompt=/g)||[]).length,2);
assert.ok(html.includes('exact final positive'));assert.ok(html.includes('final-base'));
assert.ok(html.includes('18446744073709551615'));assert.ok(!html.includes('old-seed'));
assert.ok(!html.includes('old-base'));assert.ok(!html.includes('记录 1'));
assert.ok(!html.includes('record one'));assert.ok(!html.includes('record two'));
assert.ok(!html.includes('其他已保存文本'));assert.ok(!html.includes('data-gallery-copy-index'));
assert.equal(promptRecordText(state.evidence,'positive'),'exact final positive');
assert.equal(promptRecordText(state.evidence,'negative'),'');
assert.equal(asset.metadata.generation_evidence.prompts.length,2);
"""
    )


def test_gallery_saved_export_is_labeled_and_never_replaces_exact_prompt() -> None:
    run_js(
        gallery_behavior_script()
        + r"""
const final={status:'partial',positive:{text:null,status:'unavailable'},
 negative:{text:'exact negative',status:'exact'},
 saved_export_prompts:{positive:{text:'saved export positive',status:'saved_export'},
 negative:{text:'saved export negative',status:'saved_export'}}};
renderGeneration({metadata:{generation_evidence:{extractor_version:3,
 scope:'output_connected',final_generation:final}}});
const html=fields['#galleryGenerationContent'].innerHTML;
assert.ok(html.includes('图片保存的 Prompt'));assert.ok(html.includes('无法核对编码输入'));
assert.ok(html.includes('saved export positive'));
assert.ok(!html.includes('saved export negative'));
assert.equal(promptRecordText(state.evidence,'positive'),'saved export positive');
assert.equal(promptRecordText(state.evidence,'negative'),'exact negative');
renderGeneration({metadata:{generation_evidence:{extractor_version:3,
 scope:'output_connected',final_generation:{status:'ambiguous',
 positive:{text:null,status:'ambiguous'},negative:{text:null,status:'unavailable'}}}}});
assert.equal(promptRecordText(state.evidence,'positive'),null);
assert.equal(promptRecordText(state.evidence,'negative'),null);
assert.ok(fields['#galleryGenerationContent'].innerHTML.includes('disabled'));
"""
    )


def test_gallery_final_lora_empty_state_requires_explicit_saved_empty_source() -> None:
    run_js(
        gallery_behavior_script()
        + r"""
const final={status:'resolved',loras:[],candidate_loras:[],
 lora_source:{status:'recorded_empty',kind:'saved_image_metadata',fields:['Lora hashes']},
 positive:{text:'exact main',status:'exact'},negative:{text:'',status:'exact'}};
const asset={metadata:{generation_evidence:{extractor_version:4,scope:'output_connected',
 final_generation:final,unknown_lora_nodes:[{node_id:'other-stage'}]}}};
renderGeneration(asset);let html=fields['#galleryGenerationContent'].innerHTML;
assert.equal(state.evidence.unconfirmed,false);assert.ok(html.includes('未记录使用 LoRA'));
assert.ok(!html.includes('无法确认已使用的 LoRA'));
final.lora_source.status='missing';renderGeneration(asset);
html=fields['#galleryGenerationContent'].innerHTML;
assert.equal(state.evidence.unconfirmed,true);
assert.ok(html.includes('无法确认已使用的 LoRA'));assert.ok(!html.includes('uncertain-main'));
assert.ok(!html.includes('未记录使用 LoRA'));
"""
    )


@pytest.mark.parametrize("status", ["missing", "invalid", "partial", "recorded"])
def test_gallery_saved_lora_source_controls_display_independent_of_graph(status) -> None:
    run_js(
        gallery_behavior_script()
        + f"const status={json.dumps(status)};"
        + r"""
const saved=[{name:'saved-air-anima-lora',air:'urn:air:sdxl:lora:example',
 strength_model:0,strength_clip:-0.4}];
const final={status:'ambiguous',loras:saved,candidate_loras:[{name:'graph-candidate'}],
 lora_source:{status,kind:'saved_image_metadata',fields:['Civitai resources']}};
const asset={metadata:{generation_evidence:{extractor_version:4,scope:'output_connected',
 final_generation:final,loras:[{name:'graph-active'}]}}};
renderGeneration(asset);const html=fields['#galleryGenerationContent'].innerHTML;
if(status==='recorded'||status==='partial') {
 assert.equal(state.evidence.loras.length,1);assert.ok(html.includes('saved-air-anima-lora'));
 assert.ok(html.includes('-0.4'));assert.ok(compactEvidence(asset).includes('LoRA ·'));
} else {
 assert.equal(state.evidence.loras.length,0);assert.ok(!html.includes('saved-air-anima-lora'));
 assert.ok(html.includes('无法确认已使用的 LoRA'));assert.equal(compactEvidence(asset),'');
}
assert.ok(!html.includes('graph-active'));assert.ok(!html.includes('graph-candidate'));
if(status==='partial') assert.ok(html.includes('保存记录不完整'));
"""
    )


def test_gallery_v3_graph_loras_are_not_used_without_saved_source() -> None:
    run_js(
        gallery_behavior_script()
        + r"""
const asset={metadata:{generation_evidence:{extractor_version:3,scope:'output_connected',
 final_generation:{status:'resolved',loras:[{name:'graph-lora'}],
 positive:{text:'exact prompt remains',status:'exact'},negative:{text:'',status:'exact'}}}}};
renderGeneration(asset);const html=fields['#galleryGenerationContent'].innerHTML;
assert.equal(state.evidence.loras.length,0);assert.equal(compactEvidence(asset),'');
assert.ok(html.includes('无法确认已使用的 LoRA'));assert.ok(!html.includes('graph-lora'));
assert.equal(promptRecordText(state.evidence,'positive'),'exact prompt remains');
"""
    )


def test_gallery_final_copy_preserves_known_empty_and_ignores_unavailable() -> None:
    handler = snippet(
        GALLERY,
        "  q('#galleryGenerationContent').addEventListener('click'",
        "  q('#gallerySaveAnalysis')",
    )
    run_js(
        gallery_behavior_script()
        + r"""
let click;const copied=[];
const navigator={clipboard:{writeText:async text=>copied.push(text)}};
q('#galleryGenerationContent').addEventListener=(_event,fn)=>click=fn;
"""
        + handler
        + r"""
(async()=>{
 const event=kind=>({target:{closest:()=>({dataset:{galleryCopyPrompt:kind}})}});
 state.evidence=generationEvidence({metadata:{generation_evidence:{extractor_version:3,
  scope:'output_connected',final_generation:{status:'partial',
  positive:{text:'exact copy',status:'exact'},negative:{text:'',status:'exact'}}}}});
 await click(event('positive'));await click(event('negative'));
 assert.deepEqual(copied,['exact copy','']);
 state.evidence=generationEvidence({metadata:{generation_evidence:{extractor_version:3,
  scope:'output_connected',final_generation:{status:'unavailable',
  positive:{text:null,status:'unavailable'},negative:{text:null,status:'unavailable'}}}}});
 await click(event('positive'));assert.deepEqual(copied,['exact copy','']);
 state.evidence=generationEvidence({metadata:{generation_evidence:{extractor_version:3,
  scope:'output_connected',final_generation:{status:'partial',
  positive:{text:null,status:'unavailable'},saved_export_prompts:{
  positive:{text:'saved copy',status:'saved_export'}}}}}});
 await click(event('positive'));assert.deepEqual(copied,['exact copy','','saved copy']);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )


@pytest.mark.parametrize(("size", "limit"), [(626, 500), (199, 2000), (1000, 500)])
def test_catalog_reads_every_page_and_preserves_query(size: int, limit: int) -> None:
    helper = snippet(
        BASE,
        "    async function loadPromptHubResourceCatalog(",
        "    window.loadPromptHubResourceCatalog",
    )
    run_js(
        helper
        + f"const size={size},limit={limit};"
        + r"""
const assert=require('node:assert/strict');
const all=Array.from({length:size},(_,id)=>({id})),calls=[];
(async()=>{
 const result=await loadPromptHubResourceCatalog('/api/windows-loras?query=anima',{
  limit,read:async url=>{const query=new URL(url,'http://localhost').searchParams;
   calls.push(query);const offset=Number(query.get('offset'));
   return {results:all.slice(offset,offset+limit),total:size,snapshot_id:'one'};
  }});
 assert.deepEqual(result.results,all);
 assert.equal(result.count,size);
 assert.equal(calls.length,Math.ceil(size/limit));
 assert.ok(calls.every(query=>query.get('query')==='anima'));
 assert.ok(calls.every(query=>Number(query.get('limit'))===limit));
 assert.equal(Number(calls.at(-1).get('offset')),limit*(calls.length-1));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )


def test_catalog_stops_old_api_and_rejects_changed_snapshot() -> None:
    helper = snippet(
        BASE,
        "    async function loadPromptHubResourceCatalog(",
        "    window.loadPromptHubResourceCatalog",
    )
    run_js(
        helper
        + r"""
const assert=require('node:assert/strict');
(async()=>{
 let calls=0;
 const legacy=await loadPromptHubResourceCatalog('/legacy',{limit:1,read:async()=>{
  calls++;return {results:[{id:'one'}],count:1};}});
 assert.equal(legacy.results.length,1);assert.equal(calls,1);
 calls=0;
 await assert.rejects(loadPromptHubResourceCatalog('/new',{limit:1,read:async()=>({
  results:[{id:++calls}],total:3,snapshot_id:String(calls)
 })}),/清单已更新/);
 assert.equal(calls,2);
 const empty=await loadPromptHubResourceCatalog('/empty',{read:async()=>({results:[],total:10})});
 assert.deepEqual(empty.results,[]);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )


def test_save_serializes_edits_uses_cas_and_does_not_switch_project() -> None:
    helper = snippet(
        CREATIVE, "  function creativeContentSnapshot(", "  async function creativeJson("
    )
    save = snippet(CREATIVE, "  function saveCreative(", "  async function sendWorkflowProfile(")
    run_js(
        helper
        + save
        + r"""
const assert=require('node:assert/strict');
let creativeSaveQueue=Promise.resolve(), dom='first', requests=[], resolvers=[];
const creativeState={project:{project_id:'a',revision:1,generation:{}},projects:[]};
const collectCreative=()=>({...creativeState.project,brief_zh:dom});
const $=()=>({textContent:''}),window={},renderCreativeProjects=()=>{};
const showCreativeError=()=>{},loadIterationContext=async()=>{},refreshProjectJourney=async()=>{};
const creativeJson=(url,options)=>{const body=JSON.parse(options.body);requests.push({url,body});
 return new Promise((resolve,reject)=>resolvers.push({resolve,reject,body}));};
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const first=saveCreative();await tick();
 const second=saveCreative();dom='edited during request';await tick();
 assert.equal(requests.length,1);assert.equal(requests[0].body.expected_revision,1);
 resolvers.shift().resolve({...requests[0].body,revision:2});await tick();
 assert.equal(requests[1].body.brief_zh,'edited during request');
 assert.equal(requests[1].body.expected_revision,2);
 resolvers.shift().resolve({...requests[1].body,revision:3});await first;await tick();
 assert.equal(requests[2].body.expected_revision,3);
 resolvers.shift().resolve({...requests[2].body,revision:4});await second;
 assert.equal(dom,'edited during request');assert.equal(creativeState.project.revision,4);
 const late=saveCreative();await tick();
 creativeState.project={project_id:'b',revision:1,generation:{}};dom='project b';
 resolvers.shift().resolve({project_id:'a',brief_zh:'late a',revision:5});await late;
 assert.equal(creativeState.project.project_id,'b');assert.equal(dom,'project b');
 const failed=saveCreative();await tick();resolvers.shift().reject(Error('409'));
 await assert.rejects(failed,/409/);assert.equal(dom,'project b');
 const retry=saveCreative();await tick();
 resolvers.shift().resolve({...requests.at(-1).body,revision:2});
 await retry;assert.equal(creativeState.project.project_id,'b');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )


def test_compile_discards_late_response_and_changed_input() -> None:
    helper = snippet(
        CREATIVE, "  function creativeContentSnapshot(", "  async function creativeJson("
    )
    compile_js = snippet(
        CREATIVE, "  async function compileCreative(", "  function queueCreativeSave("
    )
    run_js(
        helper
        + compile_js
        + r"""
const assert=require('node:assert/strict');
let creativeCompileRun=0,creativeCompiledInput='',dom='old',pending=[],rendered=0;
const creativeState={project:{project_id:'a'},outputs:{}};
const collectCreative=()=>({...creativeState.project,brief_zh:dom});
const creativeJson=()=>new Promise(resolve=>pending.push(resolve));
const renderOutput=()=>rendered++,renderWorkflowMessage=()=>{};
(async()=>{
 const old=compileCreative();dom='new';const latest=compileCreative();
 pending[2]({positive:'new',ready:true});pending[3]({positive:'new krea',ready:true});await latest;
 pending[0]({positive:'old'});pending[1]({positive:'old krea'});await old;
 assert.equal(creativeState.outputs.anima.positive,'new');assert.equal(rendered,1);
 const changed=compileCreative();dom='changed after request';
 pending[4]({positive:'discard'});pending[5]({positive:'discard'});await changed;
 assert.equal(rendered,1);assert.notEqual(creativeCompiledInput,creativeContentSnapshot());
 const switched=compileCreative();creativeState.project={project_id:'b'};
 pending[6]({positive:'project a'});pending[7]({positive:'project a'});await switched;
 assert.equal(rendered,1);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )


def test_send_requires_current_ready_compile_and_successful_save() -> None:
    send = snippet(
        CREATIVE, "  async function sendWorkflowProfile(", "  async function createCreativeProject("
    )
    run_js(
        send
        + r"""
const assert=require('node:assert/strict');
let creativeSending=false,compiledInput='old',creativeCompiledInput='old';
let ready=false,failed=false,calls=0;
const sceneState={applying:false};
const creativeState={project:{project_id:'a'},profile:'anima',outputs:{}};
const button={disabled:false,textContent:''};
const $=id=>id==='#workflowProfile'?{value:'workflow'}:
 id==='#workflowLowCost'?{checked:true}:button;
const setCreativeApplyBusy=busy=>sceneState.applying=busy,deviceName=()=> 'Windows';
const renderWorkflowProfiles=()=>{},refreshProjectJourney=async()=>{};
const saveCreative=async()=>{if(failed)throw Error('save conflict');};
const compileCreative=async()=>{creativeState.outputs.anima={ready,warnings:['未就绪']};
 creativeCompiledInput=compiledInput;};
const creativeContentSnapshot=()=> 'current';
const creativeJson=async()=>{calls++;return {profile:{label:'valid'}};};
(async()=>{
 await assert.rejects(sendWorkflowProfile(),/未就绪/);assert.equal(calls,0);
 assert.equal(sceneState.applying,false);assert.equal(creativeSending,false);
 ready=true;await assert.rejects(sendWorkflowProfile(),/未就绪/);assert.equal(calls,0);
 compiledInput='current';failed=true;
 await assert.rejects(sendWorkflowProfile(),/save conflict/);assert.equal(calls,0);
 failed=false;await sendWorkflowProfile();assert.equal(calls,1);
 assert.equal(sceneState.applying,false);assert.equal(creativeSending,false);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )


def test_ensure_creative_is_single_flight_and_preserves_active_dom() -> None:
    ensure_js = snippet(
        CREATIVE, "  async function ensureCreativeProject(", "  window.ensureCreativeProject"
    )
    run_js(
        ensure_js
        + r"""
const assert=require('node:assert/strict');
let creativeInit=null,reads=0,renders=0,resolve,dom='unsaved';
const creativeState={loadedMeta:true,project:{project_id:'a'}};
const loadCreativeMeta=async()=>{throw Error('should not reload metadata');};
const createCreativeProject=async()=>{throw Error('should not create');};
const refreshImportedResults=()=>{reads++;return new Promise(r=>resolve=r);};
const renderCreativeProject=()=>{renders++;dom='server';},checkTagCompletionStatus=()=>{};
(async()=>{const a=ensureCreativeProject(),b=ensureCreativeProject();
 assert.equal(reads,1);resolve();await Promise.all([a,b]);
 assert.equal(renders,0);assert.equal(dom,'unsaved');assert.equal(creativeInit,null);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )


def test_assist_fills_only_unlocked_empty_fields_and_rejects_stale_preview() -> None:
    assist = snippet(
        CREATIVE, "  function applyCreativeAssist(", "  $('#assistCreative').addEventListener"
    )
    run_js(
        assist
        + r"""
const assert=require('node:assert/strict');
const slotsMeta={character:[],outfit:[],scene:[]},fields={};
const $=id=>fields[id]||(fields[id]={});
const project={project_id:'a',slots:{character:'existing',outfit:'',scene:''},
 slot_locks:{outfit:true}};
const creativeState={project,suggestion:{projectId:'a',input:'current',suggested_slots:{
 character:'overwrite',outfit:'locked overwrite',scene:'new scene'}}};
const collectCreative=()=>structuredClone(creativeState.project);
const creativeContentSnapshot=()=> 'current';
const renderCreativeProject=()=>{},queueCreativeSave=()=>{};
applyCreativeAssist();assert.deepEqual(creativeState.project.slots,{
 character:'existing',outfit:'',scene:'new scene'});
creativeState.suggestion={projectId:'a',input:'old',suggested_slots:{}};
assert.throws(applyCreativeAssist,/内容已修改/);assert.ok(creativeState.suggestion);
"""
    )


def test_result_mutations_keep_current_controls_and_ignore_other_project() -> None:
    merge = snippet(
        CREATIVE, "  function mergeCreativeResultProject(", "  async function tagResultAsset("
    )
    run_js(
        merge
        + r"""
const assert=require('node:assert/strict');
const creativeState={projects:[],project:{project_id:'a',revision:1,brief_zh:'edited',
 generation:{seed:'999',workflow_controls:{choice:'new'},result_assets:[]}}};
assert.equal(mergeCreativeResultProject({project_id:'a',revision:2,brief_zh:'server',
 generation:{seed:'1',result_assets:[{asset_id:'image'}]}}),true);
assert.equal(creativeState.project.brief_zh,'edited');assert.equal(creativeState.project.generation.seed,'999');
assert.deepEqual(creativeState.project.generation.workflow_controls,{choice:'new'});
assert.equal(creativeState.project.generation.result_assets.length,1);
const before=structuredClone(creativeState.project);
assert.equal(mergeCreativeResultProject({project_id:'b',generation:{}}),false);
assert.deepEqual(creativeState.project,before);
"""
    )


def test_workspace_report_response_is_bound_to_workspace() -> None:
    report = snippet(WORKSPACE_SCRIPT, "  let reportRun=", "  async function selectWorkspace(")
    run_js(
        report
        + r"""
const assert=require('node:assert/strict');let resolve;
const state={active:{workspace_id:'a'},report:{images:['previous']}};
const api=()=>new Promise(r=>resolve=r);
(async()=>{const pending=loadReport();state.active={workspace_id:'b'};
 resolve({images:['wrong workspace']});await pending;
 assert.deepEqual(state.report,{images:['previous']});
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )


def test_dataset_rewrite_keeps_edited_draft_and_ignores_another_image() -> None:
    handler = snippet(
        WORKSPACE_SCRIPT,
        "  $('#datasetDetailKrea2Revise').addEventListener",
        "  $('#datasetDetailTagChips').addEventListener",
    )
    run_js(
        r"""
const assert=require('node:assert/strict');let callback,resolve,context='a:image';
const fields={};const $=id=>fields[id]||(fields[id]={value:'',textContent:'',
 addEventListener:(_,cb)=>callback=cb});
$('#datasetDetailKrea2Draft').value='original';$('#datasetDetailKrea2Revision').value='instruction';
const detailContextKey=()=>context,detailItem=()=>({relative_path:'image'});
const state={captionLocales:{}},alert=()=>{},api=()=>new Promise(r=>resolve=r);
"""
        + handler
        + r"""
(async()=>{
 let pending=callback();$('#datasetDetailKrea2Draft').value='human edit';resolve({revised:'model'});
 await pending;assert.equal($('#datasetDetailKrea2Draft').value,'human edit');
 pending=callback();context='b:other';$('#datasetDetailKrea2Draft').value='other image';
 resolve({revised:'wrong image'});await pending;
 assert.equal($('#datasetDetailKrea2Draft').value,'other image');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )


def test_language_preserves_user_titles_prompt_and_textarea_values() -> None:
    source = (ASSETS / "i18n.js").read_text()
    protected = snippet(
        source, "      const protectedContentSelectors", "      function translateTree("
    )
    run_js(
        protected
        + 'const assert=require("node:assert/strict");'
        + "const fields="
        + json.dumps([".project-item strong", ".card .content", "#datasetDetailName"])
        + ";"
        + r"""
for(const selector of fields) {
 const element={closest:selectors=>selectors.includes(selector)};
 assert.equal(preserveContent(element),true);
}
const textarea={closest:selectors=>selectors==='script, style, pre, code, textarea'};
assert.equal(preserveContent(textarea),true);
assert.equal(preserveContent(textarea,true),false);
const label={closest:()=>false};assert.equal(preserveContent(label),false);
"""
    )


def test_project_with_no_workflow_clears_previous_lora_controls() -> None:
    render = snippet(
        CREATIVE, "  function renderWorkflowControls(", "  function saveWorkflowControlsFromForm("
    )
    run_js(
        render
        + r"""
const assert=require('node:assert/strict'),fields={};
const $=id=>fields[id]||(fields[id]={dataset:{},innerHTML:'old LoRA',value:'old',
 textContent:'old defaults',hidden:false,disabled:false});
const creativeState={project:{project_id:'new',generation:{}},workflowLoraPickerOpen:true,
 workflowLoraQuery:'old search',workflowLoraFolder:'old folder'};
const selectedWorkflowProfile=()=>undefined;
renderWorkflowControls();
assert.equal($('#workflowLoraRows').innerHTML,'');
assert.equal($('#workflowDefaultLoras').textContent,'');
assert.equal($('#workflowSampler').value,'');assert.equal($('#workflowSampler').disabled,true);
assert.equal($('#workflowScheduler').value,'');assert.equal($('#workflowScheduler').disabled,true);
assert.equal($('#workflowAddLora').disabled,true);assert.equal($('#workflowLoraPicker').hidden,true);
assert.equal($('#workflowLoraResults').innerHTML,'');assert.equal($('#workflowLoraSearch').value,'');
assert.equal(creativeState.workflowLoraPickerOpen,false);
assert.deepEqual(creativeState.project.generation,{});
assert.deepEqual($('#workflowControlList').dataset,{projectId:'new',profileId:''});
"""
    )


def test_workflow_form_cannot_write_another_project_or_profile() -> None:
    save = snippet(
        CREATIVE, "  function saveWorkflowControlsFromForm(", "  function renderWorkflowProfiles("
    )
    run_js(
        save
        + r"""
const assert=require('node:assert/strict');
const creativeState={project:{project_id:'new',generation:{}}};
const owner={projectId:'old',profileId:'krea'};
const $=()=>({dataset:owner}),selectedWorkflowProfile=()=>({profile_id:'anima'});
const document={querySelectorAll:()=>{throw Error('must not read foreign form');}};
const queueCreativeSave=()=>{throw Error('must not save foreign form');};
saveWorkflowControlsFromForm();assert.deepEqual(creativeState.project.generation,{});
owner.projectId='new';saveWorkflowControlsFromForm();
assert.deepEqual(creativeState.project.generation,{});
"""
    )


def test_gallery_delete_requires_one_confirmation_and_preserves_target() -> None:
    run_js(
        "const assert=require('node:assert/strict'),fields={},calls=[];"
        "const q=s=>fields[s]||(fields[s]={showModal(){this.open=true},"
        "close(){this.open=false},focus(){}});"
        "const state={active:{asset_id:'gallery-test',title:'test'},"
        "deleteBusy:false,deleteTarget:null,detailRun:0};"
        "const message=()=>{},loadAlbums=async()=>{},loadFacets=async()=>{},loadAssets=async()=>{};"
        "let reject=false,release;const api=async(url,opts)=>{calls.push({url,...opts});"
        "if(reject)throw new Error('retry');await new Promise(r=>release=r)};"
        + snippet(GALLERY, "  function closeAsset()", "  async function updateActive")
        + r"""
(async()=>{
requestDelete();assert.equal(calls.length,0);assert.equal(q('#galleryDeleteDialog').open,true);
cancelDelete();assert.equal(calls.length,0);assert.equal(state.deleteTarget,null);
requestDelete();state.active={asset_id:'another'};await confirmDelete();
assert.equal(calls.length,0);
state.active={asset_id:'gallery-test',title:'test'};requestDelete();reject=true;
await confirmDelete();assert.equal(q('#galleryDeleteStatus').textContent,'retry');
assert.equal(q('#galleryDeleteDialog').open,true);assert.equal(state.deleteBusy,false);
reject=false;const pending=confirmDelete();await confirmDelete();cancelDelete();closeAsset();
assert.equal(state.active.asset_id,'gallery-test');assert.equal(calls.length,2);
assert.equal(calls[1].method,'DELETE');assert.equal(calls[1].url,'/api/gallery/assets/gallery-test');
assert.equal(q('#galleryDeleteConfirm').disabled,true);release();await pending;
assert.equal(state.active,null);assert.equal(q('#galleryDeleteDialog').open,false);
assert.equal(q('#galleryDeleteConfirm').disabled,false);
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    )


def test_gallery_card_delete_works_without_opening_details() -> None:
    run_js(
        "const assert=require('node:assert/strict'),fields={},calls=[];"
        "const q=s=>fields[s]||(fields[s]={showModal(){this.open=true},"
        "close(){this.open=false},focus(){}});"
        "const state={active:null,deleteBusy:false,deleteTarget:null,detailRun:0};"
        "const document={activeElement:null};"
        "const message=()=>{},loadAlbums=async()=>{},loadFacets=async()=>{},loadAssets=async()=>{};"
        "const api=async(url,opts)=>calls.push({url,...opts});"
        + snippet(GALLERY, "  function closeAsset()", "  async function updateActive")
        + r"""
(async()=>{
const selected={asset_id:'gallery-card',title:'card selected'};
requestDelete(selected);assert.equal(q('#galleryDeleteDialog').open,true);
assert.equal(q('#galleryDeleteName').textContent,'card selected');assert.equal(calls.length,0);
cancelDelete();assert.equal(calls.length,0);assert.equal(state.active,null);
requestDelete(selected);await confirmDelete();assert.equal(calls.length,1);
assert.equal(calls[0].url,'/api/gallery/assets/gallery-card');assert.equal(calls[0].method,'DELETE');
assert.equal(state.active,null);assert.equal(q('#galleryDetailDialog').open,undefined);
assert.equal(q('#galleryDeleteDialog').open,false);
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    )
