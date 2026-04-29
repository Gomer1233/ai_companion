from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from src.adapters.http.app import create_app
from src.adapters.http.dependencies import AppDependencies, ReadinessState
from src.app.settings import Settings
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories


def _make_settings(tmp_path: Path, **env: str) -> Settings:
    values = {
        "TELEGRAM_TOKEN": "tg-token",
        "OPENROUTER_API_KEY": "or-key",
        "OPENAI_API_KEY": "oa-key",
        "BOT_DB_PATH": str(tmp_path / "http-session.db"),
        "HTTP_CORS_ORIGINS": "http://localhost:3000",
        "HTTP_SESSION_TTL_SEC": "3600",
        "HTTP_TELEGRAM_INIT_MAX_AGE_SEC": "90",
        "HTTP_SESSION_RATE_LIMIT_WINDOW_SEC": "60",
        "HTTP_SESSION_RATE_LIMIT_MAX_ATTEMPTS": "2",
    }
    values.update(env)
    return Settings.from_env(values, project_root=tmp_path)


def _make_client(tmp_path: Path, **env: str) -> tuple[TestClient, AppDependencies]:
    settings = _make_settings(tmp_path, **env)
    migrate_database(settings.bot_db_path, include_relationship_state=True)
    deps = AppDependencies(
        settings=settings,
        repositories=SQLiteRepositories(settings.bot_db_path, include_relationship_state=True),
        readiness=ReadinessState(is_ready=True),
    )
    return TestClient(create_app(deps)), deps


def _telegram_init_data(*, user_id: int, auth_date: int | None = None) -> str:
    issued = int(time.time()) if auth_date is None else auth_date
    user_json = json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":"))
    return f"auth_date={issued}&user={user_json}"


def test_session_exchange_issues_opaque_token(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)

    response = client.post("/api/session/telegram", json={"init_data": _telegram_init_data(user_id=101)})

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"access_token", "token_type", "expires_at"}
    assert payload["token_type"] == "Bearer"
    assert isinstance(payload["access_token"], str)
    assert len(payload["access_token"]) >= 16
    assert deps.repositories.load_session(payload["access_token"]) is not None


def test_session_exchange_rejects_stale_init_data(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path, HTTP_TELEGRAM_INIT_MAX_AGE_SEC="30")
    stale_auth_date = int(time.time()) - 31

    response = client.post(
        "/api/session/telegram",
        json={"init_data": _telegram_init_data(user_id=101, auth_date=stale_auth_date)},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "stale_init_data"}


def test_session_exchange_rate_limits_by_client_window(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path, HTTP_SESSION_RATE_LIMIT_MAX_ATTEMPTS="2")
    stale_auth_date = int(time.time()) - 999

    for _ in range(2):
        response = client.post(
            "/api/session/telegram",
            json={"init_data": _telegram_init_data(user_id=101, auth_date=stale_auth_date)},
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/session/telegram",
        json={"init_data": _telegram_init_data(user_id=101, auth_date=stale_auth_date)},
    )

    assert limited.status_code == 429
    assert limited.json() == {"detail": "rate_limit_exceeded"}
