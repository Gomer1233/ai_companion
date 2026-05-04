# Alpha Ops Runbook

Status: alpha launch runbook.

## Roles

Operator:

- has a Telegram id listed in `OPERATOR_TELEGRAM_IDS`;
- can use operator commands for grants, revokes, fulfillment repair, user status, usage status, and admin user review;
- can access Railway, Vercel, Postgres, provider dashboards, and payment dashboards only when explicitly authorized.

Support contact:

- receives alpha user support, privacy, deletion/export, abuse, and payment requests;
- must escalate technical or policy decisions to an operator.

## Closed Alpha Cohort

Alpha access is invite-only.

Before adding a user:

- confirm Telegram username or user id;
- confirm the user understands this is a test alpha;
- explain that explicit content requires separate 18+ consent;
- record how the invite was approved outside the runtime database if needed for cohort tracking.

During alpha:

- keep cohort size small enough for manual support and incident review;
- remove users who create abuse risk or repeatedly bypass product limits;
- avoid public links that imply open signup.

## Support Intake

Primary user route:

- Users send `/support <category> <details>` to `@Lina_YourFriend_Bot`.
- The bot forwards the request to every Telegram id configured in `OPERATOR_TELEGRAM_IDS`.
- `OPERATOR_TELEGRAM_IDS` is the support owner configuration source for alpha. At least one active operator id must be configured before adding users to the closed alpha.
- Operators handle the request in Telegram and record the resolution in the support log.

Supported request categories:

- login or Mini App session issue;
- plan/usage/entitlement issue;
- payment or fulfillment issue;
- explicit consent revocation;
- export request;
- deletion or account removal request;
- abuse or safety report;
- provider/output quality or outage report.

Minimum intake fields:

- Telegram username and, if available, Telegram user id;
- request category;
- short description;
- whether the user is reporting urgent abuse or payment impact;
- operator handling the request;
- resolution and timestamp.

Users must not be asked to send passwords, provider keys, full card numbers, private documents, or unnecessary personal data.

## Export Flow

1. Confirm the requester controls the Telegram account by asking them to message the bot or support channel from that account.
2. Resolve the Telegram identity to `UserRef` through backend records.
3. Export available records for that `UserRef`:
   - linked Telegram identity;
   - profile/persona/channel state;
   - usage counters;
   - explicit consent state;
   - entitlement and payment order metadata;
   - available conversation and event records;
   - image job metadata.
4. Redact secrets, provider keys, internal operator notes unrelated to the requester, and records belonging to other users.
5. Deliver the export through the support channel approved for the alpha.
6. Record completion in the support log.

Current implementation note: `src/export_user_report.py` exports broad SQLite event reports and is not a per-user privacy export tool. A per-user export command or script must be added before public self-service export.

## Deletion And Account Removal Flow

1. Confirm the requester controls the Telegram account.
2. Resolve the Telegram identity to `UserRef`.
3. Freeze new support/payment actions for the user while the request is handled.
4. Reset removable conversation state with repository-backed reset paths where available.
5. Revoke explicit consent if requested or if the account is being removed:
   - `python -m src.revoke_explicit_consent <telegram_user_id> --operator-id <operator_id> --reason <reason> --confirm`
   - The script sets `explicit_consent.revoked_at`, changes `source` to the operator revoke source, and writes an `admin_audit_events` row.
6. Revoke active manual entitlements when removal requires access termination.
7. Minimize or delete removable profile, message, and event data where operationally possible.
8. Retain payment, entitlement, abuse, fraud, and operator audit records when needed for disputes, accounting, or safety.
9. Confirm completion and state what categories were retained.
10. Record the operator, timestamp, action, and reason.

Current implementation note: `reset_user_all()` clears conversation runtime state but does not remove every product record. Full account deletion needs a dedicated backend operation before public self-service deletion.

## Abuse And Safety Flow

Abuse reports include:

- explicit policy violations;
- harassment, coercion, or non-consensual sexual requests;
- minor-related or age-ambiguous sexual content requests;
- fraud, spam, automated scraping, or rate-limit bypass attempts;
- payment abuse or chargeback risk;
- provider output that creates safety risk.

Triage:

1. Preserve relevant request metadata, timestamps, and user id.
2. Avoid copying full sensitive prompts into support notes unless required for review.
3. Restrict explicit access or revoke entitlements if risk is immediate.
4. Disable affected provider/persona path if the issue is systemic.
5. Escalate illegal or platform-policy-sensitive cases to the owner before further user communication.
6. Record resolution and follow-up actions.

## Logging Policy

Allowed in routine logs:

- user id or `UserRef`;
- event type;
- persona/channel id;
- provider/model id;
- job id and terminal state;
- token counts and cost metadata;
- sanitized error codes.

Avoid in routine logs:

- Telegram bot token, provider keys, database URLs, webhook secrets, payment secrets;
- full Telegram init data;
- full payment payloads;
- full prompts, generated explicit content, or private user messages;
- full provider responses unless debugging an active incident.

Incident logging:

- capture the smallest useful payload;
- redact secrets immediately;
- remove temporary payload logs after the incident is resolved;
- document why the sensitive log was needed.

## Secrets Management

Secrets live only in platform env stores or local ignored env files:

- Railway: backend runtime secrets such as `TELEGRAM_TOKEN`, provider keys, `DATABASE_URL`, payment secrets, `MINI_APP_URL`, operator ids.
- Vercel: Mini App public build env such as `NEXT_PUBLIC_API_BASE_URL` and non-secret public config.
- Local: `.env` and other ignored runtime files for development only.

Rules:

- never commit `.env`, `.env.7z`, database files, logs, or local artifacts;
- rotate a secret immediately if it appears in Git, logs, screenshots, chat, or a third-party issue;
- keep production and local provider keys separate where providers support it;
- remove stale operator ids and platform users after access is no longer needed.

## Backup And Restore

Production storage is Postgres-backed in alpha.

Backup policy:

- rely on managed Postgres platform backups where available;
- before risky migrations or manual data repair, create a point-in-time backup or database dump;
- store any manual dump encrypted and outside Git;
- document dump location, timestamp, operator, and retention date.

Restore drill:

1. Identify target backup and affected environment.
2. Restore into staging or a temporary database first.
3. Run backend smoke checks against restored data.
4. Confirm entitlements, sessions, usage, consent, and job records are coherent.
5. Promote restore to production only after owner approval.
6. Record incident, restore point, commands used, and verification result.

## Launch Checklist

- Privacy policy and terms reviewed for the closed alpha.
- Explicit 18+ consent copy installed or matched in Mini App copy.
- `/support` route tested through `@Lina_YourFriend_Bot`, with at least one operator id in `OPERATOR_TELEGRAM_IDS`.
- Export/deletion request handling process tested manually.
- Abuse triage and explicit revocation process understood by operators.
- Secrets stored in Railway/Vercel env stores, not Git.
- Backup/restore path confirmed for the production Postgres service.
- Railway backend and Vercel Mini App health checks pass after deployment.
