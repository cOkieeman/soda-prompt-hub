from __future__ import annotations

from prompt_hub.database import EntryInput, PromptDatabase


def test_initialize_replace_search_and_stats(tmp_path) -> None:
    database = PromptDatabase(tmp_path / "prompt.sqlite")
    database.initialize()
    with database.connect() as connection:
        database.upsert_source(
            source_id="demo",
            name="Demo",
            source_type="git",
            url="https://example.com/demo",
            local_path=str(tmp_path / "demo"),
            commit_hash="abc123",
            license_name="MIT",
            notes="test",
            connection=connection,
        )
        count = database.replace_source_entries(
            "demo",
            [
                EntryInput(
                    source_id="demo",
                    external_id="style:1",
                    kind="style",
                    title="Gothic Ink",
                    content="dark cathedral ink drawing",
                    category="illustration",
                    model_family="krea2",
                ),
                EntryInput(
                    source_id="demo",
                    external_id="tag:1",
                    kind="tag",
                    title="black dress",
                    content="black dress",
                    category="clothing",
                ),
            ],
            connection=connection,
        )
        connection.commit()

    assert count == 2
    assert database.search("gothic")[0]["title"] == "Gothic Ink"
    assert database.search("black dress", kind="tag")[0]["kind"] == "tag"
    assert database.search("cathedral", model_family="krea2")[0]["source_name"] == "Demo"
    assert database.search("不存在") == []
    assert len(database.search(limit=1)) == 1

    stats = database.stats()
    assert stats["entries"] == 2
    assert stats["sources"] == 1
    assert stats["kinds"] == {"style": 1, "tag": 1}
    assert database.list_sources()[0]["entry_count"] == 2

    mark = database.save_mark(
        source_id="demo",
        external_id="style:1",
        favorite=True,
        rating=5,
        note="My preferred gothic reference",
    )
    assert mark["favorite"] is True
    marked = database.search("gothic")[0]
    assert marked["favorite"] is True
    assert marked["user_rating"] == 5
    assert marked["user_note"] == "My preferred gothic reference"
    assert database.search(favorites_only=True)[0]["external_id"] == "style:1"
    assert database.stats()["personal"] == {"favorites": 1, "rated": 1, "noted": 1}


def test_replace_source_entries_removes_stale_rows(tmp_path) -> None:
    database = PromptDatabase(tmp_path / "prompt.sqlite")
    database.initialize()
    with database.connect() as connection:
        database.upsert_source(
            source_id="demo",
            name="Demo",
            source_type="git",
            url="",
            local_path=str(tmp_path / "demo"),
            commit_hash="1",
            license_name="unknown",
            notes="",
            connection=connection,
        )
        database.replace_source_entries(
            "demo",
            [EntryInput("demo", "old", "tag", "old", "old")],
            connection=connection,
        )
        database.replace_source_entries(
            "demo",
            [EntryInput("demo", "new", "tag", "new", "new")],
            connection=connection,
        )
        connection.commit()

    assert database.search("old") == []
    assert database.search("new")[0]["external_id"] == "new"


def test_mark_survives_source_rebuild(tmp_path) -> None:
    database = PromptDatabase(tmp_path / "prompt.sqlite")
    database.initialize()
    with database.connect() as connection:
        database.upsert_source(
            source_id="demo",
            name="Demo",
            source_type="git",
            url="",
            local_path=str(tmp_path / "demo"),
            commit_hash="1",
            license_name="unknown",
            notes="",
            connection=connection,
        )
        database.replace_source_entries(
            "demo",
            [EntryInput("demo", "stable", "style", "Before", "old content")],
            connection=connection,
        )
        connection.commit()
    database.save_mark(
        source_id="demo",
        external_id="stable",
        favorite=True,
        rating=4,
        note="keep me",
    )
    with database.connect() as connection:
        database.replace_source_entries(
            "demo",
            [EntryInput("demo", "stable", "style", "After", "new content")],
            connection=connection,
        )
        connection.commit()

    rebuilt = database.search("After", favorites_only=True)[0]
    assert rebuilt["favorite"] is True
    assert rebuilt["user_rating"] == 4
    assert rebuilt["user_note"] == "keep me"
