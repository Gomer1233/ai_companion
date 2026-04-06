# Tasks

- [x] Implement Telegram parser helpers from `aiogram` updates to `InboundEvent`.
- [x] Implement Telegram renderer helpers from `CoreResponse.items` to ordered UI output.
- [x] Move transport classification for menu text and callbacks into adapter layer.
- [x] Move simple command rendering into adapter layer helpers.
- [x] Add adapter tests for parsing, rendering, callback/menu mapping, and default conversation resolution.
- [ ] Move full aiogram handler registration out of legacy entrypoints.
- [ ] Isolate remaining transport-only state and storage beyond current helper layer.
