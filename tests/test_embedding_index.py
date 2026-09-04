from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.embedding_index import EmbeddingIndexError, EmbeddingIndexStore


def _item(asset_id: str, digest: str, vector: list[float]) -> dict[str, object]:
    return {
        "asset_id": asset_id,
        "asset_type": "dataset_image",
        "source_path": f"{asset_id}.png",
        "source_sha256": digest,
        "vector": vector,
        "metadata": {"label": asset_id},
    }


def test_versioned_embedding_index_import_hash_gate_and_query(tmp_path) -> None:
    store = EmbeddingIndexStore(tmp_path / "embeddings")
    store.initialize()
    digest_a = "a" * 64
    digest_b = "b" * 64
    result = store.import_batch(
        model_id="openclip-vit-b-32",
        model_revision="laion2b-v1",
        dimension=3,
        generated_by="5060ti-worker",
        worker_id="training-node",
        items=[_item("asset-a", digest_a, [1, 0, 0]), _item("asset-b", digest_b, [0, 1, 0])],
        expected_hashes={"asset-a": digest_a, "asset-b": digest_b},
    )
    assert result["index_id"].startswith("embedding-")
    assert store.list_indexes()[0]["item_count"] == 2

    queried = store.query(result["index_id"], [0.9, 0.1, 0], limit=2)
    assert [item["asset_id"] for item in queried["matches"]] == ["asset-a", "asset-b"]
    assert queried["matches"][0]["match_reason"] == "visual-semantic cosine similarity"
    assert queried["matches"][0]["source_sha256"] == digest_a

    revised = store.import_batch(
        model_id="openclip-vit-b-32",
        model_revision="laion2b-v2",
        dimension=3,
        generated_by="mac-local",
        worker_id="",
        items=[_item("asset-a", digest_a, [0, 0, 1])],
        expected_hashes={"asset-a": digest_a},
    )
    assert revised["index_id"] != result["index_id"]
    assert len(store.list_indexes()) == 2

    with pytest.raises(EmbeddingIndexError, match="SHA-256"):
        store.import_batch(
            model_id="openclip-vit-b-32",
            model_revision="laion2b-v1",
            dimension=3,
            generated_by="5060ti-worker",
            worker_id="training-node",
            items=[_item("asset-a", digest_b, [1, 0, 0])],
            expected_hashes={"asset-a": digest_a},
        )


def test_embedding_index_api_imports_worker_result_and_queries(settings) -> None:
    digest = "c" * 64
    payload = {
        "task_id": "task-embedding-1",
        "model_id": "siglip-test",
        "model_revision": "revision-1",
        "dimension": 3,
        "generated_by": "5060ti-worker",
        "worker_id": "training-node",
        "items": [
            {
                **_item("asset-api", digest, [0.2, 0.8, 0]),
                "expected_sha256": digest,
            }
        ],
    }
    with TestClient(create_app(settings)) as client:
        imported = client.post("/api/embedding-indexes/import", json=payload)
        assert imported.status_code == 201
        index_id = imported.json()["index_id"]
        indexes = client.get("/api/embedding-indexes").json()
        assert indexes[0]["model_revision"] == "revision-1"
        queried = client.post(
            f"/api/embedding-indexes/{index_id}/query",
            json={"vector": [0, 1, 0], "asset_types": ["dataset_image"], "limit": 5},
        )
        assert queried.status_code == 200
        assert queried.json()["matches"][0]["asset_id"] == "asset-api"

        mismatched = dict(payload)
        mismatched["items"] = [
            {
                **_item("asset-api-2", "d" * 64, [1, 0, 0]),
                "expected_sha256": digest,
            }
        ]
        assert client.post("/api/embedding-indexes/import", json=mismatched).status_code == 422


def test_visual_clusters_group_real_vectors_and_filter_asset_types(tmp_path) -> None:
    store = EmbeddingIndexStore(tmp_path / "embeddings")
    store.initialize()
    digests = {name: char * 64 for name, char in (("a", "a"), ("b", "b"), ("c", "c"))}
    items = [
        _item("a", digests["a"], [1.0, 0.0, 0.0]),
        _item("b", digests["b"], [0.99, 0.1, 0.0]),
        {
            **_item("c", digests["c"], [0.0, 1.0, 0.0]),
            "asset_type": "lora_preview",
        },
    ]
    imported = store.import_batch(
        model_id="test-clip",
        model_revision="revision-1",
        dimension=3,
        generated_by="mac-local",
        worker_id="macbook-air",
        items=items,
        expected_hashes=dict(digests),
    )

    clustered = store.clusters(imported["index_id"], threshold=0.9)
    assert [cluster["size"] for cluster in clustered["clusters"]] == [2, 1]
    assert {item["asset_id"] for item in clustered["clusters"][0]["items"]} == {"a", "b"}

    filtered = store.clusters(
        imported["index_id"],
        asset_types={"lora_preview"},
        threshold=0.9,
    )
    assert len(filtered["clusters"]) == 1
    assert filtered["clusters"][0]["items"][0]["asset_id"] == "c"
