from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class SmokeResult:
    name: str
    ok: bool
    detail: str


def build_telegram_init_data(*, bot_token: str, user_id: int, auth_date: int | None = None) -> str:
    resolved_auth_date = int(time.time()) if auth_date is None else int(auth_date)
    user_json = json.dumps(
        {"id": int(user_id), "first_name": "LinaSmoke", "username": f"lina_smoke_{user_id}"},
        separators=(",", ":"),
    )
    fields = {
        "auth_date": str(resolved_auth_date),
        "query_id": f"smoke-{user_id}-{resolved_auth_date}",
        "user": user_json,
    }
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


def run_smoke(
    *,
    backend_url: str,
    frontend_url: str,
    exercise_auth: bool = False,
    telegram_token: str = "",
    telegram_user_id: int = 900_000_010,
    timeout: float = 20.0,
) -> list[SmokeResult]:
    backend = backend_url.rstrip("/")
    frontend = frontend_url.rstrip("/")
    results: list[SmokeResult] = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        _check_public_backend(client, backend, results)
        _check_frontend(client, frontend, backend, results)
        if exercise_auth:
            if not telegram_token:
                results.append(SmokeResult("auth_config", False, "TELEGRAM_TOKEN is required for --exercise-auth"))
            else:
                _check_authenticated_backend(client, backend, telegram_token, telegram_user_id, results)
    return results


def _check_public_backend(client: httpx.Client, backend: str, results: list[SmokeResult]) -> None:
    for path, expected in (("/healthz", "ok"), (("/readyz"), "ready")):
        try:
            response = client.get(f"{backend}{path}")
            payload = response.json()
            ok = response.status_code == 200 and payload.get("status") == expected
            results.append(SmokeResult(f"backend{path}", ok, f"{response.status_code} {payload}"))
        except Exception as exc:
            results.append(SmokeResult(f"backend{path}", False, repr(exc)))


def _check_frontend(client: httpx.Client, frontend: str, backend: str, results: list[SmokeResult]) -> None:
    try:
        response = client.get(frontend)
        html = response.text
        ok = response.status_code == 200 and "telegram-web-app.js" in html
        results.append(SmokeResult("frontend_html", ok, f"{response.status_code} telegram_sdk={ok}"))
        script_paths = _next_script_paths(html)
        has_backend_url = False
        for script_path in script_paths:
            script_response = client.get(f"{frontend}{script_path}")
            if backend in script_response.text:
                has_backend_url = True
                break
        results.append(SmokeResult("frontend_backend_url", has_backend_url, f"scripts={len(script_paths)}"))
    except Exception as exc:
        results.append(SmokeResult("frontend", False, repr(exc)))


def _check_authenticated_backend(
    client: httpx.Client,
    backend: str,
    telegram_token: str,
    telegram_user_id: int,
    results: list[SmokeResult],
) -> None:
    init_data = build_telegram_init_data(bot_token=telegram_token, user_id=telegram_user_id)
    try:
        session_response = client.post(f"{backend}/api/session/telegram", json={"init_data": init_data})
        session_payload = session_response.json()
        token = str(session_payload.get("access_token") or "")
        ok = session_response.status_code == 200 and bool(token)
        results.append(SmokeResult("session_exchange", ok, f"{session_response.status_code}"))
        if not ok:
            return
        headers = {"Authorization": f"Bearer {token}"}
        for path in ("/api/me", "/api/characters", "/api/entitlements", "/api/usage"):
            response = client.get(f"{backend}{path}", headers=headers)
            results.append(SmokeResult(path, response.status_code == 200, f"{response.status_code}"))
        consent_response = client.post(f"{backend}/api/consent/explicit", json={"accepted": True}, headers=headers)
        consent_payload: dict[str, Any] = consent_response.json()
        consent_ok = consent_response.status_code == 200 and consent_payload.get("explicit_consent") is True
        results.append(SmokeResult("explicit_consent", consent_ok, f"{consent_response.status_code} {consent_payload}"))
        job_response = client.get(f"{backend}/api/jobs/00000000-0000-4000-8000-000000000000", headers=headers)
        results.append(SmokeResult("job_lookup_protected", job_response.status_code == 404, f"{job_response.status_code}"))
    except Exception as exc:
        results.append(SmokeResult("authenticated_backend", False, repr(exc)))


def _next_script_paths(html: str) -> list[str]:
    marker = '<script src="'
    paths: list[str] = []
    start = 0
    while True:
        marker_index = html.find(marker, start)
        if marker_index < 0:
            return paths
        path_start = marker_index + len(marker)
        path_end = html.find('"', path_start)
        if path_end < 0:
            return paths
        path = html[path_start:path_end]
        if path.startswith("/_next/"):
            paths.append(path)
        start = path_end + 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Lina alpha launch smoke checks.")
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--exercise-auth", action="store_true")
    parser.add_argument("--telegram-token", default=os.getenv("TELEGRAM_TOKEN", ""))
    parser.add_argument("--telegram-user-id", type=int, default=900_000_010)
    args = parser.parse_args(argv)

    results = run_smoke(
        backend_url=args.backend_url,
        frontend_url=args.frontend_url,
        exercise_auth=args.exercise_auth,
        telegram_token=args.telegram_token,
        telegram_user_id=args.telegram_user_id,
    )
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status} {result.name}: {result.detail}")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
