# ALPHA-004 Provider Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze the explicit alpha provider matrix, remove OpenAI from the explicit critical path, and add backend enforcement points without breaking non-explicit legacy provider paths.

**Architecture:** Add a pure `AccessPolicyService` under `src/core/` for explicit provider/model eligibility, moderation block enforcement, and launch manifest validation. Keep general startup provider validation separate from explicit authorization, so legacy imports can still use OpenAI while explicit flows reject OpenAI at request-time.

**Tech Stack:** Python 3.11, dataclasses/enums, pytest, Ruff, mypy.

---

## File Structure

- Create `src/core/access_policy.py`: explicit-alpha policy types, `AccessPolicyService`, provider/model validators, moderation decisions, and manifest record validation.
- Create `src/config/alpha_launch_manifest.py`: frozen manifest config surface independent from `src/config/modes.py`.
- Modify `src/app/settings.py`: explicit-safe defaults for judge and translation settings only.
- Modify `src/main.py`: pass explicit image requests and explicit prompt translation through `AccessPolicyService` at request-time boundaries; do not call explicit validation during module import.
- Modify `tests/test_core_contracts_and_config.py`: policy, settings, manifest, and model/provider validation tests.
- Modify `tests/test_entrypoint_smoke.py`: launcher import tests proving legacy OpenAI image provider import remains valid and explicit flow rejects it.
- Modify `tests/conftest.py`: isolate new env keys used by settings/import tests.
- Modify `docs/current/alpha-launch/status.md`: mark ALPHA-003 merged and ALPHA-004 in progress.
- Modify `docs/current/alpha-launch/pr-backlog.md`: mark ALPHA-003 done and ALPHA-004 in progress.
- Modify `docs/current/alpha-launch/prs/alpha-004-provider-matrix/tasks.md`: check completed items only after implementation and verification.

## Task 1: Access Policy Service

**Files:**
- Create: `src/core/access_policy.py`
- Test: `tests/test_core_contracts_and_config.py`

- [ ] **Step 1: Write failing tests for provider, model, and moderation enforcement**

Add these tests to `tests/test_core_contracts_and_config.py`:

```python
from src.core.access_policy import (
    AccessPolicyService,
    ExplicitCapability,
    ExplicitModerationCategory,
    ExplicitPolicyInput,
    LaunchManifestRecord,
)


def test_access_policy_rejects_openai_provider_for_explicit_text_and_image() -> None:
    service = AccessPolicyService.alpha_default()

    assert service.authorize_explicit(
        ExplicitPolicyInput(mode="whore", capability=ExplicitCapability.TEXT, provider="openrouter", model="x-ai/grok-4.1-fast")
    ).allowed is True
    assert service.authorize_explicit(
        ExplicitPolicyInput(mode="whore", capability=ExplicitCapability.IMAGE, provider="modelslab", model="pinned-model")
    ).allowed is True

    text_decision = service.authorize_explicit(
        ExplicitPolicyInput(mode="whore", capability=ExplicitCapability.TEXT, provider="openai", model="gpt-4o-mini")
    )
    image_decision = service.authorize_explicit(
        ExplicitPolicyInput(mode="whore", capability=ExplicitCapability.IMAGE, provider="openai", model="gpt-image-1")
    )

    assert text_decision.allowed is False
    assert image_decision.allowed is False
    assert "provider_not_allowed" in text_decision.reasons
    assert "provider_not_allowed" in image_decision.reasons


def test_access_policy_rejects_openai_model_ids_even_when_provider_is_openrouter() -> None:
    service = AccessPolicyService.alpha_default()

    decision = service.authorize_explicit(
        ExplicitPolicyInput(mode="whore", capability=ExplicitCapability.TEXT, provider="openrouter", model="openai/gpt-4o-mini")
    )

    assert decision.allowed is False
    assert "openai_model_not_allowed" in decision.reasons


def test_access_policy_enforces_explicit_moderation_blocks() -> None:
    service = AccessPolicyService.alpha_default()

    for category in ExplicitModerationCategory:
        decision = service.authorize_explicit(
            ExplicitPolicyInput(
                mode="whore",
                capability=ExplicitCapability.TEXT,
                provider="openrouter",
                model="x-ai/grok-4.1-fast",
                moderation_categories=(category,),
            )
        )
        assert decision.allowed is False
        assert category.value in decision.reasons


def test_non_explicit_mode_is_not_blocked_by_explicit_provider_policy() -> None:
    service = AccessPolicyService.alpha_default()

    decision = service.authorize_explicit(
        ExplicitPolicyInput(mode="basic", capability=ExplicitCapability.IMAGE, provider="openai", model="gpt-image-1")
    )

    assert decision.allowed is True
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_core_contracts_and_config.py -q
```

Expected: import failure for `src.core.access_policy`.

- [ ] **Step 3: Implement minimal access policy service**

Create `src/core/access_policy.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ExplicitCapability(str, Enum):
    TEXT = "text"
    IMAGE = "image"


class ExplicitModerationCategory(str, Enum):
    MINORS = "minors"
    AGE_AMBIGUITY = "age_ambiguity"
    NCII = "ncii"
    REAL_PERSON_SEXUALIZATION = "real_person_sexualization"
    PUBLIC_FIGURE_SEXUALIZATION = "public_figure_sexualization"
    INCEST = "incest"
    COERCION = "coercion"
    EXPLOITATION = "exploitation"


EXPLICIT_ALPHA_MODES = frozenset({"whore"})


@dataclass(frozen=True, slots=True)
class ExplicitPolicyDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExplicitProviderPolicy:
    allowed_providers: dict[ExplicitCapability, tuple[str, ...]]

    @classmethod
    def alpha_default(cls) -> "ExplicitProviderPolicy":
        return cls(
            allowed_providers={
                ExplicitCapability.TEXT: ("openrouter",),
                ExplicitCapability.IMAGE: ("modelslab",),
            }
        )

    def is_provider_allowed(self, capability: ExplicitCapability, provider: str) -> bool:
        return provider.strip().lower() in self.allowed_providers.get(capability, ())


@dataclass(frozen=True, slots=True)
class ExplicitPolicyInput:
    mode: str
    capability: ExplicitCapability
    provider: str
    model: str
    moderation_categories: tuple[ExplicitModerationCategory, ...] = ()


def is_openai_model_id(model: str) -> bool:
    return model.strip().lower().startswith("openai/")


@dataclass(frozen=True, slots=True)
class AccessPolicyService:
    provider_policy: ExplicitProviderPolicy = field(default_factory=ExplicitProviderPolicy.alpha_default)
    explicit_modes: frozenset[str] = EXPLICIT_ALPHA_MODES

    @classmethod
    def alpha_default(cls) -> "AccessPolicyService":
        return cls()

    def is_explicit_mode(self, mode: str) -> bool:
        return mode.strip().lower() in self.explicit_modes

    def authorize_explicit(self, request: ExplicitPolicyInput) -> ExplicitPolicyDecision:
        if not self.is_explicit_mode(request.mode):
            return ExplicitPolicyDecision(allowed=True)

        reasons: list[str] = []
        if not self.provider_policy.is_provider_allowed(request.capability, request.provider):
            reasons.append("provider_not_allowed")
        if is_openai_model_id(request.model):
            reasons.append("openai_model_not_allowed")
        reasons.extend(category.value for category in request.moderation_categories)

        return ExplicitPolicyDecision(allowed=not reasons, reasons=tuple(reasons))


@dataclass(frozen=True, slots=True)
class LaunchManifestRecord:
    persona: str
    provider: str
    model: str
    capabilities: tuple[ExplicitCapability, ...]
    enabled: bool

    def validate(self, service: AccessPolicyService) -> None:
        if not self.persona.strip():
            raise ValueError("persona must be non-empty")
        if not self.provider.strip():
            raise ValueError("provider must be non-empty")
        if not self.model.strip():
            raise ValueError("model must be non-empty")
        if not self.capabilities:
            raise ValueError("capabilities must be non-empty")
        if not self.enabled:
            return

        for capability in self.capabilities:
            decision = service.authorize_explicit(
                ExplicitPolicyInput(
                    mode=self.persona,
                    capability=capability,
                    provider=self.provider,
                    model=self.model,
                )
            )
            if not decision.allowed:
                raise ValueError(f"launch manifest record is not allowed: {', '.join(decision.reasons)}")
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_core_contracts_and_config.py -q
```

Expected: access policy tests pass.

## Task 2: Frozen Launch Manifest Config

**Files:**
- Create: `src/config/alpha_launch_manifest.py`
- Test: `tests/test_core_contracts_and_config.py`

- [ ] **Step 1: Write failing manifest tests**

Add these tests:

```python
from src.config.alpha_launch_manifest import ALPHA_LAUNCH_MODEL_MANIFEST, validate_alpha_launch_manifest


def test_alpha_launch_manifest_is_independent_frozen_config() -> None:
    records = ALPHA_LAUNCH_MODEL_MANIFEST

    assert records
    assert all(record.persona for record in records)
    assert all(record.model for record in records)
    assert {record.persona for record in records} == {"whore"}


def test_alpha_launch_manifest_rejects_openai_model_ids() -> None:
    service = AccessPolicyService.alpha_default()
    blocked = (
        LaunchManifestRecord(
            persona="whore",
            provider="openrouter",
            model="openai/gpt-4o-mini",
            capabilities=(ExplicitCapability.TEXT,),
            enabled=True,
        ),
    )

    with pytest.raises(ValueError, match="openai_model_not_allowed"):
        validate_alpha_launch_manifest(blocked, service)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_core_contracts_and_config.py::test_alpha_launch_manifest_is_independent_frozen_config tests/test_core_contracts_and_config.py::test_alpha_launch_manifest_rejects_openai_model_ids -q
```

Expected: import failure for `src.config.alpha_launch_manifest`.

- [ ] **Step 3: Create frozen manifest config**

Create `src/config/alpha_launch_manifest.py`:

```python
from __future__ import annotations

from src.core.access_policy import AccessPolicyService, ExplicitCapability, LaunchManifestRecord


ALPHA_LAUNCH_MODEL_MANIFEST: tuple[LaunchManifestRecord, ...] = (
    LaunchManifestRecord(
        persona="whore",
        provider="openrouter",
        model="x-ai/grok-4.1-fast",
        capabilities=(ExplicitCapability.TEXT,),
        enabled=True,
    ),
    LaunchManifestRecord(
        persona="whore",
        provider="modelslab",
        model="MODELSLAB_MODEL_ID",
        capabilities=(ExplicitCapability.IMAGE,),
        enabled=True,
    ),
)


def validate_alpha_launch_manifest(
    records: tuple[LaunchManifestRecord, ...] = ALPHA_LAUNCH_MODEL_MANIFEST,
    service: AccessPolicyService | None = None,
) -> None:
    policy = service or AccessPolicyService.alpha_default()
    for record in records:
        record.validate(policy)
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_core_contracts_and_config.py -q
```

Expected: manifest tests pass.

## Task 3: Explicit-Safe Defaults and Env Overrides

**Files:**
- Modify: `src/app/settings.py`
- Test: `tests/test_core_contracts_and_config.py`
- Test: `tests/conftest.py`

- [ ] **Step 1: Write failing settings tests**

Add these tests:

```python
def test_explicit_defaults_do_not_point_to_openai() -> None:
    settings = Settings.from_env({"TELEGRAM_TOKEN": "tg-token", "OPENROUTER_API_KEY": "or-key"})

    assert settings.judge_model_whore == "x-ai/grok-4.1-fast"
    assert settings.prompt_translation_engine == "openrouter"
    assert settings.translation_model == "x-ai/grok-4.1-fast"


def test_access_policy_rejects_openai_translation_model_override() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "PROMPT_TRANSLATION_ENGINE": "openrouter",
            "TRANSLATION_MODEL": "openai/gpt-4o-mini",
        }
    )
    service = AccessPolicyService.alpha_default()

    decision = service.authorize_explicit(
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.TEXT,
            provider=settings.prompt_translation_engine,
            model=settings.translation_model,
        )
    )

    assert decision.allowed is False
    assert "openai_model_not_allowed" in decision.reasons
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_core_contracts_and_config.py::test_explicit_defaults_do_not_point_to_openai -q
```

Expected: assertion failure because current defaults still use OpenAI.

- [ ] **Step 3: Update settings defaults and env isolation**

In `src/app/settings.py`, change:

```python
prompt_translation_engine=_get_str(source, "PROMPT_TRANSLATION_ENGINE", "openrouter").lower(),
translation_model=_get_str(source, "TRANSLATION_MODEL", "x-ai/grok-4.1-fast"),
judge_model_whore=_get_str(source, "JUDGE_MODEL_WHORE", "x-ai/grok-4.1-fast"),
```

In `tests/conftest.py`, add these keys to `ENV_KEYS`:

```python
"PROMPT_TRANSLATION_ENABLED",
"PROMPT_TRANSLATION_TARGET_LANG",
"PROMPT_TRANSLATION_FOR",
"PROMPT_TRANSLATION_ENGINE",
"TRANSLATION_MODEL",
"PROMPT_TRANSLATION_DEBUG",
"JUDGE_MODEL_WHORE",
```

Set default test values:

```python
"PROMPT_TRANSLATION_ENABLED": "0",
"PROMPT_TRANSLATION_TARGET_LANG": "en",
"PROMPT_TRANSLATION_FOR": "modelslab",
"PROMPT_TRANSLATION_ENGINE": "openrouter",
"TRANSLATION_MODEL": "x-ai/grok-4.1-fast",
"PROMPT_TRANSLATION_DEBUG": "0",
"JUDGE_MODEL_WHORE": "x-ai/grok-4.1-fast",
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_core_contracts_and_config.py -q
```

Expected: settings tests pass.

## Task 4: Explicit Image Flow Enforcement Without Legacy Startup Breakage

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_entrypoint_smoke.py`

- [ ] **Step 1: Write failing launcher tests**

Add these tests to `tests/test_entrypoint_smoke.py`:

```python
@pytest.mark.asyncio
async def test_explicit_image_flow_rejects_openai_provider(module_loader):
    module = module_loader("src.main", env={"IMAGE_BACKEND_PROVIDER": "openai", "OPENAI_API_KEY": "oa-test-key"})

    with pytest.raises(RuntimeError, match="provider_not_allowed"):
        await module.generate_image_backend("prompt", mode="whore")


def test_legacy_openai_image_provider_import_still_works(module_loader):
    module = module_loader("src.main", env={"IMAGE_BACKEND_PROVIDER": "openai", "OPENAI_API_KEY": "oa-test-key"})

    assert module.IMAGE_BACKEND_PROVIDER == "openai"
```

Keep `test_supported_image_provider_configs_import` for legacy startup providers. Do not add a module-import call to explicit validation.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_entrypoint_smoke.py::test_explicit_image_flow_rejects_openai_provider tests/test_entrypoint_smoke.py::test_legacy_openai_image_provider_import_still_works -q
```

Expected: `generate_image_backend()` does not accept `mode`, so the explicit-flow test fails.

- [ ] **Step 3: Wire `AccessPolicyService` into image-generation boundary**

In `src/main.py`, import:

```python
from src.core.access_policy import AccessPolicyService, ExplicitCapability, ExplicitPolicyInput
```

Add near runtime globals:

```python
ACCESS_POLICY = AccessPolicyService.alpha_default()
```

Change `generate_image_backend` signature:

```python
async def generate_image_backend(prompt: str, *, mode: str = "basic") -> bytes:
```

Before provider dispatch, add:

```python
provider = (IMAGE_BACKEND_PROVIDER or "openrouter").strip().lower()
image_model = (
    MODELSLAB_MODEL_ID
    if provider == "modelslab"
    else OPENROUTER_IMAGE_MODEL
    if provider == "openrouter"
    else OPENAI_IMAGE_MODEL
    if provider == "openai"
    else TOG_IMAGE_MODEL
    if provider == "together"
    else ""
)
decision = ACCESS_POLICY.authorize_explicit(
    ExplicitPolicyInput(
        mode=mode,
        capability=ExplicitCapability.IMAGE,
        provider=provider,
        model=image_model,
    )
)
if not decision.allowed:
    raise RuntimeError(f"Explicit image request blocked: {', '.join(decision.reasons)}")
```

Update the existing call site:

```python
gen_task = asyncio.create_task(generate_image_backend(image_prompt, mode=mode))
```

Update the ModelsLab dispatch branch inside `generate_image_backend`:

```python
if provider == "modelslab":
    return await modelslab_generate_image(prompt, mode=mode)
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_entrypoint_smoke.py -q
```

Expected: legacy imports pass, explicit image flow rejects OpenAI provider.

## Task 5: Explicit Translation Flow Enforcement

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_entrypoint_smoke.py`

- [ ] **Step 1: Write failing tests for explicit translation routing**

Add these tests to `tests/test_entrypoint_smoke.py`:

```python
@pytest.mark.asyncio
async def test_explicit_prompt_translation_rejects_openai_engine_before_network(module_loader):
    module = module_loader(
        "src.main",
        env={
            "PROMPT_TRANSLATION_ENABLED": "1",
            "PROMPT_TRANSLATION_ENGINE": "openai",
            "TRANSLATION_MODEL": "gpt-4o-mini",
        },
    )

    with pytest.raises(RuntimeError, match="Explicit translation blocked"):
        await module.maybe_translate_prompt("modelslab", "привет", mode="whore")


@pytest.mark.asyncio
async def test_explicit_prompt_translation_uses_openrouter_engine(module_loader, monkeypatch):
    module = module_loader(
        "src.main",
        env={
            "PROMPT_TRANSLATION_ENABLED": "1",
            "PROMPT_TRANSLATION_ENGINE": "openrouter",
            "TRANSLATION_MODEL": "x-ai/grok-4.1-fast",
        },
    )
    translator = AsyncMock(return_value="hello")
    monkeypatch.setattr(module, "call_openrouter", translator)

    translated = await module.maybe_translate_prompt("modelslab", "привет", mode="whore")

    assert translated == "hello"
    translator.assert_awaited_once()
```

`AsyncMock` is already imported in `tests/test_entrypoint_smoke.py`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_entrypoint_smoke.py::test_explicit_prompt_translation_rejects_openai_engine_before_network tests/test_entrypoint_smoke.py::test_explicit_prompt_translation_uses_openrouter_engine -q
```

Expected: `maybe_translate_prompt()` does not accept `mode`, and explicit translation still routes through `translate_to_english()`.

- [ ] **Step 3: Add OpenRouter translation path and explicit guard**

In `src/main.py`, change the module globals:

```python
PROMPT_TRANSLATION_ENGINE = os.getenv("PROMPT_TRANSLATION_ENGINE", "openrouter").strip().lower()
TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "x-ai/grok-4.1-fast").strip()
```

Add a non-OpenAI translation helper:

```python
async def translate_to_english_openrouter(text: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a translation engine. Translate the user's text to natural English.\n"
                "Return ONLY the translated text, no quotes, no explanations.\n"
                "Preserve formatting, line breaks, punctuation.\n"
                "Do NOT translate code, model IDs, LoRA names, URLs, tokens, or weighted prompt fragments.\n"
                "Keep proper nouns as-is."
            ),
        },
        {"role": "user", "content": text},
    ]
    return await call_openrouter(
        model=TRANSLATION_MODEL,
        messages=messages,
        temperature=0.0,
        max_tokens=700,
    )
```

Change `maybe_translate_prompt` signature:

```python
async def maybe_translate_prompt(provider: str, prompt: str, *, mode: str = "basic") -> str:
```

Before any network translation call, add:

```python
if ACCESS_POLICY.is_explicit_mode(mode):
    decision = ACCESS_POLICY.authorize_explicit(
        ExplicitPolicyInput(
            mode=mode,
            capability=ExplicitCapability.TEXT,
            provider=PROMPT_TRANSLATION_ENGINE,
            model=TRANSLATION_MODEL,
        )
    )
    if not decision.allowed:
        raise RuntimeError(f"Explicit translation blocked: {', '.join(decision.reasons)}")
```

Then route by engine:

```python
if PROMPT_TRANSLATION_ENGINE == "openrouter":
    translated = await translate_to_english_openrouter(prompt)
elif PROMPT_TRANSLATION_ENGINE == "openai":
    translated = await translate_to_english(prompt)
else:
    raise RuntimeError(f"Unsupported PROMPT_TRANSLATION_ENGINE={PROMPT_TRANSLATION_ENGINE}")
```

Change `modelslab_generate_image` signature and calls:

```python
async def modelslab_generate_image(prompt: str, *, mode: str = "basic") -> bytes:
    prompt = await maybe_translate_prompt("modelslab", prompt, mode=mode)
    negative = await maybe_translate_prompt("modelslab", MODELSLAB_NEGATIVE_PROMPT, mode=mode)
```

Ensure `generate_image_backend(..., mode=mode)` passes mode into `modelslab_generate_image(prompt, mode=mode)`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_entrypoint_smoke.py -q
```

Expected: explicit translation blocks OpenAI before any OpenAI network call and uses OpenRouter when configured.

## Task 6: Explicit Text/Judge/Translation Validation Helper

**Files:**
- Modify: `src/core/access_policy.py`
- Test: `tests/test_core_contracts_and_config.py`

- [ ] **Step 1: Write failing tests for settings-level explicit validation**

Add this test:

```python
def test_access_policy_validates_explicit_settings_models() -> None:
    service = AccessPolicyService.alpha_default()

    ok_settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "PROMPT_TRANSLATION_ENGINE": "openrouter",
            "TRANSLATION_MODEL": "x-ai/grok-4.1-fast",
            "JUDGE_MODEL_WHORE": "x-ai/grok-4.1-fast",
        }
    )
    service.validate_explicit_settings(ok_settings)

    blocked_settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "PROMPT_TRANSLATION_ENGINE": "openrouter",
            "TRANSLATION_MODEL": "openai/gpt-4o-mini",
            "JUDGE_MODEL_WHORE": "openai/gpt-4o-mini",
        }
    )
    with pytest.raises(ValueError, match="openai_model_not_allowed"):
        service.validate_explicit_settings(blocked_settings)
```

- [ ] **Step 2: Run test and verify RED**

Run:

```powershell
python -m pytest tests/test_core_contracts_and_config.py::test_access_policy_validates_explicit_settings_models -q
```

Expected: `AccessPolicyService` lacks `validate_explicit_settings`.

- [ ] **Step 3: Implement explicit settings validation**

To avoid a runtime import cycle, type the method parameter structurally:

```python
from typing import Protocol


class ExplicitSettings(Protocol):
    prompt_translation_engine: str
    translation_model: str
    judge_model_whore: str
```

Add method:

```python
def validate_explicit_settings(self, settings: ExplicitSettings) -> None:
    checks = (
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.TEXT,
            provider="openrouter",
            model=settings.judge_model_whore,
        ),
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.TEXT,
            provider=settings.prompt_translation_engine,
            model=settings.translation_model,
        ),
    )
    reasons: list[str] = []
    for check in checks:
        decision = self.authorize_explicit(check)
        reasons.extend(decision.reasons)
    if reasons:
        raise ValueError(", ".join(dict.fromkeys(reasons)))
```

Do not call this method during `src.main` import. It is a service-level guard for explicit launch verification and tests.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_core_contracts_and_config.py -q
```

Expected: all focused config/policy tests pass.

## Task 7: Status and Backlog Sync

**Files:**
- Modify: `docs/current/alpha-launch/status.md`
- Modify: `docs/current/alpha-launch/pr-backlog.md`
- Modify: `docs/current/alpha-launch/prs/alpha-004-provider-matrix/tasks.md`

- [ ] **Step 1: Update PR status docs**

Set `ALPHA-003` to `Done` and `ALPHA-004` to `In Progress` in `pr-backlog.md`.

In `status.md`, replace stale merge-review language with:

```markdown
- `ALPHA-003 Postgres Backend + Cutover Runbook` is merged to `main`.
- `ALPHA-004 Provider Matrix + Explicit Policy Layer` is in progress on `codex/alpha-004-provider-matrix`.
```

Set `Next Step` to implementation/verification of ALPHA-004 explicit policy and provider routing.

- [ ] **Step 2: Check completed ALPHA-004 tasks**

In `tasks.md`, check only tasks that are implemented and verified by this branch.

## Task 8: Full Verification

**Files:**
- No code changes unless verification exposes a bug.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_core_contracts_and_config.py tests/test_entrypoint_smoke.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full backend tests**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass, with any integration skips explicitly noted.

- [ ] **Step 3: Run syntax and static checks**

Run:

```powershell
python -m py_compile src/main.py src/app/settings.py src/core/access_policy.py src/config/alpha_launch_manifest.py
python -m ruff check .
python -m mypy
```

Expected: all commands exit `0`.
