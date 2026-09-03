from __future__ import annotations

import hashlib
import json
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from prompt_hub.api import create_app
from prompt_hub.comfy_results import ComfyResultStore, inspect_comfy_image


def _comfy_png(*, seed: int = 12345) -> bytes:
    prompt = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "anima-test.safetensors"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 28,
                "cfg": 4.5,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
                "positive": ["4", 0],
                "negative": ["5", 0],
            },
        },
        "3": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": "ariya.safetensors",
                "strength_model": 0.8,
                "strength_clip": 0.8,
            },
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "ariya, 1girl, upper body"},
        },
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality"}},
    }
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", json.dumps(prompt))
    info.add_text("workflow", json.dumps({"nodes": [{"id": 1}]}))
    output = BytesIO()
    Image.new("RGB", (96, 128), (70, 90, seed % 255)).save(output, "PNG", pnginfo=info)
    return output.getvalue()


def test_comfy_png_metadata_and_store_deduplicate(settings) -> None:
    raw = _comfy_png()
    inspected = inspect_comfy_image(raw, filename="result.png")
    metadata = inspected["metadata"]
    assert metadata["metadata_present"] is True
    assert metadata["source"] == "comfyui"
    assert (metadata["seed"], metadata["steps"], metadata["cfg"]) == (12345, 28, 4.5)
    assert (metadata["sampler"], metadata["scheduler"]) == ("euler", "simple")
    assert metadata["checkpoint"] == "anima-test.safetensors"
    assert metadata["loras"][0]["name"] == "ariya.safetensors"
    assert metadata["positive_prompts"] == ["ariya, 1girl, upper body"]
    assert metadata["negative_prompts"] == ["blurry, low quality"]

    store = ComfyResultStore(settings.comfy_results_root)
    store.initialize()
    first = store.import_bytes(raw, filename="first.png")
    duplicate = store.import_bytes(raw, filename="same.png")
    second = store.import_bytes(_comfy_png(seed=54321), filename="second.png")
    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True
    assert second["result"]["result_id"] != first["result"]["result_id"]
    assert len(store.list_results()) == 2


def test_comfy_directory_is_read_only_and_plain_jpeg_is_explicit(settings, tmp_path) -> None:
    source = tmp_path / "comfy-output"
    source.mkdir()
    png = source / "with-metadata.png"
    jpg = source / "plain.jpg"
    png.write_bytes(_comfy_png())
    Image.new("RGB", (80, 64), "navy").save(jpg)
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source.iterdir()}
    store = ComfyResultStore(settings.comfy_results_root)
    store.initialize()
    report = store.import_directory(source)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in source.iterdir()}
    plain = next(item for item in report["results"] if item["filename"] == "plain.jpg")
    assert report["source_mode"] == "read-only"
    assert (report["scanned"], report["imported"], report["duplicates"]) == (2, 2, 0)
    assert before == after
    assert plain["metadata_present"] is False
    assert plain["metadata_source"] == "none"


def test_comfy_api_attach_candidate_failure_and_branch(settings) -> None:
    with TestClient(create_app(settings)) as client:
        project = client.post(
            "/api/creative/projects",
            json={"title": "回流测试", "slots": {"character": "ariya"}},
        ).json()
        imported = client.post(
            "/api/comfy-results/import",
            params={"filename": "ariya-0001.png"},
            content=_comfy_png(),
        ).json()
        result_id = imported["result"]["result_id"]
        attached = client.post(
            f"/api/comfy-results/{result_id}/attach/{project['project_id']}"
        ).json()
        repeated = client.post(
            f"/api/comfy-results/{result_id}/candidate/{project['project_id']}"
        ).json()
        assert attached["asset"]["comfy_metadata"]["seed"] == 12345
        assert len(repeated["project"]["generation"]["result_assets"]) == 1
        assert repeated["asset"]["dataset_selected"] is True
        assert repeated["result"]["disposition"] == "candidate"

        child = client.post(f"/api/comfy-results/{result_id}/branch/{project['project_id']}").json()
        assert child["lineage"]["created_from"] == "comfyui-result-import"
        assert child["lineage"]["comfy_metadata"]["checkpoint"] == "anima-test.safetensors"
        assert child["generation"].get("result_assets") is None
        assert client.get(imported["result"]["original_url"]).status_code == 200

        failed = client.post(
            "/api/comfy-results/import",
            params={"filename": "failed.png"},
            content=_comfy_png(seed=22222),
        ).json()["result"]
        updated = client.put(
            f"/api/comfy-results/{failed['result_id']}",
            json={"disposition": "failed_test", "note": "hands failed"},
        ).json()
        assert updated["disposition"] == "failed_test"
        assert all(
            asset.get("comfy_import_id") != failed["result_id"]
            for asset in repeated["project"]["generation"]["result_assets"]
        )
        assert client.get("/api/comfy-results/missing").status_code == 404
        assert (
            client.post(
                "/api/comfy-results/import-directory",
                json={"source_path": str(settings.library_root)},
            ).status_code
            == 422
        )
