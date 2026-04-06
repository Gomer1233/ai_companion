# Tasks

- [x] Extract shared runtime helpers out of `src/main.py`.
- [x] Move launcher state persistence wrappers behind `src/db/repositories.py`.
- [x] Move mode switch, reset, and runtime analytics/event logging paths off ad hoc launcher SQL.
- [ ] Inventory the remaining `src/main.py` responsibility buckets and explicitly track what still owns orchestration there.
- [ ] Extract remaining orchestration from `src/main.py` into service modules.
- [ ] Decide whether `init_db()` bootstrap stays in launcher or moves behind bootstrap/adapters.
- [ ] Remove or neutralize `src/core/legacy_runtime.py`.
- [ ] Keep Telegram adapter code free of product rules.
- [ ] Add or update service-level tests for extracted logic.
- [x] Run `pytest` on the touched refactor slices.
- [ ] Run `ruff`.
- [ ] Run limited `mypy` on extracted code.
- [x] Update `docs/current/alpha-launch/status.md` as refactor progress changes.
