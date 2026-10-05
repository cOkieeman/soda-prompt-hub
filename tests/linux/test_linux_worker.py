"""End-to-end check of the Compute Worker on Linux.

A fake ComfyUI endpoint speaks the HTTP API while the real worker and a real bridge
directory take part: the worker claims a task from `outbox/`, posts it to ComfyUI,
downloads the image through `/view`, and files a signed result envelope in `inbox/`
that Core can verify.

The fake returns a genuine PNG (not filler bytes) so the produced artifact can be
checked as an image, and the whole loop runs without a GPU.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlsplit

import pytest
from PIL import Image

from prompt_hub.remote_nodes import RemoteNodeStore
from prompt_hub.windows_worker import WindowsWorker, WorkerConfig

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux worker behaviour test")

PROMPT_ID = "prompt-linux-1"


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (32, 96, 160)).save(buffer, format="PNG")
    return buffer.getvalue()


class ComfyHandler(BaseHTTPRequestHandler):
    """Minimal ComfyUI surface: system_stats, object_info, prompt, history, view."""

    state: ClassVar[dict[str, Any]] = {}

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/system_stats":
            self._send_bytes(
                json.dumps({"system": {"os": "linux"}, "devices": [{"name": "CPU"}]}).encode(),
                "application/json",
            )
        elif path == "/object_info/LoraLoader":
            self._send_json({"LoraLoader": {"input": {"required": {"lora_name": [[], {}]}}}})
        elif path.startswith("/history/"):
            prompt_id = path.rsplit("/", 1)[-1]
            self._send_json(
                {
                    prompt_id: {
                        "status": {"status_str": "success", "completed": True},
                        "outputs": {
                            "9": {
                                "images": [
                                    {
                                        "filename": "linux output.png",
                                        "subfolder": "",
                                        "type": "output",
                                    },
                                ]
                            }
                        },
                    }
                }
            )
        elif path == "/view":
            self.state["view_count"] = self.state.get("view_count", 0) + 1
            self._send_bytes(_png_bytes(), "image/png")
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")) or 0)
        if self.path == "/prompt":
            self.state["post_count"] = self.state.get("post_count", 0) + 1
            self.state["last_prompt"] = json.loads(raw)
            self._send_json({"prompt_id": PROMPT_ID, "number": 1, "node_errors": {}})
        elif self.path == "/interrupt":
            self._send_json({})
        else:
            self.send_error(404)

    def log_message(self, format: str, *_args: object) -> None:  # noqa: A002
        del format

    def _send_json(self, payload: dict[str, Any]) -> None:
        self._send_bytes(json.dumps(payload).encode(), "application/json")

    def _send_bytes(self, payload: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class AuthenticatedComfyHandler(ComfyHandler):
    """ComfyUI behind HTTP Basic auth, as a reverse proxy would expose it."""

    expected = "Basic " + base64.b64encode(b"worker:secret").decode("ascii")

    def _authorized(self) -> bool:
        if self.headers.get("Authorization") == self.expected:
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="comfyui"')
        self.end_headers()
        return False

    def do_GET(self) -> None:
        if self._authorized():
            super().do_GET()

    def do_POST(self) -> None:
        if self._authorized():
            super().do_POST()


@contextmanager
def comfy_server(handler: type[ComfyHandler] = ComfyHandler) -> Any:
    handler.state = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", handler.state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest(path: Path, bridge: Path) -> dict[str, Any]:
    return {
        "relative_path": path.relative_to(bridge).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def test_worker_completes_a_generation_task_on_linux(tmp_path: Path) -> None:
    mount = tmp_path / "mount"
    bridge = mount / "prompt-hub"
    package_path = bridge / "packages" / "smoke.json"
    _write_json(
        package_path,
        {
            "format": "soda-comfyui-package-v1",
            "workflow_id": "linux-smoke",
            "api_prompt": {"1": {"class_type": "Example", "inputs": {"seed": 1}}},
        },
    )

    store = RemoteNodeStore(tmp_path / "remote-state")
    store.initialize()
    store.save_node(
        "compute-5060ti",
        {
            "role": "compute_5060ti",
            "host": "127.0.0.1",
            "smb_mount": str(mount),
            "enabled": True,
            "capabilities": ["comfyui_generate"],
        },
    )
    store.prepare_bridge("compute-5060ti")

    with comfy_server() as (url, state):
        submitted = store.submit_task(
            "compute-5060ti",
            {
                "task_type": "comfyui_generate",
                "payload": {
                    "generation_package": "packages/smoke.json",
                    "workflow_id": "linux-smoke",
                    "output_profile": "anima",
                },
                "manifest": [_manifest(package_path, bridge)],
            },
        )

        worker = WindowsWorker(
            WorkerConfig(
                bridge_root=bridge,
                comfyui_url=url,
                worker_id="linux-worker",
                history_poll_seconds=0.01,
                task_timeout_seconds=5,
                http_timeout_seconds=3,
            )
        )
        self_test = worker.self_test()
        assert self_test["comfyui_reachable"] is True
        assert worker.run_once() is True
        assert state["post_count"] == 1
        assert state["last_prompt"]["prompt"]["1"]["class_type"] == "Example"

    task_id = submitted["task_id"]
    result = json.loads((bridge / "inbox" / f"{task_id}.json").read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert result["task_id"] == task_id
    assert {item["kind"] for item in result["outputs"]} == {"image", "workflow", "run_log"}

    image = next(item for item in result["outputs"] if item["kind"] == "image")
    image_path = bridge / image["relative_path"]
    payload = image_path.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n"), "结果图应当是真正的 PNG"
    assert hashlib.sha256(payload).hexdigest() == image["sha256"]

    # Core 侧的完整性校验必须通过 (这正是 Mac 导入前会做的事)
    verified = store.verify_returned_task("compute-5060ti", task_id)
    assert verified["verified"] is True
    assert verified["output_count"] == 3

    # 任务文件已从 outbox 归档, 不会重复执行
    assert not (bridge / "outbox" / f"{task_id}.json").exists()


def test_worker_uses_credentials_embedded_in_the_comfyui_url(tmp_path: Path) -> None:
    """`http://user:password@host` 必须转成 Authorization 头, 且不残留凭据。"""
    mount = tmp_path / "mount"
    bridge = mount / "prompt-hub"
    package_path = bridge / "packages" / "auth.json"
    _write_json(
        package_path,
        {
            "format": "soda-comfyui-package-v1",
            "workflow_id": "linux-auth",
            "api_prompt": {"1": {"class_type": "Example", "inputs": {}}},
        },
    )
    store = RemoteNodeStore(tmp_path / "state")
    store.initialize()
    store.save_node(
        "compute-5060ti",
        {
            "role": "compute_5060ti",
            "host": "127.0.0.1",
            "smb_mount": str(mount),
            "enabled": True,
        },
    )
    store.prepare_bridge("compute-5060ti")

    with comfy_server(AuthenticatedComfyHandler) as (url, _state):
        credentialed = url.replace("http://", "http://worker:secret@")
        worker = WindowsWorker(
            WorkerConfig(
                bridge_root=bridge,
                comfyui_url=credentialed,
                worker_id="linux-worker",
                history_poll_seconds=0.01,
                task_timeout_seconds=5,
                http_timeout_seconds=3,
            )
        )
        assert worker.client.base_url == url, "base_url 不应残留凭据"
        assert worker.self_test()["comfyui_reachable"] is True
        submitted = store.submit_task(
            "compute-5060ti",
            {
                "task_type": "comfyui_generate",
                "payload": {
                    "generation_package": "packages/auth.json",
                    "workflow_id": "linux-auth",
                    "output_profile": "anima",
                },
                "manifest": [_manifest(package_path, bridge)],
            },
        )
        assert worker.run_once() is True

    result = json.loads(
        (bridge / "inbox" / f"{submitted['task_id']}.json").read_text(encoding="utf-8")
    )
    assert result["status"] == "completed"
