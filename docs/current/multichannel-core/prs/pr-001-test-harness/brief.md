# PR-001: Test Harness + Characterization

## Goal

Lock current behavior of `src/main.py` and `src/bot_lika.py` in automated tests before any refactor or bugfix changes.

## In Scope

- add `pytest` and minimal test harness
- add characterization tests for both legacy entrypoints
- document observed differences between `main.py` and `bot_lika.py`
- capture known-bad behavior as explicit expectations or `xfail`

## Out of Scope

- bugfixes
- code extraction
- schema changes
- cleanup of Telegram adapter code

## Expected Files

- `tests/**`
- `requirements.txt` or test config files
- `docs/current/multichannel-core/status.md`

## Test Focus

- startup/import for both entrypoints
- `/start -> mode switch -> text flow`
- image prompt flow
- `/reset` and current-mode reset
- `chef`, `oldschool_rep`, `whore` behavior

## Merge Criteria

- new tests run locally
- differences between the two bots are explicit
- no runtime behavior is intentionally changed in this PR
