from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from prompt_hub.oc_manager import OCImportBundle, character_search_text, lore_search_text

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    local_path TEXT NOT NULL,
    commit_hash TEXT NOT NULL DEFAULT '',
    license TEXT NOT NULL DEFAULT 'unknown',
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    negative_content TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '',
    model_family TEXT NOT NULL DEFAULT '',
    safety TEXT NOT NULL DEFAULT 'sfw',
    language TEXT NOT NULL DEFAULT 'en',
    source_path TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    content_hash TEXT NOT NULL,
    rating REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_entries_kind ON entries(kind);
CREATE INDEX IF NOT EXISTS idx_entries_source ON entries(source_id);
CREATE INDEX IF NOT EXISTS idx_entries_category ON entries(category);
CREATE INDEX IF NOT EXISTS idx_entries_model_family ON entries(model_family);
CREATE INDEX IF NOT EXISTS idx_entries_safety ON entries(safety);

CREATE TABLE IF NOT EXISTS user_marks (
    source_id TEXT NOT NULL,
    external_id TEXT NOT NULL,
    favorite INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1)),
    rating INTEGER CHECK (rating IS NULL OR rating BETWEEN 1 AND 5),
    note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_user_marks_favorite ON user_marks(favorite);
CREATE INDEX IF NOT EXISTS idx_user_marks_rating ON user_marks(rating);

CREATE TABLE IF NOT EXISTS oc_imports (
    import_hash TEXT PRIMARY KEY,
    format_name TEXT NOT NULL,
    source_file TEXT NOT NULL,
    character_count INTEGER NOT NULL,
    world_count INTEGER NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oc_characters (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    world TEXT NOT NULL DEFAULT '',
    gender TEXT NOT NULL DEFAULT '',
    age TEXT NOT NULL DEFAULT '',
    race TEXT NOT NULL DEFAULT '',
    affiliation TEXT NOT NULL DEFAULT '',
    identity TEXT NOT NULL DEFAULT '',
    residence TEXT NOT NULL DEFAULT '',
    faction TEXT NOT NULL DEFAULT '',
    birthplace TEXT NOT NULL DEFAULT '',
    avatar TEXT NOT NULL DEFAULT '',
    sheet_role TEXT NOT NULL DEFAULT 'pc',
    player_name TEXT NOT NULL DEFAULT '',
    story TEXT NOT NULL DEFAULT '',
    search_text TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    source_file TEXT NOT NULL,
    import_hash TEXT NOT NULL REFERENCES oc_imports(import_hash),
    source_created_at TEXT NOT NULL DEFAULT '',
    source_updated_at TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_oc_characters_name ON oc_characters(name);
CREATE INDEX IF NOT EXISTS idx_oc_characters_world ON oc_characters(world);

CREATE TABLE IF NOT EXISTS oc_prompts (
    character_id TEXT NOT NULL REFERENCES oc_characters(character_id) ON DELETE CASCADE,
    prompt_id TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (character_id, prompt_id)
);

CREATE INDEX IF NOT EXISTS idx_oc_prompts_character ON oc_prompts(character_id);

CREATE TABLE IF NOT EXISTS oc_worlds (
    world_name TEXT PRIMARY KEY,
    world_id TEXT NOT NULL DEFAULT '',
    system TEXT NOT NULL DEFAULT 'generic',
    color TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL,
    source_file TEXT NOT NULL,
    import_hash TEXT NOT NULL REFERENCES oc_imports(import_hash),
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oc_lore (
    world_name TEXT PRIMARY KEY,
    search_text TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    source_file TEXT NOT NULL,
    import_hash TEXT NOT NULL REFERENCES oc_imports(import_hash),
    imported_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    title,
    content,
    category,
    content='entries',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE VIRTUAL TABLE IF NOT EXISTS oc_characters_fts USING fts5(
    name,
    world,
    search_text,
    content='oc_characters',
    content_rowid='row_id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, title, content, category)
    VALUES (new.id, new.title, new.content, new.category);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, content, category)
    VALUES ('delete', old.id, old.title, old.content, old.category);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, title, content, category)
    VALUES ('delete', old.id, old.title, old.content, old.category);
    INSERT INTO entries_fts(rowid, title, content, category)
    VALUES (new.id, new.title, new.content, new.category);
END;

CREATE TRIGGER IF NOT EXISTS oc_characters_ai AFTER INSERT ON oc_characters BEGIN
    INSERT INTO oc_characters_fts(rowid, name, world, search_text)
    VALUES (new.row_id, new.name, new.world, new.search_text);
END;

CREATE TRIGGER IF NOT EXISTS oc_characters_ad AFTER DELETE ON oc_characters BEGIN
    INSERT INTO oc_characters_fts(oc_characters_fts, rowid, name, world, search_text)
    VALUES ('delete', old.row_id, old.name, old.world, old.search_text);
END;

CREATE TRIGGER IF NOT EXISTS oc_characters_au AFTER UPDATE ON oc_characters BEGIN
    INSERT INTO oc_characters_fts(oc_characters_fts, rowid, name, world, search_text)
    VALUES ('delete', old.row_id, old.name, old.world, old.search_text);
    INSERT INTO oc_characters_fts(rowid, name, world, search_text)
    VALUES (new.row_id, new.name, new.world, new.search_text);
END;
"""

_TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class EntryInput:
    source_id: str
    external_id: str
    kind: str
    title: str
    content: str
    negative_content: str = ""
    category: str = ""
    model_family: str = ""
    safety: str = "sfw"
    language: str = "en"
    source_path: str = ""
    source_url: str = ""
    metadata: Mapping[str, Any] | None = None


class PromptDatabase:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.commit()

    def upsert_source(
        self,
        *,
        source_id: str,
        name: str,
        source_type: str,
        url: str,
        local_path: str,
        commit_hash: str,
        license_name: str,
        notes: str,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        now = _now()
        values = (
            source_id,
            name,
            source_type,
            url,
            local_path,
            commit_hash,
            license_name,
            notes,
            now,
        )
        statement = """
            INSERT INTO sources (
                source_id, name, source_type, url, local_path, commit_hash,
                license, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                name=excluded.name,
                source_type=excluded.source_type,
                url=excluded.url,
                local_path=excluded.local_path,
                commit_hash=excluded.commit_hash,
                license=excluded.license,
                notes=excluded.notes,
                updated_at=excluded.updated_at
        """
        if connection is not None:
            connection.execute(statement, values)
            return
        with self.connect() as own_connection:
            own_connection.execute(statement, values)
            own_connection.commit()

    def replace_source_entries(
        self,
        source_id: str,
        entries: list[EntryInput],
        *,
        connection: sqlite3.Connection,
    ) -> int:
        connection.execute("DELETE FROM entries WHERE source_id = ?", (source_id,))
        for entry in entries:
            self._upsert_entry(entry, connection)
        return len(entries)

    def _upsert_entry(self, entry: EntryInput, connection: sqlite3.Connection) -> None:
        now = _now()
        metadata_json = json.dumps(entry.metadata or {}, ensure_ascii=False, sort_keys=True)
        content_hash = hashlib.sha256(
            "\n".join(
                (
                    entry.title,
                    entry.content,
                    entry.negative_content,
                    entry.category,
                    entry.model_family,
                    entry.safety,
                )
            ).encode()
        ).hexdigest()
        connection.execute(
            """
            INSERT INTO entries (
                source_id, external_id, kind, title, content, negative_content,
                category, model_family, safety, language, source_path, source_url,
                metadata_json, content_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, external_id) DO UPDATE SET
                kind=excluded.kind,
                title=excluded.title,
                content=excluded.content,
                negative_content=excluded.negative_content,
                category=excluded.category,
                model_family=excluded.model_family,
                safety=excluded.safety,
                language=excluded.language,
                source_path=excluded.source_path,
                source_url=excluded.source_url,
                metadata_json=excluded.metadata_json,
                content_hash=excluded.content_hash,
                updated_at=excluded.updated_at
            """,
            (
                entry.source_id,
                entry.external_id,
                entry.kind,
                entry.title,
                entry.content,
                entry.negative_content,
                entry.category,
                entry.model_family,
                entry.safety,
                entry.language,
                entry.source_path,
                entry.source_url,
                metadata_json,
                content_hash,
                now,
                now,
            ),
        )

    def search(
        self,
        query: str = "",
        *,
        kind: str = "",
        source_id: str = "",
        model_family: str = "",
        safety: str = "",
        favorites_only: bool = False,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 50)
        filters, values = _search_filters(
            kind=kind,
            source_id=source_id,
            model_family=model_family,
            safety=safety,
            favorites_only=favorites_only,
        )
        where = " AND ".join(filters)
        if where:
            where = " AND " + where

        with self.connect() as connection:
            rows: list[sqlite3.Row] = []
            fts_query = _to_fts_query(query)
            if fts_query:
                try:
                    rows = connection.execute(
                        f"""
                        SELECT e.*, s.name AS source_name,
                               COALESCE(um.favorite, 0) AS favorite,
                               um.rating AS user_rating,
                               COALESCE(um.note, '') AS user_note,
                               bm25(entries_fts, 4.0, 1.0, 1.5) AS relevance
                        FROM entries_fts
                        JOIN entries e ON e.id = entries_fts.rowid
                        JOIN sources s ON s.source_id = e.source_id
                        LEFT JOIN user_marks um
                          ON um.source_id = e.source_id AND um.external_id = e.external_id
                        WHERE entries_fts MATCH ? {where}
                        ORDER BY COALESCE(um.favorite, 0) DESC, um.rating DESC,
                                 relevance, e.rating DESC, e.id DESC
                        LIMIT ?
                        """,
                        [fts_query, *values, safe_limit],
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            if query and not rows:
                like_value = f"%{query.strip()}%"
                rows = connection.execute(
                    f"""
                    SELECT e.*, s.name AS source_name,
                           COALESCE(um.favorite, 0) AS favorite,
                           um.rating AS user_rating,
                           COALESCE(um.note, '') AS user_note,
                           999.0 AS relevance
                    FROM entries e
                    JOIN sources s ON s.source_id = e.source_id
                    LEFT JOIN user_marks um
                      ON um.source_id = e.source_id AND um.external_id = e.external_id
                    WHERE (e.title LIKE ? OR e.content LIKE ? OR e.category LIKE ?) {where}
                    ORDER BY COALESCE(um.favorite, 0) DESC, um.rating DESC,
                             e.rating DESC, e.id DESC
                    LIMIT ?
                    """,
                    [like_value, like_value, like_value, *values, safe_limit],
                ).fetchall()
            elif not query:
                rows = connection.execute(
                    f"""
                    SELECT e.*, s.name AS source_name,
                           COALESCE(um.favorite, 0) AS favorite,
                           um.rating AS user_rating,
                           COALESCE(um.note, '') AS user_note,
                           999.0 AS relevance
                    FROM entries e
                    JOIN sources s ON s.source_id = e.source_id
                    LEFT JOIN user_marks um
                      ON um.source_id = e.source_id AND um.external_id = e.external_id
                    WHERE 1=1 {where}
                    ORDER BY COALESCE(um.favorite, 0) DESC, um.rating DESC,
                             e.rating DESC, e.id DESC
                    LIMIT ?
                    """,
                    [*values, safe_limit],
                ).fetchall()
        return [_row_to_dict(row) for row in rows]

    def save_mark(
        self,
        *,
        source_id: str,
        external_id: str,
        favorite: bool,
        rating: int | None,
        note: str,
    ) -> dict[str, Any]:
        clean_note = note.strip()
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM entries WHERE source_id = ? AND external_id = ?",
                (source_id, external_id),
            ).fetchone()
            if exists is None:
                msg = f"Unknown entry: {source_id}/{external_id}"
                raise KeyError(msg)
            if not favorite and rating is None and not clean_note:
                connection.execute(
                    "DELETE FROM user_marks WHERE source_id = ? AND external_id = ?",
                    (source_id, external_id),
                )
                connection.commit()
                return _mark_dict(
                    source_id=source_id,
                    external_id=external_id,
                    favorite=favorite,
                    rating=rating,
                    note=clean_note,
                )
            connection.execute(
                """
                INSERT INTO user_marks (
                    source_id, external_id, favorite, rating, note, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, external_id) DO UPDATE SET
                    favorite=excluded.favorite,
                    rating=excluded.rating,
                    note=excluded.note,
                    updated_at=excluded.updated_at
                """,
                (source_id, external_id, int(favorite), rating, clean_note, _now()),
            )
            connection.commit()
        return _mark_dict(
            source_id=source_id,
            external_id=external_id,
            favorite=favorite,
            rating=rating,
            note=clean_note,
        )

    def import_oc_manager(
        self,
        bundle: OCImportBundle,
        *,
        source_file: str,
        import_hash: str,
    ) -> dict[str, Any]:
        imported_at = _now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO oc_imports (
                    import_hash, format_name, source_file, character_count,
                    world_count, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(import_hash) DO UPDATE SET imported_at=excluded.imported_at
                """,
                (
                    import_hash,
                    bundle.format_name,
                    source_file,
                    len(bundle.characters),
                    len(bundle.worlds),
                    imported_at,
                ),
            )
            for character in bundle.characters:
                self._upsert_oc_character(
                    connection,
                    character,
                    source_file=source_file,
                    import_hash=import_hash,
                    imported_at=imported_at,
                )
            self._upsert_oc_worlds(
                connection,
                bundle,
                source_file=source_file,
                import_hash=import_hash,
                imported_at=imported_at,
            )
            self._upsert_oc_lore(
                connection,
                bundle,
                source_file=source_file,
                import_hash=import_hash,
                imported_at=imported_at,
            )
            connection.commit()
        return {
            "format": bundle.format_name,
            "characters_imported": len(bundle.characters),
            "worlds_imported": len(bundle.worlds),
            "lore_worlds_imported": len(bundle.lore),
            "source_file": source_file,
            "import_hash": import_hash,
            "stats": self.oc_stats(),
        }

    def _upsert_oc_character(
        self,
        connection: sqlite3.Connection,
        character: Mapping[str, Any],
        *,
        source_file: str,
        import_hash: str,
        imported_at: str,
    ) -> None:
        character_id = _string(character.get("id"))
        connection.execute(
            """
            INSERT INTO oc_characters (
                character_id, name, world, gender, age, race, affiliation, identity,
                residence, faction, birthplace, avatar, sheet_role, player_name, story,
                search_text, raw_json, source_file, import_hash, source_created_at,
                source_updated_at, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(character_id) DO UPDATE SET
                name=excluded.name,
                world=excluded.world,
                gender=excluded.gender,
                age=excluded.age,
                race=excluded.race,
                affiliation=excluded.affiliation,
                identity=excluded.identity,
                residence=excluded.residence,
                faction=excluded.faction,
                birthplace=excluded.birthplace,
                avatar=excluded.avatar,
                sheet_role=excluded.sheet_role,
                player_name=excluded.player_name,
                story=excluded.story,
                search_text=excluded.search_text,
                raw_json=excluded.raw_json,
                source_file=excluded.source_file,
                import_hash=excluded.import_hash,
                source_created_at=excluded.source_created_at,
                source_updated_at=excluded.source_updated_at,
                imported_at=excluded.imported_at
            """,
            (
                character_id,
                _string(character.get("name")),
                _string(character.get("world")),
                _string(character.get("gender")),
                _string(character.get("age")),
                _string(character.get("race")),
                _string(character.get("affiliation")),
                _string(character.get("identity")),
                _string(character.get("residence")),
                _string(character.get("faction")),
                _string(character.get("birthplace")),
                _string(character.get("avatar")),
                _string(character.get("sheetRole"), "pc"),
                _string(character.get("playerName")),
                _string(character.get("story")),
                character_search_text(character),
                json.dumps(character, ensure_ascii=False, sort_keys=True),
                source_file,
                import_hash,
                _string(character.get("createdAt")),
                _string(character.get("updatedAt")),
                imported_at,
            ),
        )
        connection.execute("DELETE FROM oc_prompts WHERE character_id = ?", (character_id,))
        for prompt in _mapping_items(character.get("prompts")):
            text = _string(prompt.get("text"))
            if not text:
                continue
            prompt_id = _string(prompt.get("id")) or hashlib.sha256(text.encode()).hexdigest()[:16]
            connection.execute(
                """
                INSERT OR REPLACE INTO oc_prompts (
                    character_id, prompt_id, label, text, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    character_id,
                    prompt_id,
                    _string(prompt.get("label")),
                    text,
                    _string(prompt.get("createdAt")),
                ),
            )

    def _upsert_oc_worlds(
        self,
        connection: sqlite3.Connection,
        bundle: OCImportBundle,
        *,
        source_file: str,
        import_hash: str,
        imported_at: str,
    ) -> None:
        explicit_names: set[str] = set()
        for world in bundle.worlds:
            name = _string(world.get("name"))
            if not name:
                continue
            explicit_names.add(name)
            connection.execute(
                """
                INSERT INTO oc_worlds (
                    world_name, world_id, system, color, raw_json,
                    source_file, import_hash, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(world_name) DO UPDATE SET
                    world_id=excluded.world_id,
                    system=excluded.system,
                    color=excluded.color,
                    raw_json=excluded.raw_json,
                    source_file=excluded.source_file,
                    import_hash=excluded.import_hash,
                    imported_at=excluded.imported_at
                """,
                (
                    name,
                    _string(world.get("id")),
                    _string(world.get("system"), "generic"),
                    _string(world.get("color")),
                    json.dumps(world, ensure_ascii=False, sort_keys=True),
                    source_file,
                    import_hash,
                    imported_at,
                ),
            )
        inferred_names = (
            {_string(character.get("world")) for character in bundle.characters}
            - {""}
            - explicit_names
        )
        for name in inferred_names:
            connection.execute(
                """
                INSERT INTO oc_worlds (
                    world_name, raw_json, source_file, import_hash, imported_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(world_name) DO NOTHING
                """,
                (
                    name,
                    json.dumps({"name": name}, ensure_ascii=False),
                    source_file,
                    import_hash,
                    imported_at,
                ),
            )

    def _upsert_oc_lore(
        self,
        connection: sqlite3.Connection,
        bundle: OCImportBundle,
        *,
        source_file: str,
        import_hash: str,
        imported_at: str,
    ) -> None:
        world_ids = {
            _string(world.get("id")): _string(world.get("name"))
            for world in bundle.worlds
            if _string(world.get("id")) and _string(world.get("name"))
        }
        for raw_world_name, lore in bundle.lore.items():
            world_name = world_ids.get(raw_world_name, raw_world_name).strip()
            if not world_name:
                continue
            connection.execute(
                """
                INSERT INTO oc_lore (
                    world_name, search_text, raw_json, source_file, import_hash, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(world_name) DO UPDATE SET
                    search_text=excluded.search_text,
                    raw_json=excluded.raw_json,
                    source_file=excluded.source_file,
                    import_hash=excluded.import_hash,
                    imported_at=excluded.imported_at
                """,
                (
                    world_name,
                    lore_search_text(lore),
                    json.dumps(lore, ensure_ascii=False, sort_keys=True),
                    source_file,
                    import_hash,
                    imported_at,
                ),
            )

    def search_oc_characters(
        self,
        query: str = "",
        *,
        world: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        safe_limit = min(max(limit, 1), 50)
        world_filter = " AND c.world = ?" if world else ""
        values: list[Any] = [world] if world else []
        with self.connect() as connection:
            rows: list[sqlite3.Row] = []
            fts_query = _to_fts_query(query)
            if fts_query:
                try:
                    rows = connection.execute(
                        f"""
                        SELECT c.*, COUNT(p.prompt_id) AS prompt_count,
                               bm25(oc_characters_fts, 4.0, 2.0, 1.0) AS relevance
                        FROM oc_characters_fts
                        JOIN oc_characters c ON c.row_id = oc_characters_fts.rowid
                        LEFT JOIN oc_prompts p ON p.character_id = c.character_id
                        WHERE oc_characters_fts MATCH ? {world_filter}
                        GROUP BY c.row_id
                        ORDER BY relevance, c.name
                        LIMIT ?
                        """,
                        [fts_query, *values, safe_limit],
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            if query and not rows:
                like_value = f"%{query.strip()}%"
                rows = connection.execute(
                    f"""
                    SELECT c.*, COUNT(p.prompt_id) AS prompt_count, 999.0 AS relevance
                    FROM oc_characters c
                    LEFT JOIN oc_prompts p ON p.character_id = c.character_id
                    WHERE (c.name LIKE ? OR c.world LIKE ? OR c.search_text LIKE ?)
                    {world_filter}
                    GROUP BY c.row_id
                    ORDER BY c.name
                    LIMIT ?
                    """,
                    [like_value, like_value, like_value, *values, safe_limit],
                ).fetchall()
            elif not query:
                where = "WHERE c.world = ?" if world else ""
                rows = connection.execute(
                    f"""
                    SELECT c.*, COUNT(p.prompt_id) AS prompt_count, 999.0 AS relevance
                    FROM oc_characters c
                    LEFT JOIN oc_prompts p ON p.character_id = c.character_id
                    {where}
                    GROUP BY c.row_id
                    ORDER BY c.imported_at DESC, c.name
                    LIMIT ?
                    """,
                    [*values, safe_limit],
                ).fetchall()
        return [_oc_character_summary(row) for row in rows]

    def get_oc_character(self, character_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM oc_characters WHERE character_id = ?",
                (character_id,),
            ).fetchone()
            if row is None:
                return None
            prompts = connection.execute(
                """
                SELECT prompt_id, label, text, created_at
                FROM oc_prompts WHERE character_id = ? ORDER BY created_at, prompt_id
                """,
                (character_id,),
            ).fetchall()
        result = _oc_character_summary(row)
        result["profile"] = json.loads(row["raw_json"])
        result["prompts"] = [dict(prompt) for prompt in prompts]
        return result

    def get_oc_character_prompts(self, character_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT prompt_id, label, text, created_at
                FROM oc_prompts WHERE character_id = ? ORDER BY created_at, prompt_id
                """,
                (character_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_oc_worlds(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT w.world_name, w.world_id, w.system, w.color,
                       COUNT(DISTINCT c.character_id) AS character_count,
                       CASE WHEN l.world_name IS NULL THEN 0 ELSE 1 END AS has_lore
                FROM oc_worlds w
                LEFT JOIN oc_characters c ON c.world = w.world_name
                LEFT JOIN oc_lore l ON l.world_name = w.world_name
                GROUP BY w.world_name
                ORDER BY w.world_name
                """
            ).fetchall()
        return [{**dict(row), "has_lore": bool(row["has_lore"])} for row in rows]

    def search_oc_lore(
        self,
        query: str = "",
        *,
        world: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        filters = []
        values: list[Any] = []
        if world:
            filters.append("l.world_name = ?")
            values.append(world)
        if query:
            filters.append("(l.world_name LIKE ? OR l.search_text LIKE ?)")
            like_value = f"%{query.strip()}%"
            values.extend((like_value, like_value))
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT l.*, w.world_id, w.system
                FROM oc_lore l
                LEFT JOIN oc_worlds w ON w.world_name = l.world_name
                {where}
                ORDER BY l.world_name
                LIMIT ?
                """,
                [*values, min(max(limit, 1), 20)],
            ).fetchall()
        return [
            {
                "world_name": row["world_name"],
                "world_id": row["world_id"] or "",
                "system": row["system"] or "generic",
                "lore": json.loads(row["raw_json"]),
                "source_file": row["source_file"],
                "imported_at": row["imported_at"],
            }
            for row in rows
        ]

    def oc_stats(self) -> dict[str, int]:
        with self.connect() as connection:
            return {
                "characters": connection.execute("SELECT COUNT(*) FROM oc_characters").fetchone()[
                    0
                ],
                "worlds": connection.execute("SELECT COUNT(*) FROM oc_worlds").fetchone()[0],
                "prompts": connection.execute("SELECT COUNT(*) FROM oc_prompts").fetchone()[0],
                "lore_worlds": connection.execute("SELECT COUNT(*) FROM oc_lore").fetchone()[0],
                "imports": connection.execute("SELECT COUNT(*) FROM oc_imports").fetchone()[0],
            }

    def stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            total_entries = connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
            total_sources = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            kinds = {
                row["kind"]: row["count"]
                for row in connection.execute(
                    "SELECT kind, COUNT(*) AS count FROM entries GROUP BY kind ORDER BY kind"
                )
            }
            safety = {
                row["safety"]: row["count"]
                for row in connection.execute(
                    "SELECT safety, COUNT(*) AS count FROM entries GROUP BY safety ORDER BY safety"
                )
            }
            personal = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN favorite = 1 THEN 1 ELSE 0 END) AS favorites,
                    SUM(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END) AS rated,
                    SUM(CASE WHEN note != '' THEN 1 ELSE 0 END) AS noted
                FROM user_marks
                """
            ).fetchone()
        return {
            "database": str(self.path),
            "sources": total_sources,
            "entries": total_entries,
            "kinds": kinds,
            "safety": safety,
            "personal": {
                "favorites": personal["favorites"] or 0,
                "rated": personal["rated"] or 0,
                "noted": personal["noted"] or 0,
            },
            "oc_manager": self.oc_stats(),
        }

    def list_sources(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.*, COUNT(e.id) AS entry_count
                FROM sources s
                LEFT JOIN entries e ON e.source_id = s.source_id
                GROUP BY s.source_id
                ORDER BY s.name
                """
            ).fetchall()
        return [dict(row) for row in rows]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _to_fts_query(query: str) -> str:
    tokens = _TOKEN_RE.findall(query.strip())
    return " AND ".join(f'"{token}"*' for token in tokens)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["metadata"] = json.loads(result.pop("metadata_json") or "{}")
    if "favorite" in result:
        result["favorite"] = bool(result["favorite"])
    return result


def _search_filters(
    *,
    kind: str,
    source_id: str,
    model_family: str,
    safety: str,
    favorites_only: bool,
) -> tuple[list[str], list[Any]]:
    filters: list[str] = []
    values: list[Any] = []
    for column, value in (
        ("e.kind", kind),
        ("e.source_id", source_id),
        ("e.model_family", model_family),
        ("e.safety", safety),
    ):
        if value:
            filters.append(f"{column} = ?")
            values.append(value)
    if favorites_only:
        filters.append("COALESCE(um.favorite, 0) = 1")
    return filters, values


def _mark_dict(
    *,
    source_id: str,
    external_id: str,
    favorite: bool,
    rating: int | None,
    note: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "external_id": external_id,
        "favorite": favorite,
        "user_rating": rating,
        "user_note": note,
    }


def _string(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = str(value).strip()
    return text or fallback


def _mapping_items(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _oc_character_summary(row: sqlite3.Row) -> dict[str, Any]:
    row_data = dict(row)
    story = row_data["story"]
    profile = json.loads(row_data["raw_json"])
    gallery = profile.get("gallery", [])
    return {
        "character_id": row_data["character_id"],
        "name": row_data["name"],
        "world": row_data["world"],
        "gender": row_data["gender"],
        "age": row_data["age"],
        "race": row_data["race"],
        "affiliation": row_data["affiliation"],
        "identity": row_data["identity"],
        "residence": row_data["residence"],
        "faction": row_data["faction"],
        "birthplace": row_data["birthplace"],
        "avatar": row_data["avatar"],
        "sheet_role": row_data["sheet_role"],
        "player_name": row_data["player_name"],
        "story": story,
        "story_excerpt": story[:500],
        "prompt_count": row_data.get("prompt_count", 0),
        "gallery_count": len(gallery) if isinstance(gallery, list) else 0,
        "source_file": row_data["source_file"],
        "source_updated_at": row_data["source_updated_at"],
        "imported_at": row_data["imported_at"],
    }
