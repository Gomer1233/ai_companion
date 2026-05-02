# ALPHA-005: Monetization Core + Admin Commands

## Goal

Introduce backend monetization state, shared access checks, automated payment fulfillment, and protected operator controls for the alpha model.

## In Scope

- add `free`, `trial`, and `premium` tiers
- add gating for premium characters, explicit characters, and explicit image generation
- make explicit 18+ consent backend state
- introduce trial state and usage counters for messages and explicit images
- define alpha v1 limits:
  - `free`: 30 messages/day, 0 explicit images/day
  - `trial`: 7 days, 100 messages/day, 3 explicit images/day
  - `premium`: 300 messages/day, 20 explicit images/day
- estimate admin-only LLM token cost from logged model/input/output token usage
- implement automated payment order/fulfillment flow
- support Telegram Stars payment as the native in-Telegram digital-goods path
- support T-Bank/SBP/T-Pay only as an external/off-Telegram checkout path that is not presented as an in-bot digital-goods payment provider
- make manual grants an operator fallback/support path, not the primary payment flow
- add a user-facing bot action for current tariff/remaining limits
- implement `/grant_access`, `/revoke_access`, `/user_status`, `/usage_status`, and `/admin_users`
- add operator allowlist, audit events, confirmation guards, and abuse throttling
- expose operator-only backend service/API contracts for the future Mini App admin table

## Out of Scope

- recurring subscription automation
- full refund automation beyond representing refund/cancel states
- accounting-grade revenue reporting
- final persona audit decisions
- Mini App frontend implementation
- visual Mini App admin table implementation
- deploy hardening

## Agreed Access and Admin UX

`ALPHA-005` remains bot-first. Until the Mini App admin table exists, users and operators use Telegram bot fallbacks over the same backend state.

Primary purchase flow:

- user sees a locked premium/explicit capability and taps a buy action
- bot offers Telegram Stars as the native in-Telegram payment choice for premium digital access
- T-Bank/SBP/T-Pay is exposed only as an external/off-Telegram checkout path, for example a support/site checkout link or operator-provided payment link, and must not be represented as an in-bot third-party digital-goods payment provider
- purchasable alpha products:
  - `premium_30d`: 500 XTR via Telegram Stars; 499 RUB only through external/off-Telegram T-Bank/SBP/T-Pay checkout
  - `premium_1y`: 2000 XTR via Telegram Stars; 1990 RUB only through external/off-Telegram T-Bank/SBP/T-Pay checkout
  - `lifetime_premium_100`: 3000 XTR via Telegram Stars; 2990 RUB only through external/off-Telegram T-Bank/SBP/T-Pay checkout, capped to the first 100 lifetime purchases/grants
- backend creates a `payment_order` before redirecting/sending invoice
- payment provider confirmation marks the order paid
- backend fulfills the paid order by granting entitlement idempotently
- user can immediately verify access through `Остаток по тарифу`

Lifetime product rules:

- `lifetime_premium_100` grants `premium` with no expiration for the user's account
- "lifetime" means the premium tier does not expire while the Lina AI service exists
- daily usage limits, safety rules, provider availability, and feature availability remain governed by current backend policy
- lifetime access is not unlimited usage
- sales must stop once 100 lifetime purchases/grants are fulfilled

Payment fulfillment requirements:

- every payment provider must map back to an internal `order_id`
- fulfillment must be idempotent; duplicate provider callbacks must not duplicate entitlements
- paid-but-not-fulfilled orders must be visible to operators
- operator repair path must exist for paid orders that failed fulfillment
- refund/cancel state must be representable, but user-facing refund buttons are out of scope
- refund requests are handled through support/admin contact first; operator actions may revoke/mark refunded after manual review
- Telegram policy guard: premium digital access sold inside Telegram bot/Mini App must use Stars/XTR; T-Bank/SBP/T-Pay must stay outside the in-Telegram digital-goods purchase UI
- T-Bank/SBP/T-Pay implementation should leave room for receipt/fiscal payload fields, but accounting-grade fiscal reporting is out of scope
- T-Bank/SBP/T-Pay must be implemented sandbox-first with an explicit `TBANK_ENV=sandbox|production` switch
- production T-Bank/SBP/T-Pay credentials must not be required for local tests
- payment fulfillment must run in one DB transaction that links one `payment_order` to one `entitlement`
- `payment_orders.entitlement_id` or equivalent unique order-to-entitlement relation is required
- duplicate payment callbacks and operator repair commands must reuse the existing entitlement instead of creating another one

Expected payment environment shape:

- `TBANK_ENV`
- `TBANK_TERMINAL_KEY`
- `TBANK_PASSWORD`
- `TBANK_SUCCESS_URL`
- `TBANK_FAIL_URL`
- `TBANK_WEBHOOK_SECRET` or equivalent signature verification material, depending on the final T-Bank API contract

User-facing bot behavior:

- add a simple `Остаток по тарифу` action/button
- show tier, expiry, messages remaining, explicit images remaining, and explicit 18+ consent state
- do not show model token cost to regular users

Operator behavior:

- operators are configured by `OPERATOR_TELEGRAM_IDS`
- grant/revoke commands require `confirm` and are support overrides, not the primary sales flow
- trial is granted manually by an operator, not sold as a payment product
- manual trial grants must support per-user duration and per-user message/image limits
- manual lifetime grants count against the `lifetime_premium_100` 100-user cap
- `/admin_users` provides a compact paginated list with search/filter/sort arguments
- admin list fields should include Telegram ID, name/username, tier, expiry, payment/order status, message usage, explicit image usage, estimated LLM token cost, 18+ consent, last active time, and available actions
- future Mini App admin UI should use the same backend service/API contract rather than duplicating access logic

Admin list sorting should support at least tier, expiry, message usage, image usage, token cost, and last active time.

## Expected Files

- `src/core/**`
- `src/app/**`
- `src/adapters/telegram/**`
- `src/adapters/http/**`
- `src/db/**`
- `tests/**`
- `docs/current/alpha-launch/status.md`

## Test Focus

- shared access decisions across bot and Mini App-facing services
- tier/trial/consent behavior
- daily usage windows for messages and explicit images
- admin-only cost estimate calculations from logged token usage
- payment order lifecycle for Telegram Stars and T-Bank/SBP/T-Pay
- idempotent payment fulfillment and duplicate callback handling
- paid-but-not-fulfilled operator visibility/repair behavior
- operator allowlist and audit behavior
- manual grant and revoke flows
- user-facing tariff status output
- `/admin_users` filtering/sorting/pagination behavior

## Merge Criteria

- bot-first path cannot bypass explicit gate
- consent/access state is shared across transports
- user can buy premium through Telegram Stars inside Telegram, and through T-Bank/SBP/T-Pay only via an external/off-Telegram checkout path without manual admin fulfillment
- successful payment automatically grants access through idempotent fulfillment
- paid-but-not-fulfilled states are visible and repairable by an operator
- operator commands are protected and test-covered
- users can see their current tariff and remaining limits from the bot
- operators can inspect a compact user list without querying each user manually
- no public admin HTTP endpoints are introduced
