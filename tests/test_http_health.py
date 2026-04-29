from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.adapters.http.app import create_app
from src.adapters.http.dependencies import AppDependencies, ReadinessState
from src.app.settings import Settings
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories


def _make_settings(tmp_path: Path) -> Settings:
    return Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "OPENAI_API_KEY": "oa-key",
            "HTTP_CORS_ORIGINS": "http://localhost:3000",
            "BOT_DB_PATH": str(tmp_path / "http.db"),
        },
        project_root=tmp_path,
    )


def _make_dependencies(tmp_path: Path) -> AppDependencies:
    settings = _make_settings(tmp_path)
    migrate_database(settings.bot_db_path, include_relationship_state=True)
    repo = SQLiteRepositories(settings.bot_db_path, include_relationship_state=True)
    return AppDependencies(
        settings=settings,
        repositories=repo,
        readiness=ReadinessState(),
    )


def test_healthz_is_live_before_readiness(tmp_path: Path) -> None:
    deps = _make_dependencies(tmp_path)
    app = create_app(deps)
    client = TestClient(app)

    health = client.get("/healthz")
    ready = client.get("/readyz")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 503
    assert ready.json() == {"status": "starting"}


def test_readyz_turns_green_after_bootstrap(tmp_path: Path) -> None:
    deps = _make_dependencies(tmp_path)
    deps.readiness.mark_ready()
    app = create_app(deps)
    client = TestClient(app)

    ready = client.get("/readyz")

    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
