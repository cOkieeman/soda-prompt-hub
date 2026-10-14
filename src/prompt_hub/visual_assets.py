from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import quote

from prompt_hub.media import resolve_media_path
from prompt_hub.result_media import resolve_result_image

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from prompt_hub.comfy_results import ComfyResultStore
    from prompt_hub.config import Settings
    from prompt_hub.creative import CreativeStore
    from prompt_hub.database import PromptDatabase
    from prompt_hub.dataset_workspace import DatasetWorkspaceStore
    from prompt_hub.gallery import GalleryStore
    from prompt_hub.remote_nodes import RemoteNodeStore
    from prompt_hub.web_capture import WebCaptureService


class DiscoveryContext(Protocol):
    def update(self, current: int, total: int, message: str = "") -> None: ...


VISUAL_ASSET_TYPES = {
    "prompt_visual",
    "dataset_image",
    "result_image",
    "comfy_result",
    "lora_preview",
    "model_preview",
    "web_visual",
    "gallery_image",
}


@dataclass(frozen=True, slots=True)
class VisualAsset:
    asset_id: str
    asset_type: str
    path: Path
    source_sha256: str
    metadata: dict[str, Any]

    def embedding_item(self, vector: list[float]) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "asset_type": self.asset_type,
            "source_path": str(self.path),
            "source_sha256": self.source_sha256,
            "vector": vector,
            "metadata": self.metadata,
        }


class VisualAssetCatalog:
    def __init__(
        self,
        settings: Settings,
        database: PromptDatabase,
        workspace_store: DatasetWorkspaceStore,
        creative_store: CreativeStore,
        comfy_store: ComfyResultStore,
        remote_store: RemoteNodeStore,
        web_capture: WebCaptureService,
        gallery_store: GalleryStore | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.workspace_store = workspace_store
        self.creative_store = creative_store
        self.comfy_store = comfy_store
        self.remote_store = remote_store
        self.web_capture = web_capture
        self.gallery_store = gallery_store

    def discover(  # noqa: C901 - per-collector checkpoints share one bounded progress callback
        self,
        asset_types: set[str] | None = None,
        *,
        context: DiscoveryContext | None = None,
        max_items: int = 0,
    ) -> list[VisualAsset]:
        selected = asset_types or VISUAL_ASSET_TYPES
        assets: dict[str, VisualAsset] = {}
        collectors = (
            ("prompt_visual", self._prompt_visuals),
            ("dataset_image", self._dataset_images),
            ("result_image", self._creative_results),
            ("comfy_result", self._comfy_results),
            ("lora_preview", self._lora_previews),
            ("model_preview", self._model_previews),
            ("web_visual", self._web_visuals),
            ("gallery_image", self._gallery_images),
        )
        last_update = 0.0

        def progress(message: str) -> None:
            nonlocal last_update
            if context is None:
                return
            check = getattr(context, "raise_if_cancelled", None)
            if check is not None:
                check()
            now = time.monotonic()
            if now - last_update >= 0.25:
                context.update(len(assets), 0, f"扫描素材 · 已发现 {len(assets)} 张 · {message}")
                last_update = now

        for asset_type, collector in collectors:
            if asset_type not in selected:
                continue
            if context is not None:
                context.update(len(assets), 0, f"扫描素材类别: {asset_type}")
            for asset in collector(progress):
                if asset.path.is_file():
                    assets.setdefault(asset.asset_id, asset)
                    if max_items and len(assets) >= max_items:
                        return list(assets.values())
        return sorted(assets.values(), key=lambda item: (item.asset_type, item.asset_id))

    def _gallery_images(self, progress: Callable[[str], None]) -> Iterator[VisualAsset]:
        if self.gallery_store is None:
            return
        for item in self.gallery_store.iter_assets():
            progress("正在检查画廊图片")
            asset_id = str(item["asset_id"])
            path = self.gallery_store.resolve_asset_path(asset_id)
            if path is None:
                continue
            yield _asset(
                "gallery_image",
                f"gallery:{asset_id}",
                path,
                {
                    "title": item["title"],
                    "source_label": "我的作品" if item["kind"] == "work" else "收集参考",
                    "source_url": item.get("source_url", ""),
                    "safety": item.get("safety", "unrated"),
                    "media_url": item["thumbnail_url"],
                    "original_url": item["original_url"],
                    "project_id": item.get("project_id", ""),
                    "gallery_asset_id": asset_id,
                    "gallery_kind": item["kind"],
                    "albums": item.get("albums", []),
                    "note": item.get("note", ""),
                },
                known_hash=str(item["sha256"]),
                progress=progress,
            )

    def _prompt_visuals(self, progress: Callable[[str], None]) -> Iterator[VisualAsset]:
        seen_paths: set[Path] = set()
        for entry in self.database.list_visual_entries():
            progress("正在检查素材记录")
            metadata = entry.get("metadata", {})
            refs = metadata.get("image_refs", []) if isinstance(metadata, dict) else []
            for index, ref in enumerate(refs if isinstance(refs, list) else []):
                progress("正在检查素材记录")
                if not isinstance(ref, dict):
                    continue
                relative = str(ref.get("path", ""))
                path = resolve_media_path(
                    self.settings,
                    str(entry["source_id"]),
                    "original",
                    relative,
                )
                if path is None or path in seen_paths:
                    continue
                seen_paths.add(path)
                original_variant = (
                    "thumbnail" if ref.get("original_variant") == "thumbnail" else "original"
                )
                yield (
                    _asset(
                        "prompt_visual",
                        f"prompt:{entry['source_id']}:{entry['external_id']}:{index}",
                        path,
                        {
                            "title": entry["title"],
                            "source_label": entry["source_name"],
                            "source_url": entry["source_url"],
                            "safety": str(ref.get("safety", entry["safety"])),
                            "media_url": (
                                f"/media/{entry['source_id']}/thumbnail/{quote(relative, safe='/')}"
                            ),
                            "original_url": (
                                f"/media/{entry['source_id']}/"
                                f"{original_variant}/"
                                f"{quote(relative, safe='/')}"
                            ),
                        },
                        progress=progress,
                    )
                )

    def _dataset_images(self, progress: Callable[[str], None]) -> Iterator[VisualAsset]:
        for workspace in self.workspace_store.list_workspaces():
            progress("正在检查素材记录")
            workspace_id = str(workspace.get("workspace_id", ""))
            report = self.workspace_store.read_current_report(workspace_id) or {}
            source = Path(str(workspace.get("source_path", "")))
            for image in report.get("images", []):
                progress("正在检查素材记录")
                if not isinstance(image, dict) or not image.get("valid"):
                    continue
                relative = str(image.get("relative_path", ""))
                path = (source / relative).resolve()
                if not path.is_file() or not path.is_relative_to(source.resolve()):
                    continue
                yield (
                    _asset(
                        "dataset_image",
                        f"dataset:{workspace_id}:{relative}",
                        path,
                        {
                            "title": image.get("filename", relative),
                            "source_label": workspace.get("name", "数据集"),
                            "source_url": "",
                            "safety": "unrated",
                            "media_url": image.get("thumbnail_url")
                            or (
                                f"/dataset-workspaces/{workspace_id}/thumbnails/"
                                f"{Path(str(image.get('thumbnail', ''))).name}"
                            ),
                            "original_url": (
                                f"/dataset-workspaces/{workspace_id}/original"
                                f"?relative_path={quote(relative, safe='')}"
                            ),
                            "workspace_id": workspace_id,
                            "caption": image.get("caption", ""),
                        },
                        known_hash=str(image.get("sha256", "")),
                        progress=progress,
                    )
                )

    def _creative_results(self, progress: Callable[[str], None]) -> Iterator[VisualAsset]:
        for project in self.creative_store.list_projects(limit=1000):
            progress("正在检查素材记录")
            project_id = str(project.get("project_id", ""))
            generation = project.get("generation", {})
            raw_assets = generation.get("result_assets", []) if isinstance(generation, dict) else []
            for item in raw_assets if isinstance(raw_assets, list) else []:
                progress("正在检查素材记录")
                if not isinstance(item, dict):
                    continue
                asset_id = str(item.get("asset_id", ""))
                path = resolve_result_image(
                    self.settings,
                    project_id=project_id,
                    variant="original",
                    stored_name=str(item.get("original_name", "")),
                )
                if path is None:
                    continue
                yield (
                    _asset(
                        "result_image",
                        f"result:{project_id}:{asset_id}",
                        path,
                        {
                            "title": item.get("filename", project.get("title", "创作结果")),
                            "source_label": project.get("title", "创作项目"),
                            "source_url": "",
                            "safety": project.get("safety_mode", "unrated"),
                            "media_url": f"/result-media/{project_id}/thumbnail/{asset_id}",
                            "original_url": f"/result-media/{project_id}/original/{asset_id}",
                            "project_id": project_id,
                        },
                        known_hash=str(item.get("sha256", "")),
                        progress=progress,
                    )
                )

    def _comfy_results(self, progress: Callable[[str], None]) -> Iterator[VisualAsset]:
        for item in self.comfy_store.list_results(limit=2000):
            progress("正在检查素材记录")
            result_id = str(item.get("result_id", ""))
            # Reuse the loaded record; resolve_media would parse the full index per image.
            filename = str(item.get("original_name", ""))
            if not filename or Path(filename).name != filename:
                continue
            root = (self.comfy_store.root / "original").resolve()
            path = (root / filename).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                continue
            yield (
                _asset(
                    "comfy_result",
                    f"comfy:{result_id}",
                    path,
                    {
                        "title": item.get("filename", result_id),
                        "source_label": "出图结果",
                        "source_url": "",
                        "safety": "unrated",
                        "media_url": item.get("thumbnail_url", ""),
                        "original_url": item.get("original_url", ""),
                        "result_id": result_id,
                    },
                    known_hash=str(item.get("sha256", "")),
                    progress=progress,
                )
            )

    def _lora_previews(self, progress: Callable[[str], None]) -> Iterator[VisualAsset]:
        status = self.remote_store.lora_catalog_status()
        snapshot_id = str(status.get("snapshot_id", ""))
        for item in self.remote_store.search_loras(limit=500):
            progress("正在检查素材记录")
            lora_id = str(item.get("lora_id", ""))
            files = item.get("preview_files", [])
            for preview in files if isinstance(files, list) else []:
                progress("正在检查素材记录")
                if not isinstance(preview, dict):
                    continue
                filename = str(preview.get("filename", ""))
                path = (
                    self.settings.remote_nodes_root
                    / "lora-previews"
                    / snapshot_id
                    / lora_id
                    / filename
                )
                yield (
                    _asset(
                        "lora_preview",
                        f"lora:{snapshot_id}:{lora_id}:{filename}",
                        path,
                        {
                            "title": item.get("name", lora_id),
                            "source_label": "Windows LoRA 预览",
                            "source_url": item.get("source_url", ""),
                            "safety": "unrated",
                            "media_url": (
                                f"/api/windows-loras/previews/{snapshot_id}/{lora_id}/{filename}"
                            ),
                            "original_url": (
                                f"/api/windows-loras/previews/{snapshot_id}/{lora_id}/{filename}"
                            ),
                            "model_family": item.get("model_family", ""),
                            "lora_id": lora_id,
                        },
                        known_hash=str(preview.get("sha256", "")),
                        progress=progress,
                    )
                )

    def _model_previews(self, progress: Callable[[str], None]) -> Iterator[VisualAsset]:
        status = self.remote_store.model_catalog_status()
        snapshot_id = str(status.get("snapshot_id", ""))
        for item in self.remote_store.search_models(limit=2000):
            progress("正在检查素材记录")
            asset_id = str(item.get("asset_id", ""))
            files = item.get("preview_files", [])
            for preview in files if isinstance(files, list) else []:
                progress("正在检查素材记录")
                if not isinstance(preview, dict):
                    continue
                filename = str(preview.get("filename", ""))
                path = (
                    self.settings.remote_nodes_root
                    / "model-previews"
                    / snapshot_id
                    / asset_id
                    / filename
                )
                yield (
                    _asset(
                        "model_preview",
                        f"model:{snapshot_id}:{asset_id}:{filename}",
                        path,
                        {
                            "title": item.get("name", asset_id),
                            "source_label": "Windows 底模预览",
                            "source_url": item.get("source_url", ""),
                            "safety": "unrated",
                            "media_url": (
                                f"/api/windows-models/previews/{snapshot_id}/{asset_id}/{filename}"
                            ),
                            "original_url": (
                                f"/api/windows-models/previews/{snapshot_id}/{asset_id}/{filename}"
                            ),
                            "model_family": item.get("model_family", ""),
                            "model_asset_id": asset_id,
                        },
                        known_hash=str(preview.get("sha256", "")),
                        progress=progress,
                    )
                )

    def _web_visuals(self, progress: Callable[[str], None]) -> Iterator[VisualAsset]:
        for item in self.web_capture.list_captures():
            progress("正在检查素材记录")
            if item.get("media_kind") != "image":
                continue
            capture_id = str(item.get("capture_id", ""))
            try:
                path = self.web_capture.resolve_media(capture_id)
            except ValueError:
                continue
            yield (
                _asset(
                    "web_visual",
                    f"web:{capture_id}",
                    path,
                    {
                        "title": item.get("title", "网页视觉资料"),
                        "source_label": item.get("site_label", "网页资料"),
                        "source_url": item.get("url", ""),
                        "safety": item.get("safety", "unrated"),
                        "media_url": f"/api/web-captures/{capture_id}/media",
                        "original_url": f"/api/web-captures/{capture_id}/media",
                        "capture_id": capture_id,
                    },
                    known_hash=str(item.get("content_sha256", "")),
                    progress=progress,
                )
            )


def _asset(
    asset_type: str,
    asset_id: str,
    path: Path,
    metadata: dict[str, Any],
    *,
    known_hash: str = "",
    progress: Callable[[str], None] | None = None,
) -> VisualAsset:
    digest = known_hash.lower()
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        if progress is not None:
            progress(path.name)
        digest = ""
        if path.is_file():
            hasher = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    if progress is not None:
                        progress(f"校验 {path.name}")
                    hasher.update(chunk)
            digest = hasher.hexdigest()
    stable_id = hashlib.sha256(asset_id.encode()).hexdigest()[:32]
    return VisualAsset(
        asset_id=f"visual-{stable_id}",
        asset_type=asset_type,
        path=path,
        source_sha256=digest,
        metadata={**metadata, "asset_type": asset_type},
    )
