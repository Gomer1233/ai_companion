# ALPHA-010 Deployment Runbook

Status: alpha deployment runbook.

## Environments

Production alpha:

- Railway project: `lina-ai-alpha`
- Railway backend URL: `https://ai-companion-bot-production.up.railway.app`
- Railway service: `ai-companion-bot`
- Railway database: managed Postgres service connected through `DATABASE_URL`
- Vercel project: `miniapp`
- Vercel production alias: `https://miniapp-xi-smoky.vercel.app`
- Telegram bot: `@Lina_YourFriend_Bot`

Staging:

- Use a separate Railway environment or service before adding broader alpha users.
- Use a Vercel preview deployment or separate Vercel project alias.
- Use a separate Supabase/Postgres database or schema.
- Do not point staging Telegram runtime at the production bot token.

## Railway Backend

Source branch:

- Production Railway release deploys can be performed with `railway up` from a clean, reviewed branch or `main`.
- Auto-deploy from GitHub should point at `main` before it is relied on for unattended production deploys.
- The old `codex/alpha-001-refactor-boundaries` binding is not valid for alpha launch. Do not use `railway redeploy --from-source` while Railway still shows that branch.

Build/deploy config:

- `railway.json` uses Railpack.
- Start command: `python -m src.main`.
- No Railway pre-deploy or startup command runs schema DDL.
- Healthcheck path: `/healthz`.

Required Railway variables:

- `TELEGRAM_TOKEN`
- `MINI_APP_URL=https://miniapp-xi-smoky.vercel.app`
- `DB_BACKEND=postgres`
- `DATABASE_URL` with the non-owner app role only
- `HTTP_CORS_ORIGINS=https://miniapp-xi-smoky.vercel.app`
- `HTTP_TELEGRAM_INIT_MAX_AGE_SEC=7200`
- provider keys for the selected text/image providers
- `IMAGE_BACKEND_PROVIDER`
- `DEFAULT_MODEL`
- `JUDGE_MODEL_WHORE`
- `OPERATOR_TELEGRAM_IDS`
- payment variables only when payment paths are enabled

Deploy steps:

1. Confirm `main` contains the intended PR merge commit.
2. Confirm required variables are set in Railway production.
3. Confirm schema migrations were applied out-of-band with an owner/admin credential, following `docs/current/alpha-launch/prs/alpha-003-postgres-cutover/cutover-runbook.md`.
4. From a clean release workspace, run:
   - `npx @railway/cli link --project lina-ai-alpha --environment production --service ai-companion-bot`
   - `npx @railway/cli up --detach --service ai-companion-bot --message "<release message>"`
5. If GitHub auto-deploy is enabled and confirmed to point at `main`, a push to `main` can replace the manual `railway up` step.
6. Wait for deployment success.
7. Check:
   - `GET https://ai-companion-bot-production.up.railway.app/healthz`
   - `GET https://ai-companion-bot-production.up.railway.app/readyz`
8. Open Railway logs and confirm the bot polling loop starts without token, database, provider, or schema errors.

## Vercel Mini App

Required Vercel build/runtime variables:

- `NEXT_PUBLIC_API_BASE_URL=https://ai-companion-bot-production.up.railway.app`
- `NEXT_PUBLIC_TELEGRAM_INIT_MAX_AGE_SEC=7200`

Deploy command:

```powershell
cd apps/miniapp
npx vercel deploy --prod --force --yes `
  --build-env NEXT_PUBLIC_API_BASE_URL=https://ai-companion-bot-production.up.railway.app `
  --build-env NEXT_PUBLIC_TELEGRAM_INIT_MAX_AGE_SEC=7200 `
  --env NEXT_PUBLIC_API_BASE_URL=https://ai-companion-bot-production.up.railway.app `
  --env NEXT_PUBLIC_TELEGRAM_INIT_MAX_AGE_SEC=7200
```

Verification:

- `https://miniapp-xi-smoky.vercel.app` returns `200`.
- HTML includes Telegram Web App SDK.
- Next.js chunks include the Railway backend URL.
- Telegram opens the Mini App through the inline `Open Mini App` button and receives non-empty `initData`.

## Supabase/Postgres

Production database stance:

- Browser clients never connect directly to Supabase/Postgres in alpha.
- Railway backend is the only runtime database client.
- Runtime database role must have least-privilege access to Lina tables.

Required checks:

1. `DB_BACKEND=postgres` is set in Railway.
2. `DATABASE_URL` points to the production Postgres service with the non-owner app role.
3. Schema DDL and least-privilege grants were applied out-of-band with an owner/admin credential.
4. `/readyz` returns `ready`.
5. Authenticated smoke checks can create/read session, usage, entitlement, consent, and protected job lookup state.

## Smoke Commands

Public smoke, no secrets:

```powershell
python -m src.launch_smoke `
  --backend-url https://ai-companion-bot-production.up.railway.app `
  --frontend-url https://miniapp-xi-smoky.vercel.app
```

Authenticated smoke with a dedicated smoke Telegram user id:

```powershell
python -m src.launch_smoke `
  --backend-url https://ai-companion-bot-production.up.railway.app `
  --frontend-url https://miniapp-xi-smoky.vercel.app `
  --exercise-auth `
  --telegram-user-id 900000010
```

Authenticated smoke uses `TELEGRAM_TOKEN` from the environment to sign Telegram Mini App init data. It mutates backend state for the smoke user by accepting explicit consent, so use a dedicated smoke user id only.

## Staging Path

Staging should be exercised before broadening the alpha cohort:

- Railway: create or link a staging environment/service that uses the same `railway.json` start/healthcheck behavior.
- Apply staging schema DDL out-of-band with a staging owner/admin credential before deploying the Railway app role.
- Vercel: use a preview deployment or staging alias with `NEXT_PUBLIC_API_BASE_URL` pointed at the staging Railway backend.
- Postgres: use a separate staging Postgres database or schema, never production data.
- Telegram: use a separate staging bot token if Telegram end-to-end behavior is tested.

Minimum staging smoke:

```powershell
python -m src.launch_smoke `
  --backend-url <staging-railway-url> `
  --frontend-url <staging-vercel-url> `
  --exercise-auth `
  --telegram-user-id 900000010
```

## Rollback

Backend rollback:

1. Pause broader alpha testing.
2. In Railway, redeploy the last known-good deployment from `main`.
3. If the issue is configuration-only, revert the variable and redeploy.
4. If schema changes caused the issue, restore Postgres only after validating the target backup in staging or a temporary database.
5. Verify `/healthz`, `/readyz`, bot polling, and smoke checks before resuming.

Frontend rollback:

1. Promote the previous known-good Vercel production deployment.
2. Confirm `miniapp-xi-smoky.vercel.app` points to the rolled-back deployment.
3. Re-run public smoke and Telegram open-flow checks.

Incident handling:

- Record start time, affected environment, user-facing impact, deploy id, rollback action, and verification result.
- Do not paste secrets, full init data, payment payloads, or explicit prompts into incident notes.
- If explicit access or payment fulfillment is affected, pause the affected path until smoke checks pass.
