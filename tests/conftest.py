from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

from tests.support import DummyAsyncClient


MODULE_NAMES = ("src.main",)
ENV_KEYS = {
    "TELEGRAM_TOKEN",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "MODELSLAB_API_KEY",
    "TOG_API_KEY",
    "TOG_BASE_URL",
    "TOG_IMAGE_MODEL",
    "TOG_WIDTH",
    "TOG_HEIGHT",
    "IMAGE_BACKEND_PROVIDER",
    "OPENAI_IMAGE_MODEL",
    "OPENAI_IMAGE_SIZE",
    "BOT_DB_PATH",
    "DEFAULT_MODEL",
    "OPENROUTER_IMAGE_MODEL",
}


@pytest.fixture
def module_loader(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)

    def _load(module_name: str, *, env: dict[str, str] | None = None):
        for key in ENV_KEYS:
            monkeypatch.delenv(key, raising=False)

        values = {
            "TELEGRAM_TOKEN": "123456:TESTTOKEN",
            "OPENROUTER_API_KEY": "or-test-key",
            "OPENAI_API_KEY": "oa-test-key",
            "MODELSLAB_API_KEY": "ms-test-key",
            "TOG_API_KEY": "tog-test-key",
            "TOG_BASE_URL": "https://api.together.xyz/v1",
            "TOG_IMAGE_MODEL": "black-forest-labs/FLUX.1.1-pro",
            "TOG_WIDTH": "1024",
            "TOG_HEIGHT": "1024",
            "IMAGE_BACKEND_PROVIDER": "openrouter",
            "OPENROUTER_IMAGE_MODEL": "sourceful/riverflow-v2-max-preview",
            "OPENAI_IMAGE_MODEL": "gpt-image-1",
            "OPENAI_IMAGE_SIZE": "1024x1024",
            "DEFAULT_MODEL": "openai/gpt-4o-mini",
            "BOT_DB_PATH": str(tmp_path / f"{module_name.replace('.', '_')}.db"),
        }
        if env:
            values.update(env)

        for key, value in values.items():
            monkeypatch.setenv(key, value)

        for loaded_name in MODULE_NAMES:
            sys.modules.pop(loaded_name, None)

        importlib.invalidate_caches()
        return importlib.import_module(module_name)

    return _load


@pytest.fixture
def mark_mode_picked():
    def _mark(module, user_id: int, mode: str = "basic") -> None:
        module.set_user_profile(user_id, mode=mode)
        conn = sqlite3.connect(module.DB_PATH)
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE user_profile SET mode_picked=1 WHERE user_id=?",
                (user_id,),
            )
            conn.commit()
        finally:
            conn.close()

    return _mark
