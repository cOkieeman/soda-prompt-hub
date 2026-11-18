from __future__ import annotations

import json

import pytest

from prompt_hub.studio_caption_worker import (
    GBC_TAG_SEEDED_SUFFIX,
    build_gbc_config,
    write_gbc_source,
)
from prompt_hub.studio_captions import GBC_TAG_SEEDED_SUFFIX as CAPTION_GBC_TAG_SEEDED_SUFFIX


def test_pixai_tags_seed_a_bounded_gbc_nest_job(tmp_path) -> None:
    output = tmp_path / "worker"
    output.mkdir()
    image = {
        "item_id": "image-1",
        "path": str(tmp_path / "image.png"),
    }
    pixai_result = {"result": {"general": {"1girl": 0.91, "solo": 0.35, "low_confidence": 0.34}}}
    (output / "image-1.pixai.json").write_text(json.dumps(pixai_result), encoding="utf-8")
    (output / "image-1.gbc-root.json").write_text(
        json.dumps({"detail": "A girl standing alone."}), encoding="utf-8"
    )

    source = write_gbc_source([image], output, "pixai_gbc", 0.35)
    job = json.loads(source.read_text(encoding="utf-8").splitlines()[0])
    config = build_gbc_config(
        {"model": "vision-test", "base_url": "https://example.test/v1"},
        {"detector_model": "sam3-test", "embedder_model": "embed-test"},
        "cuda",
        source,
        "pixai_gbc",
    )

    assert job["tags"] == {"general": {"1girl": 0.91, "solo": 0.35}}
    assert job["captions"] == {"detail": "A girl standing alone."}
    assert job["controls"] == {"root": "tags"}
    assert config["machine"]["program"] == "gbc_nest"
    assert config["controls"]["root"] == "tags"
    assert config["controls"]["max_rounds"] == 2
    assert config["controls"]["max_depth"] == 2
    assert config["controls"]["max_features_per_entity"] == 2
    assert config["controls"]["tagging"] == "none"
    assert GBC_TAG_SEEDED_SUFFIX == ".gbc-tag-seeded.json"
    assert CAPTION_GBC_TAG_SEEDED_SUFFIX == GBC_TAG_SEEDED_SUFFIX


def test_pixai_gbc_rejects_images_without_seed_tags(tmp_path) -> None:
    output = tmp_path / "worker"
    output.mkdir()
    image = {"item_id": "image-1", "path": str(tmp_path / "image.png")}
    (output / "image-1.pixai.json").write_text(
        json.dumps({"result": {"general": {"low_confidence": 0.2}}}), encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="no Danbooru tags above threshold"):
        write_gbc_source([image], output, "pixai_gbc", 0.35)


def test_detector_suppression_uses_local_model_type(tmp_path) -> None:
    detector = tmp_path / "detector"
    detector.mkdir()
    config_file = detector / "config.json"
    options = {"detector_model": str(detector), "embedder_model": "embed-test"}
    vision = {"model": "vision-test", "base_url": "https://example.test/v1"}
    config_file.write_text('{"model_type": "owlv2"}', encoding="utf-8")
    owlv2 = build_gbc_config(vision, options, "cpu", tmp_path / "source.jsonl", "pixai_gbc")
    config_file.write_text('{"model_type": "sam3"}', encoding="utf-8")
    sam3 = build_gbc_config(vision, options, "cpu", tmp_path / "source.jsonl", "pixai_gbc")
    assert owlv2["controls"]["nms_iou"] == 0.2
    assert sam3["controls"]["nms_iou"] == 0.7


def test_sam3_litetext_retains_low_scoring_detection_proposals(tmp_path) -> None:
    detector = tmp_path / "sam3-litetext"
    detector.mkdir()
    (detector / "config.json").write_text('{"model_type": "sam3_lite_text"}', encoding="utf-8")
    config = build_gbc_config(
        {"model": "vision-test", "base_url": "https://example.test/v1"},
        {"detector_model": str(detector), "embedder_model": "embed-test"},
        "cpu",
        tmp_path / "source.jsonl",
        "pixai_gbc",
    )

    assert config["engines"]["detect"]["box_threshold"] == 0.005
    assert config["controls"]["box_score"] == 0.005
    assert config["controls"]["nms_iou"] == 0.7


def test_pixai_root_caption_is_generated_once_and_reused(tmp_path, monkeypatch) -> None:
    output = tmp_path / "worker"
    output.mkdir()
    image = {"item_id": "image-1", "path": str(tmp_path / "image.png")}
    (output / "image-1.pixai.json").write_text(
        json.dumps({"result": {"general": {"1girl": 0.91}}}), encoding="utf-8"
    )
    calls = []

    def describe(record, tags, vision):
        calls.append((record, tags, vision))
        return "A girl standing alone."

    monkeypatch.setattr("prompt_hub.studio_caption_worker.describe_root", describe)
    vision = {"model": "vision-test", "base_url": "https://example.test/v1"}
    source = write_gbc_source([image], output, "pixai_gbc", 0.35, vision)
    assert json.loads(source.read_text(encoding="utf-8"))["captions"] == {
        "detail": "A girl standing alone."
    }
    write_gbc_source([image], output, "pixai_gbc", 0.35, vision)
    assert len(calls) == 1
