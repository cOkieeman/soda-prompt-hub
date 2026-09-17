from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from prompt_hub.database_oc import DatabaseOCMixin
from prompt_hub.database_support import (
    SCHEMA,
    EntryInput,
    _mark_dict,
    _now,
    _row_to_dict,
    _search_filters,
    _to_fts_query,
)
from prompt_hub.schema_migrations import record_schema_migration


class PromptDatabase(DatabaseOCMixin):
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
            record_schema_migration(
                connection,
                "prompt_database",
                1,
                "Prompt sources, entries, marks, OC imports, and FTS baseline",
            )
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

    def upsert_entry(self, entry: EntryInput) -> None:
        """Insert or refresh one entry without removing sibling entries or user marks."""
        with self.connect() as connection:
            self._upsert_entry(entry, connection)
            connection.commit()

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
        has_visual: bool = False,
        category: str = "",
        hair_color: str = "",
        eye_color: str = "",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        results, _total = self.search_page(
            query,
            kind=kind,
            source_id=source_id,
            model_family=model_family,
            safety=safety,
            favorites_only=favorites_only,
            has_visual=has_visual,
            category=category,
            hair_color=hair_color,
            eye_color=eye_color,
            limit=limit,
        )
        return results

    def search_page(
        self,
        query: str = "",
        *,
        kind: str = "",
        source_id: str = "",
        model_family: str = "",
        safety: str = "",
        favorites_only: bool = False,
        has_visual: bool = False,
        category: str = "",
        hair_color: str = "",
        eye_color: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        safe_limit = min(max(limit, 1), 50)
        safe_offset = max(offset, 0)
        filters, values = _search_filters(
            kind=kind,
            source_id=source_id,
            model_family=model_family,
            safety=safety,
            favorites_only=favorites_only,
            has_visual=has_visual,
            category=category,
            hair_color=hair_color,
            eye_color=eye_color,
        )
        where = " AND ".join(filters)
        if where:
            where = " AND " + where

        with self.connect() as connection:
            rows: list[sqlite3.Row] = []
            total = 0
            fts_query = _to_fts_query(query)
            if fts_query:
                try:
                    total = int(
                        connection.execute(
                            f"""
                            SELECT COUNT(*)
                            FROM entries_fts
                            JOIN entries e ON e.id = entries_fts.rowid
                            JOIN sources s ON s.source_id = e.source_id
                            LEFT JOIN user_marks um
                              ON um.source_id = e.source_id AND um.external_id = e.external_id
                            WHERE entries_fts MATCH ? {where}
                            """,
                            [fts_query, *values],
                        ).fetchone()[0]
                    )
                    if total:
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
                            LIMIT ? OFFSET ?
                            """,
                            [fts_query, *values, safe_limit, safe_offset],
                        ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
                    total = 0
            if query and not total:
                like_value = f"%{query.strip()}%"
                total = int(
                    connection.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM entries e
                        JOIN sources s ON s.source_id = e.source_id
                        LEFT JOIN user_marks um
                          ON um.source_id = e.source_id AND um.external_id = e.external_id
                        WHERE (e.title LIKE ? OR e.content LIKE ? OR e.category LIKE ?) {where}
                        """,
                        [like_value, like_value, like_value, *values],
                    ).fetchone()[0]
                )
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
                    LIMIT ? OFFSET ?
                    """,
                    [like_value, like_value, like_value, *values, safe_limit, safe_offset],
                ).fetchall()
            elif not query:
                total = int(
                    connection.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM entries e
                        JOIN sources s ON s.source_id = e.source_id
                        LEFT JOIN user_marks um
                          ON um.source_id = e.source_id AND um.external_id = e.external_id
                        WHERE 1=1 {where}
                        """,
                        values,
                    ).fetchone()[0]
                )
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
                    LIMIT ? OFFSET ?
                    """,
                    [*values, safe_limit, safe_offset],
                ).fetchall()
        return [_row_to_dict(row) for row in rows], total

    def source_facets(self, source_id: str) -> dict[str, list[str]]:
        with self.connect() as connection:
            categories = [
                str(row[0])
                for row in connection.execute(
                    """
                    SELECT DISTINCT category FROM entries
                    WHERE source_id = ? AND kind = 'character_reference' AND category != ''
                    ORDER BY category COLLATE NOCASE
                    """,
                    (source_id,),
                )
            ]

            def metadata_values(path: str) -> list[str]:
                return [
                    str(row[0])
                    for row in connection.execute(
                        """
                        SELECT DISTINCT json_each.value
                        FROM entries, json_each(entries.metadata_json, ?)
                        WHERE entries.source_id = ?
                        ORDER BY json_each.value COLLATE NOCASE
                        """,
                        (path, source_id),
                    )
                ]

            kinds = [
                str(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT kind FROM entries WHERE source_id = ? ORDER BY kind",
                    (source_id,),
                )
            ]
            return {
                "categories": categories,
                "hair_colors": metadata_values("$.hair_colors"),
                "eye_colors": metadata_values("$.eye_colors"),
                "kinds": kinds,
            }

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

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT s.*, COUNT(e.id) AS entry_count,
                       SUM(CASE
                           WHEN json_extract(e.metadata_json, '$.visual_path') != '' THEN 1
                           WHEN json_extract(e.metadata_json, '$.cached_media_path') != '' THEN 1
                           WHEN json_array_length(e.metadata_json, '$.image_paths') > 0 THEN 1
                           ELSE 0
                       END) AS visual_count
                FROM sources s
                LEFT JOIN entries e ON e.source_id = s.source_id
                WHERE s.source_id = ?
                GROUP BY s.source_id
                """,
                (source_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            **dict(row),
            "visual_count": int(row["visual_count"] or 0),
            "deletable": row["source_type"] != "git",
        }

    def delete_source(self, source_id: str, *, purge_marks: bool = False) -> dict[str, int]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT source_id, source_type FROM sources WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if row is None:
                raise KeyError(source_id)

            marks_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM user_marks WHERE source_id = ?",
                    (source_id,),
                ).fetchone()[0]
            )

            cursor = connection.execute("DELETE FROM entries WHERE source_id = ?", (source_id,))
            deleted_entries = cursor.rowcount

            if purge_marks:
                connection.execute("DELETE FROM user_marks WHERE source_id = ?", (source_id,))
                purged_marks = marks_count
                retained_marks = 0
            else:
                purged_marks = 0
                retained_marks = marks_count

            connection.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))
            connection.commit()

            return {
                "deleted_entries": deleted_entries,
                "retained_marks": retained_marks,
                "purged_marks": purged_marks,
            }

    def delete_entry(
        self,
        source_id: str,
        external_id: str,
        *,
        purge_marks: bool = False,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM entries WHERE source_id = ? AND external_id = ?",
                (source_id, external_id),
            ).fetchone()
            if row is None:
                raise KeyError(external_id)

            marks_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM user_marks WHERE source_id = ? AND external_id = ?",
                    (source_id, external_id),
                ).fetchone()[0]
            )

            connection.execute(
                "DELETE FROM entries WHERE source_id = ? AND external_id = ?",
                (source_id, external_id),
            )

            if purge_marks:
                connection.execute(
                    "DELETE FROM user_marks WHERE source_id = ? AND external_id = ?",
                    (source_id, external_id),
                )
                purged_marks = marks_count
                retained_marks = 0
            else:
                purged_marks = 0
                retained_marks = marks_count

            remaining_entries = int(
                connection.execute(
                    "SELECT COUNT(*) FROM entries WHERE source_id = ?",
                    (source_id,),
                ).fetchone()[0]
            )

            source_deleted = False
            if remaining_entries == 0:
                source_row = connection.execute(
                    "SELECT source_type FROM sources WHERE source_id = ?",
                    (source_id,),
                ).fetchone()
                if source_row and source_row[0] != "git":
                    connection.execute("DELETE FROM sources WHERE source_id = ?", (source_id,))
                    source_deleted = True

            connection.commit()

            return {
                "deleted_entries": 1,
                "retained_marks": retained_marks,
                "purged_marks": purged_marks,
                "remaining_entries": remaining_entries,
                "source_deleted": source_deleted,
            }

    def list_sources(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.*, COUNT(e.id) AS entry_count,
                       SUM(CASE
                           WHEN json_extract(e.metadata_json, '$.visual_path') != '' THEN 1
                           WHEN json_extract(e.metadata_json, '$.cached_media_path') != '' THEN 1
                           WHEN json_array_length(e.metadata_json, '$.image_paths') > 0 THEN 1
                           ELSE 0
                       END) AS visual_count
                FROM sources s
                LEFT JOIN entries e ON e.source_id = s.source_id
                GROUP BY s.source_id
                ORDER BY s.name
                """
            ).fetchall()
        return [
            {
                **dict(row),
                "visual_count": int(row["visual_count"] or 0),
                "deletable": row["source_type"] != "git",
            }
            for row in rows
        ]

    def list_visual_entries(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.source_id, e.external_id, e.title, e.safety, e.source_url,
                       e.metadata_json, s.name AS source_name
                FROM entries e
                JOIN sources s ON s.source_id = e.source_id
                WHERE json_array_length(e.metadata_json, '$.image_paths') > 0
                   OR json_extract(e.metadata_json, '$.cached_media_path') != ''
                ORDER BY e.source_id, e.external_id
                """
            ).fetchall()
        return [_row_to_dict(row) for row in rows]
