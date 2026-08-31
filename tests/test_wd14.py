from __future__ import annotations

import csv

import numpy as np
from PIL import Image

from prompt_hub.wd14 import _load_labels, _prepare_image, _providers, _ranked


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
