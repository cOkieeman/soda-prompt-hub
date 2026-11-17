from __future__ import annotations

from typing import Any

from prompt_hub.studio_store import StudioError, StudioStore

MAX_ANNOTATION_RECORDS = 500
PIXAI_TAG_THRESHOLD = 0.35


def normalize_annotation(value: dict[str, Any]) -> dict[str, Any]:
    """Accept Studio, reviewed MOSS, native GBC and PixAI annotations."""
    value = value.get("record", value)
    if "vertices" in value:
        root = next((vertex for vertex in value["vertices"] if vertex.get("label") == "image"), {})
        descriptions = root.get("descs", [])
        long = value.get("detail_caption") or next(
            (d["text"] for d in descriptions if d.get("label") == "detail"), ""
        )
        regions = []
        for vertex in value["vertices"]:
            if vertex.get("label") != "entity":
                continue
            box = vertex["bbox"]
            text = " ".join(d["text"] for d in vertex.get("descs", []))
            regions.append(
                {
                    "name": vertex["vertex_id"],
                    "caption": text,
                    "bbox": [box["left"], box["top"], box["right"], box["bottom"]],
                }
            )
        return {
            "long": long,
            "short": value.get("short_caption") or "",
            "regions": regions,
            "tags": list(root.get("tags", {})),
            "source": "KohakuGBC",
            "graph": value,
        }
    if isinstance(value.get("caption"), dict):
        caption = {**value, **value["caption"]}
        caption.pop("caption", None)
        return caption
    if "result" in value and isinstance(value["result"], dict):
        scores = value["result"].get("general", {})
        tags = [name for name, score in scores.items() if float(score) >= PIXAI_TAG_THRESHOLD]
        return {"tags": tags, "long": ", ".join(tags), "source": "PixAI", "tag_scores": scores}
    if isinstance(value.get("caption"), str):
        return {**value, "long": value["caption"]}
    if not isinstance(value.get("long"), str):
        msg = "找不到可用的標注描述"
        raise StudioError(msg)
    return value


def import_annotations(
    store: StudioStore, project_id: str, records: list[dict[str, Any]]
) -> dict[str, Any]:
    if not 1 <= len(records) <= MAX_ANNOTATION_RECORDS:
        msg = "每次可匯入 1 至 500 份標注"
        raise StudioError(msg)
    images = store.images(project_id, "candidate")
    imported, errors = [], []
    for record in records:
        filename = str(record.get("filename", ""))
        value = record.get("annotation", {})
        digest = record.get("sha256") or value.get("image_sha256")
        matches = [
            image
            for image in images
            if image["item_id"] == record.get("item_id")
            or (digest and image["sha256"] == digest)
            or (filename and image["title"] == filename.rsplit(".", 1)[0])
        ]
        if len(matches) != 1:
            errors.append(
                {"filename": filename, "error": "找不到唯一對應圖片，請使用圖片 SHA256 或同名標注"}
            )
            continue
        image = store.image(project_id, matches[0]["item_id"])
        if image["caption_confirmed"]:
            errors.append({"filename": filename, "error": "圖片已有已確認標注"})
            continue
        try:
            caption = normalize_annotation(value)
            # Tag-only results add tags without discarding an existing full description.
            if caption.get("source") == "PixAI" and image["caption"].get("long"):
                caption = {
                    **image["caption"],
                    "tags": caption["tags"],
                    "tag_scores": caption["tag_scores"],
                }
            store.update_image(
                project_id, image["item_id"], {"caption": caption, "caption_confirmed": False}
            )
            imported.append(image["item_id"])
        except (StudioError, ValueError, TypeError, KeyError) as error:
            errors.append({"filename": filename, "error": str(error)})
    return {"item_ids": imported, "errors": errors}
