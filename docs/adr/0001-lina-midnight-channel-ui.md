# ADR 0001: Lina Midnight Channel UI

## Status

Accepted

## Context

Lina needs a user-facing web visual direction for the Telegram Mini App first and the future standalone web client later. The current alpha plan defines the Mini App as a thin UI over the Railway backend, with catalog, profile, usage/limits, plan/access state, onboarding, locked states, and 18+ consent.

The visual system must support product states that matter to Lina:

- personas and modes
- premium and locked access
- explicit 18+ consent
- usage limits and grants
- backend-owned entitlement state

Generic SaaS UI would make Lina forgettable. Pure synthwave/cyberpunk, literal VHS rental design, Win95 nostalgia, or full arcade UI would each overfit one aesthetic and weaken product clarity.

## Decision

Adopt **Lina Midnight Channel UI** as the visual contract for user-facing web surfaces.

The primary metaphor is a polished late-90s premium cable / pay-per-view channel guide:

- personas are channels
- selected persona is the current tuned channel
- premium and locked personas are restricted or scrambled channels
- explicit 18+ consent is age-gated channel access
- usage and grants are airtime, credits, and signal/access meters
- starting a session is tuning in

The design should feel like a premium interactive late-night channel guide, not a generic dashboard and not a retro parody.

## Scope

This ADR applies to:

- Telegram Mini App alpha UI
- future standalone web client UI
- shared web design tokens and component language
- catalog, profile, usage/limits, plan/access state, onboarding, locked states, and 18+ consent UX

This ADR does not apply to:

- backend architecture
- Telegram bot message copy, except entry points that open the Mini App
- admin/operator tools, unless a later ADR adopts this language there
- legal/compliance text content, which must stay plain, serious, and unambiguous

## Visual Formula

Use this as the target balance:

- 70% late-90s cable TV guide / pay-per-view receiver menu
- 15% restricted channel / adult access system
- 10% 90s action and arcade-era command language
- 5% CRT texture

VHS/CRT is a texture layer, not the core metaphor. Arcade is command language and interaction flavor, not the whole UI. Win95 is out of scope for this direction.

## Interface Model

The main Mini App surface should be structured like a channel guide:

- top OSD header with product identity, current access state, and account/profile entry
- preview area for the currently selected persona/channel
- channel guide list with channel numbers, titles, category/capability hints, and access state
- compact access/usage module with backend-owned limits and grants
- bottom command area with primary action such as `Tune In` and secondary navigation such as `Guide`, `Profile`, and `Limits`

The UI should remain app-first. It must not become a marketing landing page.

## Visual Calibration

The approved visual target is a dense mobile channel-guide screen, not a loose mood board. ALPHA-008 should preserve these first-screen signals:

- a branded OSD header with `Lina`, channel/time/recording-style system indicators, and a compact utility/menu affordance
- an access/status panel near the top with pass/plan, usage meter, 18+ state, next action, and signal/system widgets
- a `channels` catalog as the primary content model, using rows/cards with thumbnail, persona title, short description, access badges, and a clear action
- a restricted 18+ row/card that reads as a blocked channel, with red state, lock indicator, and age-confirmation action
- a bottom navigation bar for `Home`, `Chats`, `Access`, and `Profile` style destinations

This calibration is directional, not pixel-perfect. It defines composition, density, state language, and broadcast UI texture. Implementation may adapt spacing, typography, and exact labels for Telegram Mini App constraints.

## Palette Direction

The palette should be restrained and broadcast-oriented:

- deep TV black and charcoal
- dark navy and receiver-blue panels
- warm off-white text
- amber/yellow selected-row highlight
- broadcast red for restricted or dangerous states
- muted teal or blue for secondary system state
- gray-blue bevels or separators when useful

Avoid dominant purple gradients, glossy neon cyberpunk, crypto/casino color language, and constant cyan-magenta glow.

## Typography Direction

Use readable modern UI typography for body text and controls. Use restrained 90s broadcast or arcade-inspired display treatment only for:

- product mark
- OSD labels
- selected channel labels
- short command text
- badges such as `VIP`, `Locked`, `Restricted`, and `On Air`

Do not use all-caps everywhere. Legal, consent, billing, and safety text must prioritize clarity over style.

## Component Rules

Channel guide rows:

- are the primary catalog pattern
- use clear selected, locked, VIP, restricted, and disabled states
- may include subtle static/scrambling for locked channels, but text must remain readable

Preview panel:

- shows the selected persona/channel and key access state
- can use broadcast-style lower thirds and analog texture
- must not rely on explicit or sexualized imagery to communicate the product

Access and usage:

- render backend-owned state only
- can use airtime, credits, signal, or meter language
- must show actual limits and next actions plainly

Consent gate:

- uses restricted channel / age-gated access language
- must be serious and non-coercive
- must not be bypassable through frontend-only state
- must not animate or obscure consent text

Commands:

- primary action can use cable/remote language such as `Tune In`
- secondary actions should stay literal enough to be clear
- destructive or sensitive actions must not be hidden behind style

## Motion And Texture

Allowed in moderation:

- subtle scanlines
- very light broadcast noise
- analog tracking flicker on non-critical decoration
- selected-row movement or OSD transitions
- restrained static on locked/scrambled channels

Required constraints:

- motion must respect reduced-motion preferences
- flicker must never be required to understand state
- effects must not reduce text contrast
- legal and consent text must remain static and readable

## Accessibility And Product Clarity

The visual language must support the product, not compete with it.

- access state must be understandable within seconds
- color cannot be the only state signal
- text must pass practical contrast on its actual background
- mobile touch targets must remain reliable inside Telegram Mini App constraints
- product states must come from backend API responses, not frontend entitlement guesses

## Explicit Non-Goals

Do not make Lina's web UI:

- generic dark SaaS
- neon cyberpunk
- literal VHS rental catalog
- Win95 desktop skin
- full 16-bit game UI
- crypto/casino dashboard
- porn-site UI
- vaporwave parody
- marketing hero page as the primary product surface

## Consequences

ALPHA-008 should implement this direction in the Telegram Mini App as the first web surface. Later standalone web work should extend the same visual language instead of inventing a separate brand.

The Mini App should remain a thin client over backend state. The design contract does not change backend ownership of access, entitlement, consent, or usage decisions.

