from __future__ import annotations

from pathlib import Path

import pytest

from src.app.provider_registry import ProviderRegistry
from src.app.settings import Settings
from src.app.variants import MAIN_APP_VARIANT, TELEGRAM_CHANNEL_CONFIG
from src.config.alpha_launch_manifest import ALPHA_LAUNCH_MODEL_MANIFEST, validate_alpha_launch_manifest
from src.core.contracts import (
    AnalyticsEvent,
    AnalyticsEventType,
    ConversationRecord,
    ConversationRef,
    ConversationStatus,
    CoreResponse,
    DeferredJob,
    InboundEvent,
    InboundEventType,
    JobStatus,
    JobType,
    OutboundItem,
    OutboundItemType,
    UserRef,
    resolve_current_conversation,
    validate_default_conversations,
)
from src.core.access_policy import (
    AccessPolicyService,
    ExplicitCapability,
    ExplicitModerationCategory,
    ExplicitPolicyInput,
    LaunchManifestRecord,
)


def test_persona_models_do_not_use_known_unavailable_openrouter_ids() -> None:
    from src.config.modes import MODE_TO_MODEL

    unavailable = {
        "google/gemini-3-pro-preview",
        "google/gemini-2.5-flash-preview-09-2025",
        "nousresearch/deephermes-3-mistral-24b-preview",
        "xiaomi/mimo-v2-flash:free",
    }

    configured_unavailable = {
        mode: model for mode, model in MODE_TO_MODEL.items() if model in unavailable
    }

    assert configured_unavailable == {}


def test_access_policy_rejects_openai_provider_for_explicit_text_and_image() -> None:
    service = AccessPolicyService.alpha_default()

    assert service.authorize_explicit(
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.TEXT,
            provider="openrouter",
            model="x-ai/grok-4.1-fast",
        )
    ).allowed is True
    assert service.authorize_explicit(
        ExplicitPolicyInput(
            mode="unhinged",
            capability=ExplicitCapability.TEXT,
            provider="openrouter",
            model="x-ai/grok-4.1-fast",
        )
    ).allowed is True
    assert service.authorize_explicit(
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.IMAGE,
            provider="modelslab",
            model="pinned-model",
        )
    ).allowed is True

    text_decision = service.authorize_explicit(
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.TEXT,
            provider="openai",
            model="gpt-4o-mini",
        )
    )
    image_decision = service.authorize_explicit(
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.IMAGE,
            provider="openai",
            model="gpt-image-1",
        )
    )
    unhinged_decision = service.authorize_explicit(
        ExplicitPolicyInput(
            mode="unhinged",
            capability=ExplicitCapability.TEXT,
            provider="openai",
            model="gpt-4o-mini",
        )
    )

    assert text_decision.allowed is False
    assert image_decision.allowed is False
    assert unhinged_decision.allowed is False
    assert "provider_not_allowed" in text_decision.reasons
    assert "provider_not_allowed" in image_decision.reasons
    assert "provider_not_allowed" in unhinged_decision.reasons


def test_access_policy_rejects_openai_model_ids_even_when_provider_is_openrouter() -> None:
    service = AccessPolicyService.alpha_default()

    decision = service.authorize_explicit(
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.TEXT,
            provider="openrouter",
            model="openai/gpt-4o-mini",
        )
    )

    assert decision.allowed is False
    assert "openai_model_not_allowed" in decision.reasons


def test_access_policy_rejects_bare_openai_model_ids() -> None:
    service = AccessPolicyService.alpha_default()

    text_decision = service.authorize_explicit(
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.TEXT,
            provider="openrouter",
            model="gpt-4o-mini",
        )
    )
    image_decision = service.authorize_explicit(
        ExplicitPolicyInput(
            mode="whore",
            capability=ExplicitCapability.IMAGE,
            provider="modelslab",
            model="gpt-image-1",
        )
    )

    assert text_decision.allowed is False
    assert image_decision.allowed is False
    assert "openai_model_not_allowed" in text_decision.reasons
    assert "openai_model_not_allowed" in image_decision.reasons


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
        ExplicitPolicyInput(
            mode="basic",
            capability=ExplicitCapability.IMAGE,
            provider="openai",
            model="gpt-image-1",
        )
    )

    assert decision.allowed is True


def test_alpha_launch_manifest_is_independent_frozen_config() -> None:
    records = ALPHA_LAUNCH_MODEL_MANIFEST

    assert records
    assert all(record.persona for record in records)
    assert all(record.model for record in records)
    assert {record.persona for record in records} == {"whore", "unhinged"}


def test_persona_audit_covers_every_candidate_persona() -> None:
    from src.config.modes import PERSONAS
    from src.config.persona_audit import PERSONA_AUDIT_RECORDS

    candidate_keys = {persona.key for persona in PERSONAS}
    audited_keys = {record.persona for record in PERSONA_AUDIT_RECORDS}

    assert audited_keys == candidate_keys


def test_alpha_launch_catalog_uses_approved_personas_and_categories() -> None:
    from src.config.persona_audit import build_alpha_launch_catalog

    catalog = build_alpha_launch_catalog(env={})
    catalog_ids = [item.id for item in catalog]
    catalog_modes = [item.mode for item in catalog]
    categories = {item.id: item.category for item in catalog}

    assert catalog_ids == [
        "basic",
        "brainstorm",
        "psychologist",
        "coach",
        "oldschool_rep",
        "chef",
        "financial",
        "doctor",
        "pet_behaviorist",
        "oldtimer",
        "whore",
        "unhinged",
    ]
    assert "coach" in catalog_ids
    assert "coach_premium" not in catalog_ids
    assert "coach_premium" in catalog_modes
    assert "coach" not in catalog_modes
    assert categories["coach"] == "practice"
    assert categories["oldtimer"] == "entertainment"
    assert categories["whore"] == "explicit"
    assert categories["unhinged"] == "explicit"
    assert {"alco", "communist", "conspiro"} & set(catalog_ids) == set()


def test_alpha_launch_catalog_respects_persona_kill_switches() -> None:
    from src.config.persona_audit import build_alpha_launch_catalog

    catalog = build_alpha_launch_catalog(env={"LINA_PERSONA_UNHINGED_ENABLED": "0"})

    assert "unhinged" not in {item.id for item in catalog}


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


def test_settings_from_env_parses_values() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "OPENAI_API_KEY": "oa-key",
            "IMAGE_BACKEND_PROVIDER": "TOGETHER",
            "TOG_API_KEY": "tog-key",
            "TOG_WIDTH": "2048",
            "TOG_HEIGHT": "1536",
            "PROMPT_TRANSLATION_ENABLED": "true",
            "PROMPT_TRANSLATION_FOR": "modelslab, together",
            "JUDGE_MAX_TOKENS": "333",
            "MAX_AUTO_CONTINUATIONS": "5",
            "HTTP_HOST": "127.0.0.1",
            "HTTP_PORT": "9000",
            "HTTP_CORS_ORIGINS": "http://localhost:3000, https://miniapp.example",
            "HTTP_SESSION_TTL_SEC": "7200",
            "HTTP_TELEGRAM_INIT_MAX_AGE_SEC": "120",
            "HTTP_SESSION_RATE_LIMIT_WINDOW_SEC": "30",
            "HTTP_SESSION_RATE_LIMIT_MAX_ATTEMPTS": "7",
            "DB_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://lina_app:secret@db.example/lina",
        },
        project_root=Path("D:/projects/Lina_AI"),
    )

    assert settings.telegram_token == "tg-token"
    assert settings.image_backend_provider == "together"
    assert settings.tog_width == 2048
    assert settings.tog_height == 1536
    assert settings.prompt_translation_enabled is True
    assert settings.prompt_translation_for == {"modelslab", "together"}
    assert settings.judge_max_tokens == 333
    assert settings.max_auto_continuations == 5
    assert settings.http_host == "127.0.0.1"
    assert settings.http_port == 9000
    assert settings.http_cors_origins == ("http://localhost:3000", "https://miniapp.example")
    assert settings.http_session_ttl_sec == 7200
    assert settings.http_telegram_init_max_age_sec == 120
    assert settings.http_session_rate_limit_window_sec == 30
    assert settings.http_session_rate_limit_max_attempts == 7
    assert settings.db_backend == "postgres"
    assert settings.database_url == "postgresql://lina_app:secret@db.example/lina"
    assert settings.bot_db_path.endswith("bot_state.db")


def test_provider_registry_validates_supported_provider_matrix() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENAI_API_KEY": "oa-key",
            "IMAGE_BACKEND_PROVIDER": "openai",
        }
    )

    registry = ProviderRegistry.default()
    registry.validate_startup(settings, MAIN_APP_VARIANT, TELEGRAM_CHANNEL_CONFIG)


def test_provider_registry_rejects_unsupported_provider() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "IMAGE_BACKEND_PROVIDER": "replicate",
        }
    )

    registry = ProviderRegistry.default()
    with pytest.raises(RuntimeError, match="Unsupported IMAGE_BACKEND_PROVIDER"):
        registry.validate_startup(settings, MAIN_APP_VARIANT, TELEGRAM_CHANNEL_CONFIG)


def test_inbound_event_requires_expected_fields() -> None:
    user_ref = UserRef("user-1")
    conversation_ref = ConversationRef("conv-1")

    event = InboundEvent(
        event_type=InboundEventType.USER_TEXT,
        user_ref=user_ref,
        conversation_ref=conversation_ref,
        text="hello",
    )
    assert event.text == "hello"

    with pytest.raises(ValueError, match="requires text"):
        InboundEvent(
            event_type=InboundEventType.USER_TEXT,
            user_ref=user_ref,
            conversation_ref=conversation_ref,
        )

    with pytest.raises(ValueError, match="requires mode"):
        InboundEvent(
            event_type=InboundEventType.SWITCH_MODE,
            user_ref=user_ref,
            conversation_ref=conversation_ref,
        )


def test_core_response_preserves_item_order() -> None:
    response = CoreResponse(
        items=[
            OutboundItem(item_type=OutboundItemType.TEXT, text="first"),
            OutboundItem(item_type=OutboundItemType.IMAGE, media_ref="image-1"),
            OutboundItem(item_type=OutboundItemType.ACTION, action="select_mode"),
        ]
    )

    assert [item.item_type for item in response.items] == [
        OutboundItemType.TEXT,
        OutboundItemType.IMAGE,
        OutboundItemType.ACTION,
    ]


def test_deferred_job_cancelled_is_terminal() -> None:
    job = DeferredJob(
        job_id="job-1",
        user_ref=UserRef("user-1"),
        conversation_ref=ConversationRef("conv-1"),
        mode="basic",
        job_type=JobType.IMAGE,
        status=JobStatus.CANCELLED,
        progress=100,
    )

    assert job.can_transition_to(JobStatus.CANCELLED) is True
    assert job.can_transition_to(JobStatus.COMPLETED) is False
    assert job.can_transition_to(JobStatus.FAILED) is False

    with pytest.raises(ValueError, match="Invalid job status transition"):
        job.with_status(JobStatus.COMPLETED)


def test_conversation_lifecycle_helpers_enforce_single_default() -> None:
    user_ref = UserRef("user-1")
    archived = ConversationRecord(
        user_ref=user_ref,
        conversation_ref=ConversationRef("conv-archived"),
        active_mode="basic",
        status=ConversationStatus.ARCHIVED,
        is_default=True,
    )
    active = ConversationRecord(
        user_ref=user_ref,
        conversation_ref=ConversationRef("conv-active"),
        active_mode="chef",
        status=ConversationStatus.ACTIVE,
    )

    assert archived.accepts_events is False
    assert resolve_current_conversation([archived, active]) == active

    with pytest.raises(ValueError, match="more than one default conversation"):
        validate_default_conversations(
            [
                archived,
                ConversationRecord(
                    user_ref=user_ref,
                    conversation_ref=ConversationRef("conv-default-2"),
                    active_mode="basic",
                    is_default=True,
                ),
            ]
        )


def test_analytics_event_keeps_optional_conversation_context() -> None:
    event = AnalyticsEvent(
        event_type=AnalyticsEventType.IMAGE_REQUESTED,
        user_ref=UserRef("user-1"),
        conversation_ref=ConversationRef("conv-1"),
        mode="basic",
        job_id="job-1",
        ts=123,
        ok=True,
        note="queued",
    )

    assert event.job_id == "job-1"
    assert event.mode == "basic"
