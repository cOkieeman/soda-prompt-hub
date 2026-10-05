from __future__ import annotations

import hashlib
import json
import os
from io import BytesIO
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from prompt_hub.background_jobs import (
    BackgroundJobRunner,
    BackgroundJobStore,
    JobCancelledError,
    JobContext,
)
from prompt_hub.creative import CreativeStore
from prompt_hub.gallery import GalleryError, GalleryStore
from prompt_hub.gallery_routes import create_gallery_router
from prompt_hub.model_connections import ModelConnectionStore


def _image(*, color="red", prompt=None, workflow=None) -> bytes:
    info = PngImagePlugin.PngInfo()
    if prompt is not None:
        info.add_text("prompt", json.dumps(prompt))
    if workflow is not None:
        info.add_text("workflow", json.dumps(workflow))
    output = BytesIO()
    Image.new("RGB", (64, 96), color).save(output, "PNG", pnginfo=info)
    return output.getvalue()


@pytest.fixture
def gallery(settings):
    store = GalleryStore(settings)
    store.initialize()
    store.initialize()
    return store


@pytest.fixture
def gallery_client(settings, gallery):
    creative = CreativeStore(settings.database_path)
    creative.initialize()
    jobs = BackgroundJobStore(settings.database_path)
    jobs.initialize()
    runner = BackgroundJobRunner(
        jobs,
        {
            "gallery_scan": lambda payload, context: gallery.scan_root(
                payload["root_id"], context=context
            )
        },
    )
    connections = ModelConnectionStore(settings)
    app = FastAPI()
    app.include_router(create_gallery_router(settings, gallery, creative, runner, connections))
    with TestClient(app) as client:
        yield client, creative, jobs


def test_mapping_is_incremental_and_deduplicated_without_copying(gallery, tmp_path, monkeypatch):
    source = tmp_path / "art"
    source.mkdir()
    raw = _image()
    (source / "one.png").write_bytes(raw)
    (source / "duplicate.png").write_bytes(raw)
    root = gallery.register_root({"path": str(source), "kind": "work"})
    assert gallery.register_root({"path": str(source)})["root_id"] == root["root_id"]
    report = gallery.scan_root(root["root_id"])
    assert (report["scanned"], report["imported"], report["duplicates"]) == (2, 1, 1)
    assert list(gallery.original_root.iterdir()) == []
    page = gallery.list_assets()
    assert page["total"] == 1
    asset = page["items"][0]
    assert asset["kind"] == "work"
    assert asset["availability"] == "online"
    assert gallery.resolve_asset_path(asset["asset_id"]).read_bytes() == raw
    assert gallery.resolve_asset_path(asset["asset_id"], "thumbnail").is_file()
    assert gallery.read_asset(asset["asset_id"])["safety"] == "unrated"

    def no_reinspection(*_args, **_kwargs):
        pytest.fail("unchanged mappings must not re-read or re-hash images")

    monkeypatch.setattr("prompt_hub.gallery._inspect", no_reinspection)
    assert gallery.scan_root(root["root_id"])["unchanged"] == 2
    assert next(gallery.iter_assets())["asset_id"] == asset["asset_id"]
    assert (source / "one.png").read_bytes() == raw


def test_rescan_upgrades_old_metadata_without_losing_personal_records(gallery, tmp_path):
    source = tmp_path / "legacy-summary"
    source.mkdir()
    raw = _image(
        prompt={"1": {"class_type": "UNETLoader", "inputs": {"unet_name": "base.safetensors"}}}
    )
    (source / "work.png").write_bytes(raw)
    root = gallery.register_root({"path": str(source), "kind": "work"})
    gallery.scan_root(root["root_id"])
    asset = gallery.list_assets()["items"][0]
    saved = gallery.update_asset(
        asset["asset_id"], {"title": "My saved title", "note": "Tested at 0.4", "favorite": True}
    )
    with gallery.connect() as connection:
        row = connection.execute(
            "SELECT image_json FROM gallery_assets WHERE asset_id = ?", (asset["asset_id"],)
        ).fetchone()
        image = json.loads(row["image_json"])
        image["metadata"]["generation_evidence"] = {"loras": []}
        image["project_snapshot"] = {"generation": {"seed": "123"}, "test_notes": "saved"}
        connection.execute(
            "UPDATE gallery_assets SET image_json = ? WHERE asset_id = ?",
            (json.dumps(image), asset["asset_id"]),
        )
        connection.commit()
    assert gallery.scan_root(root["root_id"])["unchanged"] == 1
    upgraded = gallery.require_asset(asset["asset_id"])
    assert upgraded["metadata"]["generation_evidence"]["models"][0]["name"] == "base.safetensors"
    assert upgraded["project_snapshot"] == image["project_snapshot"]
    assert {key: upgraded[key] for key in ("title", "note", "favorite", "updated_at")} == {
        key: saved[key] for key in ("title", "note", "favorite", "updated_at")
    }
    assert gallery.scan_root(root["root_id"])["unchanged"] == 1
    assert (source / "work.png").read_bytes() == raw
    assert list(gallery.original_root.iterdir()) == []


def test_cancelled_scan_resumes_committed_images(gallery, tmp_path):
    source = tmp_path / "resume"
    source.mkdir()
    (source / "a.png").write_bytes(_image())
    (source / "b.png").write_bytes(_image(color="blue"))
    root = gallery.register_root({"path": str(source)})

    class CancelAfterFirst:
        def raise_if_cancelled(self):
            if gallery.list_assets()["total"]:
                raise JobCancelledError

        def update(self, *_args):
            pass

    with pytest.raises(JobCancelledError):
        gallery.scan_root(root["root_id"], context=CancelAfterFirst())
    assert gallery.list_assets()["total"] == 1
    report = gallery.scan_root(root["root_id"])
    assert report["unchanged"] == 1
    assert report["imported"] == 1
    assert gallery.list_assets()["total"] == 2


def test_missing_and_changed_source_preserve_notes_and_flag_analysis(gallery, tmp_path):
    source = tmp_path / "changing"
    source.mkdir()
    path = source / "drawing.png"
    path.write_bytes(_image())
    root = gallery.register_root({"path": str(source)})
    gallery.scan_root(root["root_id"])
    first = gallery.list_assets()["items"][0]
    gallery.update_asset(first["asset_id"], {"note": "I like the gesture", "favorite": True})
    gallery.confirm_analysis(
        first["asset_id"], {"summary_zh": "伸手", "source_sha256": first["sha256"]}
    )
    path.write_bytes(_image(color="blue"))
    stale = gallery.require_asset(first["asset_id"])
    assert stale["availability"] == "offline"
    assert stale["analysis"]["stale"] is True
    with pytest.raises(GalleryError, match="离线"):
        gallery.confirm_analysis(first["asset_id"], {"summary_zh": "old"})
    assert gallery.scan_root(root["root_id"])["imported"] == 1
    assert gallery.list_assets()["total"] == 2
    assert gallery.require_asset(first["asset_id"])["note"] == "I like the gesture"
    newest = gallery.list_assets()["items"][0]
    path.unlink()
    gallery.scan_root(root["root_id"])
    assert gallery.require_asset(newest["asset_id"])["availability"] == "offline"
    assert gallery.require_asset(first["asset_id"])["favorite"] is True
    source.rmdir()
    with pytest.raises(GalleryError, match="离线"):
        gallery.scan_root(root["root_id"])
    assert gallery.list_assets()["total"] == 2
    assert gallery.list_roots()[0]["availability"] == "offline"


def test_symlink_escape_and_root_replacement_are_not_read(gallery, tmp_path):
    source = tmp_path / "mapped"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.png").write_bytes(_image())
    (source / "escape.png").symlink_to(outside / "secret.png")
    (source / "escape-directory").symlink_to(outside, target_is_directory=True)
    root = gallery.register_root({"path": str(source)})
    report = gallery.scan_root(root["root_id"])
    assert report["imported"] == 0
    assert len(report["failed"]) == 1
    (source / "escape.png").unlink()
    (source / "escape-directory").unlink()
    (source / "safe.png").write_bytes(_image(color="green"))
    gallery.scan_root(root["root_id"])
    asset = gallery.list_assets()["items"][0]
    (source / "safe.png").unlink()
    (source / "safe.png").symlink_to(outside / "secret.png")
    assert gallery.resolve_asset_path(asset["asset_id"]) is None
    (source / "safe.png").unlink()
    source.rmdir()
    source.symlink_to(outside, target_is_directory=True)
    assert gallery.resolve_asset_path(asset["asset_id"]) is None
    with pytest.raises(GalleryError, match="替换"):
        gallery.scan_root(root["root_id"])


@pytest.mark.parametrize("source", ["relative/art", "/", "home", "library"])
def test_unsafe_registration_is_rejected(gallery, settings, source):
    path = (
        str(Path.home())
        if source == "home"
        else str(settings.library_root)
        if source == "library"
        else source
    )
    with pytest.raises(GalleryError):
        gallery.register_root({"path": path})
    assert gallery.list_roots() == []


def test_upload_metadata_pagination_and_manual_fields(gallery):
    prompt = {
        "1": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "ink.safetensors",
                "strength_model": 0.6,
            },
        },
        "2": {"class_type": "KSampler", "inputs": {"seed": 14, "steps": 8}},
    }
    first = gallery.import_bytes(_image(prompt=prompt), filename="my-work.png", kind="work")
    duplicate = gallery.import_bytes(_image(prompt=prompt), filename="copy.png", kind="reference")
    assert duplicate["asset_id"] == first["asset_id"]
    assert duplicate["kind"] == "work"
    metadata = first["metadata"]
    assert metadata["seed"] == 14
    assert metadata["loras"][0]["strength_model"] == 0.6
    assert metadata["recognition_scope"] == "api_prompt_nodes"
    gallery.update_asset(
        first["asset_id"],
        {
            "title": "Rain 100%",
            "note": "framing",
            "author": "self",
            "tags": ["door", "door"],
            "albums": ["rain", "rain"],
            "favorite": True,
        },
    )
    gui = gallery.import_bytes(
        _image(color="blue", workflow={"nodes": [{"type": "LoraLoader"}]}),
        filename="reference.png",
        kind="reference",
    )
    assert gui["metadata"]["recognition_scope"] == "gui_workflow_preserved"
    assert gui["metadata"]["loras"] == []
    assert "不保证" in gui["metadata"]["recognition_note"]
    assert gallery.list_assets(q="100%")["total"] == 1
    assert gallery.list_assets(album="rai")["total"] == 0
    assert gallery.list_assets(album="rain", favorite=True)["total"] == 1
    assert gallery.list_assets(kind="reference")["total"] == 1
    assert gallery.list_albums() == ["rain"]
    assert gallery.list_assets(offset=1, limit=1)["items"][0]["asset_id"] == first["asset_id"]
    assert len(list(gallery.original_root.iterdir())) == 2
    with pytest.raises(GalleryError):
        gallery.import_bytes(b"not an image", filename="bad.png")
    with pytest.raises(GalleryError, match="分类"):
        gallery.import_bytes(_image(), filename="invalid.png", kind="invalid")
    with pytest.raises(GalleryError, match="列表"):
        gallery.update_asset(first["asset_id"], {"tags": "invalid"})
    assert gallery.resolve_asset_path(first["asset_id"], "invalid") is None


def test_routes_scan_reference_and_explicit_analysis_confirmation(
    gallery_client, gallery, tmp_path, monkeypatch
):
    client, creative, jobs = gallery_client
    source = tmp_path / "incoming"
    source.mkdir()
    (source / "image.png").write_bytes(_image())
    root_response = client.post(
        "/api/gallery/roots", json={"path": str(source), "kind": "reference"}
    )
    assert root_response.status_code == 201
    root_id = root_response.json()["root_id"]
    queued = client.post(f"/api/gallery/roots/{root_id}/scan")
    assert queued.status_code == 202
    assert jobs.get(queued.json()["job_id"])["payload"] == {"root_id": root_id}
    gallery.scan_root(root_id)
    asset = client.get("/api/gallery/assets").json()["items"][0]
    asset_id = asset["asset_id"]
    project = creative.create_project(
        {"title": "test", "slots": {"style": "ink"}, "generation": {"seed": 9}}
    )
    project_id = project["project_id"]
    attached = client.post(
        f"/api/gallery/assets/{asset_id}/reference/{project_id}", json={"purpose": "style"}
    ).json()
    assert attached["slots"]["style"] == "ink"
    reference = attached["references"][0]
    assert reference["gallery_asset_id"] == asset_id
    assert reference["purpose"] == "style"
    assert reference["source_id"] == "local-gallery"
    repeated = client.post(
        f"/api/gallery/assets/{asset_id}/reference/{project_id}", json={"purpose": "style"}
    ).json()
    assert repeated["revision"] == attached["revision"]
    updated = client.put(
        f"/api/gallery/assets/{asset_id}", json={"project_id": project_id, "note": "manual"}
    ).json()
    assert updated["project_snapshot"]["generation"]["seed"] == 9

    def analyze(**kwargs):
        assert kwargs["image_path"].read_bytes() == _image()
        assert "不要根据外观猜测" in kwargs["project"]["brief_zh"]
        return {"summary_zh": "门口的角色", "observed_slots": {"composition": "doorway"}}

    monkeypatch.setattr("prompt_hub.gallery_routes.analyze_result_image", analyze)
    preview = client.post(
        f"/api/gallery/assets/{asset_id}/analyze",
        json={"model": "vision", "purpose": "composition"},
    )
    assert preview.status_code == 200
    assert preview.json()["confirmed"] is False
    assert gallery.require_asset(asset_id)["analysis"] == {}
    confirmed = client.put(
        f"/api/gallery/assets/{asset_id}/analysis", json={"analysis": preview.json()}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["analysis"]["confirmed_at"]
    assert confirmed.json()["note"] == "manual"
    assert confirmed.json()["metadata"]["loras"] == []
    wrong = client.put(
        f"/api/gallery/assets/{asset_id}/analysis", json={"analysis": {"source_sha256": "wrong"}}
    )
    assert wrong.status_code == 409
    assert client.get(asset["original_url"]).content == _image()
    assert client.get(asset["thumbnail_url"]).headers["content-type"] == "image/webp"
    assert client.get("/api/gallery/assets/missing").status_code == 404
    assert client.post("/api/gallery/roots/missing/scan").status_code == 404
    assert client.post("/api/gallery/import?filename=bad.png", content=b"bad").status_code == 422
    assert (
        client.post(
            "/api/gallery/import?filename=blue.png&kind=work", content=_image(color="blue")
        ).status_code
        == 201
    )
    (source / "image.png").unlink()
    assert client.get(asset["original_url"]).status_code == 404
    assert (
        client.post(f"/api/gallery/assets/{asset_id}/analyze", json={"model": "vision"}).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/gallery/assets/{asset_id}/analysis", json={"analysis": preview.json()}
        ).status_code
        == 409
    )


def test_real_job_context_cancellation_is_resumable(settings, gallery, tmp_path):
    source = tmp_path / "cancelled"
    source.mkdir()
    (source / "image.png").write_bytes(_image())
    root = gallery.register_root({"path": str(source)})
    jobs = BackgroundJobStore(settings.database_path)
    jobs.initialize()
    runner = BackgroundJobRunner(
        jobs,
        {
            "gallery_scan": lambda payload, context: gallery.scan_root(
                payload["root_id"], context=context
            )
        },
    )
    job = runner.submit("gallery_scan", {"root_id": root["root_id"]})
    jobs.claim_next({"gallery_scan"})
    jobs.request_cancel(job["job_id"])
    context = JobContext(jobs, job["job_id"], Event())
    with pytest.raises(JobCancelledError):
        gallery.scan_root(root["root_id"], context=context)
    assert gallery.list_assets()["total"] == 0
    assert gallery.scan_root(root["root_id"])["imported"] == 1


@pytest.mark.parametrize("target", ["library", "gallery", "original", "thumbnail"])
def test_owned_storage_directory_symlinks_cannot_redirect_writes(
    gallery, settings, tmp_path, target
):
    outside = tmp_path / "unrelated"
    outside.mkdir()
    owned = {
        "library": settings.library_root,
        "gallery": gallery.root,
        "original": gallery.original_root,
        "thumbnail": gallery.thumbnail_root,
    }[target]
    saved = tmp_path / f"saved-{target}"
    owned.rename(saved)
    owned.symlink_to(outside, target_is_directory=True)
    with pytest.raises(GalleryError, match="派生目录"):
        gallery.import_bytes(_image(), filename="do-not-write-outside.png")
    assert list(outside.iterdir()) == []


def test_mapping_refuses_replaced_thumbnail_directory_without_touching_source(gallery, tmp_path):
    source = tmp_path / "safe-source"
    source.mkdir()
    path = source / "reference.png"
    original = _image()
    path.write_bytes(original)
    root = gallery.register_root({"path": str(source)})
    outside = tmp_path / "thumbnail-outside"
    outside.mkdir()
    gallery.thumbnail_root.rmdir()
    gallery.thumbnail_root.symlink_to(outside, target_is_directory=True)
    report = gallery.scan_root(root["root_id"])
    assert report["imported"] == 0
    assert len(report["failed"]) == 1
    assert path.read_bytes() == original
    assert list(outside.iterdir()) == []
    assert list(gallery.original_root.iterdir()) == []


def test_atomic_temporary_symlink_is_rejected_without_touching_target(
    gallery, tmp_path, monkeypatch
):
    outside = tmp_path / "unrelated.png"
    outside.write_bytes(b"preserve this file")
    raw = _image()
    token = uuid4()
    digest = hashlib.sha256(raw).hexdigest()
    temporary = gallery.original_root / f".{digest}.png.{token.hex}.tmp"
    temporary.symlink_to(outside)
    monkeypatch.setattr("prompt_hub.gallery.uuid4", lambda: token)
    with pytest.raises(GalleryError, match="派生文件"):
        gallery.import_bytes(raw, filename="upload.png")
    assert outside.read_bytes() == b"preserve this file"
    assert temporary.is_symlink()
    assert gallery.list_assets()["total"] == 0


@pytest.mark.skipif(os.open not in os.supports_dir_fd, reason="Directory handles require POSIX")
def test_atomic_replace_aborts_if_parent_swaps_after_temporary_write(
    gallery, tmp_path, monkeypatch
):
    outside = tmp_path / "outside-after-write"
    outside.mkdir()
    preserved = gallery.root / "preserved-original"
    original_fdopen = os.fdopen

    class SwapAfterWriting:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self.stream

        def __exit__(self, *_args):
            self.stream.close()
            gallery.original_root.rename(preserved)
            gallery.original_root.symlink_to(outside, target_is_directory=True)

    def swapping_fdopen(*args, **kwargs):
        return SwapAfterWriting(original_fdopen(*args, **kwargs))

    monkeypatch.setattr("prompt_hub.gallery.os.fdopen", swapping_fdopen)
    with pytest.raises(GalleryError, match="派生目录"):
        gallery.import_bytes(_image(), filename="upload.png")
    assert list(outside.iterdir()) == []
    assert list(preserved.iterdir()) == []
    assert gallery.list_assets()["total"] == 0


@pytest.mark.parametrize("target", ["gallery", "original", "thumbnail"])
def test_initialize_refuses_preexisting_owned_directory_symlink(
    gallery, settings, tmp_path, target
):
    outside = tmp_path / f"outside-{target}"
    outside.mkdir()
    owned = {
        "gallery": gallery.root,
        "original": gallery.original_root,
        "thumbnail": gallery.thumbnail_root,
    }[target]
    owned.rename(tmp_path / f"saved-{target}")
    owned.symlink_to(outside, target_is_directory=True)
    with pytest.raises(GalleryError, match="派生目录"):
        GalleryStore(settings).initialize()
    assert list(outside.iterdir()) == []


def test_atomic_upload_fallback_without_directory_handles(gallery, monkeypatch):
    monkeypatch.setattr("prompt_hub.gallery.os.supports_dir_fd", set())
    raw = _image()
    asset = gallery.import_bytes(raw, filename="portable.png")
    assert gallery.resolve_asset_path(asset["asset_id"]).read_bytes() == raw
    assert gallery.resolve_asset_path(asset["asset_id"], "thumbnail").is_file()
    assert not list(gallery.original_root.glob("*.tmp"))


def test_atomic_temporary_collision_does_not_delete_existing_file(gallery, monkeypatch):
    raw = _image()
    token = uuid4()
    digest = hashlib.sha256(raw).hexdigest()
    temporary = gallery.original_root / f".{digest}.png.{token.hex}.tmp"
    temporary.write_bytes(b"existing temporary file")
    monkeypatch.setattr("prompt_hub.gallery.uuid4", lambda: token)
    with pytest.raises(GalleryError):
        gallery.import_bytes(raw, filename="upload.png")
    assert temporary.read_bytes() == b"existing temporary file"
    assert gallery.list_assets()["total"] == 0


def _nonfinite_png(value):
    prompt = {
        "0": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "base.safetensors"}},
        "1": {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["0", 0],
                "clip": ["0", 1],
                "lora_name": "good.safetensors",
                "strength_model": 0.6,
                "strength_clip": 0.7,
            },
        },
        "2": {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["1", 0],
                "clip": ["1", 1],
                "lora_name": "unknown-weight.safetensors",
                "strength_model": value,
                "strength_clip": 0.4,
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": "one hand shields a flame",
                "clip": ["2", 1],
                "extra": {"nested": [value, {"bad": value, "good": 1.25}]},
            },
        },
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "bad anatomy", "clip": ["2", 1]}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024}},
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["2", 0],
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0],
                "seed": 42,
                "steps": 8,
                "cfg": value,
                "denoise": 0.75,
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["0", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0]}},
    }
    workflow = {"nodes": [], "extra": {"bad": [value, {"bad": value, "good": 0.9}]}}
    return _image(prompt=prompt, workflow=workflow)


def _assert_finite_gallery_metadata(asset):
    json.dumps(asset, allow_nan=False)
    metadata = asset["metadata"]
    assert metadata["cfg"] is None
    assert metadata["seed"] == 42
    assert metadata["prompt"]["3"]["inputs"]["extra"]["nested"] == [
        None,
        {"bad": None, "good": 1.25},
    ]
    assert metadata["workflow"]["extra"]["bad"] == [None, {"bad": None, "good": 0.9}]
    assert metadata["positive_prompts"] == ["one hand shields a flame"]
    assert metadata["negative_prompts"] == ["bad anatomy"]
    evidence = metadata["generation_evidence"]
    records = {item["name"]: item for item in evidence["loras"]}
    assert records["good.safetensors"]["strength_model"] == 0.6
    assert records["unknown-weight.safetensors"]["strength_model"] is None
    assert records["unknown-weight.safetensors"]["strength_clip"] == 0.4
    assert any("无效数值" in warning and "未知" in warning for warning in evidence["warnings"])


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_gallery_png_upload_normalizes_nonfinite_metadata_without_changing_image(
    gallery_client, gallery, value
):
    client, _creative, _jobs = gallery_client
    raw = _nonfinite_png(value)
    response = client.post("/api/gallery/import?filename=recorded.png&kind=work", content=raw)
    assert response.status_code == 201
    asset = response.json()
    _assert_finite_gallery_metadata(asset)
    assert gallery.resolve_asset_path(asset["asset_id"]).read_bytes() == raw
    assert asset["sha256"] == hashlib.sha256(raw).hexdigest()
    with gallery.connect() as connection:
        stored = connection.execute("SELECT image_json FROM gallery_assets").fetchone()[0]
        assert "null" in stored
        json.loads(
            stored, parse_constant=lambda constant: pytest.fail(f"Non-standard JSON {constant}")
        )
    client.put(f"/api/gallery/assets/{asset['asset_id']}", json={"note": "manual note"})
    duplicate = client.post("/api/gallery/import?filename=copy.png&kind=reference", content=raw)
    assert duplicate.status_code == 201
    assert duplicate.json()["asset_id"] == asset["asset_id"]
    assert duplicate.json()["note"] == "manual note"
    assert client.get("/api/gallery/assets").json()["total"] == 1
    assert client.get("/api/gallery/facets").status_code == 200
    assert len(list(gallery.original_root.iterdir())) == 1


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_gallery_mapped_png_normalizes_nonfinite_metadata_and_keeps_source(
    gallery, tmp_path, value
):
    source = tmp_path / "mapped"
    source.mkdir()
    raw = _nonfinite_png(value)
    path = source / "workflow.png"
    path.write_bytes(raw)
    root = gallery.register_root({"path": str(source), "kind": "work"})
    report = gallery.scan_root(root["root_id"])
    assert report["imported"] == 1
    assert report["failed"] == []
    asset_id = gallery.list_assets()["items"][0]["asset_id"]
    asset = gallery.require_asset(asset_id)
    _assert_finite_gallery_metadata(asset)
    assert path.read_bytes() == raw
    assert gallery.resolve_asset_path(asset["asset_id"]) == path
    assert list(gallery.original_root.iterdir()) == []
    assert gallery.scan_root(root["root_id"])["unchanged"] == 1


def test_gallery_upload_keeps_valid_records_when_node_is_changed_is_nan(gallery_client, gallery):
    client, _creative, _jobs = gallery_client
    with Image.open(BytesIO(_nonfinite_png(0.5))) as image:
        prompt = json.loads(image.info["prompt"])
        workflow = json.loads(image.info["workflow"])
    prompt["280"] = {"class_type": "CacheMarker", "inputs": {}, "is_changed": float("nan")}
    raw = _image(prompt=prompt, workflow=workflow)
    response = client.post("/api/gallery/import?filename=actual-cache-case.png", content=raw)
    assert response.status_code == 201
    asset = response.json()
    metadata = asset["metadata"]
    assert metadata["prompt"]["280"]["is_changed"] is None
    assert metadata["checkpoint"] == "base.safetensors"
    assert metadata["cfg"] == 0.5
    assert metadata["positive_prompts"] == ["one hand shields a flame"]
    assert metadata["negative_prompts"] == ["bad anatomy"]
    evidence = metadata["generation_evidence"]
    assert any(item["name"] == "base.safetensors" for item in evidence["models"])
    records = {item["name"]: item for item in evidence["loras"]}
    assert records["good.safetensors"]["strength_model"] == 0.6
    assert records["unknown-weight.safetensors"]["strength_model"] == 0.5
    assert any("无效数值" in warning for warning in evidence["warnings"])
    assert gallery.resolve_asset_path(asset["asset_id"]).read_bytes() == raw
    json.dumps(asset, allow_nan=False)


def _oversized_png_text():
    info = PngImagePlugin.PngInfo()
    info.add_text(
        "workflow", json.dumps({"notes": "x" * (PngImagePlugin.MAX_TEXT_CHUNK + 1)}), zip=True
    )
    output = BytesIO()
    Image.new("RGB", (32, 32), "navy").save(output, "PNG", pnginfo=info)
    return output.getvalue()


def test_gallery_upload_rejects_excessive_compressed_png_text_with_422(gallery_client, gallery):
    client, _creative, _jobs = gallery_client
    raw = _oversized_png_text()
    response = client.post("/api/gallery/import?filename=oversized.png", content=raw)
    assert response.status_code == 422
    assert "附加信息" in response.json()["detail"]
    assert gallery.list_assets()["total"] == 0
    assert list(gallery.original_root.iterdir()) == []
    assert list(gallery.thumbnail_root.iterdir()) == []


def test_gallery_mapping_reports_excessive_png_text_and_preserves_source(gallery, tmp_path):
    source = tmp_path / "oversized"
    source.mkdir()
    raw = _oversized_png_text()
    path = source / "oversized.png"
    path.write_bytes(raw)
    root = gallery.register_root({"path": str(source)})
    report = gallery.scan_root(root["root_id"])
    assert report["imported"] == 0
    assert len(report["failed"]) == 1
    assert "附加信息" in report["failed"][0]["error"]
    assert path.read_bytes() == raw
    assert gallery.list_assets()["total"] == 0


def test_gallery_deletion_removes_index_and_keeps_originals(gallery):
    raw = _image()
    asset = gallery.import_bytes(raw, filename="keep.png")
    gallery.update_asset(
        asset["asset_id"], {"note": "delete from Hub", "favorite": True, "albums": ["mine"]}
    )
    original = gallery.resolve_asset_path(asset["asset_id"])
    thumbnail = gallery.resolve_asset_path(asset["asset_id"], "thumbnail")
    deleted = gallery.delete_asset(asset["asset_id"])
    assert deleted == {
        "asset_id": asset["asset_id"],
        "deleted": True,
        "source_files_deleted": False,
    }
    assert gallery.get_asset(asset["asset_id"]) is None
    assert gallery.list_assets()["total"] == 0
    assert gallery.list_albums() == []
    assert list(gallery.iter_assets()) == []
    assert original.read_bytes() == raw
    assert thumbnail.is_file()
    with gallery.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM gallery_origins").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM gallery_assets").fetchone()[0] == 0
    with pytest.raises(KeyError):
        gallery.delete_asset(asset["asset_id"])


def test_deleted_mapped_picture_stays_excluded_on_rescan(gallery, tmp_path):
    source = tmp_path / "mapped-deletion"
    source.mkdir()
    raw = _image()
    (source / "reference.png").write_bytes(raw)
    root = gallery.register_root({"path": str(source)})
    gallery.scan_root(root["root_id"])
    asset = gallery.list_assets()["items"][0]
    gallery.delete_asset(asset["asset_id"])
    assert gallery.scan_root(root["root_id"])["excluded"] == 1
    assert gallery.list_assets()["total"] == 0
    assert (source / "reference.png").read_bytes() == raw
    assert list(gallery.original_root.iterdir()) == []
    added = gallery.import_bytes(raw, filename="manually-added.png")
    assert added["asset_id"] != asset["asset_id"]
    assert gallery.list_assets()["total"] == 1
    assert gallery.scan_root(root["root_id"])["duplicates"] == 1


def test_explicit_reimport_after_deletion_creates_fresh_entry(gallery):
    raw = _image()
    asset = gallery.import_bytes(raw, filename="before.png")
    gallery.update_asset(asset["asset_id"], {"note": "deleted note"})
    gallery.delete_asset(asset["asset_id"])
    returned = gallery.import_bytes(raw, filename="again.png")
    assert returned["asset_id"] != asset["asset_id"]
    assert returned["note"] == ""
    assert gallery.list_assets()["total"] == 1
    assert len(list(gallery.original_root.iterdir())) == 1


def test_gallery_delete_route_and_other_records_are_untouched(gallery_client):
    client, creative, _jobs = gallery_client
    asset = client.post("/api/gallery/import?filename=remove.png", content=_image()).json()
    another = client.post(
        "/api/gallery/import?filename=keep.png", content=_image(color="blue")
    ).json()
    project = creative.create_project({"title": "Project remains"})
    project_before = creative.get_project(project["project_id"])
    url = f"/api/gallery/assets/{asset['asset_id']}"
    removed = client.delete(url)
    assert removed.status_code == 200
    assert removed.json()["source_files_deleted"] is False
    assert client.get(url).status_code == 404
    assert client.get(url + "/media/original").status_code == 404
    assert client.get("/api/gallery/assets").json()["items"][0]["asset_id"] == another["asset_id"]
    assert creative.get_project(project["project_id"]) == project_before
    assert client.delete(url).status_code == 404
    assert client.delete("/api/gallery/assets/no-such-asset").status_code == 404


def test_scan_cannot_recreate_asset_deleted_during_inspection(gallery, tmp_path, monkeypatch):
    source = tmp_path / "race"
    source.mkdir()
    raw = _image()
    path = source / "image.png"
    path.write_bytes(raw)
    root = gallery.register_root({"path": str(source)})
    asset = gallery.import_bytes(raw, filename="same.png")
    original_save = gallery._save_image  # noqa: SLF001 - Simulate deletion inside a scan.

    def delete_before_save(*args, **kwargs):
        gallery.delete_asset(asset["asset_id"])
        return original_save(*args, **kwargs)

    monkeypatch.setattr(gallery, "_save_image", delete_before_save)
    report = gallery.scan_root(root["root_id"])
    assert report["excluded"] == 1
    assert report["imported"] == 0
    assert gallery.list_assets()["total"] == 0
    assert path.read_bytes() == raw


def test_new_content_at_deleted_path_can_be_scanned(gallery, tmp_path):
    source = tmp_path / "changed"
    source.mkdir()
    path = source / "image.png"
    path.write_bytes(_image())
    root = gallery.register_root({"path": str(source)})
    gallery.scan_root(root["root_id"])
    asset = gallery.list_assets()["items"][0]
    gallery.delete_asset(asset["asset_id"])
    changed = _image(color="blue")
    path.write_bytes(changed)
    assert gallery.scan_root(root["root_id"])["imported"] == 1
    assert gallery.list_assets()["items"][0]["sha256"] == hashlib.sha256(changed).hexdigest()
    assert path.read_bytes() == changed
