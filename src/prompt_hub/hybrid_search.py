from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

if TYPE_CHECKING:
    from prompt_hub.database import PromptDatabase
    from prompt_hub.embedding_index import EmbeddingIndexStore
    from prompt_hub.remote_nodes import RemoteNodeStore

GROUPS = (
    ("prompt_library", "提示词资料"),
    ("visual_references", "视觉参考"),
    ("my_datasets", "我的数据集"),
    ("windows_loras", "Windows LoRA"),
)


class HybridSearchService:
    def __init__(
        self,
        database: PromptDatabase,
        embedding_store: EmbeddingIndexStore,
        remote_store: RemoteNodeStore | None = None,
    ) -> None:
        self.database = database
        self.embedding_store = embedding_store
        self.remote_store = remote_store

    def search_text(
        self,
        query: str,
        *,
        vector: list[float] | None = None,
        index_id: str = "",
        safety: str = "",
        limit: int = 20,
    ) -> dict[str, Any]:
        clean_query = query.strip()
        keyword = self.database.search(clean_query, safety=safety, limit=limit)
        for item in keyword:
            item["match_type"] = "keyword"
            item["match_reason"] = f"关键词命中: {clean_query}" if clean_query else "本地资料索引"
            item["visuals"] = _keyword_visuals(item, safety)
        groups = _empty_groups()
        groups["prompt_library"]["results"] = keyword
        groups["visual_references"]["results"] = [item for item in keyword if _has_image_refs(item)]
        if self.remote_store is not None:
            groups["windows_loras"]["results"] = [
                _decorate_lora(item, clean_query)
                for item in self.remote_store.search_loras(clean_query, limit=limit)
            ]

        semantic = {
            "status": "not_requested",
            "message": "当前为本地关键词检索; 提供真实 query embedding 后才会加入语义召回。",
            "index": None,
        }
        if vector is not None:
            selected_index = index_id
            if not selected_index:
                compatible = self.embedding_store.compatible_index(len(vector))
                selected_index = str(compatible["index_id"]) if compatible else ""
            if selected_index:
                queried = self.embedding_store.query(selected_index, vector, limit=limit)
                _merge_vector_matches(groups, queried["matches"])
                semantic = {
                    "status": "active",
                    "message": "已使用版本固定的真实 embedding 进行 cosine 召回。",
                    "index": queried["index"],
                }
            else:
                semantic = {
                    "status": "unavailable",
                    "message": "没有与 query embedding 维度兼容的真实索引; 未生成伪结果。",
                    "index": None,
                }
        return _response(clean_query, groups, semantic)

    def search_by_source(
        self,
        source_sha256: str,
        *,
        index_id: str = "",
        limit: int = 30,
    ) -> dict[str, Any]:
        groups = _empty_groups()
        queried = self.embedding_store.query_by_source_hash(
            source_sha256,
            index_id=index_id,
            limit=limit,
        )
        _merge_vector_matches(groups, queried["matches"])
        semantic = {
            "status": "active",
            "message": "已用这张图在同一模型版本的真实视觉索引中查找相似图片。",
            "index": queried["index"],
            "query_asset": queried["query_asset"],
        }
        return _response("", groups, semantic)


def _empty_groups() -> dict[str, dict[str, Any]]:
    return {key: {"key": key, "label": label, "results": []} for key, label in GROUPS}


def _response(
    query: str,
    groups: dict[str, dict[str, Any]],
    semantic: dict[str, Any],
) -> dict[str, Any]:
    ordered = [groups[key] for key, _label in GROUPS]
    return {
        "query": query,
        "semantic": semantic,
        "groups": ordered,
        "count": sum(len(group["results"]) for group in ordered),
    }


def _has_image_refs(item: dict[str, Any]) -> bool:
    refs = item.get("metadata", {}).get("image_refs", [])
    return isinstance(refs, list) and bool(refs)


def _keyword_visuals(item: dict[str, Any], safety_filter: str) -> list[dict[str, str]]:
    metadata = item.get("metadata", {})
    refs = metadata.get("image_refs", []) if isinstance(metadata, dict) else []
    if not isinstance(refs, list):
        return []
    source_id = str(item.get("source_id", ""))
    visuals = []
    for ref in refs[:3]:
        if not isinstance(ref, dict):
            continue
        path = str(ref.get("path", ""))
        safety = str(ref.get("safety", item.get("safety", "sfw")))
        if not path or (safety_filter and safety != safety_filter):
            continue
        encoded = quote(path, safe="/")
        visuals.append(
            {
                "thumbnail_url": f"/media/{source_id}/thumbnail/{encoded}",
                "original_url": f"/media/{source_id}/original/{encoded}",
                "safety": safety,
            }
        )
    return visuals


def _merge_vector_matches(
    groups: dict[str, dict[str, Any]],
    matches: list[dict[str, Any]],
) -> None:
    for match in matches:
        decorated = _decorate_vector_match(match)
        group_key = _group_for_asset_type(str(match.get("asset_type", "")))
        groups[group_key]["results"].append(decorated)


def _group_for_asset_type(asset_type: str) -> str:
    if asset_type in {"dataset_image", "comfy_result", "lora_dataset_image"}:
        return "my_datasets"
    if asset_type in {"windows_lora", "lora_preview"}:
        return "windows_loras"
    if asset_type in {"prompt_entry", "prompt_text"}:
        return "prompt_library"
    return "visual_references"


def _decorate_vector_match(match: dict[str, Any]) -> dict[str, Any]:
    metadata = match.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    asset_type = str(match.get("asset_type", ""))
    source_path = str(match.get("source_path", ""))
    title = str(
        metadata.get("title") or metadata.get("filename") or source_path or match["asset_id"]
    )
    result = {
        **match,
        "title": title,
        "match_type": "visual_similarity",
        "match_reason": f"视觉相似度 {float(match.get('score', 0)):.3f}",
        "thumbnail_url": str(metadata.get("thumbnail_url", "")),
        "original_url": str(metadata.get("original_url", "")),
    }
    if asset_type in {"dataset_image", "lora_dataset_image"}:
        workspace_id = str(metadata.get("workspace_id", ""))
        relative_path = str(metadata.get("relative_path", source_path))
        if workspace_id and relative_path:
            result["original_url"] = (
                f"/dataset-workspaces/{quote(workspace_id, safe='')}/original"
                f"?relative_path={quote(relative_path, safe='')}"
            )
            thumbnail = str(metadata.get("thumbnail", ""))
            if thumbnail:
                result["thumbnail_url"] = (
                    f"/dataset-workspaces/{quote(workspace_id, safe='')}/thumbnails/"
                    f"{quote(thumbnail.rsplit('/', 1)[-1], safe='')}"
                )
    return result


def _decorate_lora(item: dict[str, Any], query: str) -> dict[str, Any]:
    triggers = ", ".join(str(value) for value in item.get("trigger_words", []))
    base_model = str(item.get("base_model", ""))
    return {
        **item,
        "title": str(item.get("name", "")) or str(item.get("lora_id", "")),
        "content": f"BASE / {base_model or 'unknown'}\nTRIGGER / {triggers or 'not provided'}",
        "match_type": "keyword",
        "match_reason": f"LoRA metadata 命中: {query}",
        "source_name": "Windows LoRA Manager",
    }
