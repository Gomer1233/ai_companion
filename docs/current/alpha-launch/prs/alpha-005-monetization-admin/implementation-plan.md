# ALPHA-005 Monetization Core + Admin Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend monetization, automated payment fulfillment, shared access checks, and protected operator controls for alpha paid access.

**Architecture:** Introduce a focused monetization core service that owns products, tier decisions, usage limits, payment orders, fulfillment, and admin summaries. Keep provider-specific payment mechanics behind small adapters for Telegram Stars and external/off-Telegram T-Bank/SBP/T-Pay checkout, and route bot/admin/HTTP webhook surfaces through the same repository-backed service.

**Tech Stack:** Python 3.11, dataclasses/enums, SQLite/Postgres repositories, aiogram payment handlers, FastAPI webhook route, httpx, pytest.

---

## References

- Telegram Stars payments: `https://core.telegram.org/bots/payments-stars`
- Telegram Bot API payments: `https://core.telegram.org/bots/api#payments`
- T-Bank Init payment: `https://developer.tbank.ru/eacq/api/init`
- T-Bank operation notifications: `https://developer.tbank.ru/eacq/intro/developer/notification`
- T-Bank payment status: `https://developer.tbank.ru/eacq/api/get-state`
- T-Bank SBP QR: `https://developer.tbank.ru/eacq/api/get-qr`

## File Structure

- Create `src/core/monetization.py`: tier/product enums, alpha limits, product catalog, cost estimator, access snapshots, payment order domain types, and pure decision helpers.
- Create `src/core/payment_providers.py`: provider-facing request/verification helpers for Telegram Stars payloads and T-Bank token generation/notification verification.
- Modify `src/core/access_policy.py`: compose explicit provider policy with monetization entitlement/consent checks without moving payment logic into provider policy.
- Modify `src/app/settings.py`: add operator allowlist, T-Bank env, and public payment callback/success/fail URL settings.
- Modify `src/db/migrations.py`: add SQLite migration for entitlements, usage counters, access grants, explicit consent, and payment orders.
- Modify `src/db/postgres_schema.py`: add/align Postgres schema for explicit consent and payment orders; keep existing monetization tables compatible.
- Modify `src/db/repositories.py`: add repository methods for monetization state, usage counters, payment orders, operator summaries, and admin audit events.
- Modify `src/db/postgres.py`: ensure Postgres user bootstrap remains compatible with monetization repository methods.
- Modify `src/db/cutover.py`: include payment orders, explicit consent, admin audit events, and entitlement revoke fields in SQLite-to-Postgres cutover.
- Modify `src/adapters/http/routes/api.py`: return real entitlement/usage state for user endpoints.
- Create `src/adapters/http/routes/payments.py`: T-Bank webhook/status callback route plus safe payment order lookup route; no public admin endpoints.
- Modify `src/adapters/http/app.py`: mount payment route.
- Create `src/adapters/telegram/admin.py`: parse and render operator commands and admin summaries.
- Create `src/adapters/telegram/payments.py`: build buy keyboards/invoices and parse Telegram payment payloads.
- Modify `src/main.py`: wire user tariff button, Stars buy actions/pre-checkout/success handlers, external checkout handoff text for T-Bank/SBP/T-Pay when enabled, and operator command handlers.
- Modify `tests/conftest.py`: add payment/operator env isolation.
- Create `tests/test_monetization_core.py`: product/limit/access/cost/fulfillment unit tests.
- Create `tests/test_payment_providers.py`: Telegram payload and T-Bank signature/token tests.
- Create `tests/test_monetization_repositories.py`: SQLite repository behavior for entitlement/usage/order state.
- Modify `tests/test_postgres_backend.py`: schema smoke for new monetization/payment tables.
- Modify `tests/test_cutover.py` or existing cutover rehearsal tests: cover new monetization/payment/consent/audit tables.
- Modify `tests/test_http_api.py`: real entitlements/usage and payment webhook behavior.
- Modify `tests/test_entrypoint_smoke.py`: Telegram command/payment handler smoke coverage.
- Modify `docs/current/alpha-launch/status.md`: mark ALPHA-005 started after implementation begins, not during planning.
- Modify `docs/current/alpha-launch/prs/alpha-005-monetization-admin/tasks.md`: check tasks only after implementation and verification.

## Task 0: Start From Clean Main

**Files:**
- No code changes.

- [ ] **Step 1: switch to a fresh implementation branch**

Run:

```powershell
git fetch origin
git switch -c codex/alpha-005-monetization-admin origin/main
```

Expected: branch created from current `origin/main`.

- [ ] **Step 2: verify dirty state before coding**

Run:

```powershell
git status --short --branch
```

Expected: clean tree except intentional planning files if they have not been committed separately.

## Task 1: Core Products, Limits, and Cost Estimation

**Files:**
- Create: `src/core/monetization.py`
- Test: `tests/test_monetization_core.py`

- [ ] **Step 1: write failing tests**

Create `tests/test_monetization_core.py` with tests for:

```python
def test_alpha_products_and_prices_are_fixed() -> None:
    catalog = AlphaProductCatalog.default()

    assert catalog.get("premium_30d").price_rub == 499
    assert catalog.get("premium_30d").price_xtr == 500
    assert catalog.get("premium_30d").duration_days == 30
    assert catalog.get("premium_1y").price_rub == 1990
    assert catalog.get("premium_1y").price_xtr == 2000
    assert catalog.get("premium_1y").duration_days == 365
    assert catalog.get("lifetime_premium_100").price_rub == 2990
    assert catalog.get("lifetime_premium_100").price_xtr == 3000
    assert catalog.get("lifetime_premium_100").duration_days is None
    assert catalog.get("lifetime_premium_100").max_sales == 100


def test_alpha_limits_are_fixed_by_tier() -> None:
    policy = AlphaMonetizationPolicy.default()

    assert policy.limits_for(Tier.FREE).messages_per_day == 30
    assert policy.limits_for(Tier.FREE).explicit_images_per_day == 0
    assert policy.limits_for(Tier.TRIAL).messages_per_day == 100
    assert policy.limits_for(Tier.TRIAL).explicit_images_per_day == 3
    assert policy.limits_for(Tier.PREMIUM).messages_per_day == 300
    assert policy.limits_for(Tier.PREMIUM).explicit_images_per_day == 20


def test_cost_estimator_uses_input_and_output_token_prices() -> None:
    estimator = LlmCostEstimator.default()

    estimate = estimator.estimate("x-ai/grok-4.1-fast", prompt_tokens=1_000_000, completion_tokens=1_000_000)

    assert estimate.usd == 0.70
```

- [ ] **Step 2: run RED**

Run:

```powershell
python -m pytest tests/test_monetization_core.py -q
```

Expected: import failure for `src.core.monetization`.

- [ ] **Step 3: implement minimal core types**

Create `src/core/monetization.py` with:

- `Tier`: `free`, `trial`, `premium`
- `ProductId`: `premium_30d`, `premium_1y`, `lifetime_premium_100`
- `PaymentProvider`: `telegram_stars`, `tbank`
- `PaymentStatus`: `pending`, `paid`, `fulfilled`, `failed`, `cancelled`, `refunded`
- `UsageLimits(messages_per_day, explicit_images_per_day)`
- `Product(product_id, tier, duration_days, price_rub, price_xtr, max_sales)`
- `AlphaProductCatalog.default()`
- `AlphaMonetizationPolicy.default()`
- `LlmCostEstimator.default()`

Use `Decimal` internally for cost math and expose rounded float/string formatting only in renderers.

- [ ] **Step 4: run GREEN**

Run:

```powershell
python -m pytest tests/test_monetization_core.py -q
```

Expected: product, limit, and cost tests pass.

## Task 2: Persistence Schema and Repository API

**Files:**
- Modify: `src/db/migrations.py`
- Modify: `src/db/postgres_schema.py`
- Modify: `src/db/repositories.py`
- Test: `tests/test_monetization_repositories.py`
- Test: `tests/test_migrations.py`
- Test: `tests/test_postgres_backend.py`

- [ ] **Step 1: write failing repository tests**

Create tests that prove:

- a premium entitlement can be saved and loaded
- expired entitlement is ignored for effective tier
- usage counter increments inside a daily window
- explicit consent can be accepted and loaded
- payment order transitions `pending -> paid -> fulfilled`
- duplicate fulfillment does not create duplicate entitlements
- lifetime sales count blocks the 101st fulfilled lifetime order
- order fulfillment stores a unique `payment_order -> entitlement` link
- retry after entitlement creation but before fulfilled status reuses the existing entitlement

Use `tmp_path` SQLite DB and `migrate_database()`.

- [ ] **Step 2: run RED**

Run:

```powershell
python -m pytest tests/test_monetization_repositories.py -q
```

Expected: missing tables/repository methods.

- [ ] **Step 3: add SQLite migration 005**

Increase `SCHEMA_VERSION` to `5` and add `_migration_005_monetization_payments()` creating:

- `entitlements(entitlement_id, user_id, plan_id, tier, starts_at, expires_at, status, source, created_at, revoked_at, revoked_by, revoked_reason, metadata_json)`
- `usage_counters(user_id, counter_key, window_start, window_end, value)`
- `access_grants(grant_id, user_id, granted_by, grant_type, reason, created_at, revoked_at, metadata_json)`
- `admin_audit_events(audit_id, operator_user_id, target_user_id, target_order_id, action, result, reason, created_at, metadata_json)`
- `explicit_consent(user_id PRIMARY KEY, accepted_at, revoked_at, source)`
- `payment_orders(order_id PRIMARY KEY, user_id, provider, product_id, amount_minor, currency, status, entitlement_id, provider_payment_id, provider_payload_json, created_at, paid_at, fulfilled_at, refunded_at, cancelled_at, error_code)`

Add uniqueness rules:

- `payment_orders.entitlement_id` must be unique when present
- `entitlements.source` must be unique for payment-created entitlements, using `payment:<provider>:<order_id>`
- active entitlement queries must filter out revoked entitlements via `status`/`revoked_at`

Keep table names aligned with existing Postgres cutover table names where already present.

- [ ] **Step 4: align Postgres schema**

Add missing columns/tables to `src/db/postgres_schema.py`:

- `explicit_consent`
- `payment_orders`
- `admin_audit_events`
- `entitlements.status`, `entitlements.revoked_at`, `entitlements.revoked_by`, and `entitlements.revoked_reason`
- `metadata_json` columns where needed if absent
- `payment_orders.entitlement_id`
- indexes for `payment_orders(user_id)`, `payment_orders(status)`, `payment_orders(provider_payment_id)`, `entitlements(user_id, tier)`, and `usage_counters(user_id, counter_key)`
- uniqueness for the order-to-entitlement relation and payment entitlement source

- [ ] **Step 5: add repository methods**

Add methods to `SQLiteRepositories`:

- `upsert_entitlement(...)`
- `load_active_entitlements(user_ref, now_ts)`
- `count_fulfilled_product(product_id)`
- `increment_usage(user_ref, counter_key, window_start, window_end, amount=1)`
- `load_usage(user_ref, counter_key, window_start)`
- `set_explicit_consent(user_ref, accepted_at, source)`
- `load_explicit_consent(user_ref)`
- `create_payment_order(order)`
- `load_payment_order(order_id)`
- `mark_payment_order_paid(order_id, provider_payment_id, provider_payload_json, paid_at)`
- `fulfill_paid_order_transactionally(order_id, now_ts)` or an equivalent repository-level transaction context that creates/reuses the entitlement, links `payment_orders.entitlement_id`, and marks the order fulfilled atomically
- `revoke_entitlements(user_ref, revoked_by, revoked_at, reason, source_filter=None)`
- `list_admin_user_summaries(filters, sort, page, page_size)`

Do not implement fulfillment as service orchestration across repository methods that each open their own connection and commit independently. The atomic unit must live inside a repository transaction or explicit transaction context shared by all fulfillment writes.

Postgres inherits these methods through `_connect()` and `_ensure_user()` where needed.

- [ ] **Step 6: align cutover coverage**

Update `src/db/cutover.py` and cutover rehearsal tests so SQLite-to-Postgres migration preserves:

- `payment_orders`
- `explicit_consent`
- `admin_audit_events`
- new `entitlements` revoke/status columns
- payment order to entitlement links

- [ ] **Step 7: run GREEN**

Run:

```powershell
python -m pytest tests/test_monetization_repositories.py tests/test_migrations.py tests/test_postgres_backend.py tests/test_cutover.py -q
```

Expected: repository and schema tests pass, Postgres tests skip when no test DB is configured.

## Task 3: Monetization Service and Access Decisions

**Files:**
- Modify: `src/core/monetization.py`
- Modify: `src/core/access_policy.py`
- Test: `tests/test_monetization_core.py`
- Test: `tests/test_core_contracts_and_config.py`

- [ ] **Step 1: write failing service tests**

Add tests for:

- free user cannot access premium persona
- free user cannot access explicit persona even with consent
- trial user with consent can access explicit persona until expiry
- premium user without consent cannot access explicit persona
- custom trial grant overrides default trial message/image limits for one user
- explicit image generation is denied when daily image usage reaches limit

- [ ] **Step 2: run RED**

Run:

```powershell
python -m pytest tests/test_monetization_core.py tests/test_core_contracts_and_config.py -q
```

Expected: missing service/access methods.

- [ ] **Step 3: implement service-level decisions**

Add:

- `AccessSnapshot(user_ref, effective_tier, tier_expires_at, explicit_consent, limits, usage, blocked_reasons)`
- `MonetizationService`
- `get_effective_tier(user_ref, now_ts)`
- `get_access_snapshot(user_ref, now_ts)`
- `can_use_persona(user_ref, persona, now_ts)`
- `can_generate_explicit_image(user_ref, now_ts)`
- `record_message_usage(user_ref, now_ts)`
- `record_explicit_image_usage(user_ref, now_ts)`

Keep explicit provider/model checks in `AccessPolicyService`; monetization only answers entitlement/consent/limit questions.

- [ ] **Step 4: run GREEN**

Run:

```powershell
python -m pytest tests/test_monetization_core.py tests/test_core_contracts_and_config.py -q
```

Expected: access decision tests pass.

## Task 4: Payment Orders and Idempotent Fulfillment

**Files:**
- Modify: `src/core/monetization.py`
- Test: `tests/test_monetization_core.py`
- Test: `tests/test_monetization_repositories.py`

- [ ] **Step 1: write failing payment lifecycle tests**

Tests must cover:

- creating an order for `premium_30d`
- fulfilling paid order creates premium entitlement expiring in 30 days
- fulfilling `premium_1y` creates 365-day premium entitlement
- fulfilling `lifetime_premium_100` creates non-expiring entitlement
- fulfilling the same order twice returns the existing entitlement/order state
- lifetime order fulfillment fails when 100 lifetime orders are already fulfilled
- refund/cancel states do not expose user-facing refund actions
- transactional fulfillment crash/retry cases: entitlement exists but order is not fulfilled must converge to the same entitlement, and duplicate callbacks must not create a second entitlement
- repository fulfillment uses a single transaction boundary rather than separate committed writes

- [ ] **Step 2: run RED**

Run:

```powershell
python -m pytest tests/test_monetization_core.py tests/test_monetization_repositories.py -q
```

Expected: missing order/fulfillment methods.

- [ ] **Step 3: implement payment lifecycle**

Add service methods:

- `create_payment_order(user_ref, provider, product_id, now_ts)`
- `mark_order_paid(order_id, provider_payment_id, provider_payload, paid_at)`
- `fulfill_paid_order(order_id, now_ts)`
- `mark_order_refunded(order_id, refunded_at)`
- `mark_order_cancelled(order_id, cancelled_at)`
- `append_admin_audit_event(operator_ref, action, target_ref, result, reason, created_at)`

Fulfillment must:

- require status `paid`
- be idempotent when status is already `fulfilled`
- delegate the atomic write sequence to `fulfill_paid_order_transactionally(...)` or an equivalent repository transaction context
- run in one DB transaction from entitlement creation/linking through `payment_orders.status='fulfilled'`
- create or reuse exactly one entitlement per fulfilled order
- write `payment_orders.entitlement_id` before commit
- include `source="payment:<provider>:<order_id>"`
- enforce lifetime cap before entitlement creation
- recover safely if a prior attempt created the entitlement but failed before marking the order fulfilled

`mark_order_paid(...)` may be a separate transition because it represents provider confirmation. The entitlement creation, order-entitlement link, and fulfilled status update must not be split across independently committed repository calls.

- [ ] **Step 4: run GREEN**

Run:

```powershell
python -m pytest tests/test_monetization_core.py tests/test_monetization_repositories.py -q
```

Expected: payment lifecycle tests pass.

## Task 5: Telegram Stars Payment Flow

**Files:**
- Create: `src/adapters/telegram/payments.py`
- Modify: `src/main.py`
- Test: `tests/test_payment_providers.py`
- Test: `tests/test_entrypoint_smoke.py`

- [ ] **Step 1: write failing Telegram payment tests**

Tests must prove:

- invoice payload contains internal `order_id`
- Stars invoice amount uses XTR price from product catalog
- in-Telegram digital access buy UI exposes Stars/XTR only, not T-Bank or another third-party provider
- `pre_checkout_query` rejects unknown/mismatched order
- `successful_payment` marks the order paid and calls fulfillment once
- duplicate successful payment update is idempotent

- [ ] **Step 2: run RED**

Run:

```powershell
python -m pytest tests/test_payment_providers.py tests/test_entrypoint_smoke.py -q
```

Expected: missing Telegram payment adapter/handlers.

- [ ] **Step 3: implement Telegram payment adapter and handlers**

Use Telegram Stars requirements:

- invoice currency: `XTR`
- one `LabeledPrice` in Stars units
- payload includes JSON with `order_id`, `product_id`, and `provider="telegram_stars"`
- handle `pre_checkout_query`
- handle `successful_payment`

Render buy buttons:

- `premium_30d`
- `premium_1y`
- `lifetime_premium_100` only while cap has not been reached

Do not render T-Bank/SBP/T-Pay as an in-Telegram payment provider for digital access. Telegram Stars/XTR is the only native bot/Mini App purchase path for this digital product.

- [ ] **Step 4: run GREEN**

Run:

```powershell
python -m pytest tests/test_payment_providers.py tests/test_entrypoint_smoke.py -q
```

Expected: Stars payment tests pass without contacting Telegram.

## Task 6: T-Bank/SBP/T-Pay Sandbox-First Flow

**Files:**
- Modify: `src/app/settings.py`
- Create: `src/core/payment_providers.py`
- Create: `src/adapters/http/routes/payments.py`
- Modify: `src/adapters/http/app.py`
- Modify: `src/main.py`
- Test: `tests/test_payment_providers.py`
- Test: `tests/test_http_api.py`

- [ ] **Step 1: write failing T-Bank provider tests**

Tests must prove:

- `TBANK_ENV=sandbox` selects sandbox/test base URL
- Init payload includes `TerminalKey`, `Amount` in kopecks, `OrderId`, `NotificationURL`, `SuccessURL`, `FailURL`
- token generation sorts scalar fields, adds password, concatenates values, and SHA-256 hashes the result
- notification verification excludes `Token` and nested `Data`/`Receipt`
- confirmed notification marks order paid and triggers idempotent fulfillment
- production credentials are not required for unit tests
- no Telegram bot payment button or invoice uses T-Bank/SBP/T-Pay for premium digital access

- [ ] **Step 2: run RED**

Run:

```powershell
python -m pytest tests/test_payment_providers.py tests/test_http_api.py -q
```

Expected: missing settings/provider/webhook route.

- [ ] **Step 3: add settings**

Add settings:

- `tbank_env`
- `tbank_terminal_key`
- `tbank_password`
- `tbank_success_url`
- `tbank_fail_url`
- `tbank_notification_url`
- `tbank_webhook_secret` only if final T-Bank contract requires separate verification material

Add env isolation in `tests/conftest.py`.

- [ ] **Step 4: implement T-Bank adapter**

Implement:

- `TBankPaymentClient.build_init_payload(order, product, settings)`
- `TBankPaymentClient.init_payment(...)` using httpx
- `TBankSignature.make_token(payload, password)`
- `TBankSignature.verify_notification(payload, password)`
- status mapping: `CONFIRMED -> paid`, `AUTHORIZED` remains pending unless one-stage terminal config makes it final, `REJECTED/AUTH_FAIL/CANCELED -> failed/cancelled`

Use T-Bank `/v2/Init` for an external/off-Telegram checkout URL. Use `/v2/GetQr` for SBP QR only if needed by the final off-Telegram UX; payment URL is enough for first MVP if it exposes T-Pay/SBP options from T-Bank checkout.

Telegram policy guard:

- do not use T-Bank/SBP/T-Pay as an in-bot third-party payment provider for premium digital access
- do not present T-Bank/SBP/T-Pay next to Stars as equal bot payment choices for the same in-Telegram digital purchase
- external checkout handoff copy must make clear the user is leaving the in-Telegram purchase flow

- [ ] **Step 5: implement webhook route**

Create route:

```text
POST /api/payments/tbank/webhook
```

Behavior:

- verify token/signature
- find order by `OrderId`
- verify amount and provider payment id
- mark order paid only on confirmed paid status
- call `fulfill_paid_order`
- return a provider-compatible success response

No public admin data is returned from this endpoint.

- [ ] **Step 6: run GREEN**

Run:

```powershell
python -m pytest tests/test_payment_providers.py tests/test_http_api.py -q
```

Expected: T-Bank tests pass without network by mocking httpx.

## Task 7: User Tariff Status and Usage APIs

**Files:**
- Modify: `src/adapters/http/routes/api.py`
- Modify: `src/main.py`
- Test: `tests/test_http_api.py`
- Test: `tests/test_entrypoint_smoke.py`

- [ ] **Step 1: write failing tests**

Tests must prove:

- `GET /api/entitlements` returns real tier, expiry, products, explicit consent, and blocked reasons
- `GET /api/usage` returns message/image limits, used counts, and reset time
- bot user action `Остаток по тарифу` renders current package and remaining limits
- regular users do not see token cost

- [ ] **Step 2: run RED**

Run:

```powershell
python -m pytest tests/test_http_api.py tests/test_entrypoint_smoke.py -q
```

Expected: endpoints still return static stub data and bot action is missing.

- [ ] **Step 3: implement user-facing status**

Update HTTP routes to use `MonetizationService`.

Add bot keyboard/menu action and renderer:

```text
Остаток по тарифу
Тариф: Premium
Истекает: 2027-05-02
Сообщения сегодня: 42 / 300
Картинки сегодня: 2 / 20
18+: подтверждено
```

- [ ] **Step 4: run GREEN**

Run:

```powershell
python -m pytest tests/test_http_api.py tests/test_entrypoint_smoke.py -q
```

Expected: user status tests pass.

## Task 8: Operator Commands and Admin Summary

**Files:**
- Create: `src/adapters/telegram/admin.py`
- Modify: `src/main.py`
- Test: `tests/test_entrypoint_smoke.py`
- Test: `tests/test_monetization_core.py`

- [ ] **Step 1: write failing operator tests**

Tests must cover:

- non-operator cannot run admin commands
- operator allowlist comes from `OPERATOR_TELEGRAM_IDS`
- grant/revoke require `confirm`
- manual trial grant accepts custom `days`, `messages`, and `images`
- grant, revoke, and fulfill repair write audit events with operator id, target user/order, action, and result
- `/admin_users` supports `q`, `tier`, `sort`, `desc`, and `page`
- admin summary includes ID, name, tier, expiry, payment status, messages, images, estimated cost, 18+ state, and last active
- sensitive actions are throttled per operator
- manual lifetime grants count against the same `lifetime_premium_100` 100-user cap as paid lifetime purchases

- [ ] **Step 2: run RED**

Run:

```powershell
python -m pytest tests/test_entrypoint_smoke.py tests/test_monetization_core.py -q
```

Expected: missing operator parser/handlers/settings.

- [ ] **Step 3: implement operator parser/renderers**

Supported commands:

```text
/grant_access <telegram_user_id> premium <days|lifetime> confirm
/grant_access <telegram_user_id> trial <days> messages=<n> images=<n> confirm
/revoke_access <telegram_user_id> confirm
/fulfill_order <order_id> confirm
/user_status <telegram_user_id>
/usage_status <telegram_user_id>
/admin_users q=<text> tier=<free|trial|premium> sort=<tier|expires|messages|images|cost|last_active> desc page=<n>
```

Manual grant writes `access_grants`, an entitlement with source `manual:<operator_id>:<grant_id>`, and an audit event.

Manual lifetime grants must call the same lifetime cap check used by payment fulfillment before creating the entitlement. The 101st lifetime grant or purchase must fail with `lifetime_cap_reached`.

Grant, revoke, and `/fulfill_order` repair actions must append audit events. Audit events must include:

- operator Telegram user id
- target user id or order id
- action name
- success/failure result
- short machine-readable reason

- [ ] **Step 4: implement throttling**

Use an in-memory operator action throttle for alpha:

- key: operator Telegram user id
- window: 60 seconds
- max sensitive actions: 5

Sensitive actions: grant, revoke, fulfill repair.

- [ ] **Step 5: run GREEN**

Run:

```powershell
python -m pytest tests/test_entrypoint_smoke.py tests/test_monetization_core.py -q
```

Expected: operator command tests pass.

## Task 9: Runtime Gates and Usage Recording

**Files:**
- Modify: `src/main.py`
- Modify: `src/core/access_policy.py`
- Test: `tests/test_entrypoint_smoke.py`

- [ ] **Step 1: write failing runtime tests**

Tests must prove:

- selecting premium persona is blocked for free user
- selecting explicit persona is blocked without allowed tier and consent
- explicit image generation is blocked when user reaches image limit
- message usage increments after accepted text message
- explicit image usage increments after accepted image request

- [ ] **Step 2: run RED**

Run:

```powershell
python -m pytest tests/test_entrypoint_smoke.py -q
```

Expected: current bot flow bypasses monetization.

- [ ] **Step 3: add runtime checks**

Before mode switch and before chat/image execution:

- load user access snapshot
- block premium/explicit persona if disallowed
- render buy actions when premium is needed
- render consent prompt when explicit consent is missing
- block explicit image if usage exhausted
- record message/image usage after accepting an action

- [ ] **Step 4: run GREEN**

Run:

```powershell
python -m pytest tests/test_entrypoint_smoke.py -q
```

Expected: runtime gate tests pass.

## Task 10: Status Docs and Checklist

**Files:**
- Modify: `docs/current/alpha-launch/status.md`
- Modify: `docs/current/alpha-launch/pr-backlog.md`
- Modify: `docs/current/alpha-launch/prs/alpha-005-monetization-admin/tasks.md`

- [ ] **Step 1: mark ALPHA-005 started**

Do not update `status.md` in this planning PR. Update it only after `ALPHA-004` is merged to `main` and actual `ALPHA-005` implementation begins on the implementation branch:

- set `ALPHA-004` to `Done`
- set `ALPHA-005` to `In Progress`
- update `status.md` current context and next step

- [ ] **Step 2: update checklist**

Check ALPHA-005 tasks only after relevant tests pass.

## Task 11: Full Verification

**Files:**
- No code changes unless verification exposes a bug.

- [ ] **Step 1: run focused monetization checks**

Run:

```powershell
python -m pytest tests/test_monetization_core.py tests/test_monetization_repositories.py tests/test_payment_providers.py -q
```

Expected: all focused monetization/payment tests pass.

- [ ] **Step 2: run transport checks**

Run:

```powershell
python -m pytest tests/test_http_api.py tests/test_entrypoint_smoke.py -q
```

Expected: HTTP and Telegram smoke tests pass.

- [ ] **Step 3: run full suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass, with integration skips noted.

- [ ] **Step 4: run syntax/static checks**

Run:

```powershell
python -m py_compile src/core/monetization.py src/core/payment_providers.py src/app/settings.py src/db/migrations.py src/db/repositories.py src/adapters/http/routes/payments.py src/adapters/telegram/admin.py src/adapters/telegram/payments.py src/main.py
python -m ruff check .
python -m mypy
```

Expected: all commands exit `0`, or unavailable tooling is explicitly documented.
