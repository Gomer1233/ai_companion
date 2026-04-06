# Multichannel Core Initiative

This directory contains the only active planning documents for the refactor that extracts a multichannel application core with Telegram as the first adapter.

## Canonical Documents

- `execution-plan.md`
  Initiative-level scope, rules, phases, and acceptance criteria.
- `pr-backlog.md`
  Ordered PR queue, dependencies, and status.
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

- If any archived document conflicts with a file in this directory, this directory wins.
- Do not create ad hoc planning notes outside this directory for this initiative.
- Do not duplicate architecture rules across every PR document; link back to `execution-plan.md`.
- Keep PR briefs narrow and implementation-facing.
- Keep task lists operational and checklist-based.

## Boundaries

Use this directory for:

- active refactor planning
- PR sequencing
- execution tracking
- implementation task lists

Do not use this directory for:

- permanent architecture reference
- historical notes
- superseded plans
- scratch notes

Those belong in:

- `docs/architecture/`
- `docs/adr/`
- `docs/archive/`
