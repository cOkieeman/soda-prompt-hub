from __future__ import annotations

import hashlib
import heapq
import json
import math
import re
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

import numpy as np

MAX_EMBEDDING_DIMENSION = 8192
MAX_IMPORT_ITEMS = 100000
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class EmbeddingIndexError(ValueError):
    pass


class EmbeddingIndexStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / "embeddings.sqlite"
        self._lock = RLock()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS embedding_indexes (
                    index_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    model_revision TEXT NOT NULL,
                    dimension INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS embeddings (
                    index_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    generated_by TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    vector BLOB NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (index_id, asset_id),
                    FOREIGN KEY (index_id) REFERENCES embedding_indexes(index_id)
                );
                CREATE INDEX IF NOT EXISTS embeddings_type_idx
                    ON embeddings(index_id, asset_type);
                """
            )

    def list_indexes(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT i.*, COUNT(e.asset_id) AS item_count
                FROM embedding_indexes i
                LEFT JOIN embeddings e ON e.index_id = i.index_id
                GROUP BY i.index_id
                ORDER BY i.updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def compatible_index(self, dimension: int) -> dict[str, Any] | None:
        """Return the newest real index matching a caller-provided vector dimension."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT i.*, COUNT(e.asset_id) AS item_count
                FROM embedding_indexes i
                JOIN embeddings e ON e.index_id = i.index_id
                WHERE i.dimension = ?
                GROUP BY i.index_id
                ORDER BY i.updated_at DESC
                LIMIT 1
                """,
                (dimension,),
            ).fetchone()
        return dict(row) if row is not None else None

    def source_status(self, source_sha256: str) -> dict[str, Any]:
        digest = source_sha256.strip().lower()
        if not SHA256_RE.fullmatch(digest):
            raise EmbeddingIndexError("源 SHA-256 无效")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT i.index_id, i.model_id, i.model_revision, i.dimension,
                       i.updated_at, e.asset_id, e.asset_type
                FROM embeddings e
                JOIN embedding_indexes i ON i.index_id = e.index_id
                WHERE e.source_sha256 = ?
                ORDER BY i.updated_at DESC
                """,
                (digest,),
            ).fetchall()
        return {
            "source_sha256": digest,
            "available": bool(rows),
            "indexes": [dict(row) for row in rows],
        }

    def import_batch(
        self,
        *,
        model_id: str,
        model_revision: str,
        dimension: int,
        generated_by: str,
        worker_id: str,
        items: Iterable[Mapping[str, Any]],
        expected_hashes: Mapping[str, str],
    ) -> dict[str, Any]:
        model_id = model_id.strip()[:300]
        model_revision = model_revision.strip()[:300]
        generated_by = generated_by.strip()[:120]
        worker_id = worker_id.strip()[:160]
        if not model_id or not model_revision or not generated_by:
            raise EmbeddingIndexError("model_id、model_revision 与 generated_by 不能为空")
        if dimension <= 0 or dimension > MAX_EMBEDDING_DIMENSION:
            raise EmbeddingIndexError("Embedding dimension 无效")
        prepared = []
        for raw in items:
            if len(prepared) >= MAX_IMPORT_ITEMS:
                raise EmbeddingIndexError("单次导入 embedding 数量过多")
            asset_id = str(raw.get("asset_id", "")).strip()[:500]
            source_sha256 = str(raw.get("source_sha256", "")).strip().lower()
            expected = str(expected_hashes.get(asset_id, "")).strip().lower()
            if not asset_id or not SHA256_RE.fullmatch(source_sha256):
                raise EmbeddingIndexError("Embedding item 缺少有效 asset_id 或 source_sha256")
            if not expected or source_sha256 != expected:
                raise EmbeddingIndexError(f"源 SHA-256 回验失败: {asset_id}")
            vector = _normalize_vector(raw.get("vector"), dimension)
            metadata = raw.get("metadata", {})
            prepared.append(
                (
                    asset_id,
                    str(raw.get("asset_type", "dataset_image"))[:80],
                    str(raw.get("source_path", ""))[:4096],
                    source_sha256,
                    vector.tobytes(),
                    json.dumps(metadata if isinstance(metadata, dict) else {}, ensure_ascii=False),
                )
            )
        if not prepared:
            raise EmbeddingIndexError("没有可导入的 embedding")
        index_id = _index_id(model_id, model_revision, dimension)
        now = _now()
        with self._lock, self.connect() as connection:
            connection.execute(
                """
                INSERT INTO embedding_indexes(
                    index_id, model_id, model_revision, dimension, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(index_id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (index_id, model_id, model_revision, dimension, now, now),
            )
            connection.executemany(
                """
                INSERT INTO embeddings(
                    index_id, asset_id, asset_type, source_path, source_sha256,
                    generated_by, worker_id, vector, metadata_json, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(index_id, asset_id) DO UPDATE SET
                    asset_type = excluded.asset_type,
                    source_path = excluded.source_path,
                    source_sha256 = excluded.source_sha256,
                    generated_by = excluded.generated_by,
                    worker_id = excluded.worker_id,
                    vector = excluded.vector,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                [
                    (index_id, *item[:4], generated_by, worker_id, *item[4:], now)
                    for item in prepared
                ],
            )
            connection.commit()
        return {
            "index_id": index_id,
            "model_id": model_id,
            "model_revision": model_revision,
            "dimension": dimension,
            "imported": len(prepared),
            "generated_by": generated_by,
            "worker_id": worker_id,
        }

    def query(
        self,
        index_id: str,
        vector: object,
        *,
        asset_types: Iterable[str] = (),
        limit: int = 30,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            index = connection.execute(
                "SELECT * FROM embedding_indexes WHERE index_id = ?",
                (index_id,),
            ).fetchone()
            if index is None:
                raise EmbeddingIndexError("Embedding index not found")
            query_vector = _normalize_vector(vector, int(index["dimension"]))
            types = [str(value)[:80] for value in asset_types if str(value).strip()]
            sql = "SELECT * FROM embeddings WHERE index_id = ?"
            parameters: list[Any] = [index_id]
            if types:
                sql += f" AND asset_type IN ({','.join('?' for _ in types)})"
                parameters.extend(types)
            rows = connection.execute(sql, parameters).fetchall()
        scored = heapq.nlargest(
            max(1, min(limit, 200)),
            (
                (
                    float(np.dot(query_vector, np.frombuffer(row["vector"], dtype=np.float32))),
                    row,
                )
                for row in rows
            ),
            key=lambda item: item[0],
        )
        return {
            "index": dict(index),
            "matches": [
                {
                    "asset_id": str(row["asset_id"]),
                    "asset_type": str(row["asset_type"]),
                    "source_path": str(row["source_path"]),
                    "source_sha256": str(row["source_sha256"]),
                    "generated_by": str(row["generated_by"]),
                    "worker_id": str(row["worker_id"]),
                    "score": round(score, 7),
                    "match_reason": "visual-semantic cosine similarity",
                    "metadata": json.loads(str(row["metadata_json"])),
                }
                for score, row in scored
            ],
        }

    def query_by_source_hash(
        self,
        source_sha256: str,
        *,
        index_id: str = "",
        asset_types: Iterable[str] = (),
        limit: int = 30,
    ) -> dict[str, Any]:
        digest = source_sha256.strip().lower()
        if not SHA256_RE.fullmatch(digest):
            raise EmbeddingIndexError("源 SHA-256 无效")
        with self.connect() as connection:
            if index_id:
                row = connection.execute(
                    """
                    SELECT e.*, i.model_id, i.model_revision, i.dimension,
                           i.created_at AS index_created_at, i.updated_at AS index_updated_at
                    FROM embeddings e
                    JOIN embedding_indexes i ON i.index_id = e.index_id
                    WHERE e.source_sha256 = ? AND e.index_id = ?
                    ORDER BY i.updated_at DESC
                    LIMIT 1
                    """,
                    (digest, index_id),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT e.*, i.model_id, i.model_revision, i.dimension,
                           i.created_at AS index_created_at, i.updated_at AS index_updated_at
                    FROM embeddings e
                    JOIN embedding_indexes i ON i.index_id = e.index_id
                    WHERE e.source_sha256 = ?
                    ORDER BY i.updated_at DESC
                    LIMIT 1
                    """,
                    (digest,),
                ).fetchone()
        if row is None:
            raise EmbeddingIndexError("这张源图尚未进入真实视觉索引")
        queried = self.query(
            str(row["index_id"]),
            np.frombuffer(row["vector"], dtype=np.float32),
            asset_types=asset_types,
            limit=min(max(limit + 10, 20), 200),
        )
        queried["query_asset"] = {
            "asset_id": str(row["asset_id"]),
            "asset_type": str(row["asset_type"]),
            "source_path": str(row["source_path"]),
            "source_sha256": str(row["source_sha256"]),
            "metadata": json.loads(str(row["metadata_json"])),
        }
        queried["matches"] = [
            item for item in queried["matches"] if item["source_sha256"] != digest
        ][: max(1, min(limit, 200))]
        return queried


def _index_id(model_id: str, revision: str, dimension: int) -> str:
    digest = hashlib.sha256(f"{model_id}\0{revision}\0{dimension}".encode()).hexdigest()[:20]
    return f"embedding-{digest}"


def _normalize_vector(value: object, dimension: int) -> np.ndarray:
    try:
        vector = np.asarray(value, dtype=np.float32)
    except (TypeError, ValueError) as error:
        raise EmbeddingIndexError("Embedding vector 不是有效浮点数组") from error
    if vector.ndim != 1 or vector.size != dimension or not np.isfinite(vector).all():
        raise EmbeddingIndexError("Embedding vector 维度或数值无效")
    norm = float(np.linalg.norm(vector))
    if not math.isfinite(norm) or norm <= 0:
        raise EmbeddingIndexError("Embedding vector 不能是零向量")
    return np.asarray(vector / norm, dtype=np.float32)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
