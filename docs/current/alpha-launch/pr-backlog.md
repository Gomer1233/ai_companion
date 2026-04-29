# PR Backlog

| PR | Title | Depends On | Status | Brief |
| --- | --- | --- | --- | --- |
| ALPHA-001 | Finish Refactor + Boundaries | None | Done | `prs/alpha-001-refactor-boundaries/brief.md` |
| ALPHA-002 | FastAPI HTTP Adapter on Railway | ALPHA-001 | Done | `prs/alpha-002-http-adapter/brief.md` |
| ALPHA-003 | Postgres Backend + Cutover Runbook | ALPHA-002 | Done | `prs/alpha-003-postgres-cutover/brief.md` |
| ALPHA-004 | Provider Matrix + Explicit Policy Layer | ALPHA-003 | Planned | `prs/alpha-004-provider-matrix/brief.md` |
| ALPHA-005 | Monetization Core + Admin Commands | ALPHA-004 | Planned | `prs/alpha-005-monetization-admin/brief.md` |
| ALPHA-006 | Persona Audit + Launch Allowlist Freeze | ALPHA-005 | Planned | `prs/alpha-006-persona-audit/brief.md` |
| ALPHA-007 | Job Reliability | ALPHA-005 | Planned | `prs/alpha-007-job-reliability/brief.md` |
| ALPHA-008 | Mini App Alpha | ALPHA-006, ALPHA-007 | Planned | `prs/alpha-008-mini-app-alpha/brief.md` |
| ALPHA-009 | Compliance Completion + Alpha Ops | ALPHA-006 | Planned | `prs/alpha-009-compliance-ops/brief.md` |
| ALPHA-010 | Deploy to Railway + Vercel + Supabase | ALPHA-008, ALPHA-009 | Planned | `prs/alpha-010-deploy/brief.md` |

## Rules

- Follow PR order unless a later item is explicitly re-planned.
- Each PR must point back to `execution-plan.md`.
- Each PR must have both `brief.md` and `tasks.md`.
- Status values should stay simple: `Ready`, `Planned`, `In Progress`, `Blocked`, `Done`.
