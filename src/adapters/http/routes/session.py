from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, HTTPException, Request, status

from src.adapters.http.dependencies import get_app_dependencies, verify_telegram_init_data
from src.app.settings import Settings
from src.core.contracts import UserRef


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
    return _session_response(user_ref, session.session_token, session.expires_at, dependencies.settings, now_ts=now_ts)


@router.post("/refresh")
def refresh_telegram_session(request: Request, payload: dict[str, str]) -> dict[str, str | int]:
    dependencies = get_app_dependencies(request)
    now_ts = int(time.time())
    user_ref, refresh_expires_at = _verify_refresh_token(
        payload.get("refresh_token", ""),
        dependencies.settings,
        now_ts=now_ts,
    )
    session = dependencies.repositories.create_session(
        user_ref,
        issued_at=now_ts,
        expires_at=now_ts + dependencies.settings.http_session_ttl_sec,
    )
    return _session_response(
        user_ref,
        session.session_token,
        session.expires_at,
        dependencies.settings,
        now_ts=now_ts,
        refresh_token=payload["refresh_token"],
        refresh_expires_at=refresh_expires_at,
    )


def _session_response(
    user_ref: UserRef,
    access_token: str,
    expires_at: int,
    settings: Settings,
    *,
    now_ts: int,
    refresh_token: str | None = None,
    refresh_expires_at: int | None = None,
) -> dict[str, str | int]:
    resolved_refresh_expires_at = refresh_expires_at or now_ts + settings.http_session_refresh_ttl_sec
    resolved_refresh_token = refresh_token or _sign_refresh_token(
        user_ref,
        settings,
        issued_at=now_ts,
        expires_at=resolved_refresh_expires_at,
    )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_at": expires_at,
        "refresh_token": resolved_refresh_token,
        "refresh_expires_at": resolved_refresh_expires_at,
    }


def _sign_refresh_token(user_ref: UserRef, settings: Settings, *, issued_at: int, expires_at: int) -> str:
    payload = {"user_id": user_ref.value, "iat": issued_at, "exp": expires_at}
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload_bytes).decode("ascii").rstrip("=")
    signature = hmac.new(_refresh_secret(settings), encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"v1.{encoded_payload}.{signature}"


def _verify_refresh_token(token: str, settings: Settings, *, now_ts: int) -> tuple[UserRef, int]:
    try:
        version, encoded_payload, signature = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token") from exc
    if version != "v1":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token")

    expected = hmac.new(_refresh_secret(settings), encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token")

    try:
        padded = encoded_payload + "=" * (-len(encoded_payload) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        user_id = str(int(payload["user_id"]))
        expires_at = int(payload["exp"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token") from exc

    if expires_at <= now_ts:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_refresh_token")
    return UserRef(user_id), expires_at


def _refresh_secret(settings: Settings) -> bytes:
    return hmac.new(b"LinaMiniAppRefresh", settings.telegram_token.encode("utf-8"), hashlib.sha256).digest()
