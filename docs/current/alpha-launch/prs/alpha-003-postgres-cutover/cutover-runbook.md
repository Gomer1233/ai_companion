# ALPHA-003 Cutover Runbook

## Goal

Move alpha production persistence from SQLite to Supabase Postgres with a one-way cutover. The Mini App/browser must not receive direct database credentials; Railway remains the only backend owner of `DATABASE_URL`.

## Preconditions

- `ALPHA-002` is merged to `main`.
- Railway has `DB_BACKEND=postgres` and `DATABASE_URL` configured for the backend service.
- The Postgres app role is not an owner/superuser.
- Local SQLite runtime artifacts are snapshotted before export.
- Staging has rehearsed schema creation, import, and verification.

## Schema Deployment

1. Connect to Supabase with an owner/admin role.
2. Apply `src/db/postgres_schema.py` `POSTGRES_SCHEMA_SQL`.
3. Apply the least-privilege grants from `POSTGRES_LEAST_PRIVILEGE_SQL` after replacing the database and role names.
4. Verify the app role can `SELECT`, `INSERT`, `UPDATE`, and `DELETE` only on the runtime tables and cannot create/drop schema objects.
5. Do not apply schema DDL from Railway startup; `DATABASE_URL` is for the non-owner app role only.

## Data Export

1. Stop bot intake for the freeze window.
2. Copy the SQLite file to an immutable snapshot location.
3. Export rows for:
   - users and Telegram IDs
   - conversations
   - messages
   - mode state and mode locks
   - jobs
   - events
   - profile/settings state
   - relationship state
   - sessions
   - monetization tables, when present in the source snapshot
4. Preserve original `user_id`, `conversation_ref`, `created_at`, and `updated_at` values.

## Import

1. Import users before dependent tables.
2. Import Telegram account mappings from numeric Telegram user IDs.
3. Import conversations before messages, mode state, jobs, and relationship state.
4. Import sessions last; expired sessions may be skipped.
5. Import monetization seed rows only after runtime data import completes.

## Verification

- Count source and target rows for each migrated table.
- Confirm one Telegram user resolves to the same `UserRef` through bot startup and `POST /api/session/telegram`.
- Confirm `GET /api/me`, `GET /api/characters`, `GET /api/usage`, and `GET /api/jobs/{job_id}` work with a Postgres-backed session.
- Confirm expired sessions are rejected and deleted through the existing HTTP auth path.
- Confirm no frontend or Vercel environment contains Supabase database credentials.

## Cutover

1. Deploy Railway with `DB_BACKEND=postgres`.
2. Keep `BOT_DB_PATH` unset or ignored for production.
3. Start the backend and verify `/healthz` and `/readyz`.
4. Run one Telegram bot smoke and one Mini App session exchange smoke.
5. Leave SQLite snapshot untouched for rollback evidence.

## Rollback

Rollback is traffic-level only:

- stop the Postgres-backed Railway process;
- restore the frozen SQLite snapshot to the previous backend environment;
- redeploy with `DB_BACKEND=sqlite`;
- do not attempt schema downgrade from Postgres.
