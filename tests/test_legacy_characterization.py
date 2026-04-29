from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest

from tests.support import FakeCallbackQuery, FakeMessage, table_row_count


START_TEXT = "\u0412\u044b\u0431\u0435\u0440\u0438 \u0440\u0435\u0436\u0438\u043c"
PICK_MODE_TEXT = "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0432\u044b\u0431\u0435\u0440\u0438 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u0436\u0430"
DESCRIBE_IMAGE_TEXT = "\u041d\u0430\u043f\u0438\u0448\u0438 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435"
HISTORY_RESET_TEXT = "\u0418\u0441\u0442\u043e\u0440\u0438\u044f \u043e\u0447\u0438\u0449\u0435\u043d\u0430"
MODE_ONLY_RESET_TEXT = "\u0442\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0440\u0435\u0436\u0438\u043c\u0430"
MODE_SET_TEXT = "\u0420\u0435\u0436\u0438\u043c \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d"
CHEF_TEXT = "\u0428\u0435\u0444-\u043f\u043e\u0432\u0430\u0440"
RAP_TEXT = "\u0420\u044d\u043f\u0435\u0440"
WHORE_ONLY_TEXT = "\u0442\u043e\u043b\u044c\u043a\u043e \u0432 \u0440\u0435\u0436\u0438\u043c\u0435"
MODE_DISABLED_TEXT = "\u0412\u044b\u0431\u043e\u0440 \u043c\u043e\u0434\u0435\u043b\u0435\u0439 \u043e\u0442\u043a\u043b\u044e\u0447\u0451\u043d"
WANT_PHOTO_TEXT = "\u0425\u043e\u0447\u0443 \u0444\u043e\u0442\u043e"
RESET_MODE_TEXT = "\u0421\u0431\u0440\u043e\u0441 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u0436\u0430"
SECRET_TEXT = "\u0421\u0415\u041a\u0420\u0415\u0422\u041d\u042b\u0419_\u0422\u0415\u041a\u0421\u0422"
ANSWER_TEXT = "\u0422\u0435\u0441\u0442\u043e\u0432\u044b\u0439 \u043e\u0442\u0432\u0435\u0442."


@pytest.mark.asyncio
async def test_start_command_prompts_mode_selection(module_loader):
    module = module_loader("src.main")
    module.init_db()
    message = FakeMessage("/start")

    await module.cmd_start(message)

    assert message.answers
    assert START_TEXT in message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_want_photo_requires_mode_selection(module_loader):
    module = module_loader("src.main")
    module.init_db()
    message = FakeMessage(WANT_PHOTO_TEXT)

    await module.want_photo_btn(message)

    assert message.answers
    assert PICK_MODE_TEXT in message.answers[-1]["text"]
    assert module.get_photo_gate(message.from_user.id)["awaiting_image_prompt"] == 0


@pytest.mark.asyncio
async def test_want_photo_sets_prompt_wait_state(module_loader, mark_mode_picked):
    module = module_loader("src.main")
    module.init_db()
    mark_mode_picked(module, 1, mode="basic")
    message = FakeMessage(WANT_PHOTO_TEXT)

    await module.want_photo_btn(message)

    assert message.answers
    assert DESCRIBE_IMAGE_TEXT in message.answers[-1]["text"]
    assert module.get_photo_gate(message.from_user.id)["awaiting_image_prompt"] == 1


@pytest.mark.asyncio
async def test_full_reset_clears_history_mode_lock_photo_gate_and_relationship_state(module_loader, mark_mode_picked):
    module = module_loader("src.main")
    module.init_db()
    mark_mode_picked(module, 1, mode="whore")
    module.append_history(1, "whore", "user", "hello")
    state = module.get_mode_state(1, "whore")
    state["recap"] = "busy"
    module.save_mode_state(1, "whore", state)
    module.lock_mode(1, "whore", reason="GAME OVER")
    module.upsert_photo_gate(1, score=1, attempts=1, last_ask_ts=1, cooldown_until_ts=2, awaiting_image_prompt=1, image_cooldown_until_ts=5)
    rel_state = module._load_relationship_state(1, "whore")
    rel_state.points = 321
    rel_state.user_name = "Tester"
    module._save_relationship_state(rel_state)
    message = FakeMessage("/reset")

    await module.cmd_reset(message)

    profile = module.get_user_profile(1)
    assert profile["mode"] == "basic"
    assert profile["mode_picked"] == "0"
    assert profile["chat_locked"] == "0"
    assert module.get_history(1, "whore") == []
    assert table_row_count(module.DB_PATH, "mode_state", "user_id=?", (1,)) == 0
    assert table_row_count(module.DB_PATH, "mode_lock", "user_id=?", (1,)) == 0
    assert table_row_count(module.DB_PATH, "photo_gate", "user_id=?", (1,)) == 0
    reset_state = module._load_relationship_state(1, "whore")
    assert reset_state.points == 0
    assert reset_state.user_name is None
    assert HISTORY_RESET_TEXT in message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_reset_current_mode_keeps_other_mode_history(module_loader, mark_mode_picked):
    module = module_loader("src.main")
    module.init_db()
    mark_mode_picked(module, 1, mode="chef")
    module.append_history(1, "chef", "user", "chef thread")
    module.append_history(1, "basic", "user", "basic thread")
    state = module.get_mode_state(1, "chef")
    state["recap"] = "active"
    module.save_mode_state(1, "chef", state)
    message = FakeMessage(RESET_MODE_TEXT)

    await module.reset_here_btn(message)

    assert module.get_history(1, "chef") == []
    assert module.get_history(1, "basic") == [{"role": "user", "content": "basic thread"}]
    assert table_row_count(module.DB_PATH, "mode_state", "user_id=? AND mode=?", (1, "chef")) == 0
    assert MODE_ONLY_RESET_TEXT in message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_main_chef_mode_prompts_for_submode(module_loader):
    module = module_loader("src.main")
    module.init_db()
    callback = FakeCallbackQuery("setmode:chef")

    await module.cb_setmode(callback)

    assert callback.answers[-1]["text"] == MODE_SET_TEXT
    assert CHEF_TEXT in callback.message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_main_oldschool_rep_prompts_for_submode(module_loader):
    module = module_loader("src.main")
    module.init_db()
    callback = FakeCallbackQuery("setmode:oldschool_rep")

    await module.cb_setmode(callback)

    assert callback.answers[-1]["text"] == MODE_SET_TEXT
    assert RAP_TEXT in callback.message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_whore_status_is_mode_specific(module_loader, mark_mode_picked):
    module = module_loader("src.main")
    module.init_db()
    mark_mode_picked(module, 1, mode="basic")
    basic_message = FakeMessage("/status")

    await module.cmd_status(basic_message)

    assert basic_message.answers
    assert WHORE_ONLY_TEXT in basic_message.answers[-1]["text"]

    whore_callback = FakeCallbackQuery("setmode:whore")
    await module.cb_setmode(whore_callback)
    whore_message = FakeMessage("/status")

    await module.cmd_status(whore_message)

    assert whore_message.answers
    assert len(whore_message.answers[-1]["text"]) > 20
    assert basic_message.answers[-1]["text"] != whore_message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_model_commands_are_disabled(module_loader):
    module = module_loader("src.main")
    module.init_db()
    message_models = FakeMessage("/models")
    message_model = FakeMessage("/model")
    callback = FakeCallbackQuery("setmodel:0")

    await module.cmd_models(message_models)
    await module.cmd_model(message_model)
    await module.on_set_model_callback(callback)

    assert MODE_DISABLED_TEXT in message_models.answers[-1]["text"]
    assert MODE_DISABLED_TEXT in message_model.answers[-1]["text"]
    edited_text = (callback.message.edits[-1]["text"] if callback.message.edits else callback.message.answers[-1]["text"])
    assert MODE_DISABLED_TEXT in edited_text


@pytest.mark.asyncio
async def test_main_text_flow_appends_history_and_replies_without_raw_log_preview(module_loader, mark_mode_picked, monkeypatch, caplog):
    module = module_loader("src.main")
    module.init_db()
    mark_mode_picked(module, 1, mode="basic")
    monkeypatch.setattr(module, "keep_typing", AsyncMock())
    monkeypatch.setattr(
        module,
        "call_openrouter_with_meta",
        AsyncMock(return_value=(ANSWER_TEXT, "stop", {"total_tokens": 1})),
    )
    message = FakeMessage(SECRET_TEXT)

    with caplog.at_level(logging.INFO):
        await module.on_text(message)

    history = module.get_history(1, "basic")
    assert history[0] == {"role": "user", "content": SECRET_TEXT}
    assert history[-1] == {"role": "assistant", "content": ANSWER_TEXT}
    assert message.answers[-1]["text"] == ANSWER_TEXT
    assert SECRET_TEXT not in caplog.text
    assert ANSWER_TEXT not in caplog.text
    assert "LLM raw len" not in caplog.text
    assert "after_strip" not in caplog.text


@pytest.mark.asyncio
async def test_whore_reset_clears_relationship_state(module_loader, mark_mode_picked):
    module = module_loader("src.main")
    module.init_db()
    mark_mode_picked(module, 1, mode="whore")
    state = module._load_relationship_state(1, "whore")
    state.points = 123
    state.user_name = "Tester"
    module._save_relationship_state(state)
    message = FakeMessage(RESET_MODE_TEXT)

    await module.reset_here_btn(message)

    reset_state = module._load_relationship_state(1, "whore")
    assert reset_state.points == 0
    assert reset_state.user_name is None
