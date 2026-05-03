from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient

from src.adapters.http.app import create_app
from src.adapters.http.dependencies import AppDependencies, ReadinessState
from src.app.settings import Settings
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories

_INIT_DATA_SAFE_CHARS = '{}":,'


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


def _sign_telegram_init_data(*, telegram_token: str, fields: dict[str, str]) -> str:
    secret_key = hmac.new(b"WebAppData", telegram_token.encode("utf-8"), hashlib.sha256).digest()
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    signature = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    pairs = [f"{key}={quote(value, safe=_INIT_DATA_SAFE_CHARS)}" for key, value in fields.items()]
    pairs.append(f"hash={signature}")
    return "&".join(pairs)


def _telegram_init_data(*, telegram_token: str, user_id: int, auth_date: int | None = None) -> str:
    issued = int(time.time()) if auth_date is None else auth_date
    user_json = json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":"))
    return _sign_telegram_init_data(
        telegram_token=telegram_token,
        fields={"auth_date": str(issued), "user": user_json},
    )


def test_session_exchange_issues_opaque_token(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)

    response = client.post(
        "/api/session/telegram",
        json={"init_data": _telegram_init_data(telegram_token=deps.settings.telegram_token, user_id=101)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"access_token", "token_type", "expires_at"}
    assert payload["token_type"] == "Bearer"
    assert isinstance(payload["access_token"], str)
    assert len(payload["access_token"]) >= 16
    assert deps.repositories.load_session(payload["access_token"]) is not None


def test_session_refresh_endpoint_is_not_part_of_alpha_contract(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)

    response = client.post("/api/session/refresh", json={"refresh_token": "unused"})

    assert response.status_code == 404


def test_session_exchange_rejects_stale_init_data(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path, HTTP_TELEGRAM_INIT_MAX_AGE_SEC="30")
    stale_auth_date = int(time.time()) - 31

    response = client.post(
        "/api/session/telegram",
        json={
            "init_data": _telegram_init_data(
                telegram_token=deps.settings.telegram_token,
                user_id=101,
                auth_date=stale_auth_date,
            )
        },
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "stale_init_data"}


def test_session_exchange_rate_limits_by_client_window(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path, HTTP_SESSION_RATE_LIMIT_MAX_ATTEMPTS="2")
    stale_auth_date = int(time.time()) - 999

    for _ in range(2):
        response = client.post(
            "/api/session/telegram",
            json={
                "init_data": _telegram_init_data(
                    telegram_token=deps.settings.telegram_token,
                    user_id=101,
                    auth_date=stale_auth_date,
                )
            },
        )
        assert response.status_code == 401

    limited = client.post(
        "/api/session/telegram",
        json={
            "init_data": _telegram_init_data(
                telegram_token=deps.settings.telegram_token,
                user_id=101,
                auth_date=stale_auth_date,
            )
        },
    )

    assert limited.status_code == 429
    assert limited.json() == {"detail": "rate_limit_exceeded"}


def test_session_exchange_rejects_unsigned_init_data(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    unsigned = f"auth_date={int(time.time())}&user={json.dumps({'id': 101}, separators=(',', ':'))}"

    response = client.post("/api/session/telegram", json={"init_data": unsigned})

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_init_data"}


def test_session_exchange_rejects_tampered_init_data(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)
    signed = _telegram_init_data(telegram_token=deps.settings.telegram_token, user_id=101)
    tampered = signed.replace('"id":101', '"id":999', 1)

    response = client.post("/api/session/telegram", json={"init_data": tampered})

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_init_data"}
