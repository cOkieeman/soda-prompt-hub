from __future__ import annotations

from fastapi.testclient import TestClient

from prompt_hub.api import create_app
from prompt_hub.database import PromptDatabase
from prompt_hub.importers import import_all


def _embedding_item(
    asset_id: str,
    digest: str,
    vector: list[float],
    filename: str,
) -> dict[str, object]:
    return {
        "asset_id": asset_id,
        "asset_type": "dataset_image",
        "source_path": filename,
        "source_sha256": digest,
        "expected_sha256": digest,
        "vector": vector,
        "metadata": {"filename": filename},
    }


def test_hybrid_search_keeps_keyword_results_when_embeddings_are_absent(
    source_tree,
    monkeypatch,
) -> None:
    monkeypatch.setattr("prompt_hub.importers._git_commit", lambda _path: "deadbeef")
    database = PromptDatabase(source_tree.database_path)
    import_all(source_tree, database)
    with TestClient(create_app(source_tree)) as client:
        response = client.post(
            "/api/hybrid-search",
            json={"query": "gothic", "limit": 10},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["semantic"]["status"] == "not_requested"
        groups = {item["key"]: item for item in payload["groups"]}
        assert groups["prompt_library"]["results"][0]["title"] == "Gothic Ink"
        assert groups["prompt_library"]["results"][0]["match_type"] == "keyword"
        assert groups["visual_references"]["results"][0]["visuals"][0]["thumbnail_url"]
        assert groups["my_datasets"]["results"] == []
        assert groups["windows_loras"]["results"] == []


def test_hybrid_search_uses_real_compatible_index_and_source_image_query(settings) -> None:
    digest_a = "a" * 64
    digest_b = "b" * 64
    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/embedding-indexes/import",
            json={
                "model_id": "siglip-so400m",
                "model_revision": "revision-locked",
                "dimension": 3,
                "generated_by": "5060ti-worker",
                "worker_id": "training-node",
                "items": [
                    _embedding_item("asset-a", digest_a, [1, 0, 0], "a.png"),
                    _embedding_item("asset-b", digest_b, [0.9, 0.1, 0], "b.png"),
                ],
            },
        )
        assert imported.status_code == 201

        mixed = client.post(
            "/api/hybrid-search",
            json={"query": "portrait", "vector": [1, 0, 0], "limit": 10},
        )
        assert mixed.status_code == 200
        payload = mixed.json()
        assert payload["semantic"]["status"] == "active"
        groups = {item["key"]: item for item in payload["groups"]}
        assert [item["asset_id"] for item in groups["my_datasets"]["results"]] == [
            "asset-a",
            "asset-b",
        ]
        assert groups["my_datasets"]["results"][0]["match_reason"].startswith("视觉相似度")

        similar = client.post(
            "/api/hybrid-search/by-source",
            json={"source_sha256": digest_a, "limit": 10},
        )
        assert similar.status_code == 200
        similar_groups = {item["key"]: item for item in similar.json()["groups"]}
        assert [item["asset_id"] for item in similar_groups["my_datasets"]["results"]] == [
            "asset-b"
        ]
        assert similar.json()["semantic"]["query_asset"]["asset_id"] == "asset-a"
        status = client.get(
            "/api/hybrid-search/source-status",
            params={"source_sha256": digest_a},
        )
        assert status.status_code == 200
        assert status.json()["available"] is True
        assert status.json()["indexes"][0]["model_revision"] == "revision-locked"

        missing = client.post(
            "/api/hybrid-search/by-source",
            json={"source_sha256": "f" * 64},
        )
        assert missing.status_code == 404


def test_hybrid_search_does_not_fake_incompatible_semantic_results(settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/hybrid-search",
            json={"query": "portrait", "vector": [1, 0, 0, 0]},
        )
        assert response.status_code == 200
        assert response.json()["semantic"]["status"] == "unavailable"
        assert "未生成伪结果" in response.json()["semantic"]["message"]


def test_hybrid_search_includes_windows_lora_metadata_without_copying_weights(settings) -> None:
    with TestClient(create_app(settings)) as client:
        imported = client.post(
            "/api/windows-loras/import",
            json={
                "snapshot_id": "hybrid-loras-v1",
                "worker_id": "training-node",
                "items": [
                    {
                        "lora_id": "soda-character",
                        "name": "Soda Character",
                        "relative_path": "characters/soda.safetensors",
                        "base_model": "Anima",
                        "trigger_words": ["soda_character"],
                        "tags": ["silver_hair"],
                    }
                ],
            },
        )
        assert imported.status_code == 201
        result = client.post(
            "/api/hybrid-search",
            json={"query": "soda_character"},
        ).json()
        groups = {item["key"]: item for item in result["groups"]}
        assert groups["windows_loras"]["results"][0]["title"] == "Soda Character"
        assert groups["windows_loras"]["results"][0]["source_name"] == "Windows LoRA Manager"
        assert "weight_bytes" not in groups["windows_loras"]["results"][0]
