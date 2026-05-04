# ALPHA-012: Mini App App Shell + Chat UX

## Goal

Make the Mini App feel like a coherent chat-first application after ALPHA-011 proves the backend chat foundation.

## In Scope

- Chat-first layout and navigation around the ALPHA-011 per-persona chat API.
- Empty, loading, sending, error, locked, and usage-limit states.
- Thread reset UX using existing backend reset/conversation semantics where possible.
- Profile, access, support, and limits as secondary screens.
- Refinement of the `Lina Midnight Channel UI` visual contract for a real chat surface.

## Out of Scope

- New backend chat capabilities beyond what ALPHA-011 exposes.
- Image generation.
- Standalone Web identity.
- Billing redesign or new providers.

## Test Focus

- Mini App navigation behaves as app shell navigation, not decorative links.
- Chat panel remains the primary surface.
- Reset/empty/error states are covered by frontend tests.
- Locked persona states remain backend-owned.

## Merge Criteria

- A tester can understand and use the Mini App as a chat app without returning to Telegram for normal text turns.
- Access/Profile/Support remain reachable but secondary.
- Mini App build, typecheck, and tests pass.
