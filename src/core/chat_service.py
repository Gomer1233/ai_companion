from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List

from src.config.modes import MODE_TO_FREQUENCY_PENALTY, MODE_TO_MAX_TOKENS, MODE_TO_TEMPERATURE
from src.core.runtime_helpers import (
    estimate_tokens,
    fix_truncated_reply,
    is_truncated_for_glue,
    strip_internal_thoughts,
    strip_scene_contract,
)
from src.prompts.oldschool_rep import RAP_SUBMODE_DEFAULT_BPM, RAP_SUBMODE_PROMPTS

_GAME_OVER_RE = re.compile(
    r"""
    \[\[?\s*            # [ or [[
    G(?:A|4)M(?:E|3)?\s*   # GAME / G4ME / GME
    OVE?R\s*            # OVER / OVR / опечатки
    \]?\]               # ] или ]]
    """,
    re.IGNORECASE | re.VERBOSE,
)

AUDIO_SYSTEM_PROMPT = """
Ты говоришь голосом.
Отвечай кратко: 2–4 предложения.
Без списков.
Без длинных объяснений.
Разговорный стиль, как живой человек.
Паузы и эмоции допустимы, но без воды.
Говори так, будто записываешь короткое голосовое сообщение в мессенджере.
"""

MAX_AUTO_CONTINUATIONS = int(os.getenv("MAX_AUTO_CONTINUATIONS", "2"))
CONTINUE_PROMPT = (
    "Продолжи предыдущий ответ ровно с места обрыва. "
    "Не повторяй уже сказанное. "
    "НЕ извиняйся и НЕ упоминай, что ответ был прерван. "
    "Просто продолжай по делу и закончи логично."
)


@dataclass(frozen=True)
class ChatCompletionResult:
    reply: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    tokens_source: str


def strip_game_over_markers(text: str) -> tuple[str, bool]:
    if not text:
        return text, False
    cleaned, n = _GAME_OVER_RE.subn("", text)
    return cleaned.strip(), (n > 0)


def format_state_block(state: Dict[str, Any]) -> str:
    cast = state.get("cast") or []
    timeline = state.get("timeline") or []
    threads = state.get("open_threads") or []

    cast_lines = []
    for p in cast[:8]:
        name = (p.get("name") or "").strip()
        role = (p.get("role") or "").strip()
        notes = (p.get("notes") or "").strip()
        if not name:
            continue
        line = f"- {name} ({role})" if role else f"- {name}"
        if notes:
            line += f": {notes}"
        cast_lines.append(line)

    tl_lines = [f"- {x}" for x in timeline[-8:]]
    th_lines = [f"- {x}" for x in threads[:8]]

    return (
        "\n\n[Состояние сюжета]\n"
        f"Сезон: {state.get('season', 1)} | Эпизод: {state.get('episode', 1)}\n"
        f"Локация: {state.get('location', '')}\n"
        f"Завязка: {state.get('premise', '')}\n"
        "Персонажи:\n" + ("\n".join(cast_lines) if cast_lines else "- (пока нет)") + "\n"
        "Хронология (последнее):\n" + ("\n".join(tl_lines) if tl_lines else "- (пока нет)") + "\n"
        "Открытые нити:\n" + ("\n".join(th_lines) if th_lines else "- (пока нет)") + "\n"
        f"Кратко сейчас: {state.get('recap', '')}\n"
    )


def is_audio_request(text: str) -> bool:
    t = (text or "").lower()
    triggers = [
        "запиши аудио",
        "запиши мне аудио",
        "голосом",
        "озвучь",
        "сделай аудиосообщение",
        "сделай голосовое",
        "голосовое сообщение",
        "аудио-сообщение",
        "аудиосообщение",
    ]
    return any(x in t for x in triggers)


def build_system_prompt(*, mode: str, state: Dict[str, Any], base_prompt: str, audio_only: bool) -> str:
    base = AUDIO_SYSTEM_PROMPT if (audio_only and mode != "whore") else base_prompt
    memory_block = format_state_block(state)

    chef_addon = ""
    if mode == "chef":
        sub = (state.get("chef_submode") or "").strip()
        if sub == "restaurant":
            chef_addon = (
                "\n\n[CHEF_SUBMODE=RESTAURANT]\n"
                "РАБОТАЙ СТРОГО В ДВЕ ФАЗЫ.\n"
                "КЛЮЧЕВОЕ ПРАВИЛО: СНАЧАЛА КОЛИЧЕСТВА, ПОТОМ ТЕХНИКА.\n\n"
                "ФАЗА 1 — ПРОЕКТИРОВАНИЕ:\n"
                "- Уточни количество порций.\n"
                "- Уточни или предложи ТОЧНЫЕ КОЛИЧЕСТВА основных ингредиентов.\n"
                "- ЯВНО пропиши объёмы: граммы, миллилитры, штуки.\n"
                "- Перечисли дополнительные ингредиенты и специи С КОЛИЧЕСТВАМИ.\n"
                "- НЕ ДАВАЙ рецепт, шаги или технику.\n"
                "- Заверши вопросом подтверждения состава и количеств.\n\n"
                "ФАЗА 2 — ИСПОЛНЕНИЕ (ПОСЛЕ ПОДТВЕРЖДЕНИЯ):\n"
                "- Дай полный рецепт с объяснением техники.\n"
                "- Все ингредиенты — с точными количествами.\n"
                "- Укажи контроль готовности и подачу.\n\n"
                "СТРОГО ЗАПРЕЩЕНО:\n"
                "- Начинать готовку без фиксации количеств.\n"
                "- Описывать блюдо без указания граммовок.\n"
            )
        else:
            chef_addon = (
                "\n\n[CHEF_SUBMODE=HOME_FAST]\n"
                "РАБОТАЙ В ДВЕ ФАЗЫ.\n"
                "КЛЮЧЕВОЕ ПРАВИЛО: СНАЧАЛА КОЛИЧЕСТВА, ПОТОМ РЕЦЕПТ.\n\n"
                "ФАЗА 1 — БЫСТРОЕ ПРОЕКТИРОВАНИЕ:\n"
                "- Уточни, НА СКОЛЬКО ПОРЦИЙ готовим.\n"
                "- Уточни или предложи КОЛИЧЕСТВА основных ингредиентов (в граммах/штуках).\n"
                "- Если пользователь не указал объёмы — предложи стандартные.\n"
                "- Чётко перечисли, что ЕЩЁ понадобится и в каком количестве.\n"
                "- НЕ ДАВАЙ шаги готовки.\n"
                "- Заверши вопросом подтверждения количеств.\n\n"
                "ФАЗА 2 — БЫСТРОЕ ИСПОЛНЕНИЕ (ПОСЛЕ ПОДТВЕРЖДЕНИЯ):\n"
                "- Дай короткий рецепт.\n"
                "- Формат:\n"
                "  • Ингредиенты с точными количествами\n"
                "  • Шаги (до 6, по 1 строке)\n"
                "  • Готово, когда (1 строка)\n\n"
                "ЗАПРЕЩЕНО:\n"
                "- Давать рецепт без указания количеств.\n"
                "- Использовать формулировки «по вкусу» для базовых ингредиентов.\n"
            )

    rap_addon = ""
    if mode == "oldschool_rep":
        sub = (state.get("rap_submode") or "story").strip().lower()
        if sub not in ("street", "story", "lyrical"):
            sub = "story"
        submode_prompt = RAP_SUBMODE_PROMPTS.get(sub, RAP_SUBMODE_PROMPTS["story"])
        default_bpm = RAP_SUBMODE_DEFAULT_BPM.get(sub, 88)
        rap_addon = f"""

        {submode_prompt}

        BPM по умолчанию: {default_bpm}
        Если пользователь указал BPM явно — используй его.

        ВАЖНО:
        - Если пользователь указал "2 куплета" / "два куплета" — СРАЗУ пиши 2 куплета (без доп. вопросов).
        - Не задавай уточняющих вопросов о формате, если формат уже выбран.
        - Выводи только текст трека (без объяснений).

        """

    return base + memory_block + chef_addon + rap_addon


def build_chat_messages(*, system_prompt: str, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"role": "system", "content": system_prompt}] + history


async def generate_chat_completion(
    *,
    mode: str,
    model: str,
    messages: List[Dict[str, Any]],
    call_openrouter_with_meta: Callable[..., Awaitable[tuple[str, str, Dict[str, Any]]]],
) -> ChatCompletionResult:
    temperature = float(MODE_TO_TEMPERATURE.get(mode, MODE_TO_TEMPERATURE["basic"]))
    max_tokens = int(MODE_TO_MAX_TOKENS.get(mode, MODE_TO_MAX_TOKENS.get("basic", 600)))
    freq_pen = float(MODE_TO_FREQUENCY_PENALTY.get(mode, MODE_TO_FREQUENCY_PENALTY.get("basic", 0.2)))

    if mode == "unhinged":
        temperature = 1.3
        max_tokens = 1000
        freq_pen = 0.0

    prompt_tokens_sum = 0
    completion_tokens_sum = 0
    total_tokens_sum = 0
    tokens_source = ""

    reply_raw, finish_reason, usage = await call_openrouter_with_meta(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        frequency_penalty=freq_pen,
        timeout_s=90.0,
    )

    pt = int((usage or {}).get("prompt_tokens") or 0)
    ct = int((usage or {}).get("completion_tokens") or 0)
    tt = int((usage or {}).get("total_tokens") or 0)
    prompt_tokens_sum += pt
    completion_tokens_sum += ct
    total_tokens_sum += tt
    if tt > 0:
        tokens_source = "api"

    reply_raw = strip_scene_contract(strip_internal_thoughts(reply_raw))
    glued = reply_raw
    cont_round = 0

    while cont_round < MAX_AUTO_CONTINUATIONS and is_truncated_for_glue(glued, finish_reason):
        cont_round += 1
        cont_messages = messages + [{"role": "assistant", "content": glued}] + [{"role": "user", "content": CONTINUE_PROMPT}]
        cont_text, cont_finish, cont_usage = await call_openrouter_with_meta(
            model=model,
            messages=cont_messages,
            temperature=temperature,
            max_tokens=max(220, int(max_tokens * 0.7)),
            frequency_penalty=freq_pen,
            timeout_s=90.0,
        )

        pt = int((cont_usage or {}).get("prompt_tokens") or 0)
        ct = int((cont_usage or {}).get("completion_tokens") or 0)
        tt = int((cont_usage or {}).get("total_tokens") or 0)
        prompt_tokens_sum += pt
        completion_tokens_sum += ct
        total_tokens_sum += tt
        if tt > 0:
            tokens_source = "api"

        cont_text = strip_scene_contract(strip_internal_thoughts(cont_text))
        if not (cont_text or "").strip():
            finish_reason = cont_finish
            break

        glued = (glued.rstrip() + "\n" + cont_text.lstrip()).strip()
        finish_reason = cont_finish

    reply = fix_truncated_reply(strip_scene_contract(strip_internal_thoughts(fix_truncated_reply(glued))))

    if total_tokens_sum <= 0:
        completion_tokens_sum = estimate_tokens(reply, model=model)
        prompt_tokens_sum = 0
        total_tokens_sum = completion_tokens_sum
        tokens_source = "tiktoken" if completion_tokens_sum > 0 else ""

    return ChatCompletionResult(
        reply=reply,
        prompt_tokens=prompt_tokens_sum,
        completion_tokens=completion_tokens_sum,
        total_tokens=total_tokens_sum,
        tokens_source=tokens_source,
    )


def update_story_state(*, state: Dict[str, Any], user_text: str, reply: str) -> Dict[str, Any]:
    updated = dict(state)
    updated["episode"] = int(updated.get("episode", 1)) + 1

    recap = reply.strip().replace("\n", " ")
    if len(recap) > 240:
        recap = recap[:240].rsplit(" ", 1)[0] + "…"
    updated["recap"] = recap

    tl = list(updated.get("timeline") or [])
    user_line = user_text.strip().replace("\n", " ")
    if len(user_line) > 140:
        user_line = user_line[:140].rsplit(" ", 1)[0] + "…"
    tl.append(f"Ход: {user_line}")
    updated["timeline"] = tl[-40:]
    return updated
