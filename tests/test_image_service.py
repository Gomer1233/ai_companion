from __future__ import annotations

import pytest

from src.app.settings import Settings
from src.core.image_service import ImageService
from tests.support import DummyAsyncClient


@pytest.mark.asyncio
async def test_image_service_dispatches_to_selected_provider(monkeypatch) -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENROUTER_API_KEY": "or-key",
            "IMAGE_BACKEND_PROVIDER": "openrouter",
            "OPENROUTER_IMAGE_MODEL": "image-model",
        }
    )
    service = ImageService(settings=settings, openrouter_client=DummyAsyncClient())

    async def fake_generate(self, prompt: str, image_model: str) -> bytes:
        assert prompt == "draw this"
        assert image_model == "image-model"
        return b"png-bytes"

    monkeypatch.setattr(ImageService, "_openrouter_generate_image", fake_generate)

    result = await service.generate_image("draw this")

    assert result == b"png-bytes"
    assert service.analytics_context() == ("openrouter", "image-model")


@pytest.mark.asyncio
async def test_image_service_skips_translation_when_disabled() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENAI_API_KEY": "oa-key",
            "PROMPT_TRANSLATION_ENABLED": "0",
        }
    )
    service = ImageService(settings=settings, openrouter_client=DummyAsyncClient())

    result = await service._maybe_translate_prompt("modelslab", "prompt")

    assert result == "prompt"


@pytest.mark.asyncio
async def test_image_service_uses_cached_translation_without_network() -> None:
    settings = Settings.from_env(
        {
            "TELEGRAM_TOKEN": "tg-token",
            "OPENAI_API_KEY": "oa-key",
        }
    )
    service = ImageService(settings=settings, openrouter_client=DummyAsyncClient())
    service._translation_cache["ru text"] = "translated"

    result = await service._translate_to_english("ru text")

    assert result == "translated"


def test_image_service_rejects_malformed_data_url() -> None:
    with pytest.raises(RuntimeError, match="Malformed data URL"):
        ImageService._data_url_to_bytes("data:image/png;base64")
