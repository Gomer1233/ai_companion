from __future__ import annotations

from pathlib import Path

import pytest

from src.app.settings import Settings


def test_repository_factory_selects_postgres_backend_from_settings() -> None:
    from src.db.factory import create_repositories
    from src.db.postgres import PostgresRepositories

    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "OPENAI_API_KEY": "oa-key",
            "DB_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://lina_app:secret@db.example/lina",
        },
        project_root=Path("D:/projects/Lina_AI"),
    )

    repositories = create_repositories(settings, include_relationship_state=True)

    assert isinstance(repositories, PostgresRepositories)
    assert repositories.database_url == "postgresql://lina_app:secret@db.example/lina"
    assert repositories.include_relationship_state is True


def test_repository_factory_requires_database_url_for_postgres() -> None:
    from src.db.factory import create_repositories

    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "OPENAI_API_KEY": "oa-key",
            "DB_BACKEND": "postgres",
        },
        project_root=Path("D:/projects/Lina_AI"),
    )

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        create_repositories(settings)


def test_postgres_schema_declares_alpha_tables_and_least_privilege_grants() -> None:
    from src.db.postgres_schema import POSTGRES_SCHEMA_SQL, POSTGRES_LEAST_PRIVILEGE_SQL

    required_tables = {
        "users",
        "telegram_accounts",
        "conversations",
        "messages",
        "mode_state",
        "mode_locks",
        "jobs",
        "events",
        "relationship_state",
        "sessions",
        "plans",
        "entitlements",
        "usage_counters",
        "access_grants",
    }

    normalized_schema = POSTGRES_SCHEMA_SQL.lower()
    for table_name in required_tables:
        assert f"create table if not exists {table_name}" in normalized_schema
        assert f"alter table {table_name} enable row level security" in normalized_schema

    normalized_grants = POSTGRES_LEAST_PRIVILEGE_SQL.lower()
    assert "grant connect on database" in normalized_grants
    assert "grant usage on schema public" in normalized_grants
    assert "grant select, insert, update, delete on all tables in schema public" in normalized_grants


def test_bootstrap_database_uses_postgres_schema_for_postgres_settings(monkeypatch) -> None:
    from src.db.bootstrap import bootstrap_database

    calls: list[tuple[str, str | None]] = []

    def fake_apply_postgres_schema(database_url: str) -> None:
        calls.append(("postgres", database_url))

    def fake_migrate_database(db_path: str, *, include_relationship_state: bool = False) -> None:
        calls.append(("sqlite", db_path))

    monkeypatch.setattr("src.db.bootstrap.apply_postgres_schema", fake_apply_postgres_schema)
    monkeypatch.setattr("src.db.bootstrap.migrate_database", fake_migrate_database)
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "OPENAI_API_KEY": "oa-key",
            "DB_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://lina_app:secret@db.example/lina",
            "BOT_DB_PATH": "local.db",
        },
        project_root=Path("D:/projects/Lina_AI"),
    )

    bootstrap_database(settings, include_relationship_state=True)

    assert calls == [("postgres", "postgresql://lina_app:secret@db.example/lina")]


def test_bootstrap_database_keeps_sqlite_for_local_settings(monkeypatch) -> None:
    from src.db.bootstrap import bootstrap_database

    calls: list[tuple[str, str, bool]] = []

    def fake_migrate_database(db_path: str, *, include_relationship_state: bool = False) -> None:
        calls.append(("sqlite", db_path, include_relationship_state))

    monkeypatch.setattr("src.db.bootstrap.migrate_database", fake_migrate_database)
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "OPENAI_API_KEY": "oa-key",
            "DB_BACKEND": "sqlite",
            "BOT_DB_PATH": "local.db",
        },
        project_root=Path("D:/projects/Lina_AI"),
    )

    bootstrap_database(settings, include_relationship_state=True)

    assert calls == [("sqlite", "local.db", True)]
