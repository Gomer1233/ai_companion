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
    model: str = "google/gemini-2.5-flash-preview-09-2025"
    temperature: float = 0.75
    max_tokens: int = 750
    frequency_penalty: float = 0.20

# --- MODELS --- #
# cognitivecomputations/dolphin-mistral-24b-venice-edition:free
# nousresearch/hermes-4-70b $0.11/M input tokens $0.38/M output tokens
# nousresearch/deephermes-3-mistral-24b-preview $0.02/M input tokens $0.10/M output tokens
# nousresearch/hermes-3-llama-3.1-405b $1/M input tokens $1/M output tokens
# x-ai/grok-4 Starting at $3/M input tokens Starting at $15/M output tokens $5/K web search
# x-ai/grok-4.1-fast Starting at $0.20/M input tokens Starting at $0.50/M output tokens $5/K web search
# nousresearch/hermes-3-llama-3.1-70b $0.30/M input tokens $0.30/M output tokens
# nousresearch/deephermes-3-mistral-24b-preview $0.02/M input tokens $0.10/M output tokens
# nousresearch/hermes-4-70b $0.11/M input tokens $0.38/M output tokens
# anthropic/claude-3.5-sonnet $6/M input tokens $30/M output tokens
 
# ---------------------------
# ЕДИНСТВЕННАЯ ТОЧКА РЕДАКТИРОВАНИЯ (добавление/удаление персонажей)
# ---------------------------
PERSONAS: list[PersonaSpec] = [
    
    PersonaSpec(
        key="whore",
        premise="Флирт-режим с постепенной эскалацией без цензуры.",
        title="🔥 Шлюшка",
        prompt_module="whore",
        judge_module="judge_whore",
        judge_attr="SYSTEM_PROMPT_JUDGE_WHORE",
        model="nousresearch/hermes-3-llama-3.1-70b",
        temperature=0.85,
        max_tokens=520,
        frequency_penalty=0.55,
    ),
    
]


def _import_prompt_module(name: str):
    return importlib.import_module(f"prompts.{name}")


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
