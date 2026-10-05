from __future__ import annotations

from fastapi.testclient import TestClient

from prompt_hub import __version__
from prompt_hub.api import create_app
from prompt_hub.release_info import release_channel, system_version_info, worker_compatibility


def test_release_channel_follows_pep440_stage() -> None:
    assert release_channel("1.1.0.dev1") == "development"
    assert release_channel("1.1.0rc2") == "candidate"
    assert release_channel("1.1.0") == "stable"


def test_system_version_reports_code_schema_and_worker(settings) -> None:
    with TestClient(create_app(settings)) as client:
        health = client.get("/api/health").json()
        version = client.get("/api/system/version").json()

    assert health["version"] == __version__
    assert health["release_channel"] == release_channel()
    assert version["product"] == {
        "name": "Soda Prompt Hub",
        "version": __version__,
        "release_channel": release_channel(),
        "release_channel_label": "正式版",
    }
    assert version["data"]["initialized"] is True
    assert version["data"]["components"] == {
        "background_jobs": 1,
        "creative_store": 2,
        "danbooru_tags": 1,
        "gallery": 2,
        "prompt_database": 1,
        "scene_plan_store": 1,
        "tag_locale": 1,
    }
    assert version["worker"]["bundled_version"] == __version__
    assert version["worker"]["protocol_version"] == "soda-compute-bridge-v2"


def test_system_version_does_not_create_missing_databases(settings) -> None:
    version = system_version_info(settings)

    assert version["data"]["initialized"] is False
    assert version["embedding"]["initialized"] is False
    assert not settings.database_path.exists()
    assert not (settings.embedding_index_root / "embeddings.sqlite").exists()


def test_worker_compatibility_distinguishes_protocol_and_version() -> None:
    current = worker_compatibility(
        {
            "protocol_version": "soda-compute-bridge-v2",
            "worker_version": __version__,
        }
    )
    legacy = worker_compatibility({"protocol_version": "soda-compute-bridge-v2"})
    incompatible = worker_compatibility(
        {"protocol_version": "soda-compute-bridge-v1", "worker_version": "0.9.0"}
    )

    assert current["state"] == "compatible"
    assert current["compatible"] is True
    assert legacy["state"] == "update_recommended"
    assert legacy["compatible"] is True
    assert incompatible["state"] == "incompatible"
    assert incompatible["compatible"] is False
