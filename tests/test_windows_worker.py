from __future__ import annotations

import hashlib
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import urlsplit

import pytest

import prompt_hub.windows_worker as worker_module
from prompt_hub.remote_nodes import RemoteNodeStore
from prompt_hub.windows_worker import (
    LoraRootConfig,
    WindowsWorker,
    WorkerConfig,
    WorkerError,
    WorkerLock,
    worker_lock_path,
)

if TYPE_CHECKING:
    from pathlib import Path


class ComfyHandler(BaseHTTPRequestHandler):
    state: ClassVar[dict[str, Any]] = {}

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/system_stats":
            self._send_json({"system": {"os": "nt"}, "devices": [{"name": "RTX 5060 Ti"}]})
        elif path == "/object_info/LoraLoader":
            self._send_json(
                {
                    "LoraLoader": {
                        "input": {
                            "required": {
                                "lora_name": [self.state.get("lora_names", []), {}],
                            }
                        }
                    }
                }
            )
        elif path.startswith("/history/"):
            self.state["history_count"] += 1
            prompt_id = path.rsplit("/", 1)[-1]
            self._send_json(
                {
                    prompt_id: {
                        "status": {"status_str": "success", "completed": True},
                        "outputs": {
                            "9": {
                                "images": [
                                    {
                                        "filename": "test output.png",
                                        "subfolder": "",
                                        "type": "output",
                                    }
                                ]
                            }
                        },
                    }
                }
            )
        elif path == "/view":
            self._send_bytes(b"fake-png-content", "image/png")
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")) or 0)
        if self.path == "/prompt":
            self.state["post_count"] += 1
            self.state["last_prompt"] = json.loads(body)
            self._send_json({"prompt_id": "prompt-test-1", "number": 1, "node_errors": {}})
        elif self.path == "/interrupt":
            self.state["interrupt_count"] += 1
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


@contextmanager
def comfy_server():
    ComfyHandler.state = {
        "post_count": 0,
        "history_count": 0,
        "interrupt_count": 0,
        "last_prompt": {},
        "lora_names": [],
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), ComfyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", ComfyHandler.state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_worker_comfyui_round_trip_and_mac_integrity(tmp_path) -> None:
    mount = tmp_path / "mount"
    bridge = mount / "prompt-hub"
    package_path = bridge / "packages" / "smoke.json"
    _write_json(
        package_path,
        {
            "format": "soda-comfyui-package-v1",
            "workflow_id": "smoke-workflow",
            "api_prompt": {"1": {"class_type": "Example", "inputs": {"seed": 1}}},
        },
    )
    store = RemoteNodeStore(tmp_path / "remote-state")
    store.initialize()
    store.save_node(
        "compute-5060ti",
        {
            "role": "compute_5060ti",
            "host": "192.168.1.10",
            "smb_mount": str(mount),
            "enabled": True,
            "capabilities": ["comfyui_generate"],
        },
    )
    store.prepare_bridge("compute-5060ti")
    submitted = store.submit_task(
        "compute-5060ti",
        {
            "task_type": "comfyui_generate",
            "payload": {
                "generation_package": "packages/smoke.json",
                "workflow_id": "smoke-workflow",
                "output_profile": "anima",
            },
            "manifest": [_manifest(package_path, bridge)],
        },
    )

    with comfy_server() as (url, state):
        worker = WindowsWorker(_config(bridge, url))
        assert worker.self_test()["comfyui_reachable"] is True
        assert store.diagnostics("compute-5060ti")["worker_ready"] is True
        assert worker.run_once() is True
        assert state["post_count"] == 1
        assert state["last_prompt"]["prompt"]["1"]["class_type"] == "Example"

    task_id = submitted["task_id"]
    result = json.loads((bridge / "inbox" / f"{task_id}.json").read_text())
    assert result["status"] == "completed"
    assert {item["kind"] for item in result["outputs"]} == {"image", "workflow", "run_log"}
    verified = store.verify_returned_task("compute-5060ti", task_id)
    assert verified["verified"] is True
    assert verified["output_count"] == 3

    image = next(item for item in result["outputs"] if item["kind"] == "image")
    (bridge / image["relative_path"]).write_bytes(b"tampered")
    rejected = store.verify_returned_task("compute-5060ti", task_id)
    assert rejected["verified"] is False
    assert any("SHA-256 不匹配" in error for error in rejected["errors"])


@pytest.mark.parametrize(
    ("package_path", "manifest_hash", "expected"),
    [
        ("../outside.json", "", "相对路径无效"),
        ("packages/bad.json", "", "必须出现在已校验的 manifest"),
        ("packages/bad.json", "0" * 64, "SHA-256 不匹配"),
    ],
)
def test_worker_rejects_unsafe_path_and_hash(
    tmp_path,
    package_path: str,
    manifest_hash: str,
    expected: str,
) -> None:
    bridge = tmp_path / "prompt-hub"
    actual_package = bridge / "packages" / "bad.json"
    _write_json(actual_package, {"format": "soda-comfyui-package-v1"})
    task_id = "task-bad"
    manifest = []
    if manifest_hash:
        manifest = [
            {
                "relative_path": "packages/bad.json",
                "sha256": manifest_hash,
                "size_bytes": actual_package.stat().st_size,
            }
        ]
    _write_json(
        bridge / "outbox" / f"{task_id}.json",
        _task(task_id, package_path, manifest),
    )
    with comfy_server() as (url, state):
        worker = WindowsWorker(_config(bridge, url))
        assert worker.run_once() is True
        assert state["post_count"] == 0
    failed = json.loads((bridge / "failed" / f"{task_id}.json").read_text())
    assert failed["status"] == "failed"
    assert expected in failed["error"]


def test_worker_resumes_prompt_without_resubmitting_and_cleans_finalized_task(tmp_path) -> None:
    bridge = tmp_path / "prompt-hub"
    package_path = bridge / "packages" / "resume.json"
    _write_json(
        package_path,
        {
            "format": "soda-comfyui-package-v1",
            "workflow_id": "workflow-resume",
            "api_prompt": {"1": {"class_type": "Example", "inputs": {}}},
        },
    )
    task_id = "task-resume"
    task = _task(task_id, "packages/resume.json", [_manifest(package_path, bridge)])
    _write_json(bridge / "processing" / f"{task_id}.json", task)
    _write_json(
        bridge / "processing" / f"{task_id}.state.json",
        {"task_id": task_id, "prompt_id": "prompt-test-1"},
    )
    with comfy_server() as (url, state):
        worker = WindowsWorker(_config(bridge, url))
        worker.recover_processing()
        assert state["post_count"] == 0
        assert state["history_count"] == 1
    assert (bridge / "inbox" / f"{task_id}.json").is_file()

    stale = bridge / "processing" / f"{task_id}.json"
    _write_json(stale, task)
    WindowsWorker(_config(bridge, "http://127.0.0.1:9")).recover_processing()
    assert not stale.exists()


def test_worker_lock_prevents_two_workers(tmp_path) -> None:
    lock_path = tmp_path / "worker.lock"
    with (
        WorkerLock(lock_path),
        pytest.raises(WorkerError, match="另一个 worker"),
        WorkerLock(lock_path),
    ):
        pass


def test_windows_worker_lock_is_outside_shared_bridge(tmp_path, monkeypatch) -> None:
    local_app_data = tmp_path / "local-app-data"
    bridge = tmp_path / "shared" / "prompt-hub"
    monkeypatch.setattr(worker_module.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    path = worker_lock_path(_config(bridge, "http://127.0.0.1:8188"))
    assert path.parent == local_app_data / "PromptHub"
    assert not path.is_relative_to(bridge)


def test_worker_lora_catalog_snapshot_and_mac_import(tmp_path) -> None:
    mount = tmp_path / "mount"
    mount.mkdir()
    bridge = mount / "prompt-hub"
    lora_root = tmp_path / "loras"
    model = lora_root / "Anima" / "Character" / "linhuier-anima_v01.safetensors"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"weight-bytes-must-not-be-copied")
    preview = model.with_suffix(".jpeg")
    preview.write_bytes(b"RIFF\x10\x00\x00\x00WEBPprimary-preview")
    backup_preview = model.with_name(f"{model.stem}.civitai_bak.png")
    backup_preview.write_bytes(b"\x89PNG\r\n\x1a\nbackup-preview")
    model.with_suffix(".metadata.json").write_text(
        json.dumps(
            {
                "model_name": "林悔儿 Anima v01",
                "base_model": "Anima Base 1.0",
                "tags": ["character", "original character"],
                "preview_url": str(preview),
                "sha256": "b" * 64,
                "civitai": {
                    "id": 3262276,
                    "modelId": 2885952,
                    "trainedWords": ["linhuieroc", {"word": "brown hair"}],
                    "model": {"tags": ["original character", "anime"]},
                },
                "description": "private notes should stay bounded",
            }
        ),
        encoding="utf-8",
    )
    store = RemoteNodeStore(tmp_path / "remote-state")
    store.initialize()
    store.save_node(
        "compute-5060ti",
        {
            "role": "compute_5060ti",
            "host": "192.168.1.10",
            "smb_mount": str(mount),
            "enabled": True,
            "capabilities": ["lora_catalog_snapshot"],
        },
    )
    store.prepare_bridge("compute-5060ti")

    with comfy_server() as (url, state):
        state["lora_names"] = ["Anima\\Character\\linhuier-anima_v01.safetensors"]
        config = WorkerConfig(
            bridge_root=bridge,
            comfyui_url=url,
            worker_id="compute-5060ti-worker",
            lora_roots=(LoraRootConfig(root_id="comfyui-main", path=lora_root),),
        )
        worker = WindowsWorker(config)
        self_test = worker.self_test()
        assert self_test["capabilities"] == ["comfyui_generate", "lora_catalog_snapshot"]
        assert self_test["lora_roots"][0]["model_count"] == 1
        submitted = store.submit_lora_catalog_snapshot("compute-5060ti")
        assert worker.run_once() is True

    _assert_lora_catalog_import(store, bridge, submitted["task_id"], tmp_path)


def test_lora_preview_matching_does_not_cross_similar_model_names(tmp_path) -> None:
    lora_root = tmp_path / "loras"
    model = lora_root / "model-v1.safetensors"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"weight-bytes-must-not-be-read")
    model.with_suffix(".jpeg").write_bytes(b"\xff\xd8\xff\xdbprimary-preview")
    model.with_name(f"{model.stem}.civitai_bak.png").write_bytes(b"\x89PNG\r\n\x1a\nbackup-preview")
    model.with_name("model-v1.1.jpeg").write_bytes(b"\xff\xd8\xff\xdbother-model-preview")

    previews = worker_module._find_lora_previews(lora_root, model, {})  # noqa: SLF001

    assert previews == ["model-v1.jpeg", "model-v1.civitai_bak.png"]


def test_lora_preview_copy_reports_oversize_skip_reason(tmp_path, monkeypatch) -> None:
    lora_root = tmp_path / "loras"
    lora_root.mkdir()
    (lora_root / "model.jpeg").write_bytes(b"\xff\xd8\xffok")
    (lora_root / "model.civitai_bak.png").write_bytes(b"too-large-preview")
    items = [
        {
            "lora_id": "lora-test",
            "metadata": {"root_id": "comfyui-main"},
            "preview_relative_paths": ["model.jpeg", "model.civitai_bak.png"],
        }
    ]
    bridge = tmp_path / "bridge"
    monkeypatch.setattr(worker_module, "MAX_LORA_PREVIEW_BYTES", 8)

    outputs, summary = worker_module._copy_lora_previews(  # noqa: SLF001
        items,
        {"comfyui-main": lora_root},
        bridge,
        bridge / "inbox" / "task-test",
    )

    assert len(outputs) == 1
    assert summary["preview_skipped_count"] == 1
    assert summary["preview_skipped_reasons"] == {"file_too_large": 1}


def _assert_lora_catalog_import(
    store: RemoteNodeStore,
    bridge: Path,
    task_id: str,
    tmp_path: Path,
) -> None:
    verified = store.verify_returned_task("compute-5060ti", task_id)
    assert verified["verified"] is True
    assert verified["output_count"] == 3
    preview_outputs = [item for item in verified["outputs"] if item["kind"] == "lora_preview"]
    assert len(preview_outputs) == 2
    assert len({item["lora_id"] for item in preview_outputs}) == 1
    assert preview_outputs[0]["relative_path"].endswith("/000.webp")
    result = json.loads((bridge / "inbox" / f"{task_id}.json").read_text())
    catalog_output = next(item for item in result["outputs"] if item["kind"] == "lora_catalog")
    catalog = json.loads((bridge / catalog_output["relative_path"]).read_text())
    assert catalog["format"] == "soda-windows-lora-catalog-v1"
    assert len(catalog["items"]) == 1
    item = catalog["items"][0]
    assert item["name"] == "林悔儿 Anima v01"
    assert item["relative_path"] == "Anima/Character/linhuier-anima_v01.safetensors"
    assert item["preview_relative_path"].endswith("linhuier-anima_v01.jpeg")
    assert len(item["preview_relative_paths"]) == 2
    assert item["trigger_words"] == ["linhuieroc", "brown hair"]
    assert item["tags"] == ["character", "original character", "anime"]
    assert item["model_family"] == "anima"
    assert item["metadata"]["comfyui_visible"] is True
    assert item["metadata"]["civitai_model_id"] == 2885952
    assert item["metadata"]["civitai_version_id"] == 3262276
    assert item["sha256"] == "b" * 64
    assert "weight_bytes" not in item

    imported = store.import_returned_lora_catalog("compute-5060ti", task_id)
    assert imported["count"] == 1
    assert imported["preview_count"] == 2
    assert imported["with_preview_count"] == 1
    imported_item = store.search_loras("linhuieroc")[0]
    assert imported_item["name"] == "林悔儿 Anima v01"
    assert len(imported_item["preview_urls"]) == 2
    assert not list((tmp_path / "remote-state" / "lora-previews").rglob("*.safetensors"))


def _config(bridge: Path, url: str) -> WorkerConfig:
    return WorkerConfig(
        bridge_root=bridge,
        comfyui_url=url,
        worker_id="compute-5060ti-worker",
        history_poll_seconds=0.01,
        task_timeout_seconds=2,
        http_timeout_seconds=2,
    )


def _task(
    task_id: str,
    package_path: str,
    manifest: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "format": "soda-compute-task-v1",
        "protocol_version": "soda-compute-bridge-v2",
        "task_id": task_id,
        "task_type": "comfyui_generate",
        "target_role": "compute_5060ti",
        "created_at": "2026-09-02T00:00:00+00:00",
        "payload": {
            "generation_package": package_path,
            "workflow_id": "workflow-resume",
            "output_profile": "anima",
        },
        "manifest": manifest,
        "attempt": 1,
        "priority": 0,
    }


def _manifest(path: Path, bridge: Path) -> dict[str, Any]:
    return {
        "relative_path": path.relative_to(bridge).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
