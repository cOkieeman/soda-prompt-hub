from __future__ import annotations

import hashlib
import json
import time
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from prompt_hub.api import create_app
from prompt_hub.comfy_results import ComfyResultStore
from prompt_hub.config import Settings
from prompt_hub.creative import CreativeStore
from prompt_hub.database import PromptDatabase
from prompt_hub.dataset_workspace import DatasetWorkspaceStore
from prompt_hub.gallery import GalleryStore
from prompt_hub.local_model import LocalModelError
from prompt_hub.maintenance import BackupManager, verify_backup
from prompt_hub.remote_nodes import RemoteNodeStore
from prompt_hub.visual_assets import VisualAssetCatalog
from prompt_hub.web_capture import WebCaptureService


def _png(color="red"):
    output = BytesIO()
    Image.new("RGB", (80, 120), color).save(output, "PNG")
    return output.getvalue()


def test_gallery_generation_facets_filter_real_connected_records(client):
    prompt = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "base.safetensors"}},
        "2": {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "style.safetensors",
                "strength_model": 0.4,
                "strength_clip": 0.4,
            },
        },
        "3": {"class_type": "SaveImage", "inputs": {"images": ["6", 0]}},
        "5": {"class_type": "KSampler", "inputs": {"model": ["2", 0]}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0]}},
        "4": {"class_type": "LoraLoader", "inputs": {"lora_name": "unused.safetensors"}},
    }
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", json.dumps(prompt))
    info.add_text("parameters", 'scene\nSteps: 8, Lora hashes: "style.safetensors: 123456789A"')
    output = BytesIO()
    Image.new("RGB", (80, 120), "red").save(output, "PNG", pnginfo=info)
    imported = client.post("/api/gallery/import?filename=recorded.png", content=output.getvalue())
    assert imported.status_code == 201
    summary = client.get("/api/gallery/assets").json()["items"][0]
    assert "prompt" not in summary["metadata"]
    detail = client.get(f"/api/gallery/assets/{imported.json()['asset_id']}").json()
    assert detail["metadata"]["prompt"] == prompt
    client.post("/api/gallery/import?filename=plain.png", content=_png("blue"))
    facets = client.get("/api/gallery/facets").json()
    assert facets == {"models": ["base.safetensors"], "loras": ["style.safetensors"]}
    assert client.get("/api/gallery/assets?model=base.safetensors").json()["total"] == 1
    assert client.get("/api/gallery/assets?lora=style.safetensors").json()["total"] == 1
    assert client.get("/api/gallery/assets?lora=unused.safetensors").json()["total"] == 0
    assert client.get("/api/gallery/assets", params={"model": "' OR 1=1 --"}).json()["total"] == 0


def _wait_job(client, response):
    assert response.status_code == 202, response.text
    deadline = time.monotonic() + 5
    job_id = response.json()["job_id"]
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in {"completed", "failed", "canceled"}:
            assert job["status"] == "completed", job
            return job
        time.sleep(0.01)
    pytest.fail(f"gallery job did not finish: {job_id}")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as active_client:
        yield active_client


def _register_and_scan(client, source, *, kind="reference"):
    registered = client.post(
        "/api/gallery/roots", json={"path": str(source), "kind": kind, "label": "本地画廊"}
    )
    assert registered.status_code == 201, registered.text
    root = registered.json()
    job = _wait_job(client, client.post(f"/api/gallery/roots/{root['root_id']}/scan"))
    return root, job


def test_real_app_scan_repeat_reference_and_project_snapshot(client, settings, tmp_path):
    source = tmp_path / "collected"
    source.mkdir()
    (source / "reference.png").write_bytes(_png())
    root, first = _register_and_scan(client, source)
    assert first["result"]["imported"] == 1
    store = GalleryStore(settings)
    assert list(store.original_root.iterdir()) == []
    repeated = _wait_job(client, client.post(f"/api/gallery/roots/{root['root_id']}/scan"))
    assert repeated["result"]["unchanged"] == 1
    asset = client.get("/api/gallery/assets").json()["items"][0]
    project = client.post(
        "/api/creative/projects",
        json={
            "title": "雨夜测试",
            "slots": {"style": "ink", "composition": "doorway"},
            "slot_locks": {"style": True},
            "generation": {"seed": 43, "width": 960, "height": 1280},
        },
    ).json()
    attached = client.post(
        f"/api/gallery/assets/{asset['asset_id']}/reference/{project['project_id']}",
        json={"purpose": "all"},
    )
    assert attached.status_code == 200
    updated = attached.json()
    assert updated["slots"] == project["slots"]
    assert updated["slot_locks"] == project["slot_locks"]
    assert updated["references"][0]["purpose"] == "all"
    assert updated["references"][0]["slot"] == "composition"
    linked = client.put(
        f"/api/gallery/assets/{asset['asset_id']}",
        json={"kind": "work", "project_id": project["project_id"], "note": "这个镜头有效"},
    ).json()
    assert linked["project_snapshot"]["generation"] == project["generation"]
    assert linked["project_snapshot"]["slots"] == project["slots"]
    assert linked["metadata"]["loras"] == []
    assert client.get(asset["original_url"]).content == _png()
    assert client.get("/api/gallery/assets?kind=work").json()["total"] == 1


def test_gallery_assets_are_real_visual_sources_and_offline_is_excluded(client, settings, tmp_path):
    source = tmp_path / "visual-source"
    source.mkdir()
    raw = _png("blue")
    mapped_file = source / "reference.png"
    mapped_file.write_bytes(raw)
    _register_and_scan(client, source)
    item = client.get("/api/gallery/assets").json()["items"][0]
    database = PromptDatabase(settings.database_path)
    gallery = GalleryStore(settings)
    catalog = VisualAssetCatalog(
        settings,
        database,
        DatasetWorkspaceStore(settings),
        CreativeStore(settings.database_path),
        ComfyResultStore(settings.comfy_results_root),
        RemoteNodeStore(settings.remote_nodes_root),
        WebCaptureService(settings, database),
        gallery,
    )
    discovered = catalog.discover({"gallery_image"})
    assert len(discovered) == 1
    actual = discovered[0]
    assert actual.path == mapped_file
    assert actual.path.read_bytes() == raw
    assert actual.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert actual.metadata["gallery_asset_id"] == item["asset_id"]
    assert actual.metadata["safety"] == "unrated"
    assert actual.metadata["media_url"] == item["thumbnail_url"]
    mapped_file.unlink()
    assert client.get(f"/api/gallery/assets/{item['asset_id']}").json()["availability"] == "offline"
    assert catalog.discover({"gallery_image"}) == []
    assert client.get(item["thumbnail_url"]).status_code == 200


def test_analysis_failure_preview_confirmation_and_stale_original(client, tmp_path, monkeypatch):
    source = tmp_path / "analysis-source"
    source.mkdir()
    path = source / "reference.png"
    path.write_bytes(_png())
    _register_and_scan(client, source)
    item = client.get("/api/gallery/assets").json()["items"][0]
    analysis_url = f"/api/gallery/assets/{item['asset_id']}/analyze"
    confirmation_url = f"/api/gallery/assets/{item['asset_id']}/analysis"

    def unavailable(**_kwargs):
        error = LocalModelError("fake vision endpoint unavailable")
        raise error

    monkeypatch.setattr("prompt_hub.gallery_routes.analyze_result_image", unavailable)
    failed = client.post(analysis_url, json={"model": "fake-vision", "purpose": "style"})
    assert failed.status_code == 503
    assert client.get(f"/api/gallery/assets/{item['asset_id']}").json()["analysis"] == {}

    def fake_vision(**kwargs):
        assert kwargs["image_path"].read_bytes() == _png()
        return json.loads(
            '{"summary_zh":"门框形成前景","observed_slots":{"composition":"doorway"}}'
        )

    monkeypatch.setattr("prompt_hub.gallery_routes.analyze_result_image", fake_vision)
    preview = client.post(
        analysis_url, json={"model": "fake-vision", "purpose": "composition"}
    ).json()
    assert preview["confirmed"] is False
    assert client.get(f"/api/gallery/assets/{item['asset_id']}").json()["analysis"] == {}
    confirmed = client.put(confirmation_url, json={"analysis": preview}).json()
    assert confirmed["analysis"]["confirmed"] is True
    path.write_bytes(_png("green"))
    stale = client.get(f"/api/gallery/assets/{item['asset_id']}").json()
    assert stale["analysis_stale"] is True
    assert client.put(confirmation_url, json={"analysis": preview}).status_code == 409
    assert client.get(item["original_url"]).status_code == 404


def test_backup_preserves_gallery_and_does_not_copy_mapped_originals(client, settings, tmp_path):
    source = tmp_path / "large-reference-library"
    source.mkdir()
    mapped_raw = _png("blue")
    (source / "mapped-reference.png").write_bytes(mapped_raw)
    _register_and_scan(client, source)
    mapped = client.get("/api/gallery/assets").json()["items"][0]
    upload_raw = _png()
    uploaded = client.post(
        "/api/gallery/import?filename=work.png&kind=work", content=upload_raw
    ).json()
    client.put(
        f"/api/gallery/assets/{uploaded['asset_id']}",
        json={"favorite": True, "note": "keep this", "albums": ["雨夜"]},
    )
    client.put(
        f"/api/gallery/assets/{uploaded['asset_id']}/analysis",
        json={"analysis": {"summary_zh": "前景清楚", "source_sha256": uploaded["sha256"]}},
    )
    destination = tmp_path / "complete-backup"
    backed_up = _wait_job(
        client, client.post("/api/maintenance/backups", json={"destination": str(destination)})
    )
    assert backed_up["result"]["ok"] is True
    verified = verify_backup(destination)
    assert verified["ok"] is True
    payload = destination / "payload"
    original_files = list((payload / "gallery" / "original").iterdir())
    assert len(original_files) == 1
    assert original_files[0].read_bytes() == upload_raw
    assert len(list((payload / "gallery" / "thumbnail").iterdir())) == 2
    assert not any(path.name == "mapped-reference.png" for path in payload.rglob("*"))
    restored_root = tmp_path / "restored-gallery"
    assert BackupManager(settings).restore_to_new_directory(destination, restored_root)["ok"]
    restored_settings = Settings(
        library_root=restored_root,
        database_path=restored_root / "database" / "prompt-library.sqlite",
        git_sources_root=restored_root / "sources" / "git",
    )
    restored = GalleryStore(restored_settings)
    saved = restored.require_asset(uploaded["asset_id"])
    assert saved["favorite"] is True
    assert saved["albums"] == ["雨夜"]
    assert saved["note"] == "keep this"
    assert saved["analysis"]["confirmed"] is True
    assert restored.resolve_asset_path(uploaded["asset_id"]).read_bytes() == upload_raw
    (source / "mapped-reference.png").unlink()
    assert restored.require_asset(mapped["asset_id"])["availability"] == "offline"
    assert restored.require_asset(mapped["asset_id"])["metadata"]["loras"] == []


def test_real_app_rejects_gallery_root_and_symlink_escape(client, settings, tmp_path):
    for forbidden in (settings.library_root, settings.library_root / "gallery"):
        rejected = client.post("/api/gallery/roots", json={"path": str(forbidden)})
        assert rejected.status_code == 422
    source = tmp_path / "bounded-source"
    source.mkdir()
    secret = tmp_path / "private.png"
    secret.write_bytes(_png())
    (source / "escaped.png").symlink_to(secret)
    _, job = _register_and_scan(client, source)
    assert job["result"]["imported"] == 0
    assert len(job["result"]["failed"]) == 1
    assert client.get("/api/gallery/assets").json()["total"] == 0
    assert secret.read_bytes() == _png()
