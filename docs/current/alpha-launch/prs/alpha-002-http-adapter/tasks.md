# Tasks

## Execution Checklist

- [x] Add HTTP runtime settings and dependencies without widening ALPHA-002 scope.
- [x] Add server-side session persistence on the current SQLite runtime.
- [x] Add FastAPI app composition under `src/adapters/http/**`.
- [x] Add `GET /healthz` and `GET /readyz` with explicit readiness state.
- [x] Add `POST /api/session/telegram` with backend verification boundary, freshness checks, opaque session issuance, and no raw init-data logging.
- [x] Add bearer-token auth based on server-side session lookup and expiry validation.
- [x] Add protected `GET /api/me`, `GET /api/characters`, `GET /api/entitlements`, `GET /api/usage`.
- [x] Add `GET /api/jobs/{job_id}` with owner-only access on the current persistence model.
- [x] Add CORS allowlist and rate-limiting defaults for session exchange.
- [x] Integrate HTTP startup/readiness/shutdown into the Railway backend lifecycle without breaking bot polling.
- [x] Add focused HTTP adapter tests for auth/session/readiness behavior.
- [x] Update `docs/current/alpha-launch/status.md` when ALPHA-002 starts and when it finishes.

## File Targets

- `src/adapters/http/**`
- `src/app/settings.py`
- `src/core/contracts.py`
- `src/db/migrations.py`
- `src/db/repositories.py`
- `src/main.py`
- `tests/**`
- `docs/current/alpha-launch/status.md`

## Recommended Build Order

### 1. Runtime and config foundation

- [x] Extend `Settings` with HTTP config:
  - host/port
  - CORS origins
  - session TTL
  - Telegram init-data freshness window
  - rate-limit window and max attempts
- [x] Add HTTP dependencies needed for FastAPI serving and testing.
- [x] Keep defaults safe for local import and existing test fixtures.

### 2. Session persistence on SQLite

- [x] Add a `sessions` table to SQLite migrations.
- [x] Keep migration idempotent for already-initialized databases.
- [x] Add repository methods for:
  - create session
  - load session
  - touch session
  - delete session
  - delete expired sessions
- [x] Keep session ids opaque and non-sequential.

### 3. FastAPI app shell

- [x] Create app factory under `src/adapters/http/app.py`.
- [x] Add dependency wiring module for settings, repositories, and readiness state.
- [x] Add route modules rather than placing handlers directly in `main.py`.
- [x] Keep route handlers transport-only and push business/data decisions into existing services or repositories.

### 4. Session exchange and auth

- [x] Implement `POST /api/session/telegram`.
- [x] Keep Telegram verification behind a dedicated helper boundary so later hardening does not change the route contract.
- [x] Reject stale init data.
- [x] Return opaque bearer token plus expiry metadata.
- [x] Implement bearer auth via repository lookup, expiry check, and `last_seen_at` update.
- [x] Return `401` on missing, invalid, or expired token.

### 5. Protected API surface

- [x] Implement `GET /api/me` with stable user/session identity payload.
- [x] Implement `GET /api/characters` from backend-owned catalog data, not Telegram UI assumptions.
- [x] Implement `GET /api/entitlements` with explicit alpha-safe shape even if monetization remains placeholder-backed.
- [x] Implement `GET /api/usage` with stable usage payload shape.
- [x] Implement `GET /api/jobs/{job_id}` with owner check and correct `404`/`401` behavior.

### 6. Security and lifecycle defaults

- [x] Add origin allowlist only for configured dev/prod origins.
- [x] Do not use wildcard CORS with credentials.
- [x] Add rate limiting only on `POST /api/session/telegram`.
- [x] Ensure logs never include raw init data or bearer token values.
- [x] Add readiness state that turns green only after backend bootstrap is complete.
- [x] Add graceful shutdown path for HTTP + polling + async clients.

### 7. Test coverage

- [x] Add tests for `healthz` and `readyz`.
- [x] Add tests for successful session issuance.
- [x] Add tests for stale init data rejection.
- [x] Add tests for rate-limit rejection.
- [x] Add tests for expired-session `401`.
- [x] Add tests for bearer auth on protected endpoints.
- [x] Add tests for `/api/jobs/{job_id}` owner-only access.
- [x] Re-run launcher smoke coverage to ensure polling startup still works.

## Verification Checklist

- [x] `python -m pytest tests/test_http_health.py tests/test_http_session.py tests/test_http_api.py -q`
- [x] `python -m pytest tests/test_entrypoint_smoke.py tests/test_repositories.py tests/test_migrations.py -q`
- [x] `python -m mypy src/app src/core src/db src/adapters`
- [x] `python -m ruff check src tests`
- [x] `python -m pytest -q`

## Guardrails

- [x] Do not pull Postgres migration into ALPHA-002.
- [x] Do not move business logic into frontend/Vercel scope.
- [x] Do not introduce JWT or stateless auth.
- [x] Do not couple endpoint shapes to Telegram-only UI assumptions.
