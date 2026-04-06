# ALPHA-009: Compliance Completion + Alpha Ops

## Goal

Finish the legal, support, abuse, and operational hardening needed to run the explicit alpha in a controlled way.

## In Scope

- privacy policy
- terms
- explicit 18+ disclaimer and consent model copy/path
- deletion/export flow
- abuse/reporting path
- logging policy for sensitive data
- secrets management procedure
- backup/restore procedure
- closed alpha cohort and support process

## Out of Scope

- payment provider automation
- core product feature work unrelated to compliance/ops
- rewriting backend transport architecture

## Expected Files

- `docs/current/alpha-launch/**`
- legal/support/ops docs or app-facing copy files as needed
- `tests/**` where behavior is implemented

## Test Focus

- consent flow behavior where implemented
- removal/export flow behavior where implemented
- no sensitive payload logging
- operator/support process completeness

## Merge Criteria

- legal/compliance materials are launch-ready
- support, abuse, and account-removal process exists and is documented
- logging/secrets/backup policies are explicit and reviewable
