# Tasks

- [x] Extract shared runtime helpers out of `src/main.py`.
- [x] Move launcher state persistence wrappers behind `src/db/repositories.py`.
- [x] Move mode switch, reset, and runtime analytics/event logging paths off ad hoc launcher SQL.
- [x] Inventory the remaining `src/main.py` responsibility buckets and explicitly track what still owns orchestration there.
- [ ] Extract remaining orchestration from `src/main.py` into service modules.
  Current progress: image provider selection, prompt translation, and backend generation moved to `src/core/image_service.py`; Telegram-side image job runtime moved to `src/adapters/telegram/image_runtime.py`; chat prompt assembly, completion glue, and story-state update moved to `src/core/chat_service.py`; remaining launcher-owned work is now mostly repository-backed conversation/access orchestration plus bootstrap debt.
- [ ] Decide whether `init_db()` bootstrap stays in launcher or moves behind bootstrap/adapters.
- [ ] Remove or neutralize `src/core/legacy_runtime.py`.
- [ ] Keep Telegram adapter code free of product rules.
- [ ] Keep core/service boundaries free of `aiogram` types.
- [ ] Ensure conversation/image/reset/access flows operate on domain inputs, not Telegram message objects.
- [x] Add or update service-level tests for extracted logic.
- [x] Run `pytest` on the touched refactor slices.
- [ ] Run `ruff`.
- [ ] Run limited `mypy` on extracted code.
- [x] Update `docs/current/alpha-launch/status.md` as refactor progress changes.
