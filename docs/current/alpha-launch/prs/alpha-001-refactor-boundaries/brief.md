# ALPHA-001: Finish Refactor + Boundaries

## Goal

Finish the remaining launcher consolidation so `src/main.py` becomes a thin Telegram launcher over extracted services and no longer owns business logic or ad hoc persistence wiring.

## In Scope

- extract remaining chat/image/reset/conversation/access/job orchestration from `src/main.py`
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
- no direct SQLite paths remain in `src/main.py`
- Telegram adapter stays transport-only

## Merge Criteria

- `src/main.py` is visibly thinner
- `legacy_runtime.py` no longer participates in active runtime logic
- extracted code passes `pytest`, `ruff`, and limited `mypy`
- no Postgres or HTTP adapter work is mixed into this PR
