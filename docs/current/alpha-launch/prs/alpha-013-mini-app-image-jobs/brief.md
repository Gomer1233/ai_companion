# ALPHA-013: Mini App Image Jobs

Plan reference: `../../execution-plan.md`

## Goal

Add Mini App image generation through the existing backend job lifecycle after text chat is functional.

## In Scope

- Start image generation from an eligible Mini App persona/thread.
- Reuse ALPHA-007 job persistence, owner checks, status, terminal-state invariants, and cancellation semantics.
- Poll job status from the Mini App and display progress/result/error.
- Cancel/retry UX for image jobs.
- Locked premium/explicit image states from backend-owned access decisions.

## Out of Scope

- New image providers or provider matrix changes.
- Realtime transport.
- Gallery/library product work beyond displaying the current job result.
- Standalone Web identity.

## Test Focus

- Backend job start/status access is owner-scoped.
- Cancelled jobs do not deliver stale results.
- Mini App polls job status and renders queued/running/completed/failed/cancelled states.
- Explicit image limits and consent are enforced by backend policy.

## Merge Criteria

- An eligible user can request an image from the Mini App and see the result without using Telegram chat.
- Ineligible users see backend-owned locked/limit reasons.
- Existing Telegram image job behavior still passes.
