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

Open issue:

- Railway CLI is not authenticated in this workspace: `Unauthorized. Please login with railway login`.
- Railway MCP/GraphQL OAuth previously returned `Not Authorized` for deployment reads/writes.
- Railway production source branch must be confirmed as `main`; previous UI state showed `codex/alpha-001-refactor-boundaries`.
- Backend runtime must be redeployed from `main` after ALPHA-009 merge before ALPHA-010 can be marked ready.

Next Railway action:

```powershell
npx @railway/cli login --browserless
npx @railway/cli status
```

After Railway login, confirm project/environment/service, switch source branch to `main` if needed, trigger a production deploy, and rerun:

```powershell
python -m src.launch_smoke `
  --backend-url https://ai-companion-bot-production.up.railway.app `
  --frontend-url https://miniapp-xi-smoky.vercel.app `
  --exercise-auth `
  --telegram-user-id 900000010
```

