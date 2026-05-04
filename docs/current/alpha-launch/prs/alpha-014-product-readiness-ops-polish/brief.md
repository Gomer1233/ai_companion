# ALPHA-014: Alpha Product Readiness + Ops Polish

## Goal

Close product-readiness and operations gaps after Mini App text chat and image jobs are in place.

## In Scope

- End-to-end smoke/e2e checks for Telegram entry, Mini App chat, access, consent, usage, and image jobs.
- UX copy pass for chat, locked, consent, support, and error states.
- Support/account flow review against ALPHA-009 runbooks.
- Telemetry/logging gap review without logging raw prompts or sensitive explicit payloads.
- Launch checklist for expanding the alpha cohort.

## Out of Scope

- New core product capabilities.
- New providers or personas.
- Standalone Web identity.
- Major backend refactors unrelated to readiness gaps.

## Test Focus

- Production-like smoke coverage over Railway and Vercel.
- No sensitive payload logging.
- Support and abuse routes remain documented and executable.
- Known gaps are documented before cohort expansion.

## Merge Criteria

- Alpha Mini App has a repeatable readiness checklist.
- Critical smoke/e2e paths pass or have explicit documented blockers.
- Operators have clear support, incident, rollback, and escalation steps for the expanded alpha.
