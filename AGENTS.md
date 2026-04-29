# Working Rules

Canonical planning documents for active initiatives live only in:

## Multichannel Core

- `docs/current/multichannel-core/execution-plan.md`
- `docs/current/multichannel-core/pr-backlog.md`
- `docs/current/multichannel-core/status.md`
- `docs/current/multichannel-core/prs/**`

## Alpha Launch

- `docs/current/alpha-launch/execution-plan.md`
- `docs/current/alpha-launch/pr-backlog.md`
- `docs/current/alpha-launch/status.md`
- `docs/current/alpha-launch/prs/**`

When working in this repository:

- Use `docs/current/multichannel-core/**` as the active planning source of truth for tasks that belong to the multichannel-core refactor history and its follow-on consolidation context.
- Use `docs/current/alpha-launch/**` as the active planning source of truth for tasks that belong to the alpha launch initiative.
- Treat `docs/archive/**`, `archive/**`, and `Архив ботов/**` as historical material only.
- Treat `.env`, `.env.7z`, `*.db`, `*.log`, `.local/**`, and `src/Photo/**` as local runtime artifacts unless the task explicitly targets them.
- Do not use archived planning files to make implementation decisions.
- Do not create new planning files in the repository root.
- Put stable, implemented system docs in `docs/architecture/**`.
- Put accepted architectural decisions in `docs/adr/**`.
- Put historical or superseded material only in `docs/archive/**`.

Priority order when documents disagree:

1. Code and tests
2. Relevant `docs/current/<initiative>/**`
3. `docs/architecture/**`
4. `docs/adr/**`
5. Archived material

PR documentation rules:

- `execution-plan.md` defines initiative scope and sequencing.
- `pr-backlog.md` defines PR order and status.
- `prs/<pr-id>/brief.md` defines the scope of one PR.
- `prs/<pr-id>/tasks.md` is only an execution checklist, not a source of architectural truth.

Git worktrees:

- Do not create a new worktree for every task by default.
- Use the main repository working directory for normal sequential work.
- Create a separate worktree only when parallel branch work or isolation is clearly needed.
- Place worktrees next to the main repository, not inside it.
- Remove temporary worktrees after the related branch is merged or no longer needed.
