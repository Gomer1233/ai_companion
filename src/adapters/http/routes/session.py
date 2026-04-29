from __future__ import annotations

import time

from fastapi import APIRouter, Request

from src.adapters.http.dependencies import get_app_dependencies, verify_telegram_init_data


router = APIRouter(prefix="/api/session")


@router.post("/telegram")
def exchange_telegram_session(request: Request, payload: dict[str, str]) -> dict[str, str | int]:
    dependencies = get_app_dependencies(request)
    now_ts = int(time.time())
    client_id = request.client.host if request.client else "unknown"
    dependencies.session_rate_limiter.check(
        client_id,
        now_ts=now_ts,
        window_sec=dependencies.settings.http_session_rate_limit_window_sec,
        max_attempts=dependencies.settings.http_session_rate_limit_max_attempts,
    )

    init_data = payload.get("init_data", "")
    user_ref = verify_telegram_init_data(init_data, dependencies.settings, now_ts=now_ts)
    session = dependencies.repositories.create_session(
        user_ref,
        issued_at=now_ts,
        expires_at=now_ts + dependencies.settings.http_session_ttl_sec,
    )
    return {
        "access_token": session.session_token,
        "token_type": "Bearer",
        "expires_at": session.expires_at,
    }
