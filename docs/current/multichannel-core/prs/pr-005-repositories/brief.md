# PR-005: Repositories

## Goal

Introduce repository APIs around `UserRef + ConversationRef + mode` and enforce state-boundary rules.

## In Scope

- conversation repository methods
- history repository methods
- mode state and mode lock repository methods
- job repository methods
- relationship state repository methods
- analytics event append API
- transaction boundaries for reset and job state transitions

## Out of Scope

- service extraction
- Telegram adapter refactor
- schema redesign beyond repository needs

## Expected Files

- `src/db/repositories.py`
- related tests

## Test Focus

- multiple conversation isolation
- active mode get/set behavior
- reset scope behavior
- job transition rules
- `cancelled` cannot become `completed` or `failed`

## Merge Criteria

- repositories expose plain-structure APIs only
- direct business-path `sqlite3.connect()` calls start disappearing
- transaction-sensitive operations are test-covered
