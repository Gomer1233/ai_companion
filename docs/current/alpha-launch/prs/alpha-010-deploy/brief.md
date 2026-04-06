# ALPHA-010: Deploy to Railway + Vercel + Supabase

## Goal

Deploy the bot, backend API, Mini App, and database-backed alpha stack with staging/production environments and launch smoke checks.

## In Scope

- Railway deployment for bot runtime + FastAPI API
- Vercel deployment for Mini App frontend
- Supabase production connection and secrets wiring
- staging and production environment setup
- health/readiness checks in deployed environments
- launch smoke suite and rollback procedure alignment

## Out of Scope

- new product features
- new personas or provider changes
- payment provider integration

## Expected Files

- deployment/configuration files as needed
- environment/setup docs
- smoke scripts or verification docs
- `docs/current/alpha-launch/status.md`

## Test Focus

- deployed health/readiness behavior
- bot startup on Railway
- Mini App reachability from Telegram
- Supabase connectivity
- launch smoke suite for consent/access/image-job basics

## Merge Criteria

- staging and production deployment paths are documented and exercised
- smoke checks pass against the deployed stack
- rollback/incident procedure is explicit enough for alpha operations
