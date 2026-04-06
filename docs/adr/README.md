# Architectural Decisions

This directory stores accepted architecture decisions.

Use ADRs only for decisions that have been intentionally chosen and should not be re-litigated in every PR.

Typical ADR topics:

- Telegram is an adapter, not the system core
- active mode is conversation-scoped
- migrations are forward-only in the first cycle
- `photo_gate` is core-state

Do not put drafts or initiative planning here. Drafts belong in:

- `docs/current/multichannel-core/**`
