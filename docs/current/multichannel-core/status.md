# Status

## Initiative

- Name: `multichannel-core`
- Current date baseline: `2026-04-06`
- Initial eight-PR refactor cycle: complete
- Current consolidation follow-up: single Telegram launcher

## Current Source of Truth

- `execution-plan.md`
- `pr-backlog.md`
- `status.md`

## Completed

- active documentation structure created under `docs/current/multichannel-core/`
- archive boundary defined under `docs/archive/`
- repository-level guidance added in `AGENTS.md`
- `pytest` harness added for legacy runtime characterization
- smoke tests and characterization tests added for the Telegram launcher
- image provider startup validation centralized through `Settings`, `ProviderRegistry`, `AppVariantConfig`, and `ChannelAdapterConfig`
- full reset now clears mode lock, photo gate, relationship state, and in-memory image jobs on current schema
- raw request/reply preview logging removed from runtime logs
- stable core contracts added for `UserRef`, `ConversationRef`, `InboundEvent`, `CoreResponse.items`, deferred jobs, and analytics events
- unified forward-only SQLite migrator added with schema version tracking and `conversation_ref` backfill
- repository layer added for conversations, history, active mode, mode locks, reset scopes, analytics events, relationship state, and deferred jobs
- shared `legacy_runtime` module added for duplicated OpenRouter/text helpers and shared Telegram-era mode/reset/photo orchestration
- Telegram adapter helpers added under `src/adapters/telegram/` for update parsing, ordered response rendering, and transport routing classification
- `ruff` and limited `mypy` configuration added in `pyproject.toml`
- GitHub Actions CI added in `.github/workflows/ci.yml` to run tests, Ruff, and limited mypy on extracted code
- root cleanup moved local-only helpers into `.local/`, removed empty legacy artifacts, and aligned photo assets with the runtime path under `src/Photo`
- the remaining split between `src/main.py` and `src/bot_lika.py` has been removed; `src/main.py` is now the single active Telegram launcher with both relationship logic and rap submodes enabled

## Verification

- `python -m pytest -q`
- `python -m py_compile src/main.py src/adapters/telegram/parser.py src/adapters/telegram/renderer.py src/adapters/telegram/routing.py src/core/legacy_runtime.py src/db/repositories.py src/db/migrations.py src/app/settings.py src/app/provider_registry.py src/app/variants.py`

## Next Step

The next useful initiative is extracting the remaining chat/image/audio orchestration out of `src/main.py` and the transition-layer runtime into cleaner services.

## Notes

- `ruff` and `mypy` configs are in repo and wired into CI, but were not executed locally in the earlier refactor session because those tools were not installed in that environment
- `.local/` remains the quarantine area for local-only helpers and legacy secret-bearing artifacts that should not influence normal agent routing
- follow-on alpha launch planning now lives under `docs/current/alpha-launch/`

