# Status

## Initiative

- Name: `alpha-launch`
- Current date baseline: `2026-04-06`
- State: `In Progress`
- Depends on: completed `multichannel-core` foundation plus follow-on launcher consolidation

## Current Source of Truth

- `execution-plan.md`
- `pr-backlog.md`
- `status.md`

## Current Context

- `multichannel-core` remains the completed foundation initiative and should not be overwritten to carry alpha launch planning.
- Alpha launch planning now lives under `docs/current/alpha-launch/`.
- `ALPHA-002 FastAPI HTTP Adapter` is merged to `main`.
- `ALPHA-003 Postgres Backend + Cutover Runbook` is the next backlog item and is ready to start.

## Completed

- planning namespace created under `docs/current/alpha-launch/`
- initiative execution plan captured for alpha launch
- initial PR backlog and per-PR briefs/tasks scaffolded
- ALPHA-001 started with shared runtime helper extraction out of `src/main.py` and `src/core/legacy_runtime.py`
- `src/main.py` history, photo gate, mode state, and mode lock wrappers now route through `SQLiteRepositories` instead of ad hoc launcher SQL
- mode switch and reset flows in `src/main.py` now use repository-backed conversation reset/active-mode paths, with legacy relationship cleanup left as an explicit hook
- `ALPHA-001 Finish Refactor + Boundaries` is merged to `main`
- `ALPHA-002` now adds:
  - HTTP runtime settings
  - SQLite-backed opaque sessions
  - FastAPI adapter under `src/adapters/http/**`
  - `healthz`, `readyz`, `POST /api/session/telegram`, and protected `GET /api/*`
  - CORS allowlist, session exchange rate limiting, and launcher lifecycle integration
  - focused HTTP adapter tests plus passing full backend verification
  - Telegram Mini App init-data HMAC validation on the backend before session issuance
  - rejection of unsigned or tampered init-data payloads
- `ALPHA-002 FastAPI HTTP Adapter` is merged to `main`

## Next Step

Start `ALPHA-003 Postgres Backend + Cutover Runbook` from its existing `brief.md` and `tasks.md`, keeping the HTTP adapter contract unchanged while swapping the persistence backend.

## Risks / Notes

- `src/main.py` is still too large, so HTTP integration must stay transport-thin and avoid widening scope into a full launcher rewrite.
- Explicit launch scope is intentionally conservative on capability surface, but persona scope remains subject to audit freeze.
- Security baseline assumes no direct browser path to Supabase in alpha v1.

