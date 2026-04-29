from __future__ import annotations

from src.app.settings import Settings
from src.db.connection import connect_postgres
from src.db.migrations import migrate_database
from src.db.postgres_schema import POSTGRES_SCHEMA_SQL


def bootstrap_database(settings: Settings, *, include_relationship_state: bool = False) -> None:
    if settings.db_backend == "sqlite":
        migrate_database(settings.bot_db_path, include_relationship_state=include_relationship_state)
        return

    if settings.db_backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is required when DB_BACKEND=postgres")
        apply_postgres_schema(settings.database_url)
        return

    raise RuntimeError(f"Unsupported DB_BACKEND={settings.db_backend}")


def apply_postgres_schema(database_url: str) -> None:
    conn = connect_postgres(database_url)
    try:
        conn.execute(POSTGRES_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
