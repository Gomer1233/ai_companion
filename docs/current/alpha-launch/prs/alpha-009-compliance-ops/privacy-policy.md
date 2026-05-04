# Lina Alpha Privacy Policy

Status: alpha launch draft. This policy is intended for the closed Telegram alpha and must be reviewed before public launch or material product expansion.

## Product Scope

Lina is a Telegram-first AI companion. During alpha, users interact through the Telegram bot and Telegram Mini App. The backend runs on Railway, the Mini App runs on Vercel, and backend-owned state is stored in Postgres.

The product uses `UserRef` as the internal account identity. Telegram account data is a linked identity used to authenticate and deliver the Telegram experience.

## Data We Collect

Lina may process and store:

- Telegram identifiers needed to operate the bot and Mini App, including Telegram user id, username, first name, chat id, and message id where available.
- User messages, selected persona/channel, conversation state, and bot replies needed to provide the companion experience.
- Generated image request metadata, image job status, provider/model metadata, and delivery/error state.
- Entitlement, plan, usage, payment order, explicit consent, and operator audit records.
- Technical session data for Mini App access, including backend-issued opaque session tokens stored server-side and short-lived client bearer use.
- Operational logs needed for reliability, abuse review, debugging, and cost monitoring.

Lina should not intentionally collect government identifiers, medical records, precise location, contacts, or payment card numbers. Payment details are handled by payment providers; Lina stores order and fulfillment metadata, not full card data.

## How We Use Data

Data is used to:

- authenticate Telegram users and issue Mini App sessions;
- provide conversations, persona/channel selection, usage limits, and entitlement access;
- enforce explicit 18+ consent and provider/model access policy;
- process and repair paid orders and grants;
- prevent abuse, investigate incidents, and support users;
- monitor reliability, cost, and launch readiness.

User content must not be used for unrelated internal analytics or training workflows without a separate explicit decision and user notice.

## AI Providers

User prompts and relevant context may be sent to configured AI providers to generate responses, translations, moderation decisions, token estimates, or images. Provider routing is controlled by backend configuration and the alpha model/provider matrix.

Operators must assume provider requests can include sensitive user content and must keep provider keys, logs, and dashboards access-restricted.

## Explicit Content

Some alpha personas or image capabilities are explicit 18+ surfaces. Lina stores whether a user has accepted the explicit consent gate. The gate is backend-owned and can be revoked operationally by removing or invalidating the consent record.

Explicit content is restricted to users who confirm they are 18+ and accept the explicit content terms. Consent does not permit illegal, non-consensual, exploitative, or harmful content.

## Retention

Alpha retention is conservative:

- Sessions: expire according to backend session TTL and are removed by session cleanup.
- Conversation and user event data: retained while needed for product continuity, support, abuse handling, and alpha review.
- Payment, entitlement, and operator audit records: retained while needed for accounting, fraud prevention, dispute handling, and operational accountability.
- Generated image bytes: should not be persisted unless a provider or Telegram delivery path temporarily stores them outside Lina control. Lina stores job metadata, not generated image files, unless a later feature explicitly adds image storage.

Before public launch, retention windows must be converted from this alpha stance into explicit calendar durations.

## User Requests

Users can request:

- a copy of account, entitlement, usage, consent, and available conversation/event records;
- deletion or reset of conversation state;
- revocation of explicit 18+ consent;
- account removal where operationally possible;
- payment/entitlement support.

Requests are handled by the support process in `ops-runbook.md`.

Deletion is subject to operational limits: payment, entitlement, fraud, abuse, and operator audit records may need to be retained in minimized form where required for dispute handling, accounting, or platform safety.

## Sharing

Lina shares data only with services needed to operate the alpha:

- Telegram for bot and Mini App delivery;
- AI/model providers for generation and policy decisions;
- Railway, Vercel, and Postgres hosting/storage infrastructure;
- payment providers for purchases and fulfillment;
- operators/support staff who need access for support, incident response, or abuse review.

No sale of personal data is permitted in alpha.

## Security

Secrets must be stored in platform environment-variable stores, not committed to Git. Operator access is limited through configured Telegram operator ids and platform account access. Logs must avoid secrets and avoid full sensitive payloads unless explicitly needed for an incident and then removed or minimized afterward.

## Contact

Alpha support and privacy requests are handled by sending `/support <category> <details>` to `@Lina_YourFriend_Bot`. The bot forwards requests to the configured alpha operators listed in `OPERATOR_TELEGRAM_IDS`.
