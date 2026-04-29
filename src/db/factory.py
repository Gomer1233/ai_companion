from __future__ import annotations

from src.app.settings import Settings
from src.db.postgres import PostgresRepositories
from src.db.repositories import SQLiteRepositories


def create_repositories(
    settings: Settings,
    *,
    include_relationship_state: bool = False,
    history_limit: int | None = None,
):
    resolved_history_limit = settings.history_limit if history_limit is None else history_limit
    if settings.db_backend == "sqlite":
        return SQLiteRepositories(
            settings.bot_db_path,
            include_relationship_state=include_relationship_state,
            history_limit=resolved_history_limit,
        )

    if settings.db_backend == "postgres":
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is required when DB_BACKEND=postgres")
        return PostgresRepositories(
            settings.database_url,
            include_relationship_state=include_relationship_state,
            history_limit=resolved_history_limit,
        )

    raise RuntimeError(f"Unsupported DB_BACKEND={settings.db_backend}")
