# ALPHA-001: Finish Refactor + Boundaries

## Goal

Finish the remaining launcher consolidation so `src/main.py` becomes a thin Telegram launcher over extracted services and no longer owns business logic or ad hoc persistence wiring.

The extracted service boundaries must stay transport-neutral so the same core can later serve Telegram bot, Mini App, and a future standalone web client without another deep refactor.

## Current Decomposition Target

`src/main.py` is being split into these responsibility buckets:

- `bootstrap/init`
  config loading, DB bootstrap, startup wiring
- `telegram transport wiring`
  handler registration and transport-only concerns
- `runtime helpers`
  text chunking, OpenRouter call plumbing, truncation helpers
- `runtime persistence wrappers`
  history, profile, settings, mode state, locks, analytics/event logging
- `conversation/reset/access orchestration`
  mode switching, resets, policy checks, state transitions
- `image/audio/chat orchestration`
  provider-facing runtime flow and deferred work coordination
- `legacy persona-specific runtime glue`
  transitional behavior still sitting behind `legacy_runtime` or direct launcher hooks

## Current Progress

Already completed in this initiative:

- shared runtime helpers extracted to `src/core/runtime_helpers.py`
- `src/core/legacy_runtime.py` moved onto shared helpers instead of duplicating them
- launcher state persistence wrappers moved behind `src/db/repositories.py`
- mode switch, reset, and runtime event logging paths moved off ad hoc launcher SQL

Still remaining:

- decide whether `init_db()` bootstrap stays in launcher or moves behind bootstrap/adapters
- extract more chat/image/audio/reset orchestration out of `src/main.py`
- reduce or neutralize remaining active usage of `src/core/legacy_runtime.py`
- make the launcher visibly transport/bootstrap oriented rather than flow-owning

## In Scope

- extract remaining chat/image/reset/conversation/access/job orchestration from `src/main.py`
- keep extracted service APIs transport-neutral and reusable beyond Telegram
- remove or neutralize `src/core/legacy_runtime.py`
- remove direct `sqlite3.connect` calls and schema helpers from the launcher
- keep product rules out of Telegram adapter code
- establish service composition boundaries for `ChatService`, `ImageService`, `ResetService`, `ConversationService`, `AccessPolicyService`, and `JobService`

## Out of Scope

- FastAPI HTTP adapter
- Postgres migration
- monetization tables
- Mini App frontend
- compliance copy or legal pages

## Expected Files

- `src/main.py`
- `src/core/**`
- `src/adapters/telegram/**`
- `tests/**`
- `docs/current/alpha-launch/status.md`

## Test Focus

- launcher import/startup
- service extraction coverage for text/image/reset flows
- runtime persistence no longer lives in ad hoc launcher SQL
- Telegram adapter stays transport-only

## Merge Criteria

- `src/main.py` is visibly thinner and mostly reduced to bootstrap + Telegram wiring
- runtime persistence and event logging no longer live in ad hoc launcher SQL
- only startup/bootstrap DB work may remain local to the launcher
- `legacy_runtime.py` no longer participates in active runtime logic, or is reduced to a thin compatibility shell with no duplicated helper logic
- extracted code passes `pytest`, `ruff`, and limited `mypy`
- no Postgres or HTTP adapter work is mixed into this PR
