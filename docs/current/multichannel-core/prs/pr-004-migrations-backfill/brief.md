# PR-004: Migrations + Backfill

## Goal

Replace ad hoc schema mutation with versioned migrations and move legacy data into the new conversation model.

## In Scope

- schema version table
- unified migrator
- forward-only migrations
- new conversation model
- legacy backfill into `default conversation`

## Out of Scope

- repository extraction beyond what migration wiring requires
- service extraction
- Telegram adapter cleanup

## Expected Files

- `src/db/migrations.py`
- `src/db/connection.py`
- migration tests

## Test Focus

- fresh DB migration
- legacy DB migration
- idempotent rerun
- backfill to `default conversation`
- forward-only path

## Merge Criteria

- schema changes go through one migrator
- legacy data survives migration
- no business-logic extraction is mixed into the PR
