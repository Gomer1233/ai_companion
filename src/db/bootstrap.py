from __future__ import annotations

from src.db.migrations import migrate_database


def initialize_sqlite_runtime_db(db_path: str) -> None:
    migrate_database(db_path, include_relationship_state=True)
