# PR-007: Telegram Adapter Cleanup

## Goal

Make Telegram a clean adapter over the shared core.

## In Scope

- parser from `aiogram` updates to `InboundEvent`
- renderer from `CoreResponse.items` to Telegram UI
- adapter-level command routing
- adapter-level callback handling
- adapter-only UI and transport state

## Out of Scope

- core behavior changes
- schema changes
- unrelated cleanup

## Expected Files

- `src/adapters/telegram/**`
- Telegram entrypoint bootstrap files

## Test Focus

- update parsing
- `/reset` and callback mapping
- ordered item rendering
- default conversation resolution rules

## Merge Criteria

- `aiogram` stays in adapter layer
- Telegram-specific UI concerns do not leak back into core contracts
