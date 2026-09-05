from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

MIGRATION_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    component TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    description TEXT NOT NULL DEFAULT '',
    applied_at TEXT NOT NULL,
    PRIMARY KEY (component, version)
);
"""


class SchemaMigrationError(ValueError):
    pass


class EmptyMigrationComponentError(SchemaMigrationError):
    def __init__(self) -> None:
        super().__init__("Schema migration component cannot be empty")


class InvalidMigrationVersionError(SchemaMigrationError):
    def __init__(self) -> None:
        super().__init__("Schema migration version must be positive")


def record_schema_migration(
    connection: sqlite3.Connection,
    component: str,
    version: int,
    description: str,
) -> None:
    """Record an idempotent schema step in the database being initialized."""
    clean_component = component.strip()
    if not clean_component:
        raise EmptyMigrationComponentError
    if version < 1:
        raise InvalidMigrationVersionError
    connection.executescript(MIGRATION_TABLE_SCHEMA)
    connection.execute(
        """
        INSERT OR IGNORE INTO schema_migrations (
            component, version, description, applied_at
        ) VALUES (?, ?, ?, ?)
        """,
        (clean_component, version, description.strip(), _now()),
    )


def schema_versions(connection: sqlite3.Connection) -> dict[str, int]:
    """Return the highest recorded version for each initialized component."""
    connection.executescript(MIGRATION_TABLE_SCHEMA)
    rows = connection.execute(
        """
        SELECT component, MAX(version) AS version
        FROM schema_migrations
        GROUP BY component
        ORDER BY component
        """
    ).fetchall()
    return {str(row[0]): int(row[1]) for row in rows}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
