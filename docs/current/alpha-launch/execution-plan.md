# План Инициативы: Alpha Launch для Lina AI

## Summary
Цель: выпустить живую explicit 18+ alpha как один Telegram-бот с polling на Railway, с Telegram Mini App как вспомогательным UI на Vercel, и с Supabase Postgres как единственным production backend store.

Эта инициатива является follow-on к завершённому циклу `multichannel-core` и использует его как foundation, но не переписывает его историю.

## Current Repo State

- `src/main.py` всё ещё содержит остаточную orchestration и прямые `sqlite3.connect`.
- `src/db/repositories.py` пока остаётся SQLite-only implementation.
- HTTP adapter в `src/` отсутствует.
- `docs/current/multichannel-core/status.md` фиксирует следующий полезный шаг: вынос orchestration из `main.py` и обнуление `legacy_runtime`.

## Fixed Decisions

- Один backend truth, один Telegram bot launcher, один access-policy слой.
- Бот остаётся `bot-first`; Mini App не забирает основной чат в alpha v1.
- User-facing web surfaces use the `Lina Midnight Channel UI` visual contract from `docs/adr/0001-lina-midnight-channel-ui.md`; Mini App is the first implementation, and future standalone Web should extend the same direction.
- Railway хостит Python backend service: bot runtime + HTTP API.
- Vercel хостит только Mini App frontend.
- Mini App ходит напрямую: `browser -> Railway API`.
- Python HTTP adapter живёт в `src/adapters/http/**`.
- HTTP stack = FastAPI.
- Manual grants используются вместо payment automation в alpha v1.
- Explicit 18+ входит в alpha v1.
- Explicit alpha critical path = `text + image`.
- `audio` и `vision` не входят в explicit critical path alpha v1.
- Persona candidate set alpha v1 = текущие персонажи из `src/config/modes.py`; финальный launch allowlist определяется отдельным persona audit перед launch freeze.
- Launch behavior фиксируется не только allowlist, но и frozen launch model manifest.
- Webhook не входит в alpha critical path.
- `RLS` в alpha рассматривается как defense-in-depth, а не как основной auth boundary.

## Security Baseline

Это обязательный baseline для всей alpha, а не optional hardening.

- Mini App/browser не обращается к Supabase напрямую.
- Все privileged DB credentials живут только в Railway.
- Session model = opaque session id + server-side lookup.
- `Authorization: Bearer <token>` обязателен для всех `GET /api/*`.
- `POST /api/session/telegram` защищён rate limiting.
- `POST /api/session/telegram` принимает только свежие Telegram init data в пределах фиксированного окна валидности.
- Operator commands защищены allowlist по Telegram user ID и audit log.
- Sensitive actions требуют confirmation step.
- Raw init data, raw prompts и sensitive explicit payloads не логируются.
- Secrets rotation documented для Railway, Vercel и Supabase.
- Backup/restore policy documented и проверена.
- DB app role работает по least privilege.
- `RLS`:
  - не используется как primary auth boundary в alpha;
  - допускается только как defense-in-depth на selected tables;
  - если позже появится direct browser-to-Supabase path, `RLS` становится mandatory launch blocker.

## 1. Finish Refactor and Lock Boundaries

Сначала завершить внутренний refactor до production-safe shape.

### Сделать

- Вынести `chat/image/reset/conversation/access/job` orchestration из `src/main.py` в сервисы.
- Удалить или полностью обнулить `src/core/legacy_runtime.py`.
- Убрать из launcher прямые `sqlite3.connect`, schema helpers и provider branching.
- Закрепить `AccessPolicyService` как единственное место для:
  - character tier checks;
  - explicit eligibility;
  - consent checks;
  - entitlement checks;
  - provider eligibility.
- Закрепить `JobService` как единственное место для async image lifecycle.

### Interfaces

- `ChatService`
- `ImageService`
- `ResetService`
- `ConversationService`
- `AccessPolicyService`
- `JobService`

### Acceptance Criteria

- `src/main.py` становится thin launcher.
- Telegram adapter не содержит product rules.
- `legacy_runtime.py` больше не участвует в active runtime.

## 2. Add Python HTTP Adapter on Railway

Source of truth для `GET /api/*` живёт только в Python backend service on Railway.

### Сделать

- Добавить HTTP adapter в `src/adapters/http/**`.
- Реализовать его на FastAPI.
- Поднять HTTP surface:
  - `POST /api/session/telegram`
  - `GET /api/me`
  - `GET /api/characters`
  - `GET /api/entitlements`
  - `GET /api/usage`
  - `GET /api/jobs/{job_id}`
  - `GET /healthz`
  - `GET /readyz`
- Не добавлять entitlement/business logic в Vercel.
- Vercel отдаёт только Mini App frontend assets.

### Session Contract

После Mini App init-data verification backend создаёт opaque session record и возвращает opaque bearer token.

- `POST /api/session/telegram`:
  - принимает Telegram Mini App init data;
  - проверяет подпись на backend;
  - проверяет freshness init data в фиксированном окне;
  - резолвит `telegram_user_id -> UserRef`;
  - создаёт или обновляет server-side session record;
  - возвращает opaque session token.
- Клиент передаёт токен как `Authorization: Bearer <token>`.
- Формат токена: opaque session id, не JWT и не signed stateless token.
- Проверка токена всегда идёт через server-side lookup + expiry validation.
- TTL = 15 minutes.
- Refresh endpoint не делается.
- При `401` Mini App обязан тихо повторно вызвать `POST /api/session/telegram` и получить новый session token.
- Raw init data не передаётся дальше initial session exchange.

### Session Lifecycle

Для session record зафиксировать:

- `created_at`
- `expires_at`
- `last_seen_at`
- server-side invalidation
- cleanup expired sessions как регулярную backend maintenance задачу

### HTTP Security Defaults

- CORS/origin allowlist только для production Mini App origin и локальных dev origins.
- Rate limiting на `POST /api/session/telegram`.
- Session token rotation происходит через re-issue on re-auth, а не через refresh token flow.
- Raw init data не логируется.

### Railway Service Model

- Один Railway service хостит bot runtime и FastAPI API.
- Обязателен health endpoint.
- Обязателен readiness endpoint.
- Обязателен graceful shutdown.
- Startup sequence:
  - load config;
  - open DB deps;
  - run job reconciliation;
  - mark readiness;
  - start polling + HTTP serving.
- Shutdown sequence:
  - stop intake;
  - drain/cancel in-flight jobs by policy;
  - close DB/network clients cleanly.

### Acceptance Criteria

- Mini App browser ходит напрямую в Railway API.
- Python backend остаётся единственным owner `GET /api/*`.
- Init-data verification и session issuance не живут во frontend.

## 3. Replace SQLite with Supabase Postgres

После фиксации HTTP/backend boundaries заменить persistence.

### Сделать

- Заменить SQLite repositories на Postgres implementation.
- Перенести текущую модель:
  - `users`
  - `telegram_accounts`
  - `conversations`
  - `messages`
  - `mode_state`
  - `mode_locks`
  - `jobs`
  - `events`
  - `relationship_state`
  - `sessions`
- Добавить monetization tables:
  - `plans`
  - `entitlements`
  - `usage_counters`
  - `access_grants`
- Railway backend использует direct connection к Supabase по умолчанию.
- Если возникнут сетевые/IPv4 ограничения, допускается fallback к session pooler.
- Ввести отдельную app DB role с минимально нужными правами.
- Не использовать browser DB credentials вообще.

### DB Privilege / RLS Stance

- App backend не работает под чрезмерно широкой БД-учёткой.
- Least-privilege grants обязательны.
- `RLS` не считается primary auth boundary в alpha.
- `RLS` допускается только как defense-in-depth на selected tables.
- Direct browser-to-Supabase path запрещён в alpha v1.

### Migration Cutover Runbook

- Freeze window.
- SQLite snapshot/export.
- Deploy Postgres schema.
- Backfill/import.
- Verification checks.
- One-way cutover на Postgres.
- Rollback только через snapshot restore + traffic switch, без schema downgrade.

### Acceptance Criteria

- Production path больше не использует SQLite.
- Один и тот же пользователь одинаково резолвится из bot и Mini App.
- Cutover runbook существует и прогнан на staging.
- Backend DB role использует least privilege.

## 4. Freeze Provider Matrix and Explicit Policy Layer

До monetization и UI зафиксировать provider matrix с конкретными launch defaults.

### Alpha Provider Matrix

- `text`:
  - provider path: OpenRouter only;
  - explicit flagship persona `whore`: `x-ai/grok-4.1-fast`;
  - explicit judge path: увести из OpenAI в non-OpenAI path через OpenRouter-supported model.
- `image`:
  - provider path: ModelsLab only;
  - launch model: один pinned `MODELSLAB_MODEL_ID` в production env;
  - `MODELSLAB_MODEL_ID` immutable at launch.
- `audio`: не входит в explicit alpha critical path.
- `vision`: не входит в alpha v1.

### Launch Model Manifest

После audit freeze зафиксировать отдельный immutable manifest:

- `persona`
- `provider`
- `model`
- `capabilities`
- `enabled/disabled`

Правила:

- launch routing не должен зависеть от drift в `modes.py`;
- изменение модели в `modes.py` само по себе не меняет alpha launch behavior;
- bot catalog, Mini App catalog и model routing строятся от frozen launch manifest.

### Required Cleanup of Current OpenAI Defaults

- Убрать `JUDGE_MODEL_WHORE="openai/gpt-4o-mini"` из explicit production defaults.
- Убрать `PROMPT_TRANSLATION_ENGINE="openai"` из explicit production path.
- Убрать любые implicit OpenAI fallback’и из explicit judge/translation/image flow.
- Оставить OpenAI только вне explicit critical path, если он вообще нужен для non-explicit features.

### Moderation Rules

В `AccessPolicyService` и provider-facing services зафиксировать hard blocks:

- minors
- age ambiguity
- NCII / non-consensual intimate content
- real-person sexualization
- sexualized public figure / celebrity content
- incest / coercion / exploitation

### Acceptance Criteria

- Provider choice централизован и immutable at launch.
- Explicit text и explicit image используют зафиксированные provider paths.
- OpenAI отсутствует из explicit critical path alpha v1.
- Launch model manifest существует и используется как source of truth.

## 5. Persona Audit + Launch Allowlist Freeze

Не считать наличие persona в `src/config/modes.py` признаком launch readiness.

### Сделать

- Прогнать audit всех текущих persona из `modes.py`.
- Для каждой persona хранить операционный audit record:
  - `verdict`
  - `owner`
  - `risk_class`
  - `default_tier`
  - `kill_switch_key`
- Возможные `verdict`:
  - `launch-approved`
  - `launch-blocked`
  - `post-alpha`
- Ввести единый audit checklist:
  - prompt quality;
  - policy compliance;
  - tier/access mapping;
  - explicit eligibility;
  - bot UX sanity;
  - Mini App catalog sanity;
  - smoke pass.
- Зафиксировать итоговый alpha allowlist только из `launch-approved`.
- Добавить config kill switch: любую persona можно отключить без переписывания логики.
- На основе audit freeze собрать frozen launch model manifest.

### Acceptance Criteria

- У каждой persona есть audit verdict и операционный record.
- Alpha catalog строится только из `launch-approved`.
- Наличие persona в `modes.py` не означает launch readiness.
- Bot и Mini App используют один и тот же frozen allowlist.
- Launch model manifest собран только из approved persona.

## 6. Monetization Core and Shared Access State

Добавить monetization как backend feature.

### Сделать

- Ввести tiers:
  - `free`
  - `trial`
  - `premium`
- Ввести gating для:
  - premium characters;
  - explicit characters;
  - explicit image generation.
- Сделать explicit 18+ consent частью backend-state, а не только UI-экрана.
- И bot, и Mini App проходят через один `AccessPolicyService`.
- Ввести trial state и usage counters.
- Operator flow сделать через закрытые bot-команды:
  - `/grant_access`
  - `/revoke_access`
  - `/user_status`
  - `/usage_status`

### Admin Hardening

- Allowlist операторов по Telegram user ID.
- Audit events на `grant/revoke`.
- Confirmation guardrails для чувствительных команд.
- Abuse throttling для чувствительных операторских действий.
- Никаких публичных admin HTTP endpoints в alpha v1.

### Acceptance Criteria

- Bot-first путь не может обойти explicit gate.
- Free/trial/premium и consent state совпадают в bot и Mini App.
- Доступ выдаётся только через защищённый operator flow.

## 7. Job Reliability Before Launch

До deploy закрыть restart/crash semantics для image jobs.

### Сделать

- Хранить job state в Postgres.
- Job ids делать non-enumerable: `UUID` или `ULID`.
- На старте backend-а выполнять reconciliation stale jobs.
- Зафиксировать terminal-state invariants:
  - `cancelled` не перетирается поздним `completed/failed`.
- Разделить synchronous user ack и async completion.
- Публичный status path для job = `GET /api/jobs/{job_id}`.
- Доступ к `GET /api/jobs/{job_id}` разрешён только владельцу job или оператору.
- Owner check обязателен частью контракта endpoint-а.

### Interfaces

- `JobRepository.reconcile_stale_jobs()`
- `JobService.start_job()`
- `JobService.cancel_job()`
- `JobService.complete_job()`
- `JobService.fail_job()`

### Acceptance Criteria

- Restart Railway process не оставляет dangling `running` jobs.
- `reset_conversation` корректно cancel’ит активные jobs.
- Recovery semantics покрыты integration tests.
- Status endpoint нельзя перечислять или угадывать по последовательным id.

## 8. Mini App Alpha

Добавить Mini App как UI поверх уже готового backend truth.

### Сделать

- Поднять Next.js Telegram Mini App на Vercel.
- Реализовать alpha v1 UI:
  - каталог персонажей;
  - профиль;
  - usage/limits;
  - plan/access state;
  - locked premium states;
  - onboarding;
  - 18+ consent UX.
- Добавить `Открыть приложение` из бота.
- Не переносить основной чат в Mini App.

### Правила

- Vercel frontend не реализует entitlement logic.
- Все business checks приходят из Railway backend.

### Acceptance Criteria

- Mini App показывает тот же access state, что и бот.
- Mini App использует backend-issued session token.
- Explicit UI не открывается без backend consent state.

## 9. Compliance and Alpha Ops

Compliance начинается во время Track 4-8, а этот шаг является completion/hardening перед launch.

### Сделать

- Privacy Policy
- Terms
- explicit 18+ disclaimer and consent model
- deletion/export flow
- abuse/reporting path
- logging policy без raw sensitive content
- secrets management
- backup/restore policy
- closed alpha cohort process

### Acceptance Criteria

- Legal/compliance материалы готовы до launch.
- Consent model есть как backend behavior.
- Есть support/abuse/remove-account process.

## Delivery Sequence

Исполнять как отдельные инициативы/PR chains:

1. `Finish Refactor`
2. `FastAPI HTTP Adapter on Railway`
3. `Postgres Backend + Cutover Runbook`
4. `Provider Matrix + Explicit Policy Layer`
5. `Monetization Core + Admin Commands`
6. `Persona Audit + Launch Allowlist Freeze`
7. `Job Reliability`
8. `Mini App Alpha`
9. `Compliance Completion + Alpha Ops`
10. `Deploy to Railway + Vercel + Supabase`

## Test Plan

- Launcher tests подтверждают, что `src/main.py` больше не содержит прямых SQLite paths.
- HTTP adapter tests покрывают:
  - init-data verification;
  - freshness window checks;
  - session issuance;
  - bearer auth;
  - protected `GET /api/*`;
  - `healthz/readyz`;
  - CORS/origin allowlist;
  - session TTL and expiry behavior;
  - `401`-driven silent re-auth flow;
  - rate limiting на `POST /api/session/telegram`.
- Postgres integration tests покрывают `users/conversations/messages/entitlements/jobs/events/sessions`.
- Cutover rehearsal tests покрывают `freeze/snapshot/import/verification`.
- Access tests покрывают `free/trial/premium`, explicit consent, provider eligibility.
- Admin command tests покрывают allowlist, audit events, confirmations.
- Persona audit tests/checklist coverage.
- Frozen allowlist tests for bot catalog and Mini App catalog.
- Launch model manifest tests покрывают frozen routing и отсутствие drift из `modes.py`.
- Disabled persona does not leak into menus/API.
- Job reconciliation tests покрывают restart после running image jobs.
- `GET /api/jobs/{job_id}` tests покрывают owner/operator access, non-enumerable ids и terminal states.
- Mini App API tests подтверждают direct browser -> Railway path и единый backend truth.
- Security tests покрывают:
  - browser has no direct DB path;
  - least-privilege DB role assumptions;
  - no sensitive payload logging;
  - operator hardening.
- E2E alpha smoke:
  - Railway bot startup;
  - Supabase connectivity;
  - Mini App open from Telegram;
  - backend session exchange;
  - 18+ consent gate;
  - locked premium state;
  - granted premium state;
  - explicit image request lifecycle;
  - image job recovery after process restart.

## Assumptions and Defaults

- Webhook не нужен для alpha v1; polling на Railway остаётся дефолтом.
- Railway — фиксированный runtime choice для Python backend.
- Vercel — только Mini App frontend.
- `src/adapters/http/**` — фиксированный путь для Python HTTP adapter.
- FastAPI — фиксированный HTTP stack.
- Mini App transport path фиксирован: `browser -> Railway API` directly.
- Session token = opaque session id with server-side lookup, передаётся как bearer token, TTL 15 minutes, без refresh endpoint.
- Mini App при `401` повторно проходит `POST /api/session/telegram`.
- Postgres backend — единственный source of truth для bot и Mini App.
- Explicit alpha v1 включает `text + image`, но не включает `audio/vision` в critical path.
- OpenAI выводится из explicit critical path alpha v1.
- Текущие persona из `modes.py` считаются candidate set; финальный alpha catalog определяется audit freeze.
- `RLS` в alpha — defense-in-depth, а не primary auth boundary.
- Compliance работа начинается вместе с Provider/Monetization tracks, а не только в финале.
