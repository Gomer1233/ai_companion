from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


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


EXPLICIT_ALPHA_MODES = frozenset({"whore", "unhinged"})


class ExplicitSettings(Protocol):
    prompt_translation_engine: str
    translation_model: str
    judge_model_whore: str


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


BARE_OPENAI_MODEL_PREFIXES = (
    "gpt-",
    "gpt_",
    "gpt4",
    "gpt3",
    "o1",
    "o3",
    "o4",
    "dall-e",
    "tts-",
    "whisper-",
)


def is_openai_model_id(model: str) -> bool:
    normalized = model.strip().lower()
    return normalized.startswith("openai/") or normalized.startswith(BARE_OPENAI_MODEL_PREFIXES)


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
