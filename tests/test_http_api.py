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
from src.core.contracts import DeferredJob, JobStatus, JobType, UserRef
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories

_INIT_DATA_SAFE_CHARS = '{}":,'


def _make_settings(tmp_path: Path, **env: str) -> Settings:
    values = {
        "TELEGRAM_TOKEN": "tg-token",
        "OPENROUTER_API_KEY": "or-key",
        "OPENAI_API_KEY": "oa-key",
        "BOT_DB_PATH": str(tmp_path / "http-api.db"),
        "HTTP_CORS_ORIGINS": "http://localhost:3000",
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


def _issue_token(client: TestClient, telegram_token: str, user_id: int) -> str:
    response = client.post(
        "/api/session/telegram",
        json={"init_data": _telegram_init_data(telegram_token=telegram_token, user_id=user_id)},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_protected_api_requires_bearer_and_returns_session_identity(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)
    token = _issue_token(client, deps.settings.telegram_token, 201)

    unauthorized = client.get("/api/me")
    response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.json()["user_id"] == "201"


def test_protected_api_rejects_expired_session(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)
    expired = deps.repositories.create_session(
        UserRef("202"),
        issued_at=int(time.time()) - 100,
        expires_at=int(time.time()) - 1,
    )

    response = client.get("/api/me", headers={"Authorization": f"Bearer {expired.session_token}"})

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


def test_characters_entitlements_and_usage_are_backend_owned(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)
    token = _issue_token(client, deps.settings.telegram_token, 203)
    headers = {"Authorization": f"Bearer {token}"}

    characters = client.get("/api/characters", headers=headers)
    entitlements = client.get("/api/entitlements", headers=headers)
    usage = client.get("/api/usage", headers=headers)

    assert characters.status_code == 200
    assert len(characters.json()["items"]) > 0
    assert entitlements.status_code == 200
    assert "has_premium" in entitlements.json()
    assert usage.status_code == 200
    assert "history_limit" in usage.json()


def test_jobs_endpoint_is_owner_only(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)
    owner_token = _issue_token(client, deps.settings.telegram_token, 204)
    other_token = _issue_token(client, deps.settings.telegram_token, 205)
    owner_ref = UserRef("204")
    conversation = deps.repositories.ensure_default_conversation(owner_ref)
    now_ts = int(time.time())
    deps.repositories.create_job(
        DeferredJob(
            job_id="job-204",
            user_ref=owner_ref,
            conversation_ref=conversation.conversation_ref,
            mode="basic",
            job_type=JobType.IMAGE,
            status=JobStatus.RUNNING,
            progress=10,
            created_at=now_ts,
            updated_at=now_ts,
        )
    )

    owner = client.get("/api/jobs/job-204", headers={"Authorization": f"Bearer {owner_token}"})
    stranger = client.get("/api/jobs/job-204", headers={"Authorization": f"Bearer {other_token}"})
    missing = client.get("/api/jobs/missing-job", headers={"Authorization": f"Bearer {owner_token}"})

    assert owner.status_code == 200
    assert owner.json()["job_id"] == "job-204"
    assert stranger.status_code == 404
    assert missing.status_code == 404
