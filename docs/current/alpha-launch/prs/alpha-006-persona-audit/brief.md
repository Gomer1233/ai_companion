# ALPHA-006: Persona Audit + Launch Allowlist Freeze

## Goal

Audit every candidate persona, produce operational verdicts, freeze the alpha allowlist, and build the frozen launch model manifest from approved personas only.

## In Scope

- audit all personas currently present in `src/config/modes.py`
- store per-persona audit records with `verdict`, `owner`, `risk_class`, `default_tier`, and `kill_switch_key`
- apply the audit checklist for prompt quality, policy compliance, access mapping, explicit eligibility, bot UX, Mini App catalog sanity, and smoke pass
- freeze the alpha allowlist from `launch-approved` personas only
- add config kill switches
- assemble the frozen launch model manifest from approved personas

## Out of Scope

- provider model cleanup already covered by ALPHA-004
- Mini App UI implementation
- deploy work

## Expected Files

- `src/config/**`
- `src/core/**`
- `tests/**`
- `docs/current/alpha-launch/status.md`
- initiative docs or data files that capture persona audit records/manifest

## Test Focus

- frozen allowlist behavior in bot and API catalog paths
- disabled persona not leaking into menus or API
- manifest generation/validation
- audit checklist coverage where automated

## Merge Criteria

- every candidate persona has an explicit verdict
- alpha catalog is driven only by approved personas
- frozen launch model manifest exists and is used as the source of truth
- persona launch readiness no longer depends on implicit `modes.py` presence
