# ALPHA-004: Provider Matrix + Explicit Policy Layer

## Goal

Freeze the alpha provider matrix, remove OpenAI from the explicit critical path, and centralize explicit eligibility and moderation blocks in backend policy/services.

## In Scope

- freeze `text` to OpenRouter-only on the alpha critical path
- freeze `image` to ModelsLab-only on the alpha critical path
- remove OpenAI defaults from explicit judge/translation/image flow
- centralize provider eligibility checks in `AccessPolicyService` and related services
- implement hard moderation blocks for minors, age ambiguity, NCII, real-person sexualization, public-figure sexualization, incest, coercion, and exploitation
- define frozen launch model manifest shape for later audit freeze

## Out of Scope

- final persona launch allowlist
- Mini App UI work
- payment automation
- deploy work

## Expected Files

- `src/app/**`
- `src/core/**`
- `src/config/**`
- `tests/**`
- `docs/current/alpha-launch/status.md`

## Test Focus

- explicit provider routing
- no OpenAI fallback in explicit critical path
- moderation block behavior
- manifest shape/validation where introduced

## Merge Criteria

- explicit text and image paths are frozen and centralized
- OpenAI is absent from explicit alpha critical path defaults
- moderation rules are enforced in backend services
- launch model manifest format is defined for audit freeze
