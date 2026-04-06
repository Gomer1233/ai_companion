from __future__ import annotations

from dataclasses import dataclass

from src.app.settings import Settings
from src.app.variants import AppVariantConfig, ChannelAdapterConfig


@dataclass(frozen=True, slots=True)
class ProviderRegistry:
    image_providers: tuple[str, ...]
    text_providers: tuple[str, ...]
    tts_providers: tuple[str, ...]

    @classmethod
    def default(cls) -> "ProviderRegistry":
        return cls(
            image_providers=("openrouter", "openai", "modelslab", "together"),
            text_providers=("openrouter",),
            tts_providers=("openai", "elevenlabs"),
        )

    def supported_image_providers(
        self,
        app_variant: AppVariantConfig,
        channel: ChannelAdapterConfig,
    ) -> tuple[str, ...]:
        if not channel.supports_images:
            return ()
        return tuple(provider for provider in self.image_providers if provider in app_variant.supported_image_providers)

    def validate_startup(
        self,
        settings: Settings,
        app_variant: AppVariantConfig,
        channel: ChannelAdapterConfig,
    ) -> None:
        if not settings.telegram_token:
            raise RuntimeError("Missing env TELEGRAM_TOKEN")

        supported_images = self.supported_image_providers(app_variant, channel)
        if settings.image_backend_provider not in supported_images:
            supported = ", ".join(supported_images)
            raise RuntimeError(
                f"Unsupported IMAGE_BACKEND_PROVIDER={settings.image_backend_provider}. Supported: {supported}"
            )

        if settings.image_backend_provider == "openrouter" and not settings.openrouter_api_key:
            raise RuntimeError("Missing env OPENROUTER_API_KEY (needed for IMAGE_BACKEND_PROVIDER=openrouter)")

        if settings.image_backend_provider == "openai" and not settings.openai_api_key:
            raise RuntimeError("Missing env OPENAI_API_KEY (needed for IMAGE_BACKEND_PROVIDER=openai)")

        if settings.image_backend_provider == "modelslab" and not settings.modelslab_api_key:
            raise RuntimeError("Missing env MODELSLAB_API_KEY (needed for IMAGE_BACKEND_PROVIDER=modelslab)")

        if settings.image_backend_provider == "together" and not settings.tog_api_key:
            raise RuntimeError("Missing env TOG_API_KEY (needed for IMAGE_BACKEND_PROVIDER=together)")

