from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from src.adapters.telegram import image_runtime
from src.adapters.telegram.image_runtime import (
    ImageJobRegistry,
    ImageRuntimeHooks,
    handle_awaiting_image_prompt,
    handle_image_cancel_callback,
)
from tests.support import FakeCallbackQuery, FakeMessage


@pytest.mark.asyncio
async def test_image_job_registry_cancel_stops_active_tasks() -> None:
    jobs = ImageJobRegistry()
    handle = jobs.start(7)
    handle.status_task = asyncio.create_task(asyncio.sleep(60))
    handle.gen_task = asyncio.create_task(asyncio.sleep(60))

    cancelled = await jobs.cancel(7)

    assert cancelled is True
    assert handle.cancel_event.is_set() is True
    assert handle.status_task.cancelled() is False
    assert handle.gen_task.cancelled() is False

    await asyncio.sleep(0)

    assert handle.status_task.cancelled() is True
    assert handle.gen_task.cancelled() is True


@pytest.mark.asyncio
async def test_handle_awaiting_image_prompt_returns_photo_and_clears_job(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_status_loop(bot, chat_id, cancel_event):
        await cancel_event.wait()

    monkeypatch.setattr(image_runtime, "run_image_fun_only_loop", fake_status_loop)

    logs: list[dict] = []
    upserts: list[dict] = []

    async def fake_generate_image_backend(prompt: str) -> bytes:
        assert "Запрос пользователя: sunset portrait" in prompt
        return b"png-bytes"

    def fake_upsert_photo_gate(**kwargs):
        upserts.append(kwargs)

    hooks = ImageRuntimeHooks(
        get_user_profile=lambda user_id: {"mode": "basic"},
        upsert_photo_gate=fake_upsert_photo_gate,
        log_user_event=lambda **kwargs: logs.append(kwargs),
        image_analytics_context=lambda: ("openrouter", "model-1"),
        generate_image_backend=fake_generate_image_backend,
    )
    jobs = ImageJobRegistry()
    message = FakeMessage("sunset portrait", user_id=4, chat_id=404)
    photo_gate = {
        "score": 1,
        "attempts": 2,
        "last_ask_ts": 0,
        "cooldown_until_ts": 0,
        "awaiting_context": 0,
        "context_asked_ts": 0,
        "awaiting_image_prompt": 1,
        "image_cooldown_until_ts": 0,
    }

    handled = await handle_awaiting_image_prompt(
        bot=SimpleNamespace(),
        message=message,
        user_id=4,
        user_text="sunset portrait",
        now=100,
        photo_gate=photo_gate,
        image_cooldown_sec=300,
        mode_to_image_style={"basic": "clean studio portrait"},
        jobs=jobs,
        hooks=hooks,
    )

    assert handled is True
    assert photo_gate["awaiting_image_prompt"] == 0
    assert len(message.photos) == 1
    assert jobs.get(4) is None
    assert [entry["event_type"] for entry in logs] == ["photo_request", "photo_result"]
    assert logs[-1]["note"] == "success"
    assert upserts[0]["awaiting_image_prompt"] == 0
    assert upserts[-1]["image_cooldown_until_ts"] == 400


@pytest.mark.asyncio
async def test_handle_image_cancel_callback_cancels_job_and_updates_callback() -> None:
    jobs = ImageJobRegistry()
    handle = jobs.start(11)
    handle.status_task = asyncio.create_task(asyncio.sleep(60))
    handle.gen_task = asyncio.create_task(asyncio.sleep(60))
    callback = FakeCallbackQuery("imgcancel", user_id=11)

    await handle_image_cancel_callback(callback, jobs)
    await asyncio.sleep(0)

    assert handle.cancel_event.is_set() is True
    assert callback.answers[-1]["text"] == "Отменено"
    assert callback.message.edits[-1]["text"] == "⛔ Ок, отменил генерацию."
