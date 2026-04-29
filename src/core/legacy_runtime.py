from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Mapping

from src.core.runtime_helpers import maybe_await


@dataclass(slots=True)
class LegacySharedRuntime:
    db_path: str
    db_repositories: Any
    image_jobs: Dict[int, Dict[str, Any]]
    main_menu: Any
    mode_to_system_prompt: Mapping[str, str]
    mode_to_short_desc: Mapping[str, str]
    get_user_profile: Callable[[int], Dict[str, Any]]
    set_user_profile: Callable[..., None]
    get_photo_gate: Callable[[int], Dict[str, int]]
    upsert_photo_gate: Callable[..., None]
    log_user_event: Callable[..., None]
    unlock_chat: Callable[[int], None]
    repo_refs: Callable[[int], tuple[Any, Any]]
    menu_for: Callable[[Dict[str, Any]], Any]
    build_modes_keyboard: Callable[[int, str | None], Any]
    mark_mode_picked: Callable[[int, str], None]
    remind_context_keyboard_factory: Callable[[], Any]
    special_mode_switch_handler: (
        Callable[[int, str, str, Any, Dict[str, Any], Any], Awaitable[bool] | bool] | None
    ) = None
    extra_reset_mode: Callable[[int, str], None] | None = None
    extra_reset_user_all: Callable[[int], None] | None = None

    async def handle_reset_current_mode(
        self,
        user_id: int,
        mode: str,
        *,
        note: str,
        chat_id: int,
        username: str,
        first_name: str,
        message_id: int,
        text_len: int,
    ) -> str:
        now_ts = int(time.time())
        self.log_user_event(
            ts=now_ts,
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            event_type="reset",
            mode=mode,
            message_id=message_id,
            text_len=text_len,
            ok=1,
            note=note,
        )

        user_ref, conversation_ref = self.repo_refs(user_id)
        self.db_repositories.reset_mode_in_conversation(user_ref, conversation_ref, mode)
        if self.extra_reset_mode is not None:
            self.extra_reset_mode(user_id, mode)
        return mode

    async def handle_want_photo_request(self, message: Any) -> None:
        user_id = message.from_user.id
        profile = self.get_user_profile(user_id)
        now_ts = int(time.time())
        self.log_user_event(
            ts=now_ts,
            user_id=user_id,
            chat_id=int(message.chat.id) if message.chat else 0,
            username=(message.from_user.username or ""),
            first_name=(message.from_user.first_name or ""),
            event_type="photo_button",
            mode=(profile.get("mode") or "basic").strip(),
            message_id=int(message.message_id),
            text_len=len(message.text or ""),
            ok=1,
        )

        if int(profile.get("mode_picked") or "0") != 1:
            await message.answer(
                "\u0421\u043d\u0430\u0447\u0430\u043b\u0430 \u0432\u044b\u0431\u0435\u0440\u0438 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u0436\u0430: \u043d\u0430\u0436\u043c\u0438 \u00ab\u0420\u0435\u0436\u0438\u043c\u00bb.",
                reply_markup=self.main_menu,
            )
            return

        now = int(time.time())
        gate = self.get_photo_gate(user_id)
        cooldown_until = int(gate.get("image_cooldown_until_ts") or 0)
        if cooldown_until > now:
            left = cooldown_until - now
            await message.answer(
                f"\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0430\u044f \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u0431\u0443\u0434\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u0447\u0435\u0440\u0435\u0437 {left // 60 + 1} \u043c\u0438\u043d."
            )
            return

        self.upsert_photo_gate(
            user_id=user_id,
            score=gate["score"],
            attempts=gate["attempts"],
            last_ask_ts=now,
            cooldown_until_ts=gate["cooldown_until_ts"],
            awaiting_context=gate["awaiting_context"],
            context_asked_ts=gate["context_asked_ts"],
            awaiting_image_prompt=1,
            image_cooldown_until_ts=cooldown_until,
        )
        await message.answer("\u041e\u043a. \u041d\u0430\u043f\u0438\u0448\u0438 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435: \u0447\u0442\u043e \u0438\u043c\u0435\u043d\u043d\u043e \u0441\u0433\u0435\u043d\u0435\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c?")

    async def handle_cmd_mode(self, message: Any) -> None:
        user_id = message.from_user.id
        profile = self.get_user_profile(user_id)
        current = profile.get("mode") or "basic"
        keyboard = self.build_modes_keyboard(user_id, current)
        await message.answer(
            f"\u0422\u0435\u043a\u0443\u0449\u0438\u0439 \u0440\u0435\u0436\u0438\u043c: `{current}`\n"
            "\u0412\u044b\u0431\u0435\u0440\u0438 \u0440\u0435\u0436\u0438\u043c \u043a\u043d\u043e\u043f\u043a\u043e\u0439 \u043d\u0438\u0436\u0435.\n\n"
            "\u21a9\ufe0f \u2014 \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c   \ud83c\udd95 \u2014 \u043d\u0430\u0447\u0430\u0442\u044c \u0437\u0430\u043d\u043e\u0432\u043e",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    async def handle_set_mode_callback(self, callback: Any) -> None:
        user_id = callback.from_user.id
        prev_profile = self.get_user_profile(user_id)
        prev_mode = (prev_profile.get("mode") or "").strip()
        mode = callback.data.split(":", 1)[1].strip()

        if mode not in self.mode_to_system_prompt:
            await callback.answer("\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u044b\u0439 \u0440\u0435\u0436\u0438\u043c", show_alert=True)
            return

        self.set_user_profile(user_id, mode=mode)
        self.mark_mode_picked(user_id, mode)

        now_ts = int(time.time())
        self.log_user_event(
            ts=now_ts,
            user_id=user_id,
            chat_id=int(callback.message.chat.id) if callback.message and callback.message.chat else 0,
            username=(callback.from_user.username or ""),
            first_name=(callback.from_user.first_name or ""),
            event_type="switch_mode",
            mode=mode,
            mode_from=prev_mode,
            mode_to=mode,
            message_id=int(callback.message.message_id) if callback.message else 0,
            text_len=0,
            ok=1,
        )

        await callback.answer("\u0420\u0435\u0436\u0438\u043c \u0443\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d")
        profile = self.get_user_profile(user_id)
        menu = self.menu_for(profile)

        if self.special_mode_switch_handler is not None:
            handled = await maybe_await(
                self.special_mode_switch_handler(user_id, prev_mode, mode, callback, profile, menu)
            )
            if handled:
                return

        desc = (self.mode_to_short_desc.get(mode) or "").strip()
        text = f"\u041e\u043a. \u0420\u0435\u0436\u0438\u043c \u0442\u0435\u043f\u0435\u0440\u044c: `{mode}`"
        if desc:
            text += f"\n_{desc}_"
        text += "\n\n\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0430\u0435\u043c \u0441 \u043f\u0440\u0435\u0436\u043d\u0435\u0433\u043e \u043c\u0435\u0441\u0442\u0430."

        await callback.message.answer(text, parse_mode="Markdown", reply_markup=menu)
        await callback.message.answer(
            "\u0415\u0441\u043b\u0438 \u043f\u0435\u0440\u0435\u043a\u043b\u044e\u0447\u0430\u043b\u0441\u044f \u0438 \u043f\u043e\u0442\u0435\u0440\u044f\u043b \u043d\u0438\u0442\u044c \u2014 \u043d\u0430\u0436\u043c\u0438 \u043a\u043d\u043e\u043f\u043a\u0443 \u043d\u0438\u0436\u0435.",
            reply_markup=self.remind_context_keyboard_factory(),
        )

    async def handle_cmd_reset(self, message: Any) -> None:
        user_id = message.from_user.id
        prev_profile = self.get_user_profile(user_id)
        prev_mode = (prev_profile.get("mode") or "basic").strip()

        self.log_user_event(
            ts=int(time.time()),
            user_id=user_id,
            chat_id=int(message.chat.id) if message.chat else 0,
            username=(message.from_user.username or ""),
            first_name=(message.from_user.first_name or ""),
            event_type="reset",
            mode="basic",
            mode_from=prev_mode,
            mode_to="basic",
            message_id=int(message.message_id),
            text_len=len(message.text or ""),
            ok=1,
            note="scope=all",
        )

        self.unlock_chat(user_id)
        job = self.image_jobs.pop(user_id, None)
        if job:
            cancel_event = job.get("cancel_event")
            if cancel_event and not cancel_event.is_set():
                cancel_event.set()

            status_task = job.get("status_task")
            if status_task and not status_task.done():
                status_task.cancel()

            gen_task = job.get("gen_task")
            if gen_task and not gen_task.done():
                gen_task.cancel()

        self.set_user_profile(user_id, mode="basic")
        user_ref, _conversation_ref = self.repo_refs(user_id)
        self.db_repositories.reset_user_all(user_ref)
        if self.extra_reset_user_all is not None:
            self.extra_reset_user_all(user_id)

        await message.answer(
            "\u0421\u0431\u0440\u043e\u0441 \u0441\u0434\u0435\u043b\u0430\u043b.\n\u0420\u0435\u0436\u0438\u043c: `basic`\n\u0418\u0441\u0442\u043e\u0440\u0438\u044f \u043e\u0447\u0438\u0449\u0435\u043d\u0430.",
            parse_mode="Markdown",
            reply_markup=self.main_menu,
        )
