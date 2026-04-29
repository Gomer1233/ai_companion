from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs

from fastapi import HTTPException, Request, status

from src.app.settings import Settings
from src.core.contracts import SessionRecord, UserRef
from src.db.repositories import SQLiteRepositories


@dataclass(slots=True)
class ReadinessState:
    is_ready: bool = False

    def mark_ready(self) -> None:
        self.is_ready = True

    def mark_starting(self) -> None:
        self.is_ready = False


@dataclass(slots=True)
class SessionRateLimiter:
    attempts_by_client: dict[str, list[int]] = field(default_factory=dict)

    def check(self, client_id: str, *, now_ts: int, window_sec: int, max_attempts: int) -> None:
        attempts = [
            attempt_ts
            for attempt_ts in self.attempts_by_client.get(client_id, [])
            if attempt_ts > now_ts - window_sec
        ]
        if len(attempts) >= max_attempts:
            self.attempts_by_client[client_id] = attempts
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="rate_limit_exceeded")
        attempts.append(now_ts)
        self.attempts_by_client[client_id] = attempts


@dataclass(frozen=True, slots=True)
class AppDependencies:
    settings: Settings
    repositories: SQLiteRepositories
    readiness: ReadinessState
    session_rate_limiter: SessionRateLimiter = field(default_factory=SessionRateLimiter)


def get_app_dependencies(request: Request) -> AppDependencies:
    return request.app.state.dependencies


def verify_telegram_init_data(init_data: str, settings: Settings, *, now_ts: int | None = None) -> UserRef:
    parsed = parse_qs(init_data, strict_parsing=True)
    auth_date_raw = parsed.get("auth_date", [None])[0]
    user_raw = parsed.get("user", [None])[0]
    if auth_date_raw is None or user_raw is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_init_data")

    try:
        auth_date = int(auth_date_raw)
        user_payload = json.loads(user_raw)
        user_id = int(user_payload["id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_init_data") from exc

    resolved_now = int(time.time()) if now_ts is None else now_ts
    if auth_date < resolved_now - settings.http_telegram_init_max_age_sec:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="stale_init_data")

    return UserRef(str(user_id))


def require_session(request: Request) -> SessionRecord:
    dependencies = get_app_dependencies(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    session_token = auth_header.removeprefix("Bearer ").strip()
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    session = dependencies.repositories.load_session(session_token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    now_ts = int(time.time())
    if session.expires_at <= now_ts:
        dependencies.repositories.delete_session(session_token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    touched = dependencies.repositories.touch_session(session_token, last_seen_at=now_ts)
    if touched is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")
    return touched
