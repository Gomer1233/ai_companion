# ADR 0002: User Identity And Standalone Web Readiness

## Status

Accepted

## Context

Lina alpha is Telegram-first: one Telegram bot launcher runs on Railway, the Telegram Mini App is the first web surface on Vercel, and Supabase Postgres is the production backend store.

The product direction also includes a future standalone Web client with chat after alpha. That future Web product should not require a rewrite of account, access, consent, usage, or conversation state. Telegram must remain an adapter/channel, not the core identity model of the product.

## Decision

Use the internal `UserRef` as the primary product identity.

Telegram identities are linked accounts, not primary user identities. A Telegram account resolves to a `UserRef`, and future Web login methods must also resolve to a `UserRef`.

Backend-owned state must attach to `UserRef` and backend domain records, not directly to Telegram user ids:

- access grants and plan state
- explicit 18+ consent state
- entitlements and usage counters
- persona allowlist visibility
- conversations and messages
- image jobs and job ownership
- audit events

The Telegram bot, Telegram Mini App, and future standalone Web client should consume the same backend truth through adapter-specific authentication and shared domain services.

## Scope

This ADR applies to:

- alpha backend contracts created or modified during `ALPHA-004` through `ALPHA-010`
- Telegram session exchange and account resolution
- future standalone Web identity and chat planning
- data ownership for access, consent, usage, conversations, and jobs

This ADR does not require alpha to ship:

- email login
- OAuth login
- standalone Web chat
- public non-Telegram account creation
- webhook-based Telegram delivery

## Runtime Stance

Polling on Railway remains acceptable for alpha v1.

Webhook is a Telegram runtime choice, not a prerequisite for standalone Web. A later Telegram webhook migration may be useful for production scaling or operational simplicity, but it should not be treated as the mechanism that makes Lina Web-ready.

## Post-Alpha Web Direction

After `ALPHA-010`, standalone Web should be planned as a separate initiative:

- `WEB-001 Standalone Web Identity`
- `WEB-002 Standalone Web Shell`
- `WEB-003 Web Chat`
- `WEB-004 Web Monetization`

The standalone Web client should extend the `Lina Midnight Channel UI` visual language from `docs/adr/0001-lina-midnight-channel-ui.md`.

## Consequences

New alpha work must avoid hard-coding Telegram user ids as product identity.

Operator commands may still use Telegram user ids for operator allowlists in alpha, but grants, consent, usage, conversations, and jobs must resolve to backend users.

Mini App work should remain a thin client over Railway API responses. It should not become a Telegram-only product model that future standalone Web must replace.

Standalone Web can be added later without changing the alpha deployment path: Railway for backend, Vercel for frontend, and Supabase Postgres for backend-owned state.
