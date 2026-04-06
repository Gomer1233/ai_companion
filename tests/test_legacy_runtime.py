from __future__ import annotations

import asyncio
from types import SimpleNamespace

from src.core.legacy_runtime import LegacySharedRuntime


class FakeRepositories:
    def __init__(self) -> None:
        self.reset_mode_calls: list[tuple[str, str, str]] = []
        self.reset_all_calls: list[str] = []

    def reset_mode_in_conversation(self, user_ref: str, conversation_ref: str, mode: str) -> None:
        self.reset_mode_calls.append((user_ref, conversation_ref, mode))

    def reset_user_all(self, user_ref: str) -> None:
        self.reset_all_calls.append(user_ref)


class FakeMessage:
    def __init__(self, user_id: int, text: str = "ping") -> None:
        self.from_user = SimpleNamespace(id=user_id, username="user", first_name="User")
        self.chat = SimpleNamespace(id=500)
        self.message_id = 77
        self.text = text
        self.answers: list[dict] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append({"text": text, **kwargs})


class FakeCallback:
    def __init__(self, user_id: int, data: str) -> None:
        self.from_user = SimpleNamespace(id=user_id, username="user", first_name="User")
        self.data = data
        self.message = FakeMessage(user_id)
        self.answered: list[tuple[str, bool]] = []

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self.answered.append((text, show_alert))


def build_runtime() -> tuple[LegacySharedRuntime, dict[str, str], list[dict], list[int], list[tuple[int, str]]]:
    profile_store = {"mode": "basic", "mode_picked": "0"}
    events: list[dict] = []
    unlocked: list[int] = []
    special_calls: list[tuple[int, str]] = []
    photo_gate = {
        "score": 0,
        "attempts": 0,
        "last_ask_ts": 0,
        "cooldown_until_ts": 0,
        "awaiting_context": 0,
        "context_asked_ts": 0,
        "awaiting_image_prompt": 0,
        "image_cooldown_until_ts": 0,
    }

    def get_user_profile(user_id: int) -> dict:
        return dict(profile_store)

    def set_user_profile(user_id: int, preferred_name=None, preferred_title=None, mode=None) -> None:
        if mode is not None:
            profile_store["mode"] = mode

    def get_photo_gate(user_id: int) -> dict:
        return dict(photo_gate)

    def upsert_photo_gate(**kwargs) -> None:
        photo_gate.update(kwargs)

    def log_user_event(**kwargs) -> None:
        events.append(kwargs)

    def unlock_chat(user_id: int) -> None:
        unlocked.append(user_id)

    def repo_refs(user_id: int) -> tuple[str, str]:
        return (f"user-{user_id}", f"conv-{user_id}")

    def menu_for(profile: dict) -> str:
        return "menu"

    def build_modes_keyboard(user_id: int, current_mode: str | None = None) -> str:
        return f"kb:{current_mode}"

    def mark_mode_picked(user_id: int, mode: str) -> None:
        profile_store["mode_picked"] = "1"

    async def special_mode_switch_handler(user_id: int, prev_mode: str, mode: str, callback, profile, menu) -> bool:
        special_calls.append((user_id, mode))
        return False

    runtime = LegacySharedRuntime(
        db_path="test.db",
        db_repositories=FakeRepositories(),
        image_jobs={},
        main_menu="main-menu",
        mode_to_system_prompt={"basic": "prompt", "chef": "prompt"},
        mode_to_short_desc={"chef": "chef-desc"},
        get_user_profile=get_user_profile,
        set_user_profile=set_user_profile,
        get_photo_gate=get_photo_gate,
        upsert_photo_gate=upsert_photo_gate,
        log_user_event=log_user_event,
        unlock_chat=unlock_chat,
        repo_refs=repo_refs,
        menu_for=menu_for,
        build_modes_keyboard=build_modes_keyboard,
        mark_mode_picked=mark_mode_picked,
        remind_context_keyboard_factory=lambda: "remind-kb",
        special_mode_switch_handler=special_mode_switch_handler,
    )
    return runtime, profile_store, events, unlocked, special_calls


def test_handle_want_photo_request_sets_gate() -> None:
    runtime, profile_store, _events, _unlocked, _special_calls = build_runtime()
    profile_store["mode_picked"] = "1"
    message = FakeMessage(1, text="\u0425\u043e\u0447\u0443 \u0444\u043e\u0442\u043e")

    asyncio.run(runtime.handle_want_photo_request(message))

    assert message.answers[-1]["text"] == "\u041e\u043a. \u041d\u0430\u043f\u0438\u0448\u0438 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435: \u0447\u0442\u043e \u0438\u043c\u0435\u043d\u043d\u043e \u0441\u0433\u0435\u043d\u0435\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c?"


def test_handle_set_mode_callback_updates_profile_and_sends_default_reply() -> None:
    runtime, profile_store, events, _unlocked, special_calls = build_runtime()
    callback = FakeCallback(7, "setmode:chef")

    asyncio.run(runtime.handle_set_mode_callback(callback))

    assert profile_store["mode"] == "chef"
    assert profile_store["mode_picked"] == "1"
    assert callback.answered == [("\u0420\u0435\u0436\u0438\u043c \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d", False)]
    assert special_calls == [(7, "chef")]
    assert any(event["event_type"] == "switch_mode" for event in events)
    assert callback.message.answers[0]["reply_markup"] == "menu"
    assert callback.message.answers[1]["reply_markup"] == "remind-kb"


def test_handle_cmd_reset_cancels_running_job_and_resets_repo() -> None:
    runtime, profile_store, events, unlocked, _special_calls = build_runtime()
    cancel_event = asyncio.Event()

    class FakeTask:
        def __init__(self) -> None:
            self.cancelled = False

        def done(self) -> bool:
            return False

        def cancel(self) -> None:
            self.cancelled = True

    status_task = FakeTask()
    gen_task = FakeTask()
    runtime.image_jobs[3] = {
        "cancel_event": cancel_event,
        "status_task": status_task,
        "gen_task": gen_task,
    }
    message = FakeMessage(3, text="/reset")

    asyncio.run(runtime.handle_cmd_reset(message))

    assert cancel_event.is_set() is True
    assert status_task.cancelled is True
    assert gen_task.cancelled is True
    assert runtime.db_repositories.reset_all_calls == ["user-3"]
    assert unlocked == [3]
    assert profile_store["mode"] == "basic"
    assert events[-1]["event_type"] == "reset"
