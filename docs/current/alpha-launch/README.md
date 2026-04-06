# Alpha Launch Initiative

This directory contains the active planning documents for the alpha launch initiative that follows the completed `multichannel-core` refactor cycle.

## Canonical Documents

- `execution-plan.md`
  Initiative-level scope, fixed decisions, security baseline, sequencing, and acceptance criteria.
- `pr-backlog.md`
  Ordered PR queue, dependencies, and current status.
- `status.md`
  Current execution state of the initiative.
- `prs/`
  Per-PR briefs and task lists.

## Read Order

1. `execution-plan.md`
2. `pr-backlog.md`
3. `status.md`
4. `prs/<pr-id>/brief.md`
5. `prs/<pr-id>/tasks.md`

## Rules

- If a file in this directory conflicts with a file in `docs/current/multichannel-core/` on alpha launch scope, this directory wins for the alpha launch initiative.
- Do not create ad hoc planning notes outside this directory for this initiative.
- Keep PR briefs narrow and implementation-facing.
- Keep task lists operational and checklist-based.
- Treat `multichannel-core` as completed foundation work, not as the active plan of record for alpha release execution.

## Boundaries

Use this directory for:

- alpha launch planning
- release-path sequencing
- execution tracking
- PR briefs and task lists

Do not use this directory for:

- permanent architecture reference
- historical notes
- superseded plans
- scratch notes

Those belong in:

- `docs/architecture/`
- `docs/adr/`
- `docs/archive/`
