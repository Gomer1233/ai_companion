# PR-008: DX + Cleanup

## Goal

Finish the initiative with quality gates, cleaned active source tree, and updated documentation.

## In Scope

- `ruff`
- limited `mypy` for extracted code
- CI for tests and lint
- active source tree cleanup
- README update
- archival cleanup for stale planning material if still needed
- root cleanup for non-canonical helpers, legacy-local folders, and misplaced assets

## Out of Scope

- new runtime behavior
- new adapter work
- persistence redesign

## Expected Files

- lint/type configs
- CI files
- `README.md`
- docs cleanup
- root-level cleanup targets such as `commit_changes.ps1`, `system/`, `Тесты/`, and `Photo/`

## Test Focus

- full test suite
- lint
- type-check on extracted code

## Merge Criteria

- CI runs tests and lint successfully
- repo documentation matches implemented architecture
- cleanup stays separate from functional changes
- repository root is reduced to operational files, manifests, and canonical guidance only
