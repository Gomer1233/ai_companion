from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests.support import FakeMessage


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


@pytest.mark.asyncio
async def test_explicit_image_flow_rejects_openai_provider(module_loader):
    module = module_loader(
        "src.main",
        env={"IMAGE_BACKEND_PROVIDER": "openai", "OPENAI_API_KEY": "oa-test-key"},
    )

    with pytest.raises(RuntimeError, match="provider_not_allowed"):
        await module.generate_image_backend("prompt", mode="whore")


def test_legacy_openai_image_provider_import_still_works(module_loader):
    module = module_loader(
        "src.main",
        env={"IMAGE_BACKEND_PROVIDER": "openai", "OPENAI_API_KEY": "oa-test-key"},
    )

    assert module.IMAGE_BACKEND_PROVIDER == "openai"


@pytest.mark.asyncio
async def test_explicit_prompt_translation_rejects_openai_engine_before_network(module_loader):
    module = module_loader(
        "src.main",
        env={
            "PROMPT_TRANSLATION_ENABLED": "1",
            "PROMPT_TRANSLATION_ENGINE": "openai",
            "TRANSLATION_MODEL": "gpt-4o-mini",
        },
    )

    with pytest.raises(RuntimeError, match="Explicit translation blocked"):
        await module.maybe_translate_prompt("modelslab", "привет", mode="whore")


@pytest.mark.asyncio
async def test_explicit_prompt_translation_uses_openrouter_engine(module_loader, monkeypatch):
    module = module_loader(
        "src.main",
        env={
            "PROMPT_TRANSLATION_ENABLED": "1",
            "PROMPT_TRANSLATION_ENGINE": "openrouter",
            "TRANSLATION_MODEL": "x-ai/grok-4.1-fast",
        },
    )
    translator = AsyncMock(return_value="hello")
    monkeypatch.setattr(module, "call_openrouter", translator)

    translated = await module.maybe_translate_prompt("modelslab", "привет", mode="whore")

    assert translated == "hello"
    translator.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_text_flow_rejects_blocked_policy_before_openrouter(
    module_loader,
    mark_mode_picked,
    monkeypatch,
):
    module = module_loader("src.main")
    module.init_db()
    mark_mode_picked(module, 1, mode="whore")
    monkeypatch.setattr(module, "keep_typing", AsyncMock())
    llm = AsyncMock(return_value=("blocked bypass", "stop", {"total_tokens": 1}))
    monkeypatch.setattr(module, "call_openrouter_with_meta", llm)

    class BlockingPolicy:
        def authorize_explicit(self, request):
            return SimpleNamespace(allowed=False, reasons=("provider_not_allowed",))

    monkeypatch.setattr(module, "ACCESS_POLICY", BlockingPolicy())

    with pytest.raises(RuntimeError, match="Explicit text request blocked"):
        await module.on_text(FakeMessage("hello"))

    llm.assert_not_awaited()


def test_chef_submode_keyboard_uses_readable_labels(module_loader):
    module = module_loader("src.main")

    keyboard = module.build_chef_submode_keyboard()
    labels = [row[0].text for row in keyboard.inline_keyboard]

    assert labels == [
        "🏠 Быстро по-домашнему",
        "🍽️ Как в ресторане",
        "🧠 Вспомнить контекст",
    ]


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
