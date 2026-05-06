# ALPHA-011: Mini App Chat Foundation

## Goal

Turn the Telegram Mini App from a clickable channel guide into a useful text chat client where each launch persona has its own isolated chat history and send flow.

## Product Problem

The current Telegram bot puts every persona into one Telegram chat, so history and user context feel mixed even when backend storage tracks `mode`. The `ALPHA-008` Mini App exposes persona/access state, but its `Tune In` action sends the user back to Telegram, where they still need to operate the same bot menu. That does not solve the user-facing problem.

`ALPHA-011` makes the Mini App valuable by moving text chat for launch personas into the Mini App itself while keeping Telegram as entry point, fallback, payment/support surface, and compatibility path.

## In Scope

- Protected Railway API for Mini App text chat:
  - list persona chat threads from the launch catalog
  - load one persona thread history
  - send a text message to one persona thread
- Per-persona history isolation by `UserRef + persona/mode`.
- Shared backend policy for Mini App and Telegram:
  - persona allowlist
  - free/trial/premium entitlement checks
  - explicit consent checks
  - usage counters
  - provider/model routing
  - message history append
- Next.js Mini App chat UI:
  - persona/channel list
  - active chat panel
  - message composer
  - loading/error states
  - locked premium and explicit states
  - access/usage/profile panels as secondary surfaces
- Tests for backend chat API, frontend chat behavior, access blocking, and no frontend-owned entitlement logic.

## Out of Scope

- Standalone Web identity or non-Telegram login.
- Direct browser access to Supabase.
- Image generation from the Mini App.
- Realtime streaming, WebSockets, or server-sent events.
- Billing redesign or new payment providers.
- New personas, provider matrix changes, or prompt rewrites.
- Full account export/deletion completion beyond existing ALPHA-009 documented gaps.

## Proposed API Contract

All endpoints are under the existing opaque bearer session contract from `ALPHA-002` and must use `require_session`.

### `GET /api/miniapp/chats`

Returns one chat summary per launch catalog persona.

Response shape:

```json
{
  "items": [
    {
      "id": "basic",
      "mode": "basic",
      "title": "AI Assistant",
      "category": "assistant",
      "access": {
        "allowed": true,
        "reasons": []
      },
      "last_message": {
        "role": "assistant",
        "content_preview": "Short preview text",
        "created_at": 1777890000
      }
    }
  ]
}
```

Unread tracking is intentionally out of scope for `ALPHA-011`: no read markers, delivery state, or last-read cursor are introduced. If the UI needs a badge in this PR, it must derive from existing loaded state and not add an `unread_count` API field.

### `GET /api/miniapp/chats/{character_id}/messages`

Loads recent message history for one persona thread owned by the session user.

Response shape:

```json
{
  "character_id": "basic",
  "mode": "basic",
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "Hello",
      "created_at": 1777890001
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": "Hi.",
      "created_at": 1777890002
    }
  ]
}
```

### `POST /api/miniapp/chats/{character_id}/messages`

Sends one text message to the selected persona and returns the persisted user message plus assistant reply.

Request shape:

```json
{
  "text": "Write a short reply"
}
```

Response shape:

```json
{
  "character_id": "basic",
  "mode": "basic",
  "messages": [
    {
      "id": "msg_003",
      "role": "user",
      "content": "Write a short reply",
      "created_at": 1777890010
    },
    {
      "id": "msg_004",
      "role": "assistant",
      "content": "Short reply.",
      "created_at": 1777890011
    }
  ],
  "usage": {
    "messages": {
      "used": 5,
      "limit": 30,
      "reset_at": 1777939200
    }
  }
}
```

Error behavior:

- `404 character_not_found` for non-launch-catalog ids.
- `403 persona_locked` with backend-owned reasons for premium or explicit blocks.
- `400 empty_message` for empty/whitespace text.
- `429 usage_limit_exceeded` when backend usage policy rejects the send.

## Implementation Notes

- Prefer reusing `conversations`, `user_messages`, `conversation_mode_state`, and existing repository methods before adding schema.
- If a new conversation reference is needed, use deterministic per-user/per-mode Mini App refs such as `miniapp:{user_ref}:{mode}` rather than frontend-generated ids.
- Do not copy provider or entitlement logic into `apps/miniapp`.
- If current Telegram text-turn logic is still too coupled to `aiogram.Message`, add a shared backend function that accepts `UserRef`, `ConversationRef`, `mode`, and text, then returns assistant text plus persisted message metadata.
- Keep the first PR text-only. Image jobs can reuse ALPHA-007 job status later.

## Expected Files

- `src/adapters/http/routes/api.py` or a new route module under `src/adapters/http/routes/**`
- `src/db/repositories.py`
- `src/db/postgres.py`
- shared chat orchestration module under `src/**`
- `apps/miniapp/src/**`
- `apps/miniapp/tests/**`
- backend tests under `tests/**`
- `docs/current/alpha-launch/status.md`

## Test Focus

- Backend API requires Mini App bearer auth for every chat endpoint.
- Persona access decisions match existing `MonetizationService.can_use_persona`.
- Message histories are isolated per persona/mode.
- Sending through Mini App appends the same kind of user/assistant history as Telegram text chat.
- Locked premium and explicit personas block send and return backend reasons.
- Mini App frontend renders separate conversations and does not compute entitlement access locally.
- Existing Telegram bot text flow still passes after shared orchestration extraction.

## Merge Criteria

- Mini App user can send and receive text in at least one allowed persona without returning to Telegram.
- Switching personas changes the active history.
- Locked personas remain visible but cannot send until backend access allows them.
- `npm test`, `npm run typecheck`, `npm run build`, backend unit tests, `ruff`, and `mypy` pass for touched scope.
- Production deployment is not required in this PR, but the PR must preserve the existing Railway/Vercel deploy model.
