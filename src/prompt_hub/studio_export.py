from __future__ import annotations

import hashlib
import json
from importlib import import_module
from typing import TYPE_CHECKING, Any

from PIL import Image

from prompt_hub.studio_store import StudioError, StudioStore, write_json

if TYPE_CHECKING:
    from pathlib import Path

CAPTION_CONFIG = {
    "template": "gbc",
    "meta": {"style": {"field": "style_trigger", "drop": 0.0}},
    "tags": {"sources": [{"from": "meta:general", "weight": 1.0}], "drop": 0.0, "shuffle": False},
    "nl": {"short": 0.2},
    "graph": {"keep": 1.0, "tag_drop": 0.0},
    "formats": [
        {"weight": 3, "sections": ["style", "tags", "nl"]},
        {"weight": 2, "sections": ["style", "nl"]},
        {"weight": 3, "sections": ["style", "graph"]},
    ],
    "list_sep": ", ",
    "section_sep": ",\n",
    "text_sep": "\n",
    "underscores": True,
    "fit": {"margin": 0.75, "fallback": ["style", "nl"]},
}


def description(text: str, label: str, kind: str) -> dict[str, Any]:
    return {
        "text": text.strip(),
        "label": label,
        "full_label": f"{label}-{kind}",
        "statistics": None,
        "clip_scores": {"scores": None, "truncation": False},
        "toxicity_scores": None,
    }


def caption_graph(caption: dict[str, Any], filename: str, size: tuple[int, int]) -> dict[str, Any]:
    root = {
        "vertex_id": "",
        "label": "image",
        "bbox": {"left": 0.0, "top": 0.0, "right": 1.0, "bottom": 1.0, "confidence": None},
        "descs": [
            description(caption["long"], "detail", "image"),
            description(caption.get("short", caption["long"]), "short", "image"),
        ],
        "in_edges": [],
        "out_edges": [],
        "sub_masks": [],
        "super_masks": [],
        "tags": {str(tag).replace(",", " and"): 1.0 for tag in caption.get("tags", [])},
    }
    vertices = [root]
    for index, region in enumerate(caption.get("regions", []), 1):
        identifier = f"region_{index}"
        x0, y0, x1, y1 = region["bbox"]
        edge = {"source": "", "target": identifier, "text": str(region.get("name", identifier))}
        root["out_edges"].append(edge)
        root["sub_masks"].append(identifier)
        vertices.append(
            {
                "vertex_id": identifier,
                "label": "entity",
                "bbox": {"left": x0, "top": y0, "right": x1, "bottom": y1, "confidence": None},
                "descs": [
                    description(
                        str(region.get("caption", region.get("name", ""))), "detail", "entity"
                    )
                ],
                "in_edges": [edge],
                "out_edges": [],
                "sub_masks": [],
                "super_masks": [""],
            }
        )
    return {
        "vertices": vertices,
        "img_url": None,
        "img_path": filename,
        "original_caption": None,
        "detail_caption": caption["long"],
        "short_caption": caption.get("short", caption["long"]),
        "img_size": list(size),
        "mask_inside_threshold": 0.85,
    }


def native_moss_export(
    store: StudioStore, project: dict[str, Any], images: list[dict[str, Any]], root: Path
) -> None:
    try:
        graph_module = import_module("kohakugbc_data")
        dataset_module = import_module("kohakugbc_data.dataset")
    except ImportError as error:
        msg = "原生 MOSS 匯出需要 kohakugbc-data 套件，請安裝後重試"
        raise StudioError(msg) from error
    dataset_root = root / "gbc_dataset"
    expected: list[tuple[str, dict[str, Any]]] = []
    with dataset_module.DatasetWriter(
        dataset_root,
        header={"trainer": "KohakuMossTrainer", "project": project["title"]},
        per_shard=256,
    ) as writer:
        for image in images:
            path = store.image_path(project["project_id"], image["item_id"])
            raw = path.read_bytes()
            with Image.open(path) as opened:
                width, height = opened.size
                codec = str(opened.format).lower()
            graph_data = image["caption"].get("graph") or caption_graph(
                image["caption"], path.name, (width, height)
            )
            graph_data = {
                **graph_data,
                "img_path": path.name,
                "img_size": [width, height],
                "detail_caption": image["caption"]["long"],
            }
            graph = graph_module.GbcGraph.from_json(json.dumps(graph_data, ensure_ascii=False))
            meta = {
                "style_trigger": project["studio"]["trigger"],
                "general": image["caption"].get("tags", []),
                "caption": image["caption"],
                "image_sha256": hashlib.sha256(raw).hexdigest(),
            }
            writer.add(image["item_id"], raw, width, height, codec, graph, meta)
            expected.append((image["item_id"], meta))
    dataset = dataset_module.GbcDataset(dataset_root)
    if len(dataset) != len(images):
        msg = "原生 MOSS 資料集回讀數量不一致"
        raise StudioError(msg)
    for identifier, meta in expected:
        restored = dataset[identifier]
        if (
            hashlib.sha256(restored.image).hexdigest() != meta["image_sha256"]
            or restored.graph.prompt_dag().to_dict()["vertices"]["image"]["text"]
            != meta["caption"]["long"]
            or restored.meta["style_trigger"] != meta["style_trigger"]
        ):
            msg = "原生 MOSS 資料集回讀驗證失敗"
            raise StudioError(msg)
    config = "from pathlib import Path\nROOT = Path(__file__).resolve().parent\nCAPTION = " + repr(
        CAPTION_CONFIG
    )
    config += '\nDATASETS = [{"source":"gbc","path":str(ROOT / "gbc_dataset"),"caption":CAPTION}]\n'
    (root / "kohakumoss_data.py").write_text(config, encoding="utf-8")
    write_json(
        root / "verification.json",
        {
            "native_dataset_roundtrip": True,
            "image_hash_roundtrip": True,
            "caption_roundtrip": True,
            "image_count": len(images),
        },
    )
