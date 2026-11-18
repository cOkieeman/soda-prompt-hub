"""Run optional PixAI/GBC dependencies in a separately configured Python environment."""

from __future__ import annotations

import base64
import json
import os
import sys
from importlib import import_module
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

GBC_TAG_SEEDED_SUFFIX = ".gbc-tag-seeded.json"
PIXAI_TAG_THRESHOLD = 0.35


def pixai_root_tags(output: Path, record: dict[str, Any], threshold: float) -> dict[str, float]:
    path = output / (record["item_id"] + ".pixai.json")
    result = json.loads(path.read_text(encoding="utf-8")).get("result", {})
    scores = result.get("general", {}) if isinstance(result, dict) else {}
    if not isinstance(scores, dict):
        return {}
    tags = {}
    for name, score in scores.items():
        try:
            confidence = float(score)
        except (TypeError, ValueError):
            continue
        tag = str(name).strip()
        if tag and confidence >= threshold:
            tags[tag] = confidence
    return tags


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def describe_root(record: dict[str, Any], tags: dict[str, float], vision: dict[str, Any]) -> str:
    from PIL import Image, ImageOps  # noqa: PLC0415 - optional worker dependency

    with Image.open(record["path"]) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        encoded = BytesIO()
        image.save(encoded, "JPEG", quality=88, optimize=True)
    image_url = "data:image/jpeg;base64," + base64.b64encode(encoded.getvalue()).decode("ascii")
    payload = {
        "model": vision["model"],
        "messages": [
            {
                "role": "system",
                "content": (
                    "Describe only visible image content in one detailed English paragraph. "
                    "Do not include reasoning or Markdown."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {
                        "type": "text",
                        "text": (
                            "Describe visible subjects, objects and their relations. "
                            "Candidate tags, which may contain mistakes: " + ", ".join(tags)
                        ),
                    },
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 900,
        "stream": False,
        "enable_thinking": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    if urlsplit(vision["base_url"]).hostname == "api.deepseek.com":
        payload["thinking"] = {"type": "disabled"}
    base_url = vision["base_url"].rstrip("/")
    if urlsplit(base_url).scheme not in {"http", "https"}:
        msg = "Vision model URL must use HTTP or HTTPS"
        raise ValueError(msg)
    request = Request(  # noqa: S310 - URL scheme is validated above
        base_url + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + vision["api_key"],
        },
        method="POST",
    )
    with build_opener(NoRedirect()).open(request, timeout=180) as response:
        result = json.loads(response.read(4 * 1024 * 1024 + 1))
    choice = result["choices"][0]
    content = str(choice["message"]["content"] or "").strip()
    if not content or choice.get("finish_reason") == "length":
        msg = "Vision model returned an empty or truncated root caption"
        raise RuntimeError(msg)
    return content


def write_gbc_source(
    records: list[dict[str, Any]],
    output: Path,
    method: str,
    threshold: float,
    vision: dict[str, Any] | None = None,
) -> Path:
    source = output / ("source-pixai-tags.jsonl" if method == "pixai_gbc" else "source.jsonl")
    lines = []
    for item in records:
        job = {"key": item["item_id"], "image": item["path"]}
        if method == "pixai_gbc":
            tags = pixai_root_tags(output, item, threshold)
            if not tags:
                msg = f"PixAI returned no Danbooru tags above threshold for {item['item_id']}"
                raise RuntimeError(msg)
            caption_path = output / (item["item_id"] + ".gbc-root.json")
            if not caption_path.exists():
                if vision is None:
                    msg = "Vision connection is required to prepare the GBC root caption"
                    raise RuntimeError(msg)
                save(caption_path, {"detail": describe_root(item, tags, vision)})
            caption = json.loads(caption_path.read_text(encoding="utf-8"))
            if not str(caption.get("detail", "")).strip():
                msg = f"Missing GBC root caption for {item['item_id']}"
                raise RuntimeError(msg)
            job["tags"] = {"general": tags}
            job["captions"] = caption
            job["controls"] = {"root": "tags"}
        lines.append(json.dumps(job, ensure_ascii=False))
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return source


def build_gbc_config(
    vision: dict[str, Any], options: dict[str, Any], device: str, source: Path, method: str
) -> dict[str, Any]:
    machine = {"vlm_waiting": 2, "max_jobs": 4, "waiting": {"detect": 1}}
    controls = {
        "min_nodes": 5,
        "max_nodes": 8,
        "max_rounds": 1,
        "max_depth": 1,
        "max_top_level": 4,
        "max_features_per_entity": 0,
        "max_instances_per_text": 4,
        "max_breadth_rounds": 0,
        "max_side": 1536,
        "box_score": 0.3,
        "relation_vertices": "root",
        "tagging": "none",
    }
    detector_model = str(options["detector_model"])
    detector_config = Path(detector_model) / "config.json"
    detector_type = detector_model.lower()
    if detector_config.is_file():
        detector_type = str(
            json.loads(detector_config.read_text(encoding="utf-8")).get("model_type", "")
        ).lower()
    lite_text = "sam3_lite_text" in detector_type or "sam3-litetext" in detector_type
    if lite_text:
        # Retain low-scoring LiteText proposals for review on illustrated images.
        controls["box_score"] = 0.005
    if method == "pixai_gbc":
        machine["program"] = "gbc_nest"
        controls.update(
            {
                "root": "tags",
                "min_nodes": 5,
                "max_nodes": 12,
                "max_rounds": 2,
                "max_depth": 2,
                "max_top_level": 16,
                "max_features_per_entity": 2,
                "max_breadth_rounds": 1,
                "nms_iou": 0.7 if "sam3" in detector_type else 0.2,
                "nms_iou_single": 0.05,
                "drop_containers": False,
            }
        )
    config = {
        "engines": {
            "vlm": {
                "entry": "api",
                "protocol": "openai",
                "flavour": "openai",
                "structured": "prompt",
                "model": vision["model"],
                "endpoints": [
                    {
                        "base_url": vision["base_url"],
                        "api_key_env": "STUDIO_GBC_VLM_KEY",
                        "max_inflight": 2,
                        "rate": [2, 2],
                    }
                ],
                "timeout_s": 180,
            },
            "detect": {
                "entry": "torch",
                "model": detector_model,
                "devices": ["cuda:0" if device == "cuda" else "cpu"],
                "dtype": "float32",
                "box_threshold": 0.005 if lite_text else 0.05,
                "max_batch": 1,
                "max_texts": 8,
            },
            "embed": {
                "entry": "torch",
                "model": options["embedder_model"],
                "devices": ["cpu"],
                "impl": "st",
                "max_batch": 8,
            },
            "cpu": {"entry": "python", "workers": 2},
        },
        "controls": controls,
        "machine": machine,
        "source": {"kind": "jsonl", "path": str(source)},
        "sink": {"kind": "memory"},
    }
    if urlsplit(vision["base_url"]).hostname == "api.deepseek.com":
        config["engines"]["vlm"]["sampling"] = {"thinking": {"type": "disabled"}}
    return config


def main() -> None:  # noqa: C901 - protocol validation and dispatch stay together
    request = json.load(sys.stdin)
    options = request["options"]
    device = options.get("device", "cpu")
    if device == "cpu":
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    torch = import_module("torch")

    torch.set_num_threads(2)
    output = Path(request["output"])
    output.mkdir(parents=True, exist_ok=True)
    records = request["images"]
    if request["method"] in {"pixai", "pixai_gbc"}:
        from PIL import Image, ImageOps  # noqa: PLC0415 - optional dependency

        pipeline = import_module("transformers").pipeline

        model = options["pixai_model"]
        tagger = pipeline(
            model=model,
            image_processor=model,
            trust_remote_code=True,
            device=0 if device == "cuda" else -1,
        )
        precision = (
            torch.bfloat16 if device == "cpu" or torch.cuda.is_bf16_supported() else torch.float16
        )
        for record in records:
            path = output / (record["item_id"] + ".pixai.json")
            if path.exists():
                continue
            with (
                Image.open(record["path"]) as opened,
                torch.inference_mode(),
                torch.autocast(device, dtype=precision),
            ):
                result = tagger(ImageOps.exif_transpose(opened).convert("RGB"))["results"]
            save(path, {"image_sha256": record["sha256"], "result": result})
        del tagger
        if device == "cuda":
            torch.cuda.empty_cache()
    if request["method"] in {"gbc", "pixai_gbc"}:
        build = import_module("kohakugbc.machine").build

        suffix = GBC_TAG_SEEDED_SUFFIX if request["method"] == "pixai_gbc" else ".gbc.json"
        pending = [
            record for record in records if not (output / (record["item_id"] + suffix)).exists()
        ]
        if not pending:
            return
        vision = request["vision"]
        source = write_gbc_source(
            pending,
            output,
            request["method"],
            float(request.get("pixai_tag_threshold", PIXAI_TAG_THRESHOLD)),
            vision,
        )
        os.environ["STUDIO_GBC_VLM_KEY"] = vision["api_key"]
        config = build_gbc_config(vision, options, device, source, request["method"])
        machine, source_reader, _ = build(config)
        failed = []

        class Sink:
            def write(self, record: Any) -> None:  # noqa: ANN401 - external JSON and plugin values have heterogeneous schemas
                if record.ok and record.outputs.get("graph"):
                    save(output / (record.key + suffix), json.loads(record.outputs["graph"]))
                else:
                    failed.append(record.key)
                    diagnostic = repr(record).replace(vision["api_key"], "[REDACTED]")
                    save(output / (record.key + ".error.json"), {"error": diagnostic[:16000]})

            def close(self) -> None:
                pass

        with machine:
            machine.run(source_reader, Sink())
        if failed:
            msg = "GBC records failed"
            raise RuntimeError(msg)


def save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    main()
