from __future__ import annotations

import csv

import numpy as np
import pytest
from PIL import Image

from prompt_hub.wd14 import (
    WD14Error,
    WD14Tagger,
    _load_labels,
    _prepare_image,
    _providers,
    _ranked,
)


@pytest.mark.parametrize(
    ("general_threshold", "character_threshold"),
    [(-0.01, 0.85), (1.01, 0.85), (0.35, -0.01), (0.35, 1.01)],
)
def test_wd14_rejects_thresholds_outside_probability_range(
    tmp_path,
    general_threshold: float,
    character_threshold: float,
) -> None:
    with pytest.raises(WD14Error, match="标签阈值必须在 0 到 1 之间"):
        WD14Tagger(
            model_root=tmp_path,
            general_threshold=general_threshold,
            character_threshold=character_threshold,
        )


def test_wd14_reports_missing_model_files(tmp_path) -> None:
    with pytest.raises(WD14Error, match="WD14 模型文件不完整"):
        WD14Tagger(model_root=tmp_path)


@pytest.mark.parametrize(
    "contents",
    [
        "tag_id,name,category,count\n",
        "tag_id,name,count\n1,solo,1\n",
        "tag_id,name,category,count\n1,solo,not-a-number,1\n",
    ],
)
def test_wd14_reports_empty_or_invalid_label_tables(tmp_path, contents: str) -> None:
    labels_path = tmp_path / "selected_tags.csv"
    labels_path.write_text(contents, encoding="utf-8")

    with pytest.raises(WD14Error, match="WD14 标签表"):
        _load_labels(labels_path)


def test_wd14_reports_unavailable_coreml_provider(monkeypatch) -> None:
    monkeypatch.setattr(
        "prompt_hub.wd14.ort.get_available_providers",
        lambda: ["CPUExecutionProvider"],
    )

    with pytest.raises(WD14Error, match="当前 ONNX Runtime 不支持 CoreML"):
        _providers("coreml")


def test_wd14_reports_unreadable_image(tmp_path) -> None:
    image_path = tmp_path / "broken.png"
    image_path.write_text("not an image", encoding="utf-8")

    with pytest.raises(WD14Error, match="无法读取待打标图片"):
        _prepare_image(image_path, 448)


def test_wd14_preparation_pads_white_and_converts_to_bgr(tmp_path) -> None:
    image_path = tmp_path / "sample.png"
    Image.new("RGBA", (2, 1), (10, 20, 30, 255)).save(image_path)

    prepared = _prepare_image(image_path, 2)

    assert prepared.shape == (1, 2, 2, 3)
    assert prepared.dtype == np.float32
    assert prepared[0, 0, 0].tolist() == [30.0, 20.0, 10.0]
    assert prepared[0, 1, 0].tolist() == [255.0, 255.0, 255.0]


def test_wd14_loads_and_ranks_categories(tmp_path) -> None:
    labels_path = tmp_path / "selected_tags.csv"
    with labels_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("tag_id", "name", "category", "count"))
        writer.writerows(((1, "general", 9, 1), (2, "solo", 0, 1), (3, "alice", 4, 1)))

    labels = _load_labels(labels_path)
    ranked = _ranked(
        np.array([0.8, 0.7, 0.9], dtype=np.float32),
        labels,
        category=0,
        threshold=0.35,
    )

    assert labels == [("general", 9), ("solo", 0), ("alice", 4)]
    assert ranked == [{"tag": "solo", "score": 0.7}]
    assert _providers("auto") == ["CPUExecutionProvider"]
