from __future__ import annotations

import hashlib
import json

from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.remote_nodes import BRIDGE_DIRECTORIES


def test_remote_node_registration_diagnostics_and_bridge_prepare(settings, tmp_path) -> None:
    mount = tmp_path / "mounted-share"
    mount.mkdir()
    with TestClient(create_app(settings)) as client:
        saved = client.put(
            "/api/remote-nodes/training-node",
            json={
                "label": "5060 Ti 制图与训练机",
                "role": "compute_5060ti",
                "host": "192.168.1.50",
                "smb_mount": str(mount),
                "enabled": True,
                "capabilities": ["comfyui_generate", "embedding_batch", "lora_train"],
            },
        )
        assert saved.status_code == 200
        assert "password" not in saved.json()
        diagnostic = client.get("/api/remote-nodes/training-node/diagnostics").json()
        assert diagnostic["state"] == "mount_ready_bridge_unprepared"
        assert diagnostic["worker_ready"] is False
        assert diagnostic["credentials_stored"] is False

        prepared = client.post("/api/remote-nodes/training-node/prepare")
        assert prepared.status_code == 201
        assert prepared.json()["state"] == "ready"
        assert all((mount / "prompt-hub" / name).is_dir() for name in BRIDGE_DIRECTORIES)

        task_payload = {
            "task_type": "embedding_batch",
            "payload": {
                "model_id": "siglip-test",
                "model_revision": "revision-1",
                "items": [
                    {
                        "asset_id": "asset-1",
                        "relative_path": "datasets/asset-1.png",
                        "sha256": "a" * 64,
                    }
                ],
            },
            "manifest": [
                {
                    "relative_path": "datasets/asset-1.png",
                    "sha256": "a" * 64,
                    "size_bytes": 128,
                }
            ],
            "workspace_id": "workspace-1",
        }
        submitted = client.post(
            "/api/remote-nodes/training-node/tasks",
            json=task_payload,
        )
        assert submitted.status_code == 201
        task_id = submitted.json()["task_id"]
        outbox = mount / "prompt-hub" / "outbox" / f"{task_id}.json"
        assert outbox.is_file()
        assert client.get(f"/api/remote-nodes/training-node/tasks/{task_id}").status_code == 200
        tasks = client.get("/api/remote-nodes/training-node/tasks").json()
        assert tasks[0]["status"] == "queued"
        assert tasks[0]["workspace_id"] == "workspace-1"

        failed = mount / "prompt-hub" / "failed" / outbox.name
        outbox.replace(failed)
        failed_tasks = client.get("/api/remote-nodes/training-node/tasks").json()
        assert failed_tasks[0]["status"] == "failed"
        retried = client.post(f"/api/remote-nodes/training-node/tasks/{task_id}/retry")
        assert retried.status_code == 201
        assert retried.json()["attempt"] == 2
        assert retried.json()["retry_of"] == task_id
        assert retried.json()["task_id"] != task_id

        secret_payload = {
            **task_payload,
            "payload": {**task_payload["payload"], "credentials": {"password": "nope"}},
        }
        rejected_task_secret = client.post(
            "/api/remote-nodes/training-node/tasks",
            json=secret_payload,
        )
        assert rejected_task_secret.status_code == 422
        assert "凭据" in rejected_task_secret.json()["detail"]

        generation = client.post(
            "/api/remote-nodes/training-node/tasks",
            json={
                "task_type": "comfyui_generate",
                "payload": {
                    "generation_package": "packages/test.json",
                    "workflow_id": "workflow-1",
                    "output_profile": "anima",
                },
                "manifest": [],
            },
        )
        assert generation.status_code == 201
        assert generation.json()["status"] == "queued"
        assert generation.json()["target_role"] == "compute_5060ti"

        rejected_secret = client.put(
            "/api/remote-nodes/training-node",
            json={
                "role": "compute_5060ti",
                "password": "must-not-be-stored",
            },
        )
        assert rejected_secret.status_code == 422


def test_windows_lora_catalog_is_metadata_only_versioned_and_searchable(settings) -> None:
    payload = {
        "snapshot_id": "catalog-20260901",
        "worker_id": "training-node",
        "source_manager": "ComfyUI LoRA Manager",
        "items": [
            {
                "lora_id": "lora-anima-soda",
                "name": "Soda Character",
                "relative_path": "characters/soda_v12.safetensors",
                "sha256": "a" * 64,
                "size_bytes": 1024,
                "base_model": "Anima",
                "model_family": "anima",
                "trigger_words": ["soda_character"],
                "tags": ["character", "silver_hair"],
                "preview_relative_path": "characters/soda_v12.preview.png",
            },
            {
                "lora_id": "lora-krea-style",
                "name": "Painterly Light",
                "relative_path": "styles/painterly.safetensors",
                "base_model": "Krea 2",
                "model_family": "krea2",
                "trigger_words": ["painterly_light"],
            },
        ],
    }
    with TestClient(create_app(settings)) as client:
        imported = client.post("/api/windows-loras/import", json=payload)
        assert imported.status_code == 201
        assert imported.json()["metadata_only"] is True
        assert imported.json()["count"] == 2
        status = client.get("/api/windows-loras/status").json()
        assert status["snapshot_id"] == "catalog-20260901"
        searched = client.get("/api/windows-loras", params={"query": "silver_hair"}).json()
        assert searched["count"] == 1
        assert searched["results"][0]["relative_path"].endswith(".safetensors")
        assert "weight_bytes" not in searched["results"][0]

        changed = dict(payload)
        changed["items"] = [{**payload["items"][0], "name": "Changed"}]
        assert client.post("/api/windows-loras/import", json=changed).status_code == 422

        traversal = dict(payload)
        traversal["snapshot_id"] = "catalog-bad"
        traversal["items"] = [{**payload["items"][0], "relative_path": "../secret"}]
        assert client.post("/api/windows-loras/import", json=traversal).status_code == 422


def test_windows_lora_catalog_task_routes_verify_and_import(settings, tmp_path) -> None:
    mount = tmp_path / "mounted-share"
    mount.mkdir()
    bridge = mount / "prompt-hub"
    with TestClient(create_app(settings)) as client:
        assert (
            client.put(
                "/api/remote-nodes/compute-5060ti",
                json={
                    "role": "compute_5060ti",
                    "host": "192.168.1.10",
                    "smb_mount": str(mount),
                    "enabled": True,
                    "capabilities": ["lora_catalog_snapshot"],
                },
            ).status_code
            == 200
        )
        assert client.post("/api/remote-nodes/compute-5060ti/prepare").status_code == 201
        (bridge / "worker-status.json").write_text(
            json.dumps(
                {
                    "format": "soda-worker-status-v1",
                    "status": "ready",
                    "protocol_version": "soda-compute-bridge-v2",
                    "role": "compute_5060ti",
                    "comfyui_reachable": True,
                    "capabilities": ["comfyui_generate", "lora_catalog_snapshot"],
                    "lora_roots": [{"root_id": "comfyui-main", "exists": True, "model_count": 1}],
                }
            ),
            encoding="utf-8",
        )
        submitted = client.post("/api/remote-nodes/compute-5060ti/lora-catalog/sync")
        assert submitted.status_code == 201
        task_id = submitted.json()["task_id"]
        task_path = bridge / "outbox" / f"{task_id}.json"
        task = json.loads(task_path.read_text())
        assert task["payload"]["lora_roots"] == ["comfyui-main"]

        catalog = {
            "format": "soda-windows-lora-catalog-v1",
            "snapshot_id": "catalog-route-test",
            "worker_id": "compute-5060ti-worker",
            "source_manager": "ComfyUI LoRA Manager + LoraLoader",
            "items": [
                {
                    "lora_id": "lora-route-test",
                    "name": "Route Test",
                    "relative_path": "Anima/Character/route-test.safetensors",
                    "model_family": "anima",
                    "preview_relative_path": "Anima/Character/route-test.png",
                    "preview_relative_paths": ["Anima/Character/route-test.png"],
                }
            ],
        }
        output_path = bridge / "inbox" / task_id / "lora-catalog.json"
        output_path.parent.mkdir(parents=True)
        raw = json.dumps(catalog).encode()
        output_path.write_bytes(raw)
        preview_path = output_path.parent / "lora-previews" / "lora-route-test" / "000.png"
        preview_path.parent.mkdir(parents=True)
        preview_raw = b"\x89PNG\r\n\x1a\nroute-preview"
        preview_path.write_bytes(preview_raw)
        result = {
            "format": "soda-compute-result-v1",
            "protocol_version": "soda-compute-bridge-v2",
            "task_id": task_id,
            "task_type": "lora_catalog_snapshot",
            "worker_id": "compute-5060ti-worker",
            "status": "completed",
            "started_at": "2026-09-03T00:00:00+00:00",
            "finished_at": "2026-09-03T00:00:01+00:00",
            "source_hashes": [],
            "outputs": [
                {
                    "kind": "lora_catalog",
                    "relative_path": output_path.relative_to(bridge).as_posix(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "size_bytes": len(raw),
                },
                {
                    "kind": "lora_preview",
                    "relative_path": preview_path.relative_to(bridge).as_posix(),
                    "sha256": hashlib.sha256(preview_raw).hexdigest(),
                    "size_bytes": len(preview_raw),
                    "lora_id": "lora-route-test",
                    "preview_index": 0,
                    "source_relative_path": "Anima/Character/route-test.png",
                },
            ],
        }
        task_path.unlink()
        (bridge / "inbox" / f"{task_id}.json").write_text(json.dumps(result), encoding="utf-8")
        imported = client.post(
            f"/api/remote-nodes/compute-5060ti/tasks/{task_id}/import-lora-catalog"
        )
        assert imported.status_code == 201
        assert imported.json()["integrity_verified"] is True
        assert imported.json()["preview_count"] == 1
        searched = client.get("/api/windows-loras", params={"query": "Route Test"}).json()
        assert searched["count"] == 1
        preview_url = searched["results"][0]["preview_urls"][0]
        preview_response = client.get(preview_url)
        assert preview_response.status_code == 200
        assert preview_response.content == preview_raw
        assert preview_response.headers["content-type"].startswith("image/png")
        cached_preview = next((settings.remote_nodes_root / "lora-previews").rglob("000.png"))
        cached_preview.write_bytes(b"tampered")
        assert client.get(preview_url).status_code == 404


def test_remote_task_can_cancel_before_or_after_claim(settings, tmp_path) -> None:
    mount = tmp_path / "mounted-share"
    mount.mkdir()
    with TestClient(create_app(settings)) as client:
        saved = client.put(
            "/api/remote-nodes/compute-5060ti",
            json={
                "role": "compute_5060ti",
                "host": "192.168.1.10",
                "smb_mount": str(mount),
                "enabled": True,
                "capabilities": ["comfyui_generate"],
            },
        )
        assert saved.status_code == 200
        assert client.post("/api/remote-nodes/compute-5060ti/prepare").status_code == 201

        def submit() -> dict:
            response = client.post(
                "/api/remote-nodes/compute-5060ti/tasks",
                json={
                    "task_type": "comfyui_generate",
                    "payload": {
                        "generation_package": "packages/test.json",
                        "workflow_id": "workflow-1",
                        "output_profile": "anima",
                    },
                    "manifest": [],
                },
            )
            assert response.status_code == 201
            return response.json()

        queued = submit()
        canceled = client.post(f"/api/remote-nodes/compute-5060ti/tasks/{queued['task_id']}/cancel")
        assert canceled.status_code == 200
        assert canceled.json()["status"] == "canceled"

        running = submit()
        task_id = running["task_id"]
        outbox = mount / "prompt-hub" / "outbox" / f"{task_id}.json"
        processing = mount / "prompt-hub" / "processing" / outbox.name
        outbox.replace(processing)
        requested = client.post(f"/api/remote-nodes/compute-5060ti/tasks/{task_id}/cancel")
        assert requested.status_code == 200
        assert requested.json()["cancel_requested"] is True
        assert (processing.parent / f"{task_id}.cancel").is_file()
