from __future__ import annotations

from pathlib import Path

from src.app.settings import Settings


def test_settings_reads_mini_app_url(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "OPENAI_API_KEY": "oa-key",
            "MINI_APP_URL": "https://mini.lina.example",
        },
        project_root=tmp_path,
    )

    assert settings.mini_app_url == "https://mini.lina.example"


def test_settings_uses_platform_port_when_http_port_is_unset(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "OPENAI_API_KEY": "oa-key",
            "PORT": "18080",
        },
        project_root=tmp_path,
    )

    assert settings.http_port == 18080
