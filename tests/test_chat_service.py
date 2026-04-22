from __future__ import annotations

import pytest

from src.core.chat_service import (
    build_chat_messages,
    build_system_prompt,
    generate_chat_completion,
    is_audio_request,
    strip_game_over_markers,
    update_story_state,
)


def test_is_audio_request_matches_expected_phrases() -> None:
    assert is_audio_request("запиши мне аудио ответ") is True
    assert is_audio_request("обычный текст") is False


def test_build_system_prompt_includes_state_and_mode_addons() -> None:
    chef_prompt = build_system_prompt(
        mode="chef",
        state={"chef_submode": "restaurant", "premise": "cook", "cast": [], "timeline": [], "open_threads": [], "episode": 1, "season": 1},
        base_prompt="BASE",
        audio_only=False,
    )
    rap_prompt = build_system_prompt(
        mode="oldschool_rep",
        state={"rap_submode": "story", "premise": "rap", "cast": [], "timeline": [], "open_threads": [], "episode": 1, "season": 1},
        base_prompt="BASE",
        audio_only=False,
    )

    assert "[CHEF_SUBMODE=RESTAURANT]" in chef_prompt
    assert "[Состояние сюжета]" in chef_prompt
    assert "BPM по умолчанию" in rap_prompt


def test_strip_game_over_markers_detects_and_cleans() -> None:
    cleaned, triggered = strip_game_over_markers("hello [[GAME OVER]] world")
    assert triggered is True
    assert cleaned == "hello  world".strip()


def test_update_story_state_rolls_episode_and_timeline() -> None:
    updated = update_story_state(
        state={"episode": 2, "timeline": ["old"], "recap": "", "cast": [], "open_threads": []},
        user_text="new user action",
        reply="assistant reply",
    )

    assert updated["episode"] == 3
    assert updated["recap"] == "assistant reply"
    assert updated["timeline"][-1] == "Ход: new user action"


@pytest.mark.asyncio
async def test_generate_chat_completion_glues_truncated_reply_and_falls_back_to_estimate() -> None:
    calls: list[dict] = []

    async def fake_call_openrouter_with_meta(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return ("First sentence that", "length", {})
        return (" continues and ends.", "stop", {})

    result = await generate_chat_completion(
        mode="basic",
        model="model-1",
        messages=build_chat_messages(system_prompt="sys", history=[{"role": "user", "content": "hi"}]),
        call_openrouter_with_meta=fake_call_openrouter_with_meta,
    )

    assert len(calls) == 2
    assert "continues and ends" in result.reply
    assert result.total_tokens > 0
    assert result.tokens_source == "tiktoken"
