from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

IMAGE_FUN_PHRASES = [
    "Анализирую композицию…",
    "Ищу лучшую позу для кадра…",
    "Проверяю, не убежал ли стиль…",
    "Уточняю художественное намерение…",
    "Формирую финальный визуальный замысел…",
    "Сверяю результат с внутренним вкусом…",
    "Навожу последний визуальный лоск…",
    "Собираю финальный образ…",
    "Проверяю картинку на соответствие реальности…",
]

IMAGE_FUN_EMOJIS = [
    "🎲", "🧩", "⚙️", "🔮", "🫧", "✨", "🧪", "📐", "📊",
    "🧠", "🎛️", "🪄", "🌀", "🧿", "🎯", "📎", "🔧",
]

IMAGE_FUN_VISIBLE_SEC = 2.0
DUST_FADE_CHARS = ["·", "⋅", "•", "✧"]


@dataclass
class ImageJobHandle:
    cancel_event: asyncio.Event
    status_task: asyncio.Task[Any] | None = None
    gen_task: asyncio.Future[bytes] | None = None


@dataclass(frozen=True)
class ImageRuntimeHooks:
    get_user_profile: Callable[[int], dict[str, Any]]
    upsert_photo_gate: Callable[..., Any]
    log_user_event: Callable[..., Any]
    image_analytics_context: Callable[[], tuple[str, str]]
    generate_image_backend: Callable[[str], Awaitable[bytes]]


class ImageJobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[int, ImageJobHandle] = {}

    def get(self, user_id: int) -> ImageJobHandle | None:
        return self._jobs.get(user_id)

    def is_active(self, user_id: int) -> bool:
        job = self.get(user_id)
        return bool(job and not job.cancel_event.is_set())

    def start(self, user_id: int) -> ImageJobHandle:
        handle = ImageJobHandle(cancel_event=asyncio.Event())
        self._jobs[user_id] = handle
        return handle

    def clear(self, user_id: int) -> None:
        self._jobs.pop(user_id, None)

    async def cancel(self, user_id: int) -> bool:
        job = self.get(user_id)
        if not job:
            return False
        job.cancel_event.set()
        if job.status_task and not job.status_task.done():
            job.status_task.cancel()
        if job.gen_task and not job.gen_task.done():
            job.gen_task.cancel()
        return True


def image_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⛔ Отмена", callback_data="imgcancel")]]
    )


def make_dust_frame(count: int) -> str:
    if count <= 0:
        return "\u200b"

    parts = []
    for _ in range(count):
        parts.append(random.choice(DUST_FADE_CHARS))
        parts.append(" " * random.randint(1, 3))

    return "".join(parts).rstrip()


async def fade_out_text(bot: Bot, chat_id: int, message_id: int) -> bool:
    start = random.randint(5, 7)

    for n in range(start, -1, -1):
        frame = make_dust_frame(n)
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=frame,
                reply_markup=None,
            )
        except Exception as exc:  # pragma: no cover - aiogram/telegram-specific
            if "message is not modified" in str(exc).lower():
                await asyncio.sleep(0.06)
                continue
            return False

        await asyncio.sleep(0.10)

    return True


def render_fun_phrase_only() -> str:
    emoji = random.choice(IMAGE_FUN_EMOJIS)
    if random.random() < 0.25:
        emoji += random.choice(IMAGE_FUN_EMOJIS)
    phrase = random.choice(IMAGE_FUN_PHRASES)
    return f"{emoji} {phrase}"


async def run_image_fun_only_loop(bot: Bot, chat_id: int, cancel_event: asyncio.Event) -> None:
    try:
        while not cancel_event.is_set():
            try:
                msg = await bot.send_message(chat_id, render_fun_phrase_only())
            except Exception:
                return

            await asyncio.sleep(IMAGE_FUN_VISIBLE_SEC)
            if cancel_event.is_set():
                try:
                    await bot.delete_message(chat_id, msg.message_id)
                except Exception:
                    pass
                return

            try:
                await fade_out_text(bot, chat_id, msg.message_id)
            except Exception:
                pass
            try:
                await bot.delete_message(chat_id, msg.message_id)
            except Exception:
                pass
    except asyncio.CancelledError:
        return


async def handle_awaiting_image_prompt(
    *,
    bot: Bot,
    message: Any,
    user_id: int,
    user_text: str,
    now: int,
    photo_gate: dict[str, Any],
    image_cooldown_sec: int,
    mode_to_image_style: Mapping[str, str],
    jobs: ImageJobRegistry,
    hooks: ImageRuntimeHooks,
) -> bool:
    if int(photo_gate.get("awaiting_image_prompt") or 0) != 1:
        return False

    cd_until = int(photo_gate.get("image_cooldown_until_ts") or 0)
    if cd_until > now:
        left = cd_until - now
        await message.answer(f"Кулдаун. Подожди ещё {left // 60 + 1} мин.")
        return True

    hooks.upsert_photo_gate(
        user_id=user_id,
        score=photo_gate["score"],
        attempts=photo_gate["attempts"],
        last_ask_ts=now,
        cooldown_until_ts=photo_gate["cooldown_until_ts"],
        awaiting_context=photo_gate["awaiting_context"],
        context_asked_ts=photo_gate["context_asked_ts"],
        awaiting_image_prompt=0,
        image_cooldown_until_ts=photo_gate.get("image_cooldown_until_ts", 0),
    )
    photo_gate["awaiting_image_prompt"] = 0

    job = jobs.start(user_id)
    job.status_task = asyncio.create_task(run_image_fun_only_loop(bot, message.chat.id, job.cancel_event))

    profile = hooks.get_user_profile(user_id)
    mode = (profile.get("mode") or "basic").strip()
    style_hint = mode_to_image_style.get(mode, mode_to_image_style["basic"])
    image_prompt = f"Стиль/арт-дирекшн: {style_hint}\nЗапрос пользователя: {user_text}"
    provider, model = hooks.image_analytics_context()

    hooks.log_user_event(
        ts=now,
        user_id=user_id,
        chat_id=int(message.chat.id) if message.chat else 0,
        username=(message.from_user.username or ""),
        first_name=(message.from_user.first_name or ""),
        event_type="photo_request",
        mode=mode,
        message_id=int(message.message_id),
        text_len=len(user_text),
        photo_provider=provider,
        photo_model=model,
        ok=1,
    )

    job.gen_task = asyncio.ensure_future(hooks.generate_image_backend(image_prompt))

    try:
        img_bytes = await job.gen_task
    except asyncio.CancelledError:
        await jobs.cancel(user_id)
        jobs.clear(user_id)
        hooks.log_user_event(
            ts=int(time.time()),
            user_id=user_id,
            chat_id=int(message.chat.id) if message.chat else 0,
            username=(message.from_user.username or ""),
            first_name=(message.from_user.first_name or ""),
            event_type="photo_result",
            mode=mode,
            message_id=int(message.message_id),
            text_len=len(user_text),
            photo_provider=provider,
            photo_model=model,
            ok=0,
            note="cancelled",
        )
        return True
    except Exception as exc:
        logging.exception("Image generation failed (provider=%s user_id=%s): %s", provider, user_id, exc)
        await jobs.cancel(user_id)
        jobs.clear(user_id)
        hooks.log_user_event(
            ts=int(time.time()),
            user_id=user_id,
            chat_id=int(message.chat.id) if message.chat else 0,
            username=(message.from_user.username or ""),
            first_name=(message.from_user.first_name or ""),
            event_type="photo_result",
            mode=mode,
            message_id=int(message.message_id),
            text_len=len(user_text),
            photo_provider=provider,
            photo_model=model,
            ok=0,
            note=f"error: {type(exc).__name__}",
        )
        await message.answer("Не получилось сгенерировать картинку. (см. лог ошибок)")
        return True

    await jobs.cancel(user_id)
    jobs.clear(user_id)
    await message.answer_photo(BufferedInputFile(img_bytes, filename="image.png"))

    hooks.log_user_event(
        ts=int(time.time()),
        user_id=user_id,
        chat_id=int(message.chat.id) if message.chat else 0,
        username=(message.from_user.username or ""),
        first_name=(message.from_user.first_name or ""),
        event_type="photo_result",
        mode=mode,
        message_id=int(message.message_id),
        text_len=len(user_text),
        photo_provider=provider,
        photo_model=model,
        ok=1,
        note="success",
    )

    hooks.upsert_photo_gate(
        user_id=user_id,
        score=photo_gate["score"],
        attempts=photo_gate["attempts"],
        last_ask_ts=now,
        cooldown_until_ts=photo_gate["cooldown_until_ts"],
        awaiting_context=photo_gate["awaiting_context"],
        context_asked_ts=photo_gate["context_asked_ts"],
        awaiting_image_prompt=0,
        image_cooldown_until_ts=now + image_cooldown_sec,
    )
    return True


async def handle_image_cancel_callback(callback: Any, jobs: ImageJobRegistry) -> None:
    user_id = callback.from_user.id
    cancelled = await jobs.cancel(user_id)
    if not cancelled:
        await callback.answer("Нечего отменять", show_alert=False)
        return

    try:
        await callback.message.edit_text("⛔ Ок, отменил генерацию.", reply_markup=None)
    except Exception:
        pass

    await callback.answer("Отменено")
