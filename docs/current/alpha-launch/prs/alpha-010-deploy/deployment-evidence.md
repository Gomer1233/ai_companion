# ALPHA-010 Deployment Evidence

Status: work in progress.

Date: 2026-05-04

## Vercel Production

Deployment:

- Alias: `https://miniapp-xi-smoky.vercel.app`
- Deployment URL: `https://miniapp-gmklgwcuw-andreis-projects-8db07cf9.vercel.app`
- Deployment id: `dpl_GXM3c97UfnqgwTLa6Kv7ha8XjjcF`
- Result: ready and aliased to production

Command:

```powershell
npx vercel deploy --prod --force --yes `
  --build-env NEXT_PUBLIC_API_BASE_URL=https://ai-companion-bot-production.up.railway.app `
  --build-env NEXT_PUBLIC_TELEGRAM_INIT_MAX_AGE_SEC=7200 `
  --env NEXT_PUBLIC_API_BASE_URL=https://ai-companion-bot-production.up.railway.app `
  --env NEXT_PUBLIC_TELEGRAM_INIT_MAX_AGE_SEC=7200
```

Verification:

- `https://miniapp-xi-smoky.vercel.app` returns `200`.
- Telegram Web App SDK is present.
- Next.js chunks include `https://ai-companion-bot-production.up.railway.app`.
- Next.js chunks include the ALPHA-009 consent copy: `I am 18+ and accept`.

## Railway Production

Deployment:

- Deployment id: `9aee7536-5e5c-444b-adcf-4b73fa1c5ce6`
- Deploy method: `npx @railway/cli up --detach --service ai-companion-bot --message "Deploy ALPHA-010 smokeable backend"`
- Result: `SUCCESS`
- Service status: active deployment `9aee7536-5e5c-444b-adcf-4b73fa1c5ce6`, status `SUCCESS`, stopped `false`

Runtime log notes:

- Uvicorn started on `0.0.0.0:8000`.
- Aiogram polling started for `@Lina_YourFriend_Bot`.
- A transient Telegram `getUpdates` conflict appeared during rolling replacement, then polling reported `Connection established`.
- `/healthz` and `/readyz` returned `200`.

Public checks:

```text
PASS backend/healthz: 200 {'status': 'ok'}
PASS backend/readyz: 200 {'status': 'ready'}
```

Authenticated smoke:

```text
PASS session_exchange: 200
PASS /api/me: 200
PASS /api/characters: 200
PASS /api/entitlements: 200
PASS /api/usage: 200
PASS explicit_consent: 200 {'tier': 'free', 'tier_expires_at': None, 'has_premium': False, 'explicit_consent': True, 'consent_required': False, 'blocked_reasons': []}
PASS job_lookup_protected: 404
```

Production smoke command:

```powershell
python -m src.launch_smoke `
  --backend-url https://ai-companion-bot-production.up.railway.app `
  --frontend-url https://miniapp-xi-smoky.vercel.app `
  --exercise-auth `
  --telegram-user-id 900000010
```

## Remaining Operational Note

Railway production can be deployed with `railway up`, which was exercised above. GitHub auto-deploy source binding should still be corrected to `main` before relying on `redeploy --from-source` or unattended auto-deploys, because earlier deployment metadata showed the old branch `codex/alpha-001-refactor-boundaries`.
