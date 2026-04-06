from prompts import basic
from prompts import whore
from prompts import judge_whore
from prompts import alco
from prompts import coach
from prompts import oldtimer
from prompts import psychologist
from prompts import communist
from prompts import conspiro


MODE_TO_SYSTEM_PROMPT = {
    "basic": basic.SYSTEM_PROMPT,
    "psychologist": psychologist.SYSTEM_PROMPT,
    "whore": whore.SYSTEM_PROMPT,
    "alco": alco.SYSTEM_PROMPT,
    "coach": coach.SYSTEM_PROMPT,
    "oldtimer": oldtimer.SYSTEM_PROMPT,
    "communist": communist.SYSTEM_PROMPT,
    "conspiro": conspiro.SYSTEM_PROMPT,
}

MODE_TO_IMAGE_STYLE = {
    "basic": getattr(basic, "IMAGE_STYLE", ""),
    "whore": getattr(whore, "IMAGE_STYLE", ""),
    "alco": getattr(alco, "IMAGE_STYLE", ""),
    "coach": getattr(coach, "IMAGE_STYLE", ""),
    "oldtimer": getattr(oldtimer, "IMAGE_STYLE", ""),
    "psychologist": getattr(psychologist, "IMAGE_STYLE", ""),
    "communist": getattr(communist, "IMAGE_STYLE", ""),
    "conspiro": getattr(conspiro, "IMAGE_STYLE", ""),
}


# Персонаж-специфичное (опционально)
MODE_TO_HARD_REJECT_PHRASES = {
    "whore": getattr(whore, "HARD_REJECT_PHRASES", None),
}

MODE_TO_JUDGE_PROMPT = {
    "whore": getattr(judge_whore, "SYSTEM_PROMPT_JUDGE_WHORE", None),
}

# Модели/параметры — оставляем тут, чтобы bot-файл был “тонким”
MODE_TO_MODEL = {
    "basic": "google/gemini-3-flash-preview",
    "alco": "google/gemini-2.5-flash-preview-09-2025",
    "whore": "google/gemini-2.5-flash-preview-09-2025",
    "coach": "google/gemini-2.5-flash-preview-09-2025",
    "oldtimer": "google/gemini-2.5-flash-preview-09-2025",
    "communist": "google/gemini-2.5-flash-preview-09-2025",
    "psychologist": "google/gemini-3-flash-preview",
    "conspiro": "google/gemini-2.5-flash-preview-09-2025",
}

# x-ai/grok-4.1-fast
# deepseek/deepseek-r1-0528
# deepseek/deepseek-v3.2
# deepseek/deepseek-chat-v3-0324
# google/gemini-2.5-flash-lite-preview-09-2025
# google/gemini-3-flash-preview

MODE_TO_TEMPERATURE = {
    "basic": 0.45,
    "psychologist": 0.45,
    "coach": 0.65,
    "communist": 0.70,
    "oldtimer": 0.75,
    "whore": 0.85,
    "alco": 0.90,
    "conspiro": 0.75,
}

MODE_TO_MAX_TOKENS = {
    "basic": 600,
    "psychologist": 600,
    "coach": 650,
    "communist": 750,
    "oldtimer": 850,
    "whore": 520,
    "alco": 900,
    "conspiro": 750,
}

MODE_TO_FREQUENCY_PENALTY = {
    "basic": 0.20,
    "psychologist": 0.40,
    "coach": 0.30,
    "communist": 0.20,
    "oldtimer": 0.20,
    "whore": 0.55,
    "alco": 0.10,
    "conspiro": 0.20,
}
