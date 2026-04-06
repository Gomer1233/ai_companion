# ALPHA-008: Mini App Alpha

## Goal

Ship the Telegram Mini App frontend on Vercel as a thin UI over the Railway backend without duplicating entitlement or business logic.

## In Scope

- create Next.js Mini App frontend
- implement catalog, profile, usage/limits, plan/access state, locked premium states, onboarding, and 18+ consent UX
- integrate backend session exchange and silent re-auth on `401`
- add open-app entry point from the bot
- keep frontend thin over Railway API responses

## Out of Scope

- moving the primary chat into the Mini App
- direct Supabase access from browser code
- admin HTTP surfaces

## Expected Files

- frontend app files for the Mini App
- Telegram bot entry-point wiring for open-app button
- `tests/**`
- `docs/current/alpha-launch/status.md`

## Test Focus

- direct browser -> Railway API path
- backend session exchange and re-auth
- catalog and access-state parity with the bot
- no frontend-owned entitlement logic

## Merge Criteria

- Mini App uses backend-issued session tokens only
- UI reflects backend access state exactly
- explicit UI remains gated by backend consent state
- Vercel frontend stays a thin client over Railway API
