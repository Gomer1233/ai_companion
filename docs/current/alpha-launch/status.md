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
- `ALPHA-003 Postgres Backend + Cutover Runbook` is merged to `main`.
- `ALPHA-004 Provider Matrix + Explicit Policy Layer` is in progress on `codex/alpha-004-provider-matrix`.
- Post-alpha standalone Web direction is captured as an accepted identity/readiness decision: `docs/adr/0002-user-identity-and-standalone-web-readiness.md`.

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
- `ALPHA-003` has started with:
  - backend selection through `DB_BACKEND`
  - Supabase/Postgres `DATABASE_URL` settings
  - repository factory wiring
  - initial Postgres schema and least-privilege grant template
  - one-way cutover runbook under `prs/alpha-003-postgres-cutover/cutover-runbook.md`
  - `TEST_DATABASE_URL`-gated Postgres integration tests for repository and HTTP adapter behavior
  - Supabase staging project `Lina_AI_staging` created as `aruvavburiqtedregusi`
  - Supabase migrations applied on staging:
    - `alpha_003_initial_postgres_schema`
    - `alpha_003_enable_public_table_rls`
    - `alpha_003_add_foreign_key_indexes`
    - `alpha_003_add_app_role_rls_policies`
  - Supabase security advisors reduced from RLS errors to `RLS Enabled No Policy` INFO notices, matching the alpha no-browser-DB stance
  - `TEST_DATABASE_URL`-gated Postgres integration tests passed against `Lina_AI_staging`:
    - `python -m pytest tests/test_postgres_integration.py -q`
    - result: `2 passed`
  - SQLite fixture cutover rehearsal added:
    - `tests/test_cutover_rehearsal.py`
    - `tests/test_postgres_integration.py::test_sqlite_fixture_cutover_rehearsal_imports_into_postgres`
  - expanded `TEST_DATABASE_URL`-gated Postgres integration tests passed against `Lina_AI_staging`:
    - `python -m pytest tests/test_postgres_integration.py -q`
    - result: `3 passed`
  - P1 review follow-ups added:
    - Postgres startup no longer runs owner DDL through runtime `DATABASE_URL`
    - runtime tables now get `lina_app` RLS read/write policies alongside least-privilege grants
    - whore-mode relationship state now routes through repository storage in Postgres mode
    - cutover snapshot/import now covers profile/settings/events/Telegram mappings/legacy state/runtime tables and monetization tables when present
- `ALPHA-003 Postgres Backend + Cutover Runbook` is merged to `main`
- `ADR 0002 User Identity And Standalone Web Readiness` accepted:
  - `UserRef` is the primary product identity
  - Telegram accounts are linked identities
  - standalone Web with chat is a post-alpha direction

## Next Step

Continue `ALPHA-004 Provider Matrix + Explicit Policy Layer` from `codex/alpha-004-provider-matrix`.

## Risks / Notes

- `src/main.py` is still too large, so HTTP integration must stay transport-thin and avoid widening scope into a full launcher rewrite.
- Explicit launch scope is intentionally conservative on capability surface, but persona scope remains subject to audit freeze.
- Security baseline assumes no direct browser path to Supabase in alpha v1.
- Standalone Web with chat is a post-alpha direction. Alpha remains Telegram-first, but `ALPHA-004` through `ALPHA-010` must preserve `UserRef`-first backend contracts and avoid treating Telegram as the product identity model.

