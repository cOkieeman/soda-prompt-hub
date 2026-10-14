from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.background_jobs import BackgroundJobStore

BASE_PATH = Path(__file__).resolve().parents[1] / "src/prompt_hub/web_assets/base.js"


def test_source_history_api_is_scoped_and_duplicate_submit_is_exclusive(settings) -> None:
    # Do not enter lifespan: no worker and no real source downloads.
    client = TestClient(create_app(settings))
    store = BackgroundJobStore(settings.database_path)
    store.initialize()
    unrelated = store.enqueue("unrelated", {})
    first = client.post("/api/sources/sync", json={"source_ids": ["clio-style-preview"]})
    second = client.post("/api/sources/sync", json={"source_ids": ["sd-wildcards"]})
    assert first.status_code == second.status_code == 202
    assert second.json()["job"]["job_id"] == first.json()["job"]["job_id"]
    history = client.get("/api/sources/sync-jobs")
    assert history.status_code == 200
    assert [job["job_id"] for job in history.json()] == [first.json()["job"]["job_id"]]
    assert all(job["job_id"] != unrelated["job_id"] for job in history.json())


def test_source_update_result_survives_status_refresh() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    base = BASE_PATH.read_text()
    script = base[
        base.index("    async function syncPublicSources(") : base.index(
            "    async function cloneSource("
        )
    ]
    script += base[
        base.index("    function sourceSyncResultMessage(") : base.index(
            "    function renderSourceJob("
        )
    ]
    script += base[
        base.index("    async function refreshSourceViews(") : base.index(
            "    async function installRecommendedSources("
        )
    ]
    harness = r"""
const assert=require('node:assert/strict');
const elements=new Map();
const $=key=>{
 if(!elements.has(key))elements.set(key,{textContent:'',disabled:false});
 return elements.get(key);
};
const result={updated:2,unchanged:1,skipped:0,missing:4,failed:1,
 sources:[{source_id:'bad',name:'Bad',status:'failed',message:'offline'}]};
const runSourceSyncJob=async()=>result;
const sourceSyncUi={epoch:0};
const lockSourceActions=()=>{};
const sourceSyncError=error=>{throw error;};
let failStats=false;
const loadStats=async()=>{if(failStats)throw new Error('stats offline');};
const loadSourceSyncStatus=async()=>{$('#sourceSyncMessage').textContent='old status';};
(async()=>{
 await syncPublicSources();
 assert.match($('#sourceSyncMessage').textContent,/2 个已更新/);
 assert.match($('#sourceSyncMessage').textContent,/1.*最新/);
 assert.match($('#sourceSyncMessage').textContent,/4.*未安装/);
 assert.match($('#sourceSyncMessage').textContent,/1.*失败/);
 assert.equal($('#sourceSyncButton').disabled,false);
 failStats=true;await syncPublicSources('a');
 assert.match($('#sourceSyncMessage').textContent,/1.*最新/);
 assert.match($('#sourceSyncSummary').textContent,/统计.*未能刷新/);
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    subprocess.run([node, "-e", script + harness], check=True)  # noqa: S603


def test_restore_source_history_does_not_resubmit_and_poll_failure_is_visible() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    base = BASE_PATH.read_text()
    script = base[
        base.index("    function sourceJobActive(") : base.index("    async function loadOcWorlds(")
    ]
    script += base[
        base.index("    function sourceSyncError(") : base.index(
            "    async function installRecommendedSources("
        )
    ]
    harness = r"""
const assert=require('node:assert/strict');
const elements=new Map();
const $=key=>{
 if(!elements.has(key))elements.set(key,{
  textContent:'',innerHTML:'',disabled:false,hidden:true,dataset:{},
  querySelectorAll:()=>[],removeAttribute(){}
 });return elements.get(key);
};
const document={querySelectorAll:()=>[]};
const window={};
const formatNumber=value=>String(Number(value)||0);
const escapeHtml=s=>String(s??'');
const renderHomeSourceSetup=()=>{};
const sourceSyncUi={busy:false,rebuilding:false,sources:[],jobs:[],job:null,epoch:0,loadSerial:0};
const completed={job_id:'job1',status:'completed',result:{updated:0,unchanged:1,missing:1,
 sources:[{source_id:'a',name:'A',status:'unchanged'},{source_id:'b',name:'B',status:'missing'}]}};
let calls=[],failPolling=false;
const fetchJsonWithTimeout=async(url,options={})=>{
 calls.push({url,method:options.method||'GET'});
 if(url.endsWith('sync-status'))return [
  {source_id:'a',name:'A',status:'ready'},{source_id:'b',name:'B',status:'missing'},
  {source_id:'dirty',name:'Dirty',status:'dirty'}
 ];
 if(url.endsWith('sync-jobs'))return [completed];
 if(failPolling)throw new Error('HTTP 503');
 return completed;
};
(async()=>{
 await loadSourceSyncStatus();
 assert.match($('#sourceSyncMessage').textContent,/1.*最新/);
 assert.match($('#sourceSyncMessage').textContent,/1.*未安装/);
 assert.match($('#sourceSyncList').innerHTML,/data-update-source="a"/);
 assert.match($('#sourceSyncList').innerHTML,/data-clone-source="b"/);
 assert.doesNotMatch($('#sourceSyncList').innerHTML,/data-update-source="dirty"/);
 await loadSourceSyncStatus();
 assert.match($('#sourceSyncMessage').textContent,/1.*最新/);
 assert.ok(calls.every(call=>call.method==='GET'));
 failPolling=true;sourceSyncUi.job={job_id:'active',status:'running',progress_total:2};
 await resumeSourceSync();
 assert.match($('#sourceSyncMessage').textContent,/连接中断.*HTTP 503/);
 assert.equal($('#sourceSyncResume').hidden,false);
 assert.equal(sourceSyncUi.busy,false);
 assert.equal(sourceJobActive(),true);
 failPolling=false;await resumeSourceSync();
 assert.match($('#sourceSyncMessage').textContent,/1.*最新/);
 assert.equal($('#sourceSyncResume').hidden,true);
 assert.ok(calls.every(call=>call.method==='GET'));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    subprocess.run([node, "-e", script + harness], check=True)  # noqa: S603
