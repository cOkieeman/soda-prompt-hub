from __future__ import annotations

import hashlib
import io
import os

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prompt_hub.api import create_app
from prompt_hub.embedding_index import EmbeddingIndexStore
from prompt_hub.local_visual import (
    MODEL_FILENAME,
    MODEL_SIZE_BYTES,
    LocalVisualEncoder,
    LocalVisualIndexService,
    VisualIndexError,
    prepare_clip_image,
    write_model_info,
)
from prompt_hub.visual_assets import VisualAsset


class _Input:
    name = "pixel_values"


class _Session:
    def __init__(self) -> None:
        self.tensor = None

    def get_inputs(self):
        return [_Input()]

    def run(self, _outputs, values):
        self.tensor = values["pixel_values"]
        return [np.asarray([[3.0, 4.0] + [0.0] * 510], dtype=np.float32)]


class _Context:
    def __init__(self) -> None:
        self.updates = []

    def update(self, current, total, message="") -> None:
        self.updates.append((current, total, message))


def _png(path, color) -> str:
    Image.new("RGB", (320, 180), color).save(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_clip_preprocess_center_crop_and_projection_normalization(tmp_path) -> None:
    wide = Image.new("RGB", (400, 200), (255, 0, 0))
    tensor = prepare_clip_image(wide)
    assert tensor.shape == (1, 3, 224, 224)
    assert tensor.dtype == np.float32
    assert np.isfinite(tensor).all()

    model_root = tmp_path / "model"
    model_root.mkdir()
    model_path = model_root / MODEL_FILENAME
    model_path.touch()
    os.truncate(model_path, MODEL_SIZE_BYTES)
    write_model_info(
        model_root,
        sha256="fd6e1402a588279d1723c7534d4bcba5bc0b14b47dfab0e46f8c47b8270d7d40",
    )
    session = _Session()
    encoder = LocalVisualEncoder(model_root, session_factory=lambda _path: session)
    image_path = tmp_path / "query.png"
    wide.save(image_path)
    vector = np.asarray(encoder.encode_path(image_path))
    assert vector.shape == (512,)
    assert np.linalg.norm(vector) == pytest.approx(1.0)
    assert vector[:2].tolist() == pytest.approx([0.6, 0.8])
    assert session.tensor is not None
    assert session.tensor.shape == (1, 3, 224, 224)


class _Encoder:
    model_id = "test-clip"
    model_revision = "revision-1"
    dimension = 3

    def __init__(self) -> None:
        self.calls = []
        self.fail_once = set()

    def status(self):
        return {"available": True, "model_id": self.model_id, "dimension": 3}

    def encode_path(self, path):
        self.calls.append(path.name)
        if path.name in self.fail_once:
            self.fail_once.remove(path.name)
            message = "temporary decode failure"
            raise VisualIndexError(message)
        return [1.0, 0.0, 0.0] if "red" in path.name else [0.0, 1.0, 0.0]

    def encode_bytes(self, raw):
        del raw
        return [1.0, 0.0, 0.0]


class _Catalog:
    def __init__(self, assets):
        self.assets = assets

    def discover(self, asset_types=None):
        if not asset_types:
            return self.assets
        return [asset for asset in self.assets if asset.asset_type in asset_types]


def test_local_visual_index_is_incremental_resumable_and_queryable(tmp_path) -> None:
    red = tmp_path / "red.png"
    blue = tmp_path / "blue.png"
    digest_red = _png(red, "red")
    digest_blue = _png(blue, "blue")
    assets = [
        VisualAsset(
            "red",
            "dataset_image",
            red,
            digest_red,
            {"title": "red", "safety": "sfw", "media_url": "/red"},
        ),
        VisualAsset(
            "blue",
            "lora_preview",
            blue,
            digest_blue,
            {"title": "blue", "safety": "adult", "media_url": "/blue"},
        ),
    ]
    store = EmbeddingIndexStore(tmp_path / "index")
    store.initialize()
    encoder = _Encoder()
    encoder.fail_once.add("blue.png")
    service = LocalVisualIndexService(store, _Catalog(assets), encoder)

    first = service.job({}, _Context())
    assert first["indexed"] == 1
    assert first["failed"] == 1
    second = service.job({}, _Context())
    assert second["indexed"] == 1
    assert second["skipped_unchanged"] == 1
    third = service.job({}, _Context())
    assert third["indexed"] == 0
    assert third["skipped_unchanged"] == 2

    queried = service.query_bytes(
        b"query",
        asset_types=set(),
        safety="sfw",
        scope_id="",
        limit=10,
    )
    assert [item["asset_id"] for item in queried["matches"]] == ["red"]
    assert queried["groups"][0]["label"] == "我的数据集"
    assert service.status()["truthful_empty"] is False


def test_local_visual_query_has_truthful_empty_states(tmp_path) -> None:
    model_root = tmp_path / "missing"
    encoder = LocalVisualEncoder(model_root)
    assert encoder.status()["available"] is False
    with pytest.raises(VisualIndexError, match="尚未安装"):
        encoder.encode_bytes(_image_bytes())

    store = EmbeddingIndexStore(tmp_path / "index")
    store.initialize()
    service = LocalVisualIndexService(store, _Catalog([]), _Encoder())
    with pytest.raises(VisualIndexError, match="真实视觉索引"):
        service.query_bytes(b"query", asset_types=set(), safety="", scope_id="", limit=5)
    assert service.status()["truthful_empty"] is True


def test_local_visual_query_never_crosses_model_revisions(tmp_path) -> None:
    store = EmbeddingIndexStore(tmp_path / "index")
    store.initialize()
    foreign_digest = "f" * 64
    store.import_batch(
        model_id="another-clip-model",
        model_revision="foreign-revision",
        dimension=3,
        generated_by="test",
        worker_id="",
        items=[
            {
                "asset_id": "foreign",
                "asset_type": "dataset_image",
                "source_path": "foreign.png",
                "source_sha256": foreign_digest,
                "vector": [1.0, 0.0, 0.0],
                "metadata": {"title": "foreign"},
            }
        ],
        expected_hashes={"foreign": foreign_digest},
    )
    service = LocalVisualIndexService(store, _Catalog([]), _Encoder())

    with pytest.raises(VisualIndexError, match="真实视觉索引"):
        service.query_bytes(b"query", asset_types=set(), safety="", scope_id="", limit=5)


def test_visual_api_reports_missing_model_without_fake_results(settings) -> None:
    with TestClient(create_app(settings)) as client:
        status = client.get("/api/visual-index/status")
        assert status.status_code == 200
        assert status.json()["model"]["available"] is False
        assert status.json()["truthful_empty"] is True
        build = client.post("/api/visual-index/build", json={"asset_types": []})
        assert build.status_code == 503
        query = client.post("/api/visual-search/query", content=_image_bytes())
        assert query.status_code == 503
        assert "模型文件尚未安装" in query.json()["detail"]
        page = client.get("/").text
        assert 'id="visualSearchPanel"' in page
        assert 'id="visualQueryFile"' in page
        assert 'id="visualClusterPanel"' in page
        assert 'id="sourceCaptureForm"' in page


def _image_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(output, "PNG")
    return output.getvalue()
