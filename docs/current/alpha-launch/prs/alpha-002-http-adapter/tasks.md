# Tasks

- [ ] Add FastAPI application structure under `src/adapters/http/**`.
- [ ] Implement `POST /api/session/telegram` with backend verification and opaque session issuance.
- [ ] Implement protected `GET /api/me`, `GET /api/characters`, `GET /api/entitlements`, `GET /api/usage`.
- [ ] Implement `GET /api/jobs/{job_id}` with placeholder ownership checks if persistence remains unchanged.
- [ ] Implement `GET /healthz` and `GET /readyz`.
- [ ] Add CORS/origin allowlist and rate limiting defaults.
- [ ] Ensure raw init data is not logged.
- [ ] Keep endpoint contracts channel-neutral so they can later serve a standalone web client.
- [ ] Keep session/auth composition extensible so Telegram init-data auth is not the only future-compatible entry path.
- [ ] Add HTTP adapter tests for auth/session/readiness behavior.
- [ ] Update `docs/current/alpha-launch/status.md` when PR starts and when it finishes.
