# Tasks

- [x] Extract shared runtime helpers out of `src/main.py`.
- [x] Move launcher state persistence wrappers behind `src/db/repositories.py`.
- [x] Move mode switch, reset, and runtime analytics/event logging paths off ad hoc launcher SQL.
- [x] Inventory the remaining `src/main.py` responsibility buckets and explicitly track what still owns orchestration there.
- [x] Extract remaining orchestration from `src/main.py` into service modules.
  Current progress: image provider selection, prompt translation, and backend generation moved to `src/core/image_service.py`; Telegram-side image job runtime moved to `src/adapters/telegram/image_runtime.py`; chat prompt assembly, completion glue, and story-state update moved to `src/core/chat_service.py`; reset orchestration moved to `src/core/reset_service.py`; mode switch and submode persistence moved to `src/core/conversation_service.py`; DB bootstrap moved to `src/db/bootstrap.py`. Remaining `src/main.py` work is now Telegram UI-heavy branching and launcher wiring, which is acceptable scope for this PR.
- [x] Decide whether `init_db()` bootstrap stays in launcher or moves behind bootstrap/adapters.
- [x] Remove or neutralize `src/core/legacy_runtime.py`.
- [x] Keep Telegram adapter code free of product rules.
- [x] Keep core/service boundaries free of `aiogram` types.
- [x] Ensure conversation/image/reset/access flows operate on domain inputs, not Telegram message objects.
- [x] Add or update service-level tests for extracted logic.
- [x] Run `pytest` on the touched refactor slices.
- [x] Run `ruff`.
  Scoped ALPHA-001 refactor slice passed. Full-repo `ruff check .` still reports legacy cleanup outside this PR scope.
- [x] Run limited `mypy` on extracted code.
  Passed with configured `pyproject.toml` scope.
- [x] Update `docs/current/alpha-launch/status.md` as refactor progress changes.
