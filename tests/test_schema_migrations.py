from __future__ import annotations

import sqlite3

from prompt_hub.background_jobs import BackgroundJobStore
from prompt_hub.creative import CREATIVE_SCHEMA, CreativeStore
from prompt_hub.database import PromptDatabase
from prompt_hub.embedding_index import EmbeddingIndexStore
from prompt_hub.schema_migrations import schema_versions


def test_main_database_records_component_versions_idempotently(tmp_path) -> None:
    database_path = tmp_path / "prompt.sqlite"
    stores = (
        PromptDatabase(database_path),
        CreativeStore(database_path),
        BackgroundJobStore(database_path),
    )

    for _ in range(2):
        for store in stores:
            store.initialize()

    with sqlite3.connect(database_path) as connection:
        assert schema_versions(connection) == {
            "background_jobs": 1,
            "creative_store": 2,
            "prompt_database": 1,
        }
        count = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == 4


def test_legacy_creative_database_records_lineage_migration(tmp_path) -> None:
    database_path = tmp_path / "legacy.sqlite"
    legacy_schema = CREATIVE_SCHEMA.replace(
        "    lineage_json TEXT NOT NULL DEFAULT '{}',\n",
        "",
    )
    with sqlite3.connect(database_path) as connection:
        connection.executescript(legacy_schema)

    CreativeStore(database_path).initialize()

    with sqlite3.connect(database_path) as connection:
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(creative_projects)").fetchall()
        }
        assert "lineage_json" in columns
        assert schema_versions(connection) == {"creative_store": 2}


def test_embedding_database_has_independent_schema_version(tmp_path) -> None:
    store = EmbeddingIndexStore(tmp_path / "embeddings")

    store.initialize()
    store.initialize()

    with sqlite3.connect(store.path) as connection:
        assert schema_versions(connection) == {"embedding_index": 1}
        count = connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert count == 1
