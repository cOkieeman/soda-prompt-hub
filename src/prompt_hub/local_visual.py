from __future__ import annotations

import hashlib
import io
import json
from collections import Counter
from collections.abc import Callable, Mapping
from pathlib import Path
from threading import RLock
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps, UnidentifiedImageError

from prompt_hub.embedding_index import (
    EmbeddingIndexError,
    EmbeddingIndexStore,
    embedding_index_id,
)

if TYPE_CHECKING:
    from prompt_hub.visual_assets import VisualAsset

MODEL_ID = "Xenova/clip-vit-base-patch32"
MODEL_REVISION = "d15189d7028b43f1d3e65039190477f6af591c2a"
MODEL_DIMENSION = 512
MODEL_FILENAME = "vision_model.onnx"
MODEL_SIZE_BYTES = 351_685_709
MODEL_SHA256 = "fd6e1402a588279d1723c7534d4bcba5bc0b14b47dfab0e46f8c47b8270d7d40"
IMAGE_SIZE = 224
MAX_QUERY_BYTES = 25 * 1024 * 1024
CLIP_MEAN = np.asarray([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
CLIP_STD = np.asarray([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)


class VisualIndexError(ValueError):
    pass


class VisualJobProgress(Protocol):
    def update(self, current: int, total: int, message: str = "") -> None: ...


class VisualEncoderProtocol(Protocol):
    model_id: str
    model_revision: str
    dimension: int

    def status(self) -> dict[str, Any]: ...

    def encode_path(self, path: Path) -> list[float]: ...

    def encode_bytes(self, raw: bytes) -> list[float]: ...


class VisualCatalogProtocol(Protocol):
    def discover(self, asset_types: set[str] | None = None) -> list[VisualAsset]: ...


SessionFactory = Callable[[Path], Any]


class LocalVisualEncoder:
    def __init__(
        self,
        model_root: Path,
        *,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self.model_root = model_root
        self.model_path = model_root / MODEL_FILENAME
        self.session_factory = session_factory or _create_session
        self.model_id = MODEL_ID
        self.model_revision = MODEL_REVISION
        self.dimension = MODEL_DIMENSION
        self._session: Any | None = None
        self._verify_digest = session_factory is None
        self._lock = RLock()

    def status(self) -> dict[str, Any]:
        available = self.model_path.is_file()
        size = self.model_path.stat().st_size if available else 0
        info = _read_model_info(self.model_root / "model-info.json")
        metadata_valid = (
            info.get("model_revision") == MODEL_REVISION and info.get("sha256") == MODEL_SHA256
        )
        return {
            "available": available and size == MODEL_SIZE_BYTES and metadata_valid,
            "model_id": self.model_id,
            "model_revision": self.model_revision,
            "dimension": self.dimension,
            "model_path": str(self.model_path),
            "size_bytes": size,
            "expected_size_bytes": MODEL_SIZE_BYTES,
            "sha256": info.get("sha256", ""),
            "expected_sha256": MODEL_SHA256,
            "runtime": "ONNX Runtime",
            "input_size": IMAGE_SIZE,
            "reason": (
                "模型可用"
                if available and size == MODEL_SIZE_BYTES and metadata_valid
                else "模型文件尚未安装"
                if not available
                else "模型文件或版本校验信息不一致"
            ),
        }

    def encode_path(self, path: Path) -> list[float]:
        try:
            with Image.open(path) as image:
                return self._encode_image(image)
        except (OSError, UnidentifiedImageError) as error:
            raise VisualIndexError(f"无法读取图片：{path.name}") from error

    def encode_bytes(self, raw: bytes) -> list[float]:
        if not raw:
            raise VisualIndexError("查询图片为空")
        if len(raw) > MAX_QUERY_BYTES:
            raise VisualIndexError("查询图片超过 25 MiB 限制")
        try:
            with Image.open(io.BytesIO(raw)) as image:
                return self._encode_image(image)
        except (OSError, UnidentifiedImageError) as error:
            raise VisualIndexError("无法识别查询图片") from error

    def _encode_image(self, image: Image.Image) -> list[float]:
        tensor = prepare_clip_image(image)
        with self._lock:
            session = self._get_session()
            input_name = str(session.get_inputs()[0].name)
            outputs = session.run(None, {input_name: tensor})
        vector = _select_projection(outputs, self.dimension)
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 1e-12:
            raise VisualIndexError("视觉模型返回了无效向量")
        return [float(value) for value in vector / norm]

    def _get_session(self) -> Any:
        if self._session is None:
            status = self.status()
            if not status["available"]:
                raise VisualIndexError(str(status["reason"]))
            if self._verify_digest and _sha256_file(self.model_path) != MODEL_SHA256:
                raise VisualIndexError("视觉模型 SHA-256 校验失败")
            self._session = self.session_factory(self.model_path)
        return self._session


class LocalVisualIndexService:
    def __init__(
        self,
        store: EmbeddingIndexStore,
        catalog: VisualCatalogProtocol,
        encoder: VisualEncoderProtocol,
    ) -> None:
        self.store = store
        self.catalog = catalog
        self.encoder = encoder

    @property
    def index_id(self) -> str:
        return embedding_index_id(
            self.encoder.model_id,
            self.encoder.model_revision,
            self.encoder.dimension,
        )

    def status(self) -> dict[str, Any]:
        indexes = self.store.list_indexes()
        current = next((item for item in indexes if item["index_id"] == self.index_id), None)
        return {
            "model": self.encoder.status(),
            "current_index": current,
            "type_counts": self.store.type_counts(self.index_id) if current else {},
            "indexes": indexes,
            "truthful_empty": current is None,
        }

    def job(self, payload: Mapping[str, Any], context: VisualJobProgress) -> dict[str, Any]:
        raw_types = payload.get("asset_types", [])
        selected_types = {
            str(value) for value in raw_types if isinstance(raw_types, list) and str(value).strip()
        }
        invalid = selected_types.difference(_asset_types())
        if invalid:
            raise VisualIndexError(f"未知视觉素材类型：{', '.join(sorted(invalid))}")
        assets = self.catalog.discover(selected_types or None)
        max_items = int(payload.get("max_items", 0) or 0)
        if max_items:
            assets = assets[: max(1, min(max_items, 10000))]
        known = self.store.known_hashes(self.index_id)
        pending = [asset for asset in assets if known.get(asset.asset_id) != asset.source_sha256]
        skipped = len(assets) - len(pending)
        failures: list[dict[str, str]] = []
        indexed = 0
        context.update(0, len(pending), f"发现 {len(assets)} 张素材，{len(pending)} 张需要建立索引")
        batch: list[tuple[VisualAsset, list[float]]] = []
        for number, asset in enumerate(pending, start=1):
            try:
                vector = self.encoder.encode_path(asset.path)
            except (OSError, VisualIndexError) as error:
                failures.append({"asset_id": asset.asset_id, "error": str(error)[:500]})
            else:
                batch.append((asset, vector))
            if len(batch) >= 8 or number == len(pending):
                indexed += self._flush(batch)
                batch.clear()
            context.update(number, len(pending), f"已处理 {number}/{len(pending)} 张视觉素材")
        if pending and not indexed and failures:
            raise VisualIndexError(f"视觉索引没有写入任何图片：{failures[0]['error']}")
        pruned = 0
        if not max_items:
            pruned = self.store.prune_assets(
                self.index_id,
                {asset.asset_id for asset in assets},
                asset_types=selected_types or _asset_types(),
            )
        return {
            "index_id": self.index_id,
            "discovered": len(assets),
            "indexed": indexed,
            "skipped_unchanged": skipped,
            "failed": len(failures),
            "failures": failures[:50],
            "pruned": pruned,
            "type_counts": self.store.type_counts(self.index_id),
        }

    def query_bytes(
        self,
        raw: bytes,
        *,
        asset_types: set[str],
        safety: str,
        scope_id: str,
        limit: int,
    ) -> dict[str, Any]:
        vector = self.encoder.encode_bytes(raw)
        current = next(
            (
                item
                for item in self.store.list_indexes()
                if item["index_id"] == self.index_id and int(item["item_count"]) > 0
            ),
            None,
        )
        if current is None:
            raise VisualIndexError("还没有兼容的真实视觉索引，请先建立索引")
        result = self.store.query(
            self.index_id,
            vector,
            asset_types=asset_types,
            limit=min(max(limit * 3, 30), 200),
        )
        matches = result["matches"]
        if safety:
            matches = [item for item in matches if item["metadata"].get("safety") == safety]
        if scope_id:
            matches = [item for item in matches if _matches_scope(item, scope_id)]
        result["matches"] = matches[:limit]
        result["groups"] = _group_matches(result["matches"])
        return result

    def query_source(
        self,
        source_sha256: str,
        *,
        asset_types: set[str],
        safety: str,
        scope_id: str,
        limit: int,
    ) -> dict[str, Any]:
        try:
            result = self.store.query_by_source_hash(
                source_sha256,
                index_id=self.index_id,
                asset_types=asset_types,
                limit=min(max(limit * 3, 30), 200),
            )
        except EmbeddingIndexError as error:
            raise VisualIndexError(str(error)) from error
        matches = result["matches"]
        if safety:
            matches = [item for item in matches if item["metadata"].get("safety") == safety]
        if scope_id:
            matches = [item for item in matches if _matches_scope(item, scope_id)]
        result["matches"] = matches[:limit]
        result["groups"] = _group_matches(result["matches"])
        return result

    def _flush(self, batch: list[tuple[VisualAsset, list[float]]]) -> int:
        if not batch:
            return 0
        items = [asset.embedding_item(vector) for asset, vector in batch]
        expected = {asset.asset_id: asset.source_sha256 for asset, _vector in batch}
        result = self.store.import_batch(
            model_id=self.encoder.model_id,
            model_revision=self.encoder.model_revision,
            dimension=self.encoder.dimension,
            generated_by="mac-local-onnx",
            worker_id="macbook-air",
            items=items,
            expected_hashes=expected,
        )
        return int(result["imported"])


def prepare_clip_image(image: Image.Image) -> np.ndarray:
    prepared = ImageOps.exif_transpose(image).convert("RGB")
    prepared = ImageOps.fit(
        prepared,
        (IMAGE_SIZE, IMAGE_SIZE),
        method=Image.Resampling.BICUBIC,
        centering=(0.5, 0.5),
    )
    array = np.asarray(prepared, dtype=np.float32) / 255.0
    array = (array - CLIP_MEAN) / CLIP_STD
    return np.transpose(array, (2, 0, 1))[None, ...].astype(np.float32, copy=False)


def write_model_info(model_root: Path, *, sha256: str) -> Path:
    model_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "filename": MODEL_FILENAME,
        "size_bytes": MODEL_SIZE_BYTES,
        "sha256": sha256,
        "dimension": MODEL_DIMENSION,
        "input_size": IMAGE_SIZE,
        "runtime": "onnxruntime",
        "purpose": "Mac 本地图像到图像检索，不包含文本编码器",
    }
    path = model_root / "model-info.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _read_model_info(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _create_session(model_path: Path) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(
        str(model_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )


def _select_projection(outputs: list[Any], dimension: int) -> np.ndarray:
    candidates = []
    for output in outputs:
        array = np.asarray(output, dtype=np.float32)
        if array.ndim == 2 and array.shape[0] == 1 and array.shape[1] == dimension:
            candidates.append(array[0])
    if not candidates:
        raise VisualIndexError("视觉模型输出中没有固定的 512 维投影")
    return candidates[0]


def _asset_types() -> set[str]:
    from prompt_hub.visual_assets import VISUAL_ASSET_TYPES

    return set(VISUAL_ASSET_TYPES)


def _group_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {
        "prompt_visual": "提示词视觉",
        "dataset_image": "我的数据集",
        "result_image": "创作结果",
        "comfy_result": "ComfyUI 回流",
        "lora_preview": "LoRA 预览",
        "model_preview": "底模预览",
        "web_visual": "网页视觉资料",
    }
    counts = Counter(str(item.get("asset_type", "")) for item in matches)
    return [
        {
            "key": key,
            "label": labels.get(key, key),
            "count": counts[key],
            "results": [item for item in matches if item.get("asset_type") == key],
        }
        for key in labels
        if counts[key]
    ]


def _matches_scope(item: Mapping[str, Any], scope_id: str) -> bool:
    metadata = item.get("metadata", {})
    if not isinstance(metadata, Mapping):
        return False
    return scope_id in {str(metadata.get("project_id", "")), str(metadata.get("workspace_id", ""))}
