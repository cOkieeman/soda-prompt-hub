from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from prompt_hub.remote_web import REMOTE_SCRIPT


def test_remote_actions_have_persistent_feedback_and_unlock_after_failure() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for frontend behavior checks")
    start = REMOTE_SCRIPT.index("  async function act(")
    end = REMOTE_SCRIPT.index("  async function ensure(", start)
    harness = r"""
const assert = require('node:assert/strict');
let resolveRequest;
let fail = false;
const buttons = ['save','diagnose','prepare'].map(action => ({
  dataset:{remoteAction:action}, textContent:action, disabled:false,
  setAttribute(){}, removeAttribute(){}
}));
const feedback = {dataset:{},textContent:'',hidden:true};
const message = {textContent:''};
const card = {dataset:{remoteNode:'test'},
  querySelector: selector => selector === '[data-remote-message]' ? message : feedback,
  querySelectorAll: () => buttons,
  setAttribute(){}, removeAttribute(){}
};
const state = {nodes:[]};
const combinedNodes = () => [{node_id:'test'}];
const payload = () => ({});
const confirm = () => true;
const renderDiagnostic = () => {};
const api = async () => {
  if (fail) throw new Error('offline');
  return {node_id:'test',state:'ready'};
};
const diagnoseNode = async () => new Promise(resolve => {resolveRequest=resolve;});
(async () => {
  const pending = runNodeAction(card,buttons[1]);
  assert.equal(buttons[1].textContent,'正在检查…');
  assert.ok(buttons.every(button => button.disabled));
  assert.equal(feedback.dataset.tone,'busy');
  resolveRequest({state:'ready'});
  await pending;
  assert.equal(feedback.dataset.tone,'success');
  assert.match(feedback.textContent,/检查完成/);
  assert.ok(buttons.every(button => !button.disabled));
  await runNodeAction(card,buttons[2]);
  assert.match(feedback.textContent,/已就绪/);
  fail=true;
  await runNodeAction(card,buttons[0]);
  assert.equal(feedback.dataset.tone,'error');
  assert.match(feedback.textContent,/offline/);
  assert.ok(buttons.every(button => !button.disabled));
})().catch(error => {console.error(error);process.exitCode=1;});
"""
    # Execute only repository-owned JavaScript and this fixed test harness.
    subprocess.run([node, "-e", REMOTE_SCRIPT[start:end] + harness], check=True)  # noqa: S603


def test_launcher_connection_buttons_reset_native_appearance() -> None:
    root = Path(__file__).resolve().parents[1]
    css = (root / "deploy/desktop-ui/desktop.css").read_text()
    rule = css.split(".connection-actions button {", 1)[1].split("}", 1)[0]
    assert "appearance: none" in rule
    assert "box-shadow: none" in rule
