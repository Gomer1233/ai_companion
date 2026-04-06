# ALPHA-003: Postgres Backend + Cutover Runbook

## Goal

Replace the SQLite production path with Supabase Postgres, add session persistence, and document the one-way cutover procedure.

## In Scope

- introduce backend-agnostic repository contracts if still needed
- add Postgres-backed repository implementation
- migrate `users`, `telegram_accounts`, `conversations`, `messages`, `mode_state`, `mode_locks`, `jobs`, `events`, `relationship_state`, and `sessions`
- add monetization tables `plans`, `entitlements`, `usage_counters`, and `access_grants`
- define least-privilege DB role requirements
- document cutover runbook and staging rehearsal expectations

## Out of Scope

- provider matrix cleanup
- persona audit decisions
- Mini App frontend
- deploy automation

## Expected Files

- `src/db/**`
- migration files or migrator support
- `tests/**`
- `docs/current/alpha-launch/execution-plan.md`
- `docs/current/alpha-launch/status.md`

## Test Focus

- Postgres repository integration tests
- migration/backfill rehearsal
- session table behavior
- user resolution consistency between bot and Mini App paths
- least-privilege assumptions where testable

## Merge Criteria

- production path no longer requires SQLite
- cutover runbook exists and is staging-ready
- least-privilege backend DB role is documented
- HTTP adapter contract survives persistence swap unchanged
