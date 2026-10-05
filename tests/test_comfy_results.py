from __future__ import annotations

import hashlib
import json
import math
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin

from prompt_hub.api import create_app
from prompt_hub.comfy_results import (
    ComfyResultStore,
    inspect_comfy_image,
    parse_generation_metadata,
)


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


def test_metadata_numeric_overflow_is_unknown_and_integer_seed_stays_exact() -> None:
    raw = '{"1":{"class_type":"KSampler","inputs":{"seed":9007199254740993,"cfg":1e999,"steps":8}}}'
    metadata = parse_generation_metadata({"prompt": raw}, width=96, height=128)
    assert metadata["seed"] == 9007199254740993
    assert isinstance(metadata["seed"], int)
    assert metadata["cfg"] is None
    assert metadata["prompt"]["1"]["inputs"]["cfg"] is None
    assert any("无效数值" in item for item in metadata["generation_evidence"]["warnings"])
    json.dumps(metadata, allow_nan=False)


def test_metadata_dict_normalization_does_not_mutate_input() -> None:
    prompt = {"280": {"is_changed": float("nan"), "inputs": {"values": [float("inf"), 0.6]}}}
    metadata = parse_generation_metadata({"prompt": prompt}, width=96, height=128)
    assert metadata["prompt"]["280"] == {"is_changed": None, "inputs": {"values": [None, 0.6]}}
    assert math.isnan(prompt["280"]["is_changed"])
    assert math.isinf(prompt["280"]["inputs"]["values"][0])
    json.dumps(metadata, allow_nan=False)


def test_saved_resource_metadata_survives_image_import_without_workflow_candidates() -> None:
    records = [
        {
            "kind": "lora",
            "status": "resolved",
            "name": "light_c1-st2000",
            "hash": "B24C8D432F",
            "weight": 0.3,
        },
        {
            "kind": "lora",
            "status": "resolved",
            "name": "Ps_impasto_style_v1-000024",
            "hash": "E22D6DA913",
            "weight": 0.05,
        },
        {
            "kind": "lora",
            "status": "resolved",
            "name": "harustyle_v1.6",
            "hash": "CC13749B1B",
            "weight": 0.15,
        },
        {
            "kind": "lora",
            "status": "resolved",
            "name": "kieed_v1_epoch20",
            "hash": "533DE01417",
            "weight": 0.5,
        },
    ]
    info = PngImagePlugin.PngInfo()
    info.add_text("resources_json", json.dumps(records))
    info.add_text("comment", "not a resource record")
    output = BytesIO()
    Image.new("RGB", (32, 48), "teal").save(output, "PNG", pnginfo=info)
    metadata = inspect_comfy_image(output.getvalue(), filename="recorded-resources.png")["metadata"]
    assert metadata["metadata_present"] is True
    assert metadata["saved_resource_metadata"] == {"resources_json": records}
    final = metadata["generation_evidence"]["final_generation"]
    assert [row["name"] for row in final["loras"]] == [row["name"] for row in records]
    assert final["lora_source"]["status"] == "recorded"
    json.dumps(metadata, allow_nan=False)


def test_saved_resource_fields_normalize_numbers_without_mutating_input() -> None:
    records = [
        {
            "kind": "lora",
            "status": "resolved",
            "name": "known",
            "hash": "AABBCCDDEE",
            "weight": float("nan"),
        }
    ]
    raw_info = {
        "resources_json": records,
        "lora_hashes": "",
        "additional_hashes": "known:AABBCCDDEE",
    }
    metadata = parse_generation_metadata(raw_info, width=32, height=48)
    assert metadata["saved_resource_metadata"]["resources_json"][0]["weight"] is None
    assert metadata["saved_resource_metadata"]["lora_hashes"] == ""
    assert metadata["saved_resource_metadata"]["additional_hashes"] == "known:AABBCCDDEE"
    assert math.isnan(records[0]["weight"])
    assert any("无效数值" in row for row in metadata["generation_evidence"]["warnings"])
    json.dumps(metadata, allow_nan=False)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("Lora hashes", "first: AABBCCDDEE, second: 123456789A"),
        ("lora_hashes", 'Lora hashes: "first: AABBCCDDEE, second: 123456789A"'),
    ],
)
def test_named_png_lora_hash_fields_reach_recorded_evidence(key, value) -> None:
    metadata = parse_generation_metadata({key: value}, width=32, height=48)
    final = metadata["generation_evidence"]["final_generation"]
    assert [row["name"] for row in final["loras"]] == ["first", "second"]
    assert final["lora_source"]["status"] == "recorded"
    assert all(row["strength_model"] is None for row in final["loras"])
    assert metadata["saved_resource_metadata"] == {key: value}


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


def test_comfy_impact_wildcard_uses_populated_prompt() -> None:
    prompt = {
        "1": {
            "class_type": "ImpactWildcardEncode",
            "inputs": {
                "wildcard_text": "a __character__ in a library",
                "populated_text": "an adult silver-haired investigator in a library",
            },
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {"positive": ["1", 0], "seed": 7, "steps": 4},
        },
    }
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", json.dumps(prompt))
    output = BytesIO()
    Image.new("RGB", (64, 64), "black").save(output, "PNG", pnginfo=info)

    metadata = inspect_comfy_image(output.getvalue(), filename="impact-wildcard.png")["metadata"]

    expected = "an adult silver-haired investigator in a library"
    assert metadata["positive_prompts"] == [expected]
    assert metadata["text_prompts"] == [expected]


def test_comfy_parameters_preserve_multiline_positive_prompt() -> None:
    positive = (
        "Anima:\n\n"
        "——————————————————————————————————\n"
        "Tag:\n\n"
        "masterpiece, best quality, 1girl, silver hair, rainy railway platform"
    )
    parameters = (
        f"{positive}\n"
        "Negative prompt: lowres, blurry, bad anatomy\n"
        "Steps: 4, CFG scale: 1, Seed: 26090901, Size: 512x768, Model: anima-base-v1.0"
    )
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", parameters)
    output = BytesIO()
    Image.new("RGB", (64, 96), "navy").save(output, "PNG", pnginfo=info)

    metadata = inspect_comfy_image(output.getvalue(), filename="multiline-parameters.png")[
        "metadata"
    ]

    assert metadata["positive_prompts"] == [positive]
    assert metadata["text_prompts"] == [positive]
    assert metadata["negative_prompts"] == ["lowres, blurry, bad anatomy"]


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
    assert plain["source_kind"] == "directory_scan"
    assert plain["source_root"] == str(source.resolve())
    assert plain["import_batch_id"]
    assert plain["origins"][0]["source_path"] == "plain.jpg"


def test_comfy_default_directory_and_recoverable_removal(settings, tmp_path) -> None:
    source = tmp_path / "dedicated-output"
    source.mkdir()
    original = source / "keep-source.png"
    original.write_bytes(_comfy_png())
    store = ComfyResultStore(settings.comfy_results_root)
    store.initialize()

    saved = store.update_settings({"default_directory": str(source)})
    assert saved["default_directory"] == str(source.resolve())
    assert ComfyResultStore(settings.comfy_results_root).get_settings() == saved

    report = store.import_directory(source)
    result = report["results"][0]
    removed = store.remove(result["result_id"])
    assert removed["recoverable"] is True
    assert original.is_file()
    assert store.get(result["result_id"]) is None
    assert (settings.comfy_results_root / "trash" / result["result_id"] / "record.json").is_file()


def test_comfy_refuses_to_remove_associated_result(settings) -> None:
    store = ComfyResultStore(settings.comfy_results_root)
    store.initialize()
    result = store.import_bytes(_comfy_png(), filename="linked.png")["result"]
    store.update(result["result_id"], {"association": {"kind": "project", "id": "p1"}})
    with pytest.raises(Exception, match="关联"):
        store.remove(result["result_id"])


def test_comfy_settings_and_remove_routes_keep_source_file(settings, tmp_path) -> None:
    source = tmp_path / "output"
    source.mkdir()
    image = source / "route.png"
    image.write_bytes(_comfy_png())
    with TestClient(create_app(settings)) as client:
        submitted = client.post(
            "/api/comfy-results/import-directory",
            json={"source_path": str(source), "remember": True},
        )
        assert submitted.status_code == 200
        result = submitted.json()["results"][0]
        saved = client.put(
            "/api/comfy-results/settings",
            json={"default_directory": str(source)},
        )
        assert saved.status_code == 200
        assert client.get("/api/comfy-results/settings").json()["default_directory"] == str(
            source.resolve()
        )
        removed = client.delete(f"/api/comfy-results/{result['result_id']}")
        assert removed.status_code == 200
        assert removed.json()["source_files_untouched"] is True
        assert image.is_file()


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
