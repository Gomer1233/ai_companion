# ALPHA-007: Job Reliability

## Goal

Make image jobs restart-safe, ownership-aware, and observable through a protected status endpoint before launch.

## In Scope

- persist job state in Postgres
- use non-enumerable job ids (`UUID` or `ULID`)
- reconcile stale jobs on backend startup
- enforce terminal-state invariants
- separate user ack from async completion
- add protected `GET /api/jobs/{job_id}` with owner/operator checks

## Out of Scope

- Mini App frontend polling UX
- provider matrix changes
- deployment pipeline changes

## Expected Files

- `src/core/**`
- `src/db/**`
- `src/adapters/http/**`
- `tests/**`
- `docs/current/alpha-launch/status.md`

## Test Focus

- stale job reconciliation after restart
- `cancelled` precedence over late completion/failure
- owner/operator authorization for job status
- non-enumerable ids and status endpoint behavior

## Merge Criteria

- restart does not leave dangling running jobs
- `reset_conversation` closes active jobs correctly
- status endpoint cannot be enumerated or bypass ownership checks
- reconciliation behavior is integration-tested
