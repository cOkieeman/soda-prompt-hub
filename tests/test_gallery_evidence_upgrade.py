from __future__ import annotations

import json
from io import BytesIO

import pytest
from PIL import Image, PngImagePlugin

from prompt_hub.gallery import GalleryStore
from prompt_hub.generation_evidence import EXTRACTOR_VERSION


def _recorded_png(*, connected: bool) -> bytes:
    prompt = {
        "base": {"class_type": "UNETLoader", "inputs": {"unet_name": "base.safetensors"}},
        "used": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["base", 0],
                "lora_name": "used.safetensors",
                "strength_model": 0.4,
            },
        },
        "unused": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["base", 0],
                "lora_name": "unused.safetensors",
                "strength_model": 1,
            },
        },
    }
    if connected:
        prompt.update(
            {
                "sampler": {"class_type": "KSampler", "inputs": {"model": ["used", 0]}},
                "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["sampler", 0]}},
                "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0]}},
            }
        )
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", json.dumps(prompt))
    if connected:
        info.add_text("parameters", 'scene\nSteps: 8, Lora hashes: "used.safetensors: 123456789A"')
    output = BytesIO()
    Image.new("RGB", (32, 48), "teal").save(output, "PNG", pnginfo=info)
    return output.getvalue()


def _write_stale_summary(store, asset_id, *, version=1):
    with store.connect() as connection:
        row = connection.execute(
            "SELECT image_json FROM gallery_assets WHERE asset_id = ?", (asset_id,)
        ).fetchone()
        image = json.loads(row["image_json"])
        image["metadata"]["generation_evidence"] = {
            "extractor_version": version,
            "status": "saved_api_prompt",
            "scope": "output_connected",
            "models": [],
            "loras": [{"name": "unused.safetensors", "strength_model": 1, "strength_clip": 0}],
            "prompts": [],
            "sampling": [],
            "warnings": ["部分生成记录字段含无效数值; 已标为未知并保留其余字段, 记录可能不完整。"],
        }
        image["project_snapshot"] = {
            "project_id": "kept",
            "generation": {"seed": "9007199254740993"},
        }
        connection.execute(
            "UPDATE gallery_assets SET image_json = ?, analysis_json = ? WHERE asset_id = ?",
            (
                json.dumps(image),
                json.dumps({"confirmed": True, "source_sha256": image["sha256"]}),
                asset_id,
            ),
        )
        connection.commit()
        return dict(
            connection.execute(
                "SELECT * FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
        )


def test_stale_lora_summary_refreshes_offline_without_changing_personal_records(
    settings, tmp_path, monkeypatch
):
    store = GalleryStore(settings)
    store.initialize()
    source = tmp_path / "mapped"
    source.mkdir()
    original = source / "recorded.png"
    original.write_bytes(_recorded_png(connected=True))
    root = store.register_root({"path": str(source), "kind": "reference"})
    store.scan_root(root["root_id"])
    asset_id = store.list_assets()["items"][0]["asset_id"]
    store.update_asset(
        asset_id,
        {
            "title": "Keep title",
            "note": "Keep notes",
            "favorite": True,
            "tags": ["kept"],
            "albums": ["Album"],
            "author": "Artist",
            "source_url": "https://example.com/art",
            "project_id": "kept",
        },
    )
    before = _write_stale_summary(store, asset_id)
    offline = source.with_name("offline")
    source.rename(offline)

    def do_not_read_original(*_args, **_kwargs):
        pytest.fail("Summary upgrades must use cached metadata")

    monkeypatch.setattr("prompt_hub.gallery._inspect", do_not_read_original)
    restarted = GalleryStore(settings)
    restarted.initialize()
    detail = restarted.require_asset(asset_id)
    evidence = detail["metadata"]["generation_evidence"]
    assert [item["name"] for item in evidence["loras"]] == ["used.safetensors"]
    assert evidence["extractor_version"] == EXTRACTOR_VERSION
    assert any("无效数值" in item for item in evidence["warnings"])
    assert detail["availability"] == "offline"
    assert restarted.list_facets()["loras"] == ["used.safetensors"]
    assert restarted.list_assets(lora="unused.safetensors")["total"] == 0
    with restarted.connect() as connection:
        after = dict(
            connection.execute(
                "SELECT * FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
        )
    assert {key: value for key, value in before.items() if key != "image_json"} == {
        key: value for key, value in after.items() if key != "image_json"
    }
    old_image, new_image = json.loads(before["image_json"]), json.loads(after["image_json"])
    old_image["metadata"].pop("generation_evidence")
    new_image["metadata"].pop("generation_evidence")
    assert old_image == new_image
    assert (offline / "recorded.png").read_bytes() == _recorded_png(connected=True)

    monkeypatch.setattr("prompt_hub.gallery.inspect_generation_evidence", do_not_read_original)
    assert restarted.require_asset(asset_id)["metadata"]["generation_evidence"] == evidence
    assert restarted.list_facets()["loras"] == ["used.safetensors"]
    assert restarted.list_assets()["total"] == 1


def test_stale_unconnected_loras_do_not_enter_default_filters(settings):
    store = GalleryStore(settings)
    store.initialize()
    asset_id = store.import_bytes(_recorded_png(connected=False), filename="unconnected.png")[
        "asset_id"
    ]
    _write_stale_summary(store, asset_id)
    assert store.list_assets(lora="unused.safetensors")["total"] == 0
    assert store.list_facets()["loras"] == []
    detail = store.require_asset(asset_id)
    assert detail["metadata"]["generation_evidence"]["loras"] == []
    assert detail["metadata"]["generation_evidence"]["extractor_version"] == EXTRACTOR_VERSION


def _multi_stage_png() -> bytes:
    graph = {
        "base": {"class_type": "UNETLoader", "inputs": {"unet_name": "krea2-base.safetensors"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "clip.safetensors"}},
        "used": {
            "class_type": "LoraLoader",
            "inputs": {
                "model": ["base", 0],
                "clip": ["clip", 0],
                "lora_name": "character.safetensors",
                "strength_model": 0.6,
                "strength_clip": 0.3,
            },
        },
        "positive": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["used", 1], "text": "final scene"},
        },
        "negative": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["used", 1], "text": ""}},
        "main": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["used", 0],
                "positive": ["positive", 0],
                "negative": ["negative", 0],
            },
        },
        "other-base": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "detail-base.safetensors"},
        },
        "other-lora": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["other-base", 0],
                "lora_name": "postprocess.safetensors",
                "strength_model": 0.5,
            },
        },
        "post": {
            "class_type": "KSampler",
            "inputs": {"model": ["other-lora", 0], "latent_image": ["main", 0]},
        },
        "decode": {"class_type": "VAEDecode", "inputs": {"samples": ["post", 0]}},
        "save": {"class_type": "SaveImage", "inputs": {"images": ["decode", 0]}},
    }
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", json.dumps(graph))
    info.add_text(
        "parameters",
        "saved final scene\nNegative prompt: \nSteps: 20, Model: krea2-base.safetensors, "
        'Lora hashes: "character.safetensors: 123456789A"',
    )
    output = BytesIO()
    Image.new("RGB", (32, 48), "teal").save(output, "PNG", pnginfo=info)
    return output.getvalue()


def test_final_stage_filters_and_offline_v2_cache_upgrade(settings, monkeypatch):
    store = GalleryStore(settings)
    store.initialize()
    detail = store.import_bytes(_multi_stage_png(), filename="multi-stage.png")
    asset_id = detail["asset_id"]
    with store.connect() as connection:
        before = dict(
            connection.execute(
                "SELECT * FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
        )
        image = json.loads(before["image_json"])
        image["metadata"]["generation_evidence"]["extractor_version"] = 2
        image["metadata"]["generation_evidence"].pop("final_generation", None)
        connection.execute(
            "UPDATE gallery_assets SET image_json = ? WHERE asset_id = ?",
            (json.dumps(image), asset_id),
        )
        connection.commit()
    monkeypatch.setattr(
        "prompt_hub.gallery._inspect", lambda *_args, **_kwargs: pytest.fail("Must use cache")
    )
    upgraded = store.require_asset(asset_id)
    final = upgraded["metadata"]["generation_evidence"]["final_generation"]
    assert final["positive"]["text"] == "final scene"
    assert final["negative"]["text"] == ""
    assert final["saved_export_prompts"]["positive"]["text"] == "saved final scene"
    assert [item["name"] for item in final["loras"]] == ["character.safetensors"]
    assert store.list_facets()["loras"] == ["character.safetensors"]
    assert store.list_assets(lora="postprocess.safetensors")["total"] == 0
    assert store.list_assets(lora="character.safetensors")["total"] == 1
    assert store.list_assets(model="detail-base.safetensors")["total"] == 0
    assert store.list_facets()["models"] == ["krea2-base.safetensors"]
    with store.connect() as connection:
        after = dict(
            connection.execute(
                "SELECT * FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
        )
    assert {key: value for key, value in before.items() if key != "image_json"} == {
        key: value for key, value in after.items() if key != "image_json"
    }
    original = json.loads(before["image_json"])
    refreshed = json.loads(after["image_json"])
    original["metadata"].pop("generation_evidence")
    refreshed["metadata"].pop("generation_evidence")
    assert original == refreshed


def test_v3_cached_saved_resource_list_refreshes_offline_and_filters_only_recorded_loras(
    settings, tmp_path, monkeypatch
):
    records = [
        {
            "kind": "lora",
            "status": "resolved",
            "name": f"recorded-{index}",
            "hash": f"123456789{index}",
            "weight": 0.2,
        }
        for index in range(4)
    ]
    with Image.open(BytesIO(_recorded_png(connected=True))) as image:
        prompt = image.info["prompt"]
    info = PngImagePlugin.PngInfo()
    info.add_text("prompt", prompt)
    info.add_text("resources_json", json.dumps(records))
    output = BytesIO()
    Image.new("RGB", (32, 48), "teal").save(output, "PNG", pnginfo=info)
    raw = output.getvalue()
    source = tmp_path / "mapped-v3"
    source.mkdir()
    (source / "recorded.png").write_bytes(raw)
    store = GalleryStore(settings)
    store.initialize()
    root = store.register_root({"path": str(source), "kind": "reference"})
    store.scan_root(root["root_id"])
    asset_id = store.list_assets()["items"][0]["asset_id"]
    store.update_asset(asset_id, {"note": "keep", "favorite": True, "tags": ["keep"]})
    before = _write_stale_summary(store, asset_id, version=3)
    offline = source.with_name("offline-v3")
    source.rename(offline)
    monkeypatch.setattr(
        "prompt_hub.gallery._inspect",
        lambda *_args, **_kwargs: pytest.fail("Must use cached metadata"),
    )
    restarted = GalleryStore(settings)
    restarted.initialize()
    detail = restarted.require_asset(asset_id)
    final = detail["metadata"]["generation_evidence"]["final_generation"]
    expected = [row["name"] for row in records]
    assert [row["name"] for row in final["loras"]] == expected
    assert final["lora_source"]["status"] == "recorded"
    assert restarted.list_facets()["loras"] == expected
    assert restarted.list_assets(lora="used.safetensors")["total"] == 0
    assert restarted.list_assets(lora="recorded-0")["total"] == 1
    assert detail["availability"] == "offline"
    with restarted.connect() as connection:
        after = dict(
            connection.execute(
                "SELECT * FROM gallery_assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
        )
    assert {key: value for key, value in before.items() if key != "image_json"} == {
        key: value for key, value in after.items() if key != "image_json"
    }
    old_image, new_image = json.loads(before["image_json"]), json.loads(after["image_json"])
    old_image["metadata"].pop("generation_evidence")
    new_image["metadata"].pop("generation_evidence")
    assert old_image == new_image
    assert (offline / "recorded.png").read_bytes() == raw
