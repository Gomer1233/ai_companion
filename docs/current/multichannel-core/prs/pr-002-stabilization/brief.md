# PR-002: Stabilization Fixes

## Goal

Fix confirmed runtime bugs and false product promises without changing the overall architecture.

## In Scope

- fix `bot_lika` startup bug for `IMAGE_BACKEND_PROVIDER=openai`
- align declared and actual provider support
- remove or disable false `/model` feature
- make reset deterministic on the current schema
- remove raw content and reply preview logging
- fix critical SQL and init defects

## Out of Scope

- new core contracts
- new persistence model
- adapter extraction

## Expected Files

- `src/main.py`
- `src/bot_lika.py`
- `.env.example`
- `README.md`
- tests introduced in `PR-001`

## Test Focus

- startup/provider matrix
- deterministic reset
- `/model` removal does not break other flows
- no raw user or assistant content remains in logs

## Merge Criteria

- documented configurations start successfully
- reset clears expected state on current schema
- characterization tests only change where a deliberate bugfix requires it
