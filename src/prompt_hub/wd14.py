from __future__ import annotations

import csv
from pathlib import Path
from time import perf_counter
from typing import Literal, TypedDict

import numpy as np
import numpy.typing as npt
import onnxruntime as ort
from PIL import Image, UnidentifiedImageError

ProviderMode = Literal["auto", "coreml", "cpu"]


class WD14Error(ValueError):
    pass


class ScoredTag(TypedDict):
    tag: str
    score: float


def tag_image(
    image_path: Path | str,
    *,
    model_root: Path | str,
    general_threshold: float = 0.35,
    character_threshold: float = 0.85,
    limit: int = 80,
    provider: ProviderMode = "auto",
) -> dict[str, object]:
    if not 0 <= general_threshold <= 1 or not 0 <= character_threshold <= 1:
        raise WD14Error("标签阈值必须在 0 到 1 之间")
    if limit < 1:
        raise WD14Error("标签数量上限必须大于 0")
    image = Path(image_path).expanduser()
    root = Path(model_root).expanduser()
    model_path = root / "model.onnx"
    labels_path = root / "selected_tags.csv"
    if not image.is_file():
        raise WD14Error(f"图片不存在: {image}")
    if not model_path.is_file() or not labels_path.is_file():
        raise WD14Error(f"WD14 模型文件不完整: {root}")

    labels = _load_labels(labels_path)
    providers = _providers(provider)
    started = perf_counter()
    session = ort.InferenceSession(model_path, providers=providers)
    input_meta = session.get_inputs()[0]
    output_meta = session.get_outputs()[0]
    target_size = int(input_meta.shape[1])
    image_input = _prepare_image(image, target_size)
    raw_output = session.run([output_meta.name], {input_meta.name: image_input})[0]
    if not isinstance(raw_output, np.ndarray):
        raise WD14Error("WD14 模型返回了不支持的稀疏输出")
    probabilities = np.asarray(raw_output[0], dtype=np.float32)
    if len(probabilities) != len(labels):
        raise WD14Error("模型输出数量与标签表不匹配")

    ratings = _ranked(probabilities, labels, category=9, threshold=0)[:1]
    general = _ranked(
        probabilities,
        labels,
        category=0,
        threshold=general_threshold,
    )[:limit]
    characters = _ranked(
        probabilities,
        labels,
        category=4,
        threshold=character_threshold,
    )[:limit]
    return {
        "model": "SmilingWolf/wd-swinv2-tagger-v3",
        "provider": session.get_providers()[0],
        "image": str(image.resolve()),
        "input_size": target_size,
        "general_threshold": general_threshold,
        "character_threshold": character_threshold,
        "rating": ratings[0] if ratings else None,
        "general": general,
        "characters": characters,
        "tag_string": ", ".join(str(item["tag"]) for item in general),
        "elapsed_seconds": round(perf_counter() - started, 3),
    }


def _load_labels(path: Path) -> list[tuple[str, int]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = csv.DictReader(stream)
        try:
            labels = [(str(row["name"]), int(row["category"])) for row in rows]
        except (KeyError, TypeError, ValueError) as error:
            raise WD14Error("无法读取 WD14 标签表") from error
    if not labels:
        raise WD14Error("WD14 标签表为空")
    return labels


def _providers(mode: ProviderMode) -> list[str]:
    available = set(ort.get_available_providers())
    if mode == "coreml":
        if "CoreMLExecutionProvider" not in available:
            raise WD14Error("当前 ONNX Runtime 不支持 CoreML")
        return ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    if mode == "cpu":
        return ["CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def _prepare_image(path: Path, target_size: int) -> npt.NDArray[np.float32]:
    try:
        with Image.open(path) as opened:
            image = opened.convert("RGBA")
    except (OSError, UnidentifiedImageError) as error:
        raise WD14Error("无法读取待打标图片") from error
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
    canvas.alpha_composite(image)
    rgb = canvas.convert("RGB")
    max_dimension = max(rgb.size)
    padded = Image.new("RGB", (max_dimension, max_dimension), (255, 255, 255))
    padded.paste(
        rgb,
        ((max_dimension - rgb.width) // 2, (max_dimension - rgb.height) // 2),
    )
    if max_dimension != target_size:
        padded = padded.resize((target_size, target_size), Image.Resampling.BICUBIC)
    array = np.asarray(padded, dtype=np.float32)[:, :, ::-1]
    return np.expand_dims(array, axis=0)


def _ranked(
    probabilities: npt.NDArray[np.float32],
    labels: list[tuple[str, int]],
    *,
    category: int,
    threshold: float,
) -> list[ScoredTag]:
    ranked: list[ScoredTag] = []
    for index in np.argsort(probabilities)[::-1].tolist():
        name, label_category = labels[index]
        probability = float(probabilities[index])
        if label_category == category and probability > threshold:
            ranked.append({"tag": name, "score": round(probability, 6)})
    return ranked
