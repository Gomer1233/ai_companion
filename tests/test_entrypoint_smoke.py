from __future__ import annotations

import sqlite3
from unittest.mock import AsyncMock

import pytest


def index_exists(db_path: str, index_name: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def table_exists(db_path: str, table_name: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_main_startup_runs(module_loader):
    module = module_loader("src.main")
    module.dp.start_polling = AsyncMock()
    module.run_http_server = AsyncMock()
    module.openrouter_client.aclose = AsyncMock()

    await module.main()

    module.dp.start_polling.assert_awaited_once_with(module.bot)
    module.run_http_server.assert_awaited_once()
    module.openrouter_client.aclose.assert_awaited_once()


@pytest.mark.parametrize(
    ("provider", "extra_env"),
    [
        ("openrouter", {}),
        ("openai", {"OPENAI_API_KEY": "oa-test-key"}),
        ("modelslab", {"MODELSLAB_API_KEY": "ms-test-key"}),
        ("together", {"TOG_API_KEY": "tog-test-key"}),
    ],
)
def test_supported_image_provider_configs_import(module_loader, provider, extra_env):
    module = module_loader("src.main", env={"IMAGE_BACKEND_PROVIDER": provider, **extra_env})

    assert module.IMAGE_BACKEND_PROVIDER == provider


def test_unsupported_image_provider_fails_fast(module_loader):
    with pytest.raises(RuntimeError, match="Unsupported IMAGE_BACKEND_PROVIDER"):
        module_loader("src.main", env={"IMAGE_BACKEND_PROVIDER": "replicate"})


def test_init_db_is_idempotent_and_creates_llm_index(module_loader):
    module = module_loader("src.main")

    module.init_db()
    module.init_db()

    assert index_exists(module.DB_PATH, "idx_user_events_llm")


def test_init_db_creates_conversation_schema(module_loader):
    module = module_loader("src.main")

    module.init_db()

    assert table_exists(module.DB_PATH, "conversations")


def test_init_db_creates_sessions_schema(module_loader):
    module = module_loader("src.main")

    module.init_db()

    assert table_exists(module.DB_PATH, "sessions")


def test_main_import_uses_postgres_repository_when_configured(module_loader):
    module = module_loader(
        "src.main",
        env={
            "DB_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://lina_app:secret@db.example/lina",
        },
    )

    from src.db.postgres import PostgresRepositories

    assert isinstance(module.DB_REPOSITORIES, PostgresRepositories)
    assert module.DB_REPOSITORIES.database_url == "postgresql://lina_app:secret@db.example/lina"
