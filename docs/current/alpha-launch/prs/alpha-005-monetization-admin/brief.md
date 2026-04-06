# ALPHA-005: Monetization Core + Admin Commands

## Goal

Introduce backend monetization state, shared access checks, and protected operator bot commands for the manual-grant alpha model.

## In Scope

- add `free`, `trial`, and `premium` tiers
- add gating for premium characters, explicit characters, and explicit image generation
- make explicit 18+ consent backend state
- introduce trial state and usage counters
- implement `/grant_access`, `/revoke_access`, `/user_status`, `/usage_status`
- add operator allowlist, audit events, confirmation guards, and abuse throttling

## Out of Scope

- payment automation
- final persona audit decisions
- Mini App frontend implementation
- deploy hardening

## Expected Files

- `src/core/**`
- `src/adapters/telegram/**`
- `src/db/**`
- `tests/**`
- `docs/current/alpha-launch/status.md`

## Test Focus

- shared access decisions across bot and Mini App-facing services
- tier/trial/consent behavior
- operator allowlist and audit behavior
- manual grant and revoke flows

## Merge Criteria

- bot-first path cannot bypass explicit gate
- consent/access state is shared across transports
- operator commands are protected and test-covered
- no public admin HTTP endpoints are introduced
