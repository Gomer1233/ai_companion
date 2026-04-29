# Lina AI

Lina AI now runs as a single Telegram bot launcher with one active entrypoint and one shared runtime path.

## Project Layout

- `src/main.py`
  Single Telegram launcher with the full product functionality, including relationship logic and rap submodes.
- `src/app/`
  Typed settings, provider registry, and runtime config.
- `src/core/`
  Core contracts and shared transition runtime.
- `src/db/`
  SQLite local persistence, Postgres production bootstrap, and repository implementations.
- `src/adapters/telegram/`
  Telegram parser, renderer, and routing helpers.
- `tests/`
  Smoke, characterization, migration, repository, shared runtime, and adapter tests.
- `docs/current/multichannel-core/`
  Active planning contour for the completed refactor initiative.

## Canonical Docs

Use these files as the active source of truth:

- `docs/current/multichannel-core/execution-plan.md`
- `docs/current/multichannel-core/pr-backlog.md`
- `docs/current/multichannel-core/status.md`

Archived material is historical only:

- `docs/archive/**`
- `archive/**`

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Run

```bash
python -m src.main
```

Local development defaults to SQLite via `DB_BACKEND=sqlite` and `BOT_DB_PATH`.
Production alpha uses Supabase Postgres by setting `DB_BACKEND=postgres` and `DATABASE_URL` in Railway.

Utilities:

```bash
python -m src.check_events
python -m src.export_user_report
```

## Quality Gates

```bash
python -m pytest -q
python -m ruff check src tests
python -m mypy src/app src/core src/db src/adapters
```

## Root Policy

Keep only operational files, manifests, and canonical guidance in the repository root:

- `README.md`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `.rgignore`
- `AGENTS.md`
- `.github/workflows/`

Local-only helpers and legacy artifacts belong under `.local/` and must not be treated as source of truth.
