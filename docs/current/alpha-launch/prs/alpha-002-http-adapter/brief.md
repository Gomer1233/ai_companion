# ALPHA-002: FastAPI HTTP Adapter on Railway

## Goal

Add the Python HTTP adapter under `src/adapters/http/**` so the Railway backend becomes the single owner of Mini App API surface and session exchange.

This API must be designed as a reusable backend surface for Mini App first and future standalone web client second, without duplicating business logic in another stack.

## In Scope

- introduce FastAPI-based HTTP adapter structure
- add `POST /api/session/telegram`
- add `GET /api/me`, `GET /api/characters`, `GET /api/entitlements`, `GET /api/usage`, `GET /api/jobs/{job_id}`
- add `GET /healthz` and `GET /readyz`
- implement opaque session token issuance, lookup, expiry, and `401` re-auth contract
- add HTTP security defaults: CORS allowlist, rate limiting, no raw init-data logging
- define Railway service startup/readiness integration points
- keep auth/session and job/media endpoints extensible so a future web auth/client layer can be added without rewriting core services

## Out of Scope

- Postgres persistence swap
- Mini App frontend implementation
- monetization/admin commands
- provider matrix freeze

## Expected Files

- `src/adapters/http/**`
- backend bootstrap/composition files
- `tests/**`
- `docs/current/alpha-launch/status.md`

## Test Focus

- init-data verification and freshness checks
- session issuance and expiry
- bearer auth on protected endpoints
- `healthz/readyz`
- CORS/origin allowlist
- `401`-driven silent re-auth behavior

## Merge Criteria

- Railway backend owns all documented `GET /api/*`
- no business logic is moved into Vercel/frontend scope
- HTTP adapter remains channel-neutral enough to serve future standalone web client needs
- session contract is implemented and test-covered
- HTTP adapter does not force the Postgres migration into the same PR
