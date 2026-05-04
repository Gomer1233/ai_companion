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

- Production Railway must deploy from `main`.
- The old `codex/alpha-001-refactor-boundaries` binding is not valid for alpha launch. If Railway UI still shows that branch, switch the production source branch to `main` before enabling auto-deploy.

Build/deploy config:

- `railway.json` uses Railpack.
- Start command: `python -m src.main`.
- Pre-deploy command applies the Postgres schema through owner-capable `DATABASE_URL`.
- Healthcheck path: `/healthz`.

Required Railway variables:

- `TELEGRAM_TOKEN`
- `MINI_APP_URL=https://miniapp-xi-smoky.vercel.app`
- `DB_BACKEND=postgres`
- `DATABASE_URL`
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
2. Confirm Railway source branch is `main`.
3. Confirm required variables are set in Railway production.
4. Trigger deploy from Railway or push to `main` if auto-deploy is enabled.
5. Wait for deployment success.
6. Check:
   - `GET https://ai-companion-bot-production.up.railway.app/healthz`
   - `GET https://ai-companion-bot-production.up.railway.app/readyz`
7. Open Railway logs and confirm the bot polling loop starts without token, database, provider, or schema errors.

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
2. `DATABASE_URL` points to the production Postgres service.
3. Railway pre-deploy schema bootstrap succeeds.
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
