"""Central registry for personas (modes).

Single source of truth: PERSONAS list below.

To add a new persona:
  1) create prompts/<module>.py with SYSTEM_PROMPT (and optional IMAGE_STYLE / HARD_REJECT_PHRASES)
  2) add one entry to PERSONAS

To remove a persona:
  1) delete its entry in PERSONAS (and optionally delete prompts/<module>.py)
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PersonaSpec:
    key: str
    title: str                    # UI label
    prompt_module: str            # module inside prompts/, e.g. "basic"
    judge_module: Optional[str] = None  # module inside prompts/, e.g. "judge_whore"
    judge_attr: Optional[str] = None    # attribute name in judge module
    
    premise: str = "Базовый режим."
    
    # LLM runtime params
    model: str = "google/gemini-3-flash-preview"
    temperature: float = 0.75
    max_tokens: int = 750
    frequency_penalty: float = 0.20

# --- MODELS --- #
# cognitivecomputations/dolphin-mistral-24b-venice-edition:free
# nousresearch/hermes-4-70b $0.11/M input tokens $0.38/M output tokens
# nousresearch/hermes-3-llama-3.1-405b $1/M input tokens $1/M output tokens
# x-ai/grok-4 Starting at $3/M input tokens Starting at $15/M output tokens $5/K web search
# x-ai/grok-4.1-fast Starting at $0.20/M input tokens Starting at $0.50/M output tokens $5/K web search
# nousresearch/hermes-3-llama-3.1-70b $0.30/M input tokens $0.30/M output tokens
# nousresearch/hermes-4-70b $0.11/M input tokens $0.38/M output tokens
# anthropic/claude-3.5-sonnet $6/M input tokens $30/M output tokens
# google/gemini-3-flash-preview $0.50/M input tokens $3/M output tokens
# google/gemini-3-flash-preview
# google/gemini-3.1-pro-preview
# 
 
# ---------------------------
# ЕДИНСТВЕННАЯ ТОЧКА РЕДАКТИРОВАНИЯ (добавление/удаление персонажей)
# ---------------------------
PERSONAS: list[PersonaSpec] = [
        PersonaSpec(
        key="oldschool_rep",
        title="🎤 Рэп тексты",
        prompt_module="oldschool_rep",
        premise=(
            "Рэпер старой школы: помогает писать куплеты/припевы, "
            "держит ритм (BPM/слоги), правит рифмы и флоу. "
            "Подрежимы: STREET / STORY (абсурдные истории) / LYRICAL."
        ),
        model="google/gemini-3-flash-preview",
        temperature=0.9,
        max_tokens=900,
        frequency_penalty=0.20,
    ),

    PersonaSpec(
        key="basic",
        premise="Помогаю решить задачу: чётко, структурно, без ролевой игры.",
        title="🧠 ИИ-Помощник",
        prompt_module="basic",
        model="google/gemini-3-flash-preview",
        temperature=0.45,
        max_tokens=600,
        frequency_penalty=0.20,
    ),
    PersonaSpec(
        key="psychologist",
        premise="Психолог: эмпатия, уточняющие вопросы, анализ, упражнения и понятный план действий.",
        title="🧩 Психолог",
        prompt_module="psychologist",
        model="google/gemini-3-flash-preview",
        temperature=0.45,
        max_tokens=600,
        frequency_penalty=0.40,
    ),
    PersonaSpec(
        key="whore",
        premise="Флирт-режим с постепенной эскалацией без цензуры.",
        title="🔥 Шлюшка",
        prompt_module="whore",
        judge_module="judge_whore",
        judge_attr="SYSTEM_PROMPT_JUDGE_WHORE",
        model="x-ai/grok-4.1-fast",
        temperature=0.85,
        max_tokens=520,
        frequency_penalty=0.55,
    ),
    PersonaSpec(
        key="alco",
        premise="Кухонные разговоры под выпивку, философия и подначивание.",
        title="🍺 Собутыльник",
        prompt_module="alco",
        model="google/gemini-3-flash-preview",
        temperature=0.90,
        max_tokens=900,
        frequency_penalty=0.10,
    ),
    PersonaSpec(
        key="coach",
        premise="Тренер: дисциплина, план, прогресс, жёстко, но справедливо.",
        title="🏋️ Тренер-СССР",
        prompt_module="coach",
        model="google/gemini-3-flash-preview",
        temperature=0.65,
        max_tokens=650,
        frequency_penalty=0.30,
    ),

        PersonaSpec(
        key="coach_premium",
        premise=(
            "Премиальный тренер: индивидуальный подход, "
            "глубокое понимание физиологии, техника и восстановление. "
            "Без давления, с фокусом на устойчивый результат."
        ),
        title="💎 Тренер-Premium",
        prompt_module="coach_premium",
        model="google/gemini-3-flash-preview",
        temperature=0.55,
        max_tokens=850,
        frequency_penalty=0.20,
    ),

    PersonaSpec(
        key="oldtimer",
        premise="Помещик XIX века: медленные монологи, сомнения, нравственный поиск, язык эпохи.",
        title="🎩 Помещик XIX века",
        prompt_module="oldtimer",
        model="nousresearch/hermes-4-70b",
        temperature=0.75,
        max_tokens=850,
        frequency_penalty=0.20,
    ),
    PersonaSpec(
        key="communist",
        premise="Коммунист СССР: идеологический тон, советская лексика, жёсткая полемика, серьёзно.",
        title="☭ Коммунист СССР",
        prompt_module="communist",
        model="google/gemini-3-flash-preview",
        temperature=0.70,
        max_tokens=750,
        frequency_penalty=0.20,
    ),
    PersonaSpec(
        key="conspiro",
        premise="Конспиролог-эрудит: версии, сомнения, альтернативные теории. Уверен ли ты в том, что тебе говорят?",
        title="🛸 Конспиролог",
        prompt_module="conspiro",
        model="google/gemini-3-flash-preview",
        temperature=0.75,
        max_tokens=750,
        frequency_penalty=0.20,
    ),
    PersonaSpec(
        key="doctor",
        title="🩺 Доктор",
        prompt_module="doctor",
        premise=(
            "Врач-консультант: помогает понять симптомы и анализы, "
            "подсказывает безопасный план обследований и профилактику. "
            "Без диагнозов и без назначения лечения вместо очного врача."
        ),
        model="google/gemini-3-flash-preview",
        temperature=0.40,
        max_tokens=750,
        frequency_penalty=0.25,
    ),
    PersonaSpec(
        key="pet_behaviorist",
        title="🐾 Кинолог-зоопсихолог",
        prompt_module="pet_behaviorist",
        premise=(
            "Кинолог-зоопсихолог и ветеринар: помогает понять поведение кошек и собак, "
            "даёт план обучения и коррекции поведения, советы по уходу и питанию. "
            "Без назначения лечения и без жестоких методов."
        ),
        model="xiaomi/mimo-v2-flash",
        temperature=0.50,
        max_tokens=900,
        frequency_penalty=0.20,
    ),
        PersonaSpec(
        key="chef",
        title="👨‍🍳 Шеф-повар",
        prompt_module="chef",
        premise="Шеф-повар: рецепты, техника, вкусы, подача. Два формата — быстро или ресторан.",
        model="google/gemini-3-flash-preview",
        temperature=0.55,
        max_tokens=1800,
        frequency_penalty=0.20,
    ),
    PersonaSpec(
        key="financial",
        title="💰 Финансовый консультант",
        prompt_module="financial",
        premise=(
            "Финансовый консультант: бюджет, анализ расходов, подушка, долги, "
            "финансовые цели и инвестиционная стратегия с обязательным разбором рисков."
        ),
        model="google/gemini-3-flash-preview",
        temperature=0.45,
        max_tokens=900,
        frequency_penalty=0.20,
    ),
        PersonaSpec(
        key="brainstorm",
        title="💡 Брейнсторм",
        prompt_module="brainstorm",
        premise=(
            "Критический партнёр по идеям: жёсткий разбор, плюс и минсу, альтернативы, монетизация, "
            "конкуренция, MVP. Фокус на результат, а не на процесс."
        ),
        model="google/gemini-3-flash-preview",
        temperature=0.70,
        max_tokens=850,
        frequency_penalty=0.25,
    ),
        PersonaSpec(
        key="unhinged",
        title="😈 Unhinged",
        prompt_module="unhinged",
        premise="Максимально дикий, vulgar и unpredictable режим без цензуры. Абсурдные истории, taboo NSFW, хаос на лету.",
        model="x-ai/grok-4.1-fast",  # или "x-ai/grok-4-fast" если хочешь дешевле/быстрее
        temperature=1.1,             # высокая для максимального креатива и хаоса
        max_tokens=2000,             # чтобы хватило на длинные безумные истории
        frequency_penalty=0.0,       # 0 = больше повторений и "потока сознания" — усиливает дикость
    ),

]


def _import_prompt_module(name: str):
    return importlib.import_module(f"src.prompts.{name}")


def _require_attr(mod, attr: str):
    if not hasattr(mod, attr):
        raise AttributeError(f"{mod.__name__} is missing required attribute: {attr}")
    return getattr(mod, attr)


# ---------------------------
# Автосборка мап (обратная совместимость с bot_simple_memory4.py)
# ---------------------------
MODE_TO_SYSTEM_PROMPT: dict[str, str] = {}
MODE_TO_IMAGE_STYLE: dict[str, str] = {}
MODE_TO_HARD_REJECT_PHRASES: dict[str, Optional[list[str]]] = {}
MODE_TO_JUDGE_PROMPT: dict[str, Optional[str]] = {}

MODE_TO_PREMISE: dict[str, str] = {p.key: p.premise for p in PERSONAS}

MODE_TO_MODEL: dict[str, str] = {}
MODE_TO_TEMPERATURE: dict[str, float] = {}
MODE_TO_MAX_TOKENS: dict[str, int] = {}
MODE_TO_FREQUENCY_PENALTY: dict[str, float] = {}

# Для клавиатуры в боте (замена MODE_PRESETS)
MODE_CATALOG: list[tuple[str, str]] = []  # (title, key)

for p in PERSONAS:
    mod = _import_prompt_module(p.prompt_module)

    MODE_TO_SYSTEM_PROMPT[p.key] = _require_attr(mod, "SYSTEM_PROMPT")
    MODE_TO_IMAGE_STYLE[p.key] = getattr(mod, "IMAGE_STYLE", "")

    # HARD_REJECT_PHRASES — нужен сейчас только для whore, но механизм общий
    if hasattr(mod, "HARD_REJECT_PHRASES"):
        MODE_TO_HARD_REJECT_PHRASES[p.key] = getattr(mod, "HARD_REJECT_PHRASES")

    # Judge prompt (опционально)
    if p.judge_module and p.judge_attr:
        jmod = _import_prompt_module(p.judge_module)
        MODE_TO_JUDGE_PROMPT[p.key] = getattr(jmod, p.judge_attr, None)

    # Runtime params
    MODE_TO_MODEL[p.key] = p.model
    MODE_TO_TEMPERATURE[p.key] = p.temperature
    MODE_TO_MAX_TOKENS[p.key] = p.max_tokens
    MODE_TO_FREQUENCY_PENALTY[p.key] = p.frequency_penalty

    MODE_CATALOG.append((p.title, p.key))

# ---------------------------
# UI: короткое описание персонажа/режима (для сообщения при переключении)
# ---------------------------
MODE_TO_SHORT_DESC: dict[str, str] = {p.key: p.premise for p in PERSONAS}
