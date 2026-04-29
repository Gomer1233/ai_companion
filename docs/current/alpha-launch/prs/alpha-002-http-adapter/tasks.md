# Tasks

## Execution Checklist

- [ ] Add HTTP runtime settings and dependencies without widening ALPHA-002 scope.
- [ ] Add server-side session persistence on the current SQLite runtime.
- [ ] Add FastAPI app composition under `src/adapters/http/**`.
- [ ] Add `GET /healthz` and `GET /readyz` with explicit readiness state.
- [ ] Add `POST /api/session/telegram` with backend verification boundary, freshness checks, opaque session issuance, and no raw init-data logging.
- [ ] Add bearer-token auth based on server-side session lookup and expiry validation.
- [ ] Add protected `GET /api/me`, `GET /api/characters`, `GET /api/entitlements`, `GET /api/usage`.
- [ ] Add `GET /api/jobs/{job_id}` with owner-only access on the current persistence model.
- [ ] Add CORS allowlist and rate-limiting defaults for session exchange.
- [ ] Integrate HTTP startup/readiness/shutdown into the Railway backend lifecycle without breaking bot polling.
- [ ] Add focused HTTP adapter tests for auth/session/readiness behavior.
- [ ] Update `docs/current/alpha-launch/status.md` when ALPHA-002 starts and when it finishes.

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

- [ ] Extend `Settings` with HTTP config:
  - host/port
  - CORS origins
  - session TTL
  - Telegram init-data freshness window
  - rate-limit window and max attempts
- [ ] Add HTTP dependencies needed for FastAPI serving and testing.
- [ ] Keep defaults safe for local import and existing test fixtures.

### 2. Session persistence on SQLite

- [ ] Add a `sessions` table to SQLite migrations.
- [ ] Keep migration idempotent for already-initialized databases.
- [ ] Add repository methods for:
  - create session
  - load session
  - touch session
  - delete session
  - delete expired sessions
- [ ] Keep session ids opaque and non-sequential.

### 3. FastAPI app shell

- [ ] Create app factory under `src/adapters/http/app.py`.
- [ ] Add dependency wiring module for settings, repositories, and readiness state.
- [ ] Add route modules rather than placing handlers directly in `main.py`.
- [ ] Keep route handlers transport-only and push business/data decisions into existing services or repositories.

### 4. Session exchange and auth

- [ ] Implement `POST /api/session/telegram`.
- [ ] Keep Telegram verification behind a dedicated helper boundary so later hardening does not change the route contract.
- [ ] Reject stale init data.
- [ ] Return opaque bearer token plus expiry metadata.
- [ ] Implement bearer auth via repository lookup, expiry check, and `last_seen_at` update.
- [ ] Return `401` on missing, invalid, or expired token.

### 5. Protected API surface

- [ ] Implement `GET /api/me` with stable user/session identity payload.
- [ ] Implement `GET /api/characters` from backend-owned catalog data, not Telegram UI assumptions.
- [ ] Implement `GET /api/entitlements` with explicit alpha-safe shape even if monetization remains placeholder-backed.
- [ ] Implement `GET /api/usage` with stable usage payload shape.
- [ ] Implement `GET /api/jobs/{job_id}` with owner check and correct `404`/`401` behavior.

### 6. Security and lifecycle defaults

- [ ] Add origin allowlist only for configured dev/prod origins.
- [ ] Do not use wildcard CORS with credentials.
- [ ] Add rate limiting only on `POST /api/session/telegram`.
- [ ] Ensure logs never include raw init data or bearer token values.
- [ ] Add readiness state that turns green only after backend bootstrap is complete.
- [ ] Add graceful shutdown path for HTTP + polling + async clients.

### 7. Test coverage

- [ ] Add tests for `healthz` and `readyz`.
- [ ] Add tests for successful session issuance.
- [ ] Add tests for stale init data rejection.
- [ ] Add tests for rate-limit rejection.
- [ ] Add tests for expired-session `401`.
- [ ] Add tests for bearer auth on protected endpoints.
- [ ] Add tests for `/api/jobs/{job_id}` owner-only access.
- [ ] Re-run launcher smoke coverage to ensure polling startup still works.

## Verification Checklist

- [ ] `python -m pytest tests/test_http_health.py tests/test_http_session.py tests/test_http_api.py -q`
- [ ] `python -m pytest tests/test_entrypoint_smoke.py tests/test_repositories.py tests/test_migrations.py -q`
- [ ] `python -m mypy src/app src/core src/db src/adapters`
- [ ] `python -m ruff check src tests`
- [ ] `python -m pytest -q`

## Guardrails

- [ ] Do not pull Postgres migration into ALPHA-002.
- [ ] Do not move business logic into frontend/Vercel scope.
- [ ] Do not introduce JWT or stateless auth.
- [ ] Do not couple endpoint shapes to Telegram-only UI assumptions.
