from __future__ import annotations

import hashlib
import io
from typing import Any, cast

from PIL import Image

from prompt_hub.comfy_results import ComfyResultStore
from prompt_hub.creative import CreativeStore
from prompt_hub.database import PromptDatabase
from prompt_hub.dataset_workspace import DatasetWorkspaceStore
from prompt_hub.importers import import_all
from prompt_hub.result_media import store_result_image
from prompt_hub.visual_assets import VisualAssetCatalog
from prompt_hub.web_capture import FetchResult, WebCaptureService


class _Context:
    def update(self, _current, _total, _message="") -> None:
        return None


class _Remote:
    def __init__(self, digest: str) -> None:
        self.digest = digest

    def lora_catalog_status(self):
        return {"snapshot_id": "lora-snapshot"}

    def model_catalog_status(self):
        return {"snapshot_id": "model-snapshot"}

    def search_loras(self, **_kwargs):
        return [
            {
                "lora_id": "lora-one",
                "name": "Style LoRA",
                "model_family": "anima",
                "source_url": "https://civitai.com/models/1/style",
                "preview_files": [{"filename": "000.png", "sha256": self.digest}],
            }
        ]

    def search_models(self, **_kwargs):
        return [
            {
                "asset_id": "model-one",
                "name": "Anima base",
                "model_family": "anima",
                "source_url": "",
                "preview_files": [{"filename": "000.png", "sha256": self.digest}],
            }
        ]


def test_visual_catalog_discovers_all_mac_material_types(
    source_tree,
    tmp_path,
    monkeypatch,
) -> None:
    settings = source_tree
    database = PromptDatabase(settings.database_path)
    database.initialize()
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "a" * 40)
    import_all(settings, database)

    raw = _image_bytes("purple")
    digest = hashlib.sha256(raw).hexdigest()
    dataset_source = tmp_path / "dataset-source"
    dataset_source.mkdir()
    (dataset_source / "sample.png").write_bytes(raw)
    workspace_store = DatasetWorkspaceStore(settings)
    workspace_store.initialize()
    workspace = workspace_store.register(dataset_source, name="视觉测试数据集")
    workspace_store.scan(str(workspace["workspace_id"]), cast("Any", _Context()))

    creative_store = CreativeStore(settings.database_path)
    creative_store.initialize()
    project = creative_store.create_project({"title": "视觉项目", "safety_mode": "adult"})
    asset = store_result_image(
        settings,
        project_id=str(project["project_id"]),
        filename="result.png",
        raw=raw,
        safety_mode="adult",
    )
    creative_store.update_project(
        str(project["project_id"]),
        {"generation": {"result_assets": [asset]}},
    )

    comfy_store = ComfyResultStore(settings.comfy_results_root)
    comfy_store.initialize()
    comfy_store.import_bytes(raw, filename="comfy.png")

    for relative in (
        "lora-previews/lora-snapshot/lora-one/000.png",
        "model-previews/model-snapshot/model-one/000.png",
    ):
        path = settings.remote_nodes_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def fetcher(_url: str, _limit: int) -> FetchResult:
        return FetchResult(
            final_url="https://raw.githubusercontent.com/example/prompts/main/ref.png",
            content_type="image/png",
            body=raw,
        )

    web_capture = WebCaptureService(settings, database, fetcher=fetcher)
    web_capture.capture(
        url="https://raw.githubusercontent.com/example/prompts/main/ref.png",
        title="网页参考图",
        note="构图参考",
        safety="sfw",
        license_name="MIT",
    )

    catalog = VisualAssetCatalog(
        settings,
        database,
        workspace_store,
        creative_store,
        comfy_store,
        cast("Any", _Remote(digest)),
        web_capture,
    )
    assets = catalog.discover()
    types = {item.asset_type for item in assets}
    assert {
        "prompt_visual",
        "dataset_image",
        "result_image",
        "comfy_result",
        "lora_preview",
        "model_preview",
        "web_visual",
    } <= types
    assert all(item.source_sha256 for item in assets)
    assert all(item.metadata.get("media_url") for item in assets)


def _image_bytes(color: str) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (96, 64), color).save(output, "PNG")
    return output.getvalue()
