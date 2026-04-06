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
- `src/main.py` still needs service extraction and launcher thinning before HTTP, Postgres, and Mini App work should proceed.

## Completed

- planning namespace created under `docs/current/alpha-launch/`
- initiative execution plan captured for alpha launch
- initial PR backlog and per-PR briefs/tasks scaffolded
- ALPHA-001 started with shared runtime helper extraction out of `src/main.py` and `src/core/legacy_runtime.py`
- `src/main.py` history, photo gate, mode state, and mode lock wrappers now route through `SQLiteRepositories` instead of ad hoc launcher SQL
- mode switch and reset flows in `src/main.py` now use repository-backed conversation reset/active-mode paths, with legacy relationship cleanup left as an explicit hook

## Next Step

Continue `ALPHA-001 Finish Refactor + Boundaries` by addressing the remaining launcher-owned profile/settings helpers and extracting more orchestration out of `src/main.py`.

## Risks / Notes

- The alpha release path depends on finishing launcher cleanup before introducing a second transport surface.
- Explicit launch scope is intentionally conservative on capability surface, but persona scope remains subject to audit freeze.
- Security baseline assumes no direct browser path to Supabase in alpha v1.

