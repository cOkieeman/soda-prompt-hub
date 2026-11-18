from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.pairing_web import PAIRING_SCRIPT
from prompt_hub.remote_web import REMOTE_HTML, REMOTE_SCRIPT


def test_pairing_is_embedded_and_preserves_configuration() -> None:
    assert 'id="pairingDialog"' in REMOTE_HTML
    assert "PAIRING_GUIDE" not in REMOTE_HTML
    assert "notes:saved?.notes" in REMOTE_SCRIPT
    assert "capabilities:saved?.capabilities" in REMOTE_SCRIPT
    assert "summary.worker_online" in PAIRING_SCRIPT
    assert "summary.can_compute" in PAIRING_SCRIPT
    assert "AbortSignal.timeout(15000)" in PAIRING_SCRIPT


def test_pairing_address_parser_rejects_credentials_and_subpaths() -> None:
    node = shutil.which("node")
    assert node
    start = PAIRING_SCRIPT.index("  function parseAddress(")
    end = PAIRING_SCRIPT.index("  async function verify()", start)
    harness = r"""
const assert = require('node:assert/strict');
assert.deepEqual(parseAddress('smb://pc/My%20Share'), {host:'pc',smb_share:'My Share'});
for(const value of ['http://pc/share','smb://user:pass@pc/share','smb://pc:445/share',
 'smb://pc/share/sub','smb://pc/share/../other','smb://pc/%2fprivate','smb://pc/%00',
 'smb://pc/share?token=secret','smb://pc/share#fragment','smb://pc/%2e%2e']) {
 assert.throws(()=>parseAddress(value), value);
}
"""
    subprocess.run([node, "-e", PAIRING_SCRIPT[start:end] + harness], check=True)  # noqa: S603


def test_connection_check_is_scoped_to_selected_device(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.put(
            "/api/remote-nodes/compute-5060ti",
            json={
                "role": "compute_5060ti",
                "host": "pc",
                "enabled": True,
                "label": "primary",
                "smb_mount": str(settings.library_root / "missing-pairing-test"),
            },
        )
        assert response.status_code == 200
        result = client.get("/api/remote-nodes/not-the-primary/connection").json()
        assert result["state"] == "not_configured"
        assert result["device"] != "primary"
        assert not result["can_compute"]


def test_worker_guide_only_reads_shares() -> None:
    root = Path(__file__).resolve().parents[1]
    host = (root / "deploy/windows-shell/SodaComputeWorker/WorkerHost.cs").read_text()
    guide = host.split("internal Dictionary<string, object?> GetPairingInfo()", 1)[1]
    guide = guide.split("internal async Task<string> ExportDiagnosticsAsync()", 1)[0]
    assert "NetShareEnum" in guide
    assert "NetShareAdd" not in guide
    assert "netsh" not in guide
    assert "NetApiBufferFree(buffer)" in guide
    assert "Uri.EscapeDataString(share.Name)" in guide
    js = (root / "deploy/desktop-ui/desktop.js").read_text()
    assert "product==='desktop')await checkGuide()" in js
    assert "current.localWorkerState" in js
    assert "current.localComfyState" in js
