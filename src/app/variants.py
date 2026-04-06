from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AppVariantConfig:
    name: str
    relationship_enabled: bool = False
    supports_rap_submode: bool = False
    supported_image_providers: tuple[str, ...] = ()
    supported_text_providers: tuple[str, ...] = ("openrouter",)
    supported_tts_providers: tuple[str, ...] = ("openai", "elevenlabs")
    enabled_commands: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class ChannelAdapterConfig:
    name: str
    supports_images: bool = True
    supports_audio: bool = True
    supports_inline_callbacks: bool = True
    default_conversation_strategy: str = "last_active_or_default"


COMMON_COMMANDS = frozenset({"/start", "/mode", "/reset", "/status", "/models", "/model"})
COMMON_IMAGE_PROVIDERS = ("openrouter", "openai", "modelslab", "together")

MAIN_APP_VARIANT = AppVariantConfig(
    name="telegram",
    relationship_enabled=True,
    supports_rap_submode=True,
    supported_image_providers=COMMON_IMAGE_PROVIDERS,
    enabled_commands=COMMON_COMMANDS,
)

TELEGRAM_CHANNEL_CONFIG = ChannelAdapterConfig(name="telegram")
