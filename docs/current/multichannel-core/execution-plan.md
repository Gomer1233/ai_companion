# План Рефакторинга: Мультиканальный Core для Lina AI

## Summary
Цель: выделить **мультиканальный application core**, где Telegram является первым адаптером, а не архитектурным центром.

Жёсткие правила:
- `aiogram` живёт только в adapter layer.
- services/repositories работают только с plain Python structures.
- `active mode` всегда **conversation-scoped**.
- ответы core возвращаются как **упорядоченный** `items: list[OutboundItem]`.
- deferred jobs входят в контракт сразу.
- миграции первого цикла только **forward-only**.
- один PR не смешивает migration, business-logic move и adapter cleanup.

## Core Contracts
### Identity
- `UserRef`: внутренний идентификатор пользователя.
- `ConversationRef`: внутренний идентификатор диалога.

### Reset scopes
Использовать ровно три операции:
- `reset_conversation(user_ref, conversation_ref)`
- `reset_mode_in_conversation(user_ref, conversation_ref, mode)`
- `reset_user_all(user_ref)`

### Inbound / Outbound
`InboundEvent` покрывает:
- `user_text`
- `switch_mode`
- `reset_conversation`
- `reset_mode_in_conversation`
- `reset_user_all`
- `request_image`
- `request_audio`
- `cancel_job`
- `request_context_reminder`

`CoreResponse`:
- `items: list[OutboundItem]`

`OutboundItem`:
- `text`
- `image`
- `audio`
- `action`
- `progress`
- `deferred_result`

### Deferred jobs
Минимальная job model:
- `job_id`
- `user_ref`
- `conversation_ref`
- `mode`
- `job_type`
- `status`
- `progress`
- `error_code?`
- `result_ref?`
- `created_at`
- `updated_at`

Статусы:
- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

Implementation notes:
- completion rule idempotent: `completed` и `failed` не могут перетереть уже выставленный `cancelled`
- terminal statuses: `completed`, `failed`, `cancelled`
- повторная запись terminal status допустима только если статус не меняется

## Conversation Lifecycle
Фиксируем сразу:

- `default conversation` создаётся лениво при первом пользовательском событии для `UserRef`, если у пользователя ещё нет ни одной conversation
- у пользователя **не может быть две `default conversation`**
- новая conversation в первом цикле создаётся только явным core-вызовом `create_conversation(user_ref)`; Telegram самопроизвольно новые conversation не создаёт
- архивирование поддерживается как soft-state на conversation: `active | archived`
- archived conversation не принимает новые user events, пока не будет явно re-opened
- archived conversation можно читать без reopen
- archived conversation можно reset’ить без reopen
- Telegram по умолчанию считает “текущей conversation” последнюю `active` conversation пользователя
- если у пользователя нет active conversation, Telegram adapter создаёт или выбирает `default conversation`
- в первом цикле Telegram UX может не показывать список conversation, но core-модель обязана это поддерживать

## Execution Model для Jobs
На первом цикле:

- jobs выполняются как **локальные background tasks в том же процессе**, без отдельного worker
- job создаёт core service при `request_image` / `request_audio`
- статус job хранится в **core persistence**
- completion path обязателен через polling-style `get_job_status(job_id)`
- push-completion допускается позже как дополнительный путь
- отдельный worker не вводится в первом цикле

## Scope Rules по Сущностям
### User-scoped
- profile / user settings верхнего уровня
- список conversation пользователя
- user-wide analytics, если событие не относится к конкретной conversation

### Conversation-scoped
- active mode
- history
- conversation status (`active/archived`)
- photo/image generation gate, cooldown и pending image flow
- job ownership
- relationship state
- context reminder source data

### Conversation + mode-scoped
- mode state
- mode lock
- mode-specific recap / timeline / open threads

Правило:
- transport metadata не попадает ни в одну из этих групп и считается adapter-state

## Reset Semantics
### `reset_conversation`
Очищает:
- history этой conversation
- active mode state в этой conversation
- relationship state этой conversation
- mode locks этой conversation
- gates/cooldowns/jobs этой conversation

Поведение с running job:
- running job этой conversation переводится в `cancelled`
- core пытается отправить cancel signal
- reset не ждёт физического завершения фоновой задачи; synchronously фиксирует доменное состояние как `cancelled`
- completion от уже отменённой задачи не должен повторно записывать успех/ошибку поверх `cancelled`

### `reset_mode_in_conversation`
Очищает:
- state и lock только указанного mode внутри conversation
- history conversation не очищается целиком, если иное не задано mode-policy
- jobs/cooldowns трогаются только если они mode-bound; если conversation-wide, не трогаются

### `reset_user_all`
Очищает:
- все active и archived conversation state пользователя
- все user-scoped и conversation-scoped jobs пользователя
- profile flags, если они не являются постоянной identity-частью

Implementation note:
- reset и job-cancel должны выполняться как **транзакционные операции**, чтобы локальные background tasks не создавали гонки между state cleanup и поздней записью completion

## Analytics / Events
Минимальная event schema:
- `event_type`
- `user_ref`
- `conversation_ref?`
- `mode?`
- `job_id?`
- `ts`
- `ok`
- `note?`

Базовый словарь `event_type`:
- `conversation_created`
- `conversation_archived`
- `mode_switched`
- `user_message_received`
- `assistant_reply_sent`
- `image_requested`
- `image_completed`
- `audio_requested`
- `audio_completed`
- `job_cancelled`
- `reset_conversation`
- `reset_mode_in_conversation`
- `reset_user_all`

## Фаза 0. Test Harness и Characterization Baseline
Сделать до любых крупных изменений:
- добавить `pytest` и минимальный test harness
- собрать characterization matrix для `main.py` и `bot_lika.py`
- явно разделить:
  - application behavior
  - adapter behavior
  - variant behavior
- зафиксировать текущие отличия по startup, provider support, reset, меню, image flow, logging, mode-specific behavior

## Фаза 1. Stabilization PRs
Исправить явные баги и ложные обещания без архитектурного переноса.

Сделать:
- починить `bot_lika` crash-path при `IMAGE_BACKEND_PROVIDER=openai`
- выровнять declared и actual provider support
- удалить или отключить ложную feature `/model`
- сделать deterministic reset на текущей схеме
- убрать raw content/reply preview из логов
- исправить критичные SQL/init дефекты

## Фаза 2. Minimal Core API и Config Layer
До DB migration ввести минимальный стабильный слой contracts.

Сделать:
- `UserRef`
- `ConversationRef`
- conversation lifecycle rules
- conversation-scoped active mode rule
- reset-scope API
- `InboundEvent`
- `CoreResponse`
- `OutboundItem`
- `Settings`
- `ProviderRegistry`
- `AppVariantConfig`
- `ChannelAdapterConfig`
- deferred job contract
- minimal analytics schema

## Фаза 3. Versioned Migrations и Persistence Migration
Построить новую persistence-модель и выполнить migration со старой БД.

Правила:
- только **forward-only**
- downgrade-логика не делается
- каждая миграция versioned и прогоняется через единый migrator

Backfill strategy:
- для каждого legacy `user_id` создать один `default conversation`
- привязать legacy history к `default conversation`
- `active mode` перенести как active mode `default conversation`
- `mode_state` перенести как conversation+mode-scoped state
- `relationship_state` перенести как conversation-scoped state
- `mode_lock` перенести как conversation+mode-scoped state
- profile оставить user-scoped
- events мигрировать в новую event schema, подставляя `default conversation`, где conversation можно восстановить

## Фаза 4. Repositories и State Boundary Cleanup
Сделать:
- `db/connection.py`
- `db/migrations.py`
- `db/repositories.py`

Repository methods:
- `create_conversation`
- `archive_conversation`
- `load_conversation`
- `load_active_conversation_for_user`
- `append_history`
- `load_history`
- `set_active_mode`
- `get_active_mode`
- `reset_conversation`
- `reset_mode_in_conversation`
- `reset_user_all`
- `lock_mode`
- `unlock_mode`
- `create_job`
- `update_job_status`
- `load_job`
- `load_relationship_state`
- `save_relationship_state`
- `append_event`

Implementation notes:
- операции `reset_*`, `cancel_job`, `complete_job`, `fail_job` должны иметь транзакционные границы
- persistence API должен запрещать переход `cancelled -> completed/failed`

## Фаза 5. Shared Core Extraction
Сделать:
- общий chat orchestration
- общий image/audio orchestration
- общую mode/policy logic
- общую reset/state logic
- relationship logic как optional extension
- variant-specific differences описывать через `AppVariantConfig`

## Фаза 6. Telegram Adapter Cleanup
Сделать Telegram чистым адаптером:
- parser: aiogram update -> `InboundEvent`
- renderer: `CoreResponse.items` -> Telegram UI
- command routing на adapter уровне
- keyboard/callback handling на adapter уровне
- transport-only state/storage на adapter уровне

## Фаза 7. Future-Ready Interfaces
Заложить:
- HTTP API / WebSocket adapter path
- auth/identity expansion поверх `UserRef`
- media abstraction через payload/reference
- polling-first, push-compatible deferred jobs
- готовность persistence к переходу SQLite -> Postgres

## Фаза 8. DX и Cleanup
Сделать:
- `ruff`
- ограниченный `mypy` на extracted code
- cleanup active source tree
- обновить README под architecture-as-built
- CI запускает tests + lint

## PR Process Rules
Обязательное правило:
- один PR не смешивает schema migration, перенос business logic и adapter cleanup

Рекомендуемая серия PR:
1. test harness + characterization
2. stabilization fixes
3. core contracts + config layer
4. migrations + backfill
5. repositories
6. shared core extraction
7. telegram adapter cleanup
8. DX/cleanup

## Test Plan
### Characterization
- оба legacy entrypoint’а
- различия `main` и `bot_lika`
- startup/provider matrix
- reset/image/mode behavior

### Core contract tests
- services работают только с plain structures
- `CoreResponse.items` сохраняет порядок mixed outputs
- `active mode` всегда conversation-scoped
- `ConversationRef` участвует во всех history/state APIs
- deferred job contract работает для image/audio
- reset scopes тестируются отдельно
- archived conversation не принимает новые inbound events
- archived conversation history читается без reopen
- у пользователя не создаются две `default conversation`

### Migration tests
- миграция с нуля
- миграция старой базы
- backfill в `default conversation`
- forward-only migration path
- несколько conversation’ов у одного пользователя не смешивают историю
- `reset_conversation`, `reset_mode_in_conversation`, `reset_user_all` очищают разный объём данных строго по контракту

### Persistence / race tests
- `cancelled` не перетирается поздним `completed`
- `cancelled` не перетирается поздним `failed`
- reset conversation с running job завершает job-state в `cancelled`
- транзакционный reset не оставляет полувычищенного state

### Adapter tests
- Telegram update корректно маппится в `InboundEvent`
- transport-команды остаются adapter-level
- `CoreResponse.items` корректно рендерится в Telegram
- Telegram default conversation resolution работает по правилам lifecycle

## Assumptions
- Telegram остаётся первым реализованным адаптером, но не считается ядром.
- `ConversationRef` закладывается сразу, даже если Telegram по умолчанию использует один основной тред.
- `active mode` всегда conversation-scoped.
- `photo_gate` и generation gate считаются core-state.
- jobs в первом цикле исполняются локально в том же процессе.
- `CoreCommand` не вводится, пока `InboundEvent` покрывает реальные сценарии.
- миграции в первом цикле только forward-only.
- целевая формулировка проекта: **мультиканальный core с Telegram как первым адаптером**.
