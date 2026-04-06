# PR-006: Shared Core Extraction

## Goal

Move shared business logic out of the two monolith entrypoints into a common application core.

## In Scope

- shared chat orchestration
- shared image orchestration
- shared audio orchestration
- shared mode and policy logic
- shared reset and state logic
- relationship logic as optional extension
- variant differences expressed through `AppVariantConfig`

## Out of Scope

- schema migration
- Telegram UI cleanup
- unrelated cleanup and renaming

## Expected Files

- `src/core/**`
- simplified `src/main.py`
- simplified `src/bot_lika.py`

## Test Focus

- integration tests for text, image, reset, and mode switch
- variant behavior tests
- no change to contract ordering in `CoreResponse.items`

## Merge Criteria

- `main.py` and `bot_lika.py` no longer hold independent business logic
- characterization regressions are explained by prior approved bugfixes only
