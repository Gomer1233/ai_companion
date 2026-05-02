# ALPHA-004 Design: Provider Matrix + Explicit Policy Layer

## Scope

`ALPHA-004` removes OpenAI from the explicit alpha critical path only. OpenAI may remain in non-explicit legacy/default settings and non-critical capabilities such as TTS until a separate cleanup decision is made.

The explicit alpha critical path covers:

- explicit text routing for launch-approved explicit personas
- explicit judge routing for `whore`
- explicit image generation routing
- prompt translation used by explicit image generation
- backend policy checks that decide whether explicit content may proceed

## Architecture

Add a small backend policy/config layer that is independent of network clients and adapters. It should expose pure validation helpers for explicit provider eligibility, explicit moderation blocks, and launch manifest shape. The Telegram launcher and future HTTP/Mini App surfaces should consume these helpers instead of duplicating provider rules.

Keep the existing provider registry for general startup validation, but add explicit-alpha validation separately so legacy provider support does not imply explicit launch eligibility.

## Provider Decisions

- Explicit text provider: `openrouter`.
- Explicit image provider: `modelslab`.
- Explicit `whore` judge model default: `x-ai/grok-4.1-fast`.
- Explicit translation engine must not use OpenAI. If translation remains enabled for ModelsLab prompts, it should use a non-OpenAI OpenRouter path or be blocked from OpenAI fallback.

## Moderation Blocks

The explicit policy layer must hard-block at least these categories:

- minors
- age ambiguity
- NCII / non-consensual intimate content
- real-person sexualization
- public-figure / celebrity sexualization
- incest
- coercion
- exploitation

The first implementation may expose category-level decisions without attempting natural-language classification. That keeps `ALPHA-004` focused on backend enforcement points and lets later product work plug in classifiers or UI flows.

## Launch Manifest Shape

Define a frozen launch model manifest format for later audit freeze. The manifest should be separate from `src/config/modes.py` so changing candidate personas does not change alpha launch routing by accident.

Initial manifest records should include:

- `persona`
- `provider`
- `model`
- `capabilities`
- `enabled`

## Testing

Use test-first changes for each behavior:

- explicit defaults do not point to OpenAI
- explicit text and image provider eligibility rejects OpenAI
- explicit moderation categories block as expected
- launch manifest records validate required fields and provider eligibility
- existing non-explicit startup behavior remains intentionally preserved unless it conflicts with explicit alpha policy
