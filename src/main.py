from dotenv import load_dotenv
load_dotenv()

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
import time
import asyncio
import logging
import sqlite3
import base64
import random
import json
from typing import Any, Dict, List
from src.config.modes import (
    MODE_TO_SYSTEM_PROMPT,
    MODE_TO_IMAGE_STYLE,
    MODE_TO_SHORT_DESC,
    MODE_TO_MODEL,
    MODE_TO_TEMPERATURE,
    MODE_TO_MAX_TOKENS,
    MODE_TO_FREQUENCY_PENALTY,
    MODE_CATALOG,
    MODE_TO_PREMISE,
)
import httpx
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import BufferedInputFile
from aiogram.types.input_file import FSInputFile

from src.prompts.oldschool_rep import RAP_SUBMODE_PROMPTS, RAP_SUBMODE_DEFAULT_BPM
from src.prompts.relationship import (
    ensure_relationship_table,
    get_relationship_state,
    save_relationship_state,
    reset_relationship_state,
    analyze_user_message,
    update_relationship_from_analysis,
    check_ghosting,
)
from src.prompts.lika_prompt import build_lika_system_prompt
from src.app.settings import Settings
from src.core.runtime_helpers import (
    call_openrouter_with_meta as shared_call_openrouter_with_meta,
    chunk_text,
    estimate_tokens,
    extract_json_object,
    fix_truncated_reply,
    is_truncated_for_glue,
    keep_typing,
    strip_internal_thoughts,
    strip_scene_contract,
)
from src.core.image_service import ImageService
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories, legacy_user_ref

# ----------------------------
# CONFIG
# ----------------------------
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
# ----------------------------
# OpenAI IMAGE (generation)
# ----------------------------
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()
OPENAI_IMAGE_SIZE = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024").strip()
IMAGE_COOLDOWN_SEC = int(os.getenv("IMAGE_COOLDOWN_SEC", "300"))  # 5 minutes

# ----------------------------
# MODELSLAB IMAGE (NSFW)
# ----------------------------
MODELSLAB_API_KEY = os.getenv("MODELSLAB_API_KEY", "").strip()

# text2img endpoint ModelsLab
MODELSLAB_TEXT2IMG_URL = "https://modelslab.com/api/v6/images/text2img"

# ВАЖНО:
# model_id — базовая SDXL-модель
# lora_model — конкретная NSFW-модель
MODELSLAB_MODEL_ID = os.getenv("MODELSLAB_MODEL_ID", "").strip()
MODELSLAB_LORA_MODEL = os.getenv("MODELSLAB_LORA_MODEL", "").strip()

MODELSLAB_WIDTH = int(os.getenv("MODELSLAB_WIDTH", "1024"))
MODELSLAB_HEIGHT = int(os.getenv("MODELSLAB_HEIGHT", "1024"))
MODELSLAB_STEPS = int(os.getenv("MODELSLAB_STEPS", "30"))
MODELSLAB_GUIDANCE = float(os.getenv("MODELSLAB_GUIDANCE", "7.5"))
MODELSLAB_NEGATIVE_PROMPT = os.getenv("MODELSLAB_NEGATIVE_PROMPT", "").strip()
MODELSLAB_SCHEDULER = os.getenv("MODELSLAB_SCHEDULER", "DPMSolverMultistepScheduler").strip()
MODELSLAB_ENHANCE_PROMPT = os.getenv("MODELSLAB_ENHANCE_PROMPT", "0").strip().lower() in ("1", "true", "yes")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts").strip()
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "alloy").strip()
OPENAI_TTS_FORMAT = os.getenv("OPENAI_TTS_FORMAT", "mp3").strip()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()
ELEVENLABS_OUTPUT_FORMAT = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128").strip()
ELEVENLABS_BASE = "https://api.elevenlabs.io"

# ----------------------------
# IMAGE BACKEND SWITCH (single place)
# ----------------------------
# Варианты:
#   - "openai"     -> OpenAI Images API
#   - "openrouter" -> OpenRouter chat/completions with modalities=["image","text"]
#   - "replicate"  -> (заготовка, добавим позже)
IMAGE_BACKEND_PROVIDER = os.getenv("IMAGE_BACKEND_PROVIDER", "openrouter").strip()

# Модель для OpenRouter image (пример: sourceful/riverflow-v2-max-preview)
OPENROUTER_IMAGE_MODEL = os.getenv(
    "OPENROUTER_IMAGE_MODEL",
    "sourceful/riverflow-v2-max-preview"
).strip()

# ----------------------------
# TOGETHER IMAGE (generation)
# ----------------------------
TOG_API_KEY = os.getenv("TOG_API_KEY", "").strip()
TOG_BASE_URL = os.getenv("TOG_BASE_URL", "https://api.together.xyz/v1").strip()
TOG_IMAGE_MODEL = os.getenv("TOG_IMAGE_MODEL", "black-forest-labs/FLUX.1.1-pro").strip()

TOG_WIDTH = int(os.getenv("TOG_WIDTH", "1024"))
TOG_HEIGHT = int(os.getenv("TOG_HEIGHT", "1024"))


PROMPT_TRANSLATION_ENABLED = os.getenv("PROMPT_TRANSLATION_ENABLED", "0").strip() == "1"
PROMPT_TRANSLATION_TARGET_LANG = os.getenv("PROMPT_TRANSLATION_TARGET_LANG", "en").strip()
PROMPT_TRANSLATION_FOR = {s.strip().lower() for s in os.getenv("PROMPT_TRANSLATION_FOR", "modelslab").split(",") if s.strip()}
PROMPT_TRANSLATION_ENGINE = os.getenv("PROMPT_TRANSLATION_ENGINE", "openai").strip().lower()
TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "gpt-4o-mini").strip()

PROMPT_TRANSLATION_DEBUG = os.getenv("PROMPT_TRANSLATION_DEBUG", "0").strip() == "1"

logging.info(
    "TRANSLATION CFG: enabled=%s target=%s for=%s engine=%s model=%s debug=%s OPENAI_API_KEY=%s",
    PROMPT_TRANSLATION_ENABLED,
    PROMPT_TRANSLATION_TARGET_LANG,
    ",".join(sorted(PROMPT_TRANSLATION_FOR)),
    PROMPT_TRANSLATION_ENGINE,
    TRANSLATION_MODEL,
    PROMPT_TRANSLATION_DEBUG,
    "SET" if bool(os.getenv("OPENAI_API_KEY", "").strip()) else "MISSING",
)


if not TELEGRAM_TOKEN:
    raise RuntimeError("Missing env TELEGRAM_TOKEN")

if IMAGE_BACKEND_PROVIDER == "openrouter" and not OPENROUTER_API_KEY:
    raise RuntimeError("Missing env OPENROUTER_API_KEY (needed for IMAGE_BACKEND_PROVIDER=openrouter)")

if IMAGE_BACKEND_PROVIDER == "openai" and not OPENAI_API_KEY:
    raise RuntimeError("Missing env OPENAI_API_KEY (needed for IMAGE_BACKEND_PROVIDER=openai)")

if IMAGE_BACKEND_PROVIDER == "modelslab" and not MODELSLAB_API_KEY:
    raise RuntimeError("Missing env MODELSLAB_API_KEY (needed for IMAGE_BACKEND_PROVIDER=modelslab)")

if IMAGE_BACKEND_PROVIDER == "together" and not TOG_API_KEY:
    raise RuntimeError("Missing env TOG_API_KEY (needed for IMAGE_BACKEND_PROVIDER=together)")

if IMAGE_BACKEND_PROVIDER not in {"openrouter", "openai", "modelslab", "together"}:
    raise RuntimeError(f"Unsupported IMAGE_BACKEND_PROVIDER={IMAGE_BACKEND_PROVIDER}")


OR_TIMEOUT = httpx.Timeout(connect=45.0, read=90.0, write=30.0, pool=15.0)
OR_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=10, keepalive_expiry=30.0)

openrouter_client = httpx.AsyncClient(timeout=OR_TIMEOUT, limits=OR_LIMITS)  # http2 по умолчанию False

# Get project root directory for DB path
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = os.getenv("BOT_DB_PATH", str(PROJECT_ROOT / "bot_state.db"))
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "openai/gpt-4o-mini")

JUDGE_MODEL_WHORE = os.getenv("JUDGE_MODEL_WHORE", "openai/gpt-4o-mini").strip()
JUDGE_MAX_TOKENS = int(os.getenv("JUDGE_MAX_TOKENS", "220"))


# Сколько сообщений хранить (user+assistant вместе). Например 12 = 6 реплик туда-обратно.
HISTORY_LIMIT = int(os.getenv("HISTORY_LIMIT", "12"))

DB_REPOSITORIES = SQLiteRepositories(DB_PATH, history_limit=HISTORY_LIMIT)


def _repo_refs(user_id: int):
    user_ref = legacy_user_ref(user_id)
    conversation = DB_REPOSITORIES.ensure_default_conversation(user_ref)
    return user_ref, conversation.conversation_ref

MODEL_PRESETS = [
    "openai/gpt-4o-mini",  # Starting at $0.15/M input tokens Starting at $0.60/M output tokens
    "openai/gpt-4.1-mini",  # Starting at $0.40/M input tokens Starting at $1.60/M output tokens
    "anthropic/claude-3.5-haiku",  # $0.80/M input tokens $4/M output tokens
    "google/gemini-2.5-flash-lite",  # $0.10/M input tokens $0.40/M output tokens
    "google/gemini-2.5-flash",  # $0.30/M input tokens $2.50/M output tokens $1/M audio tokens
    "google/gemini-2.5-flash-preview-09-2025", # $0.30/M input tokens $2.50/M output tokens $1/M audio tokens
    "google/gemini-3-flash-preview", # $0.50/M input tokens $3/M output tokens $1/M audio tokens 
    "meta-llama/llama-3.1-70b-instruct",  # $0.40/M input tokens $0.40/M output tokens
    "tngtech/deepseek-r1t2-chimera",  # $0.25/M input tokens $0.85/M output tokens
    "xiaomi/mimo-v2-flash",  # $0/M input tokens $0/M output tokens
    "deepseek/deepseek-v3.2",  # $0.25/M input tokens $0.38/M output tokens
    "deepseek/deepseek-chat-v3-0324",  # $0.19/M input tokens $0.87/M output tokens
    "nousresearch/hermes-4-70b",  # $0.11/M input tokens $0.38/M output tokens
    "nousresearch/hermes-3-llama-3.1-405b:free",  # $0/M input tokens $0/M output tokens
    "mistralai/mistral-nemo",  # $0.02/M input tokens $0.04/M output tokens
    "sao10k/l3-lunaris-8b",  # $0.04/M input tokens $0.05/M output tokens
    "gryphe/mythomax-l2-13b",  # $0.06/M input tokens $0.06/M output tokens
    "deepseek/deepseek-r1-0528",  # $0.45/M input tokens $2.15/M output tokens
    "x-ai/grok-4.1-fast", # Starting at $0.20/M input tokens Starting at $0.50/M output tokens
    "z-ai/glm-4.7", # $0.40/M input tokens $1.50/M output tokens
    "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",  # free
]

# Короткий ключ -> полное имя модели (для callback_data <= 64 bytes)
MODEL_KEYS = {str(i): m for i, m in enumerate(MODEL_PRESETS)}
MODEL_KEYS_REV = {m: str(i) for i, m in enumerate(MODEL_PRESETS)}

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_IMAGE_MODEL = os.getenv("OPENROUTER_IMAGE_MODEL_DEFAULT", "sourceful/riverflow-v2-max-preview").strip()

# Пресеты для быстрого теста (можешь расширять)
IMAGE_MODEL_PRESETS = [
    "sourceful/riverflow-v2-max-preview",
    # добавь сюда любые другие image-модели OpenRouter, которые хочешь тестить
]


OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "tg-model-tester")

# ----------------------------
# PHOTO GATE (уговоры)
# ----------------------------
PHOTO_RE = re.compile(r"\b(фото|фотку|картинк|изображени|скинь|покажи|пришли)\b", re.I)
POLITE_RE = re.compile(r"\b(пожалуйста|плиз|прошу|будь добр|если можно|умоляю)\b", re.I)
PERSIST_RE = re.compile(r"\b(ну давай|ну пожалуйста|очень надо|в последний раз|обещаю)\b", re.I)
RUDE_RE = re.compile(r"\b(быстро|срочно|немедленно|дай)\b", re.I)

PHOTO_MIN_GAP_SEC = 6          # чуть выше — спам становится бессмысленнее
PHOTO_COOLDOWN_SEC = 90        # после фото чуть дольше пауза

# ----------------------------
# DRIFTING DUST FIELD (no <pre>, no copy header)
# ----------------------------

DUST_W = 18
DUST_H = 3
DUST_BG = "\u2800"  # braille blank "⠀" (не пробел) — выглядит пустым, но стабилен в сетке

DUST_PARTICLE_CHARS = ["·", "⋅", "•", "✧", "✦", "✺", "✹", "✷"]
DUST_SPAWN_MIN = 1
DUST_SPAWN_MAX = 2
DUST_MAX_PARTICLES = 14
DUST_TTL_MIN = 10
DUST_TTL_MAX = 30

def _clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v

def dust_step(field: dict) -> None:
    field["tick"] += 1
    rnd = random.Random(field["rnd_seed"] ^ (field["tick"] * 1103515245))

    # лёгкий "ветер" меняется редко — даёт ощущение живого облака
    if field["tick"] % 9 == 0:
        field["wind_dx"] = rnd.choice([-1, 0, 1])
    if field["tick"] % 13 == 0:
        field["wind_dy"] = rnd.choice([-1, 0, 1, 0, 0])

    new_particles = []
    for p in field["particles"]:
        p["ttl"] -= 1
        if p["ttl"] <= 0:
            continue

        # небольшая случайная дрожь
        jx = rnd.choice([-1, 0, 0, 1])
        jy = rnd.choice([-1, 0, 0, 1, 0])

        nx = p["x"] + p["dx"] + field["wind_dx"] + jx
        ny = p["y"] + p["dy"] + field["wind_dy"] + jy

        # отражение от стен
        if nx < 0:
            nx = 0
            p["dx"] = 1
        elif nx >= DUST_W:
            nx = DUST_W - 1
            p["dx"] = -1

        if ny < 0:
            ny = 0
            p["dy"] = 1
        elif ny >= DUST_H:
            ny = DUST_H - 1
            p["dy"] = -1

        p["x"], p["y"] = nx, ny

        # редкая смена символа (искры)
        if rnd.random() < 0.08:
            p["ch"] = rnd.choice(DUST_PARTICLE_CHARS)

        new_particles.append(p)

    field["particles"] = new_particles

    # спавн новых частиц
    spawn_n = rnd.randint(DUST_SPAWN_MIN, DUST_SPAWN_MAX)
    if len(field["particles"]) < DUST_MAX_PARTICLES and rnd.random() < 0.9:
        dust_spawn(field, spawn_n)


def is_photo_request(text: str) -> bool:
    return bool(PHOTO_RE.search(text or ""))

# Папка с фото: ...\Lina_AI\Photo (рядом со скриптом)
PHOTOS_DIR = Path(__file__).resolve().parent / "Photo"

def pick_random_photo() -> Path | None:
    if not PHOTOS_DIR.exists():
        return None
    files = [
        p for p in PHOTOS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    return random.choice(files) if files else None

async def send_random_photo(message: types.Message) -> None:
    photo_path = pick_random_photo()
    if not photo_path:
        await message.answer("Пока нет доступных фото.")
        return
    await message.answer_photo(FSInputFile(str(photo_path)))

# ----------------------------
# DB
# ----------------------------

def ensure_user_profile_schema(cur: sqlite3.Cursor) -> None:
    # Базовая таблица (на всякий случай)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
          user_id INTEGER PRIMARY KEY,
          preferred_name TEXT,
          preferred_title TEXT
        )
    """)

    # Добавляем mode, если его ещё нет
    try:
        cur.execute("ALTER TABLE user_profile ADD COLUMN mode TEXT")
    except sqlite3.OperationalError:
        # column already exists
        pass
    
    # --- chat lock fields ---
    try:
        cur.execute("ALTER TABLE user_profile ADD COLUMN chat_locked INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE user_profile ADD COLUMN lock_reason TEXT NOT NULL DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    # --- mode picked flag ---
    try:
        cur.execute("ALTER TABLE user_profile ADD COLUMN mode_picked INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    
    # --- /chat lock fields ---


def ensure_mode_state_schema(cur: sqlite3.Cursor) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mode_state (
          user_id INTEGER NOT NULL,
          mode TEXT NOT NULL,
          state_json TEXT NOT NULL,
          updated_at INTEGER NOT NULL,
          PRIMARY KEY (user_id, mode)
        )
    """)

def ensure_photo_gate_schema(cur: sqlite3.Cursor) -> None:
    """
    Создаёт таблицу photo_gate, если её нет.
    Если таблица уже была создана ранее (без новых колонок) — добавляет недостающие колонки.
    """
    cur.execute("""
        CREATE TABLE IF NOT EXISTS photo_gate (
          user_id INTEGER PRIMARY KEY,
          score INTEGER NOT NULL DEFAULT 0,
          attempts INTEGER NOT NULL DEFAULT 0,
          last_ask_ts INTEGER NOT NULL DEFAULT 0,
          cooldown_until_ts INTEGER NOT NULL DEFAULT 0,

          awaiting_context INTEGER NOT NULL DEFAULT 0,
          context_asked_ts INTEGER NOT NULL DEFAULT 0,

          awaiting_image_prompt INTEGER NOT NULL DEFAULT 0,
          image_cooldown_until_ts INTEGER NOT NULL DEFAULT 0
        )
    """)


    cur.execute("PRAGMA table_info(photo_gate)")
    existing = {row[1] for row in cur.fetchall()}  # row[1] = column name

    needed = {
        "score": "INTEGER NOT NULL DEFAULT 0",
        "attempts": "INTEGER NOT NULL DEFAULT 0",
        "last_ask_ts": "INTEGER NOT NULL DEFAULT 0",
        "cooldown_until_ts": "INTEGER NOT NULL DEFAULT 0",

        "awaiting_context": "INTEGER NOT NULL DEFAULT 0",
        "context_asked_ts": "INTEGER NOT NULL DEFAULT 0",

        "awaiting_image_prompt": "INTEGER NOT NULL DEFAULT 0",
        "image_cooldown_until_ts": "INTEGER NOT NULL DEFAULT 0",
    }


    for col, ddl in needed.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE photo_gate ADD COLUMN {col} {ddl}")
    
    
    try:
        cur.execute("ALTER TABLE photo_gate ADD COLUMN awaiting_prompt INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

def ensure_user_events_schema(cur: sqlite3.Cursor) -> None:
    cur.execute("PRAGMA table_info(user_events)")
    existing = {row[1] for row in cur.fetchall()}

    needed = {
        # кто/что посчитали по LLM
        "llm_provider": "TEXT NOT NULL DEFAULT ''",
        "llm_model": "TEXT NOT NULL DEFAULT ''",
        "prompt_tokens": "INTEGER NOT NULL DEFAULT 0",
        "completion_tokens": "INTEGER NOT NULL DEFAULT 0",
        "total_tokens": "INTEGER NOT NULL DEFAULT 0",
        "tokens_source": "TEXT NOT NULL DEFAULT ''",  # 'api' | 'tiktoken' | ''
    }

    for col, ddl in needed.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE user_events ADD COLUMN {col} {ddl}")

    # индекс под отчёты по стоимости
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_events_llm ON user_events(date(ts, 'unixepoch'), llm_model)")
    except Exception:
        pass


def init_db() -> None:
    migrate_database(DB_PATH, include_relationship_state=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # ----------------------------
        # MODE LOCK (per-mode)
        # ----------------------------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS mode_lock (
              user_id INTEGER NOT NULL,
              mode TEXT NOT NULL,
              locked INTEGER NOT NULL DEFAULT 0,
              reason TEXT NOT NULL DEFAULT '',
              updated_at INTEGER NOT NULL,
              PRIMARY KEY (user_id, mode)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
              user_id INTEGER PRIMARY KEY,
              model TEXT NOT NULL,
              image_model TEXT NOT NULL DEFAULT '',
              image_provider TEXT NOT NULL DEFAULT 'openrouter'
            )
        """)

        cur.execute("PRAGMA table_info(user_settings)")
        _cols = {row[1] for row in cur.fetchall()}

        if "image_model" not in _cols:
            cur.execute("ALTER TABLE user_settings ADD COLUMN image_model TEXT NOT NULL DEFAULT ''")

        if "image_provider" not in _cols:
            cur.execute("ALTER TABLE user_settings ADD COLUMN image_provider TEXT NOT NULL DEFAULT 'openrouter'")


        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('user','assistant')),
              content TEXT NOT NULL,
              created_at INTEGER NOT NULL
            )
        """)

        # --- MIGRATION: user_messages.mode ---
        cur.execute("PRAGMA table_info(user_messages)")
        _cols = {row[1] for row in cur.fetchall()}
        if "mode" not in _cols:
            cur.execute("ALTER TABLE user_messages ADD COLUMN mode TEXT NOT NULL DEFAULT 'basic'")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_messages_user_id_mode ON user_messages(user_id, mode)")
        # --- /MIGRATION ---
 
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_messages_user_id ON user_messages(user_id)")

        ensure_photo_gate_schema(cur)

        ensure_user_profile_schema(cur)

        ensure_mode_state_schema(cur)

        # ----------------------------
        # USER EVENTS (analytics log)
        # ----------------------------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts INTEGER NOT NULL,                  -- unix time
              user_id INTEGER NOT NULL,
              chat_id INTEGER NOT NULL DEFAULT 0,
              username TEXT NOT NULL DEFAULT '',
              first_name TEXT NOT NULL DEFAULT '',
              event_type TEXT NOT NULL,             -- message | switch_mode | photo_button | photo_request | photo_result
              mode TEXT NOT NULL DEFAULT '',         -- current mode at event time

              mode_from TEXT NOT NULL DEFAULT '',
              mode_to   TEXT NOT NULL DEFAULT '',

              message_id INTEGER NOT NULL DEFAULT 0,
              text_len   INTEGER NOT NULL DEFAULT 0,

              photo_provider TEXT NOT NULL DEFAULT '',
              photo_model    TEXT NOT NULL DEFAULT '',
              ok INTEGER NOT NULL DEFAULT 1,
              note TEXT NOT NULL DEFAULT ''
            )
        """)
        ensure_user_events_schema(cur)
        ensure_relationship_table(DB_PATH)

        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_events_user_ts ON user_events(user_id, ts)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_events_ts ON user_events(ts)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_events_type ON user_events(event_type)")

        conn.commit()
    finally:
        conn.close()

def log_user_event(
    *,
    ts: int,
    user_id: int,
    chat_id: int = 0,
    username: str = "",
    first_name: str = "",
    event_type: str,
    mode: str = "",
    mode_from: str = "",
    mode_to: str = "",
    message_id: int = 0,
    text_len: int = 0,
    photo_provider: str = "",
    photo_model: str = "",
    ok: int = 1,
    note: str = "",
    llm_provider: str = "",
    llm_model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    tokens_source: str = "",
) -> None:
    """
    ?????????? 1 ?????????????? ?? user_events. ?????????????? ???? ???????????? ???????????????????? ????????????.
    """
    try:
        user_ref = legacy_user_ref(user_id)
        DB_REPOSITORIES.append_legacy_user_event(
            user_ref,
            ts=ts,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
            event_type=event_type,
            mode=mode,
            mode_from=mode_from,
            mode_to=mode_to,
            message_id=message_id,
            text_len=text_len,
            photo_provider=photo_provider,
            photo_model=photo_model,
            ok=ok,
            note=note,
            llm_provider=llm_provider,
            llm_model=llm_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            tokens_source=tokens_source,
        )
    except Exception:
        # ?????????????????????? ???? ???????????? ???????????? ????????
        pass


def get_user_model(user_id: int) -> str:
    user_ref = legacy_user_ref(user_id)
    return DB_REPOSITORIES.get_user_model(user_ref, default_model=DEFAULT_MODEL)

def set_user_model(user_id: int, model: str) -> None:
    user_ref = legacy_user_ref(user_id)
    DB_REPOSITORIES.set_user_model(user_ref, model)

APP_SETTINGS = Settings.from_env(project_root=PROJECT_ROOT)
IMAGE_SERVICE = ImageService(settings=APP_SETTINGS, openrouter_client=openrouter_client)


def _image_analytics_context() -> tuple[str, str]:
    return IMAGE_SERVICE.analytics_context()


async def generate_image_backend(prompt: str) -> bytes:
    return await IMAGE_SERVICE.generate_image(prompt)


def clear_history(user_id: int, mode: str | None = None) -> None:
    user_ref, conversation_ref = _repo_refs(user_id)
    DB_REPOSITORIES.clear_history(user_ref, conversation_ref, mode=mode)

def append_history(user_id: int, mode: str, role: str, content: str) -> None:
    user_ref, conversation_ref = _repo_refs(user_id)
    DB_REPOSITORIES.append_history(user_ref, conversation_ref, mode, role, content)

def get_history(user_id: int, mode: str) -> List[Dict[str, Any]]:
    user_ref, conversation_ref = _repo_refs(user_id)
    return DB_REPOSITORIES.load_history(user_ref, conversation_ref, mode)

def get_active_dialog_stats(user_id: int) -> dict[str, int]:
    """?????????????? ?????????????????? ?????????????????? ???? ?????????????? mode ?? user_messages."""
    user_ref = legacy_user_ref(user_id)
    return DB_REPOSITORIES.get_active_dialog_stats(user_ref)

def get_photo_gate(user_id: int) -> Dict[str, int]:
    user_ref, conversation_ref = _repo_refs(user_id)
    return DB_REPOSITORIES.get_photo_gate(user_ref, conversation_ref)

def upsert_photo_gate(
    user_id: int,
    score: int,
    attempts: int,
    last_ask_ts: int,
    cooldown_until_ts: int,
    awaiting_context: int = 0,
    context_asked_ts: int = 0,
    awaiting_image_prompt: int = 0,
    image_cooldown_until_ts: int = 0,
) -> None:
    user_ref, conversation_ref = _repo_refs(user_id)
    DB_REPOSITORIES.upsert_photo_gate(
        user_ref,
        conversation_ref,
        {
            "score": score,
            "attempts": attempts,
            "last_ask_ts": last_ask_ts,
            "cooldown_until_ts": cooldown_until_ts,
            "awaiting_context": awaiting_context,
            "context_asked_ts": context_asked_ts,
            "awaiting_image_prompt": awaiting_image_prompt,
            "image_cooldown_until_ts": image_cooldown_until_ts,
        },
    )

def get_user_profile(user_id: int) -> Dict[str, str]:
    user_ref = legacy_user_ref(user_id)
    return DB_REPOSITORIES.get_user_profile(user_ref)

GAME_OVER_MARKER = "[[GAME_OVER]]"

# ловим и кривые варианты: [GAME_OVER]], [[GAME OVER]], [GAMT_OVER], и т.п.
_GAME_OVER_RE = re.compile(
    r"""
    \[\[?\s*            # [ или [[
    GA?M[E]?\s*         # GAME / GAM / опечатки
    [_\s-]*             # _, пробел, -
    OVE?R\s*            # OVER / OVR / опечатки
    \]?\]               # ] или ]]
    """,
    re.IGNORECASE | re.VERBOSE
)

def strip_game_over_markers(text: str) -> tuple[str, bool]:
    """
    Возвращает (clean_text, triggered)
    triggered=True если нашли хотя бы один маркер (даже кривой)
    """
    if not text:
        return text, False
    cleaned, n = _GAME_OVER_RE.subn("", text)
    return cleaned.strip(), (n > 0)


def lock_chat(user_id: int, reason: str = "") -> None:
    user_ref = legacy_user_ref(user_id)
    DB_REPOSITORIES.lock_chat(user_ref, reason)

def unlock_chat(user_id: int) -> None:
    user_ref = legacy_user_ref(user_id)
    DB_REPOSITORIES.unlock_chat(user_ref)

def is_chat_locked(profile: Dict[str, str]) -> tuple[bool, str]:
    locked = int(profile.get("chat_locked") or "0") == 1
    reason = (profile.get("lock_reason") or "").strip()
    return locked, reason

def lock_mode(user_id: int, mode: str, reason: str = "") -> None:
    mode = (mode or "basic").strip()
    user_ref, conversation_ref = _repo_refs(user_id)
    DB_REPOSITORIES.lock_mode(user_ref, conversation_ref, mode, reason=reason)

def unlock_mode(user_id: int, mode: str) -> None:
    mode = (mode or "basic").strip()
    user_ref, conversation_ref = _repo_refs(user_id)
    DB_REPOSITORIES.unlock_mode(user_ref, conversation_ref, mode)

def is_mode_locked(user_id: int, mode: str) -> tuple[bool, str]:
    mode = (mode or "basic").strip()
    user_ref, conversation_ref = _repo_refs(user_id)
    return DB_REPOSITORIES.is_mode_locked(user_ref, conversation_ref, mode)

def set_user_profile(
    user_id: int,
    preferred_name: str | None = None,
    preferred_title: str | None = None,
    mode: str | None = None,
) -> None:
    user_ref = legacy_user_ref(user_id)
    DB_REPOSITORIES.set_user_profile(
        user_ref,
        preferred_name=preferred_name,
        preferred_title=preferred_title,
        mode=mode,
    )


def set_mode_picked(user_id: int, picked: bool) -> None:
    user_ref = legacy_user_ref(user_id)
    DB_REPOSITORIES.set_mode_picked(user_ref, picked)

def default_mode_state(mode: str) -> Dict[str, Any]:
    return {
        "season": 1,
        "episode": 1,
        "genre": mode,
        "location": "",
        "premise": MODE_TO_PREMISE.get(mode, "Базовый режим."),
        "cast": [{"role": "главная", "notes": ""}],
        "timeline": [],
        "open_threads": [],
        "recap": "",
    }

def build_context_reminder(user_id: int, mode: str, history_n: int = 8) -> str:
    """
    Универсальная "напоминалка контекста" для любого режима.
    Источник: mode_state (recap/timeline/open_threads) + fallback к последним сообщениям.
    Без LLM.
    """
    mode = (mode or "basic").strip()
    st = get_mode_state(user_id, mode)  # гарантирует dict

    recap = (st.get("recap") or "").strip()

    # последнее событие из timeline (у тебя туда пишется "Ход: ...")
    last_event = ""
    tl = st.get("timeline") or []
    if isinstance(tl, list) and tl:
        last_event = (str(tl[-1]) or "").strip()

    # важное: 1-2 открытые нити
    important = ""
    threads = st.get("open_threads") or []
    if isinstance(threads, list) and threads:
        imp = [str(x).strip() for x in threads if str(x).strip()]
        if imp:
            important = "; ".join(imp[:2])

    # fallback: если state пустой — попробуем из истории вытащить последний user intent
    if not recap:
        hist = get_history(user_id, mode)
        if hist:
            # ищем последний user
            for msg in reversed(hist[-max(2, history_n):]):
                if msg.get("role") == "user":
                    t = (msg.get("content") or "").strip().replace("\n", " ")
                    if len(t) > 160:
                        t = t[:160].rsplit(" ", 1)[0] + "…"
                    last_event = last_event or f"Ход: {t}"
                    break

        recap = recap or "Диалог продолжается, конкретная цель явно не зафиксирована."

    # формат фиксированный и короткий
    lines = []
    lines.append(f"Контекст режима «{mode}»:")
    lines.append("")
    lines.append(f"Сейчас: {recap}")

    if last_event:
        # чуть подчистим чтобы не было слишком длинно
        le = last_event.replace("\n", " ")
        if len(le) > 220:
            le = le[:220].rsplit(" ", 1)[0] + "…"
        lines.append(f"Последнее: {le}")

    if important:
        im = important.replace("\n", " ")
        if len(im) > 200:
            im = im[:200].rsplit(" ", 1)[0] + "…"
        lines.append(f"Важно: {im}")

    return "\n".join(lines).strip()

def reset_current_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Сброс персонажа",
                    callback_data="reset_current"
                )
            ]
        ]
    )


def remind_context_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🧠 Напомнить контекст", callback_data="remindctx")]]
    )


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
        f"Кратко сейчас: {state.get('recap','')}\n"
    )


def get_mode_state(user_id: int, mode: str) -> Dict[str, Any]:
    user_ref, conversation_ref = _repo_refs(user_id)
    state = DB_REPOSITORIES.load_mode_state(user_ref, conversation_ref, mode)
    if isinstance(state, dict):
        return state
    state = default_mode_state(mode)
    DB_REPOSITORIES.save_mode_state(user_ref, conversation_ref, mode, state)
    return state


def save_mode_state(user_id: int, mode: str, state: Dict[str, Any]) -> None:
    user_ref, conversation_ref = _repo_refs(user_id)
    DB_REPOSITORIES.save_mode_state(user_ref, conversation_ref, mode, state)

AUDIO_SYSTEM_PROMPT = """
Ты говоришь голосом.
Отвечай кратко: 2–4 предложения.
Без списков.
Без длинных объяснений.
Разговорный стиль, как живой человек.
Паузы и эмоции допустимы, но без воды.
Говори так, будто записываешь короткое голосовое сообщение в мессенджере.
"""

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

# ----------------------------
# OpenAI TTS (async)
# ----------------------------
async def openai_tts(text: str) -> bytes:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing env OPENAI_API_KEY")

    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_TTS_MODEL,
        "voice": OPENAI_TTS_VOICE,
        "format": OPENAI_TTS_FORMAT,  # mp3
        "input": text,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, headers=headers, json=payload)

    ctype = (r.headers.get("content-type") or "").lower()
    if r.status_code >= 400:
        body_preview = r.text[:400] if r.text else ""
        raise RuntimeError(f"OpenAI TTS HTTP {r.status_code}, content-type={ctype}, body={body_preview}")

    if "audio" not in ctype:
        body_preview = r.text[:400] if r.text else ""
        raise RuntimeError(f"OpenAI TTS returned non-audio: content-type={ctype}, body={body_preview}")

    return r.content

# ----------------------------
# OpenRouter call (async)
# ----------------------------
async def call_openrouter(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 700,
    frequency_penalty: float = 0.0,
    timeout_s: float = 60.0,
) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_APP_NAME,
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "frequency_penalty": frequency_penalty,
    }

    retry_delays = [0.8, 1.6, 3.2]
    last_exc = None

    for attempt, delay in enumerate([0.0] + retry_delays, start=1):
        if delay:
            await asyncio.sleep(delay)

        try:
            r = await openrouter_client.post(OPENROUTER_URL, headers=headers, json=payload)
            break
        except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout) as e:
            last_exc = e
            logging.warning(
                "OpenRouter network error attempt %s/%s: %s",
                attempt,
                1 + len(retry_delays),
                type(e).__name__,
            )
    else:
        raise RuntimeError(f"OpenRouter network error after retries: {last_exc}")


    if r.status_code >= 400:
        try:
            err = r.json()
        except Exception:
            err = {"error": {"message": r.text}}
        msg = err.get("error", {}).get("message", r.text)
        raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {msg}")

    data = r.json()
    return data["choices"][0]["message"]["content"]

async def call_openrouter_with_meta(
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 700,
    frequency_penalty: float = 0.0,
    timeout_s: float = 60.0,
) -> tuple[str, str, Dict[str, Any]]:
    return await shared_call_openrouter_with_meta(
        client=openrouter_client,
        api_key=OPENROUTER_API_KEY,
        site_url=OPENROUTER_SITE_URL,
        app_name=OPENROUTER_APP_NAME,
        url=OPENROUTER_URL,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        frequency_penalty=frequency_penalty,
        timeout_s=timeout_s,
    )


MAX_AUTO_CONTINUATIONS = int(os.getenv("MAX_AUTO_CONTINUATIONS", "2"))

_CONTINUE_PROMPT = (
    "Продолжи предыдущий ответ ровно с места обрыва. "
    "Не повторяй уже сказанное. "
    "НЕ извиняйся и НЕ упоминай, что ответ был прерван. "
    "Просто продолжай по делу и закончи логично."
)


# ----------------------------
# Telegram bot
# ----------------------------
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ----------------------------
# IMAGE GENERATION: live status + cancel
# ----------------------------

IMAGE_STATUS_INTERVAL_SEC = 3.0  # как часто менять фразу/прогресс
IMAGE_VANISH_SEC = 0.6           # "испарение" (короткая пауза между фразами)
PROGRESS_BAR_LEN = 14

# Храним активные генерации по user_id
IMAGE_JOBS: Dict[int, Dict[str, Any]] = {}

IMAGE_FUN_PHRASES = [
    "Запускаю сигнатуры…",
    "Тестирую на котиках…",
    "Сверяюсь с реестром ламантинов…",
    "Разогреваю нейроны до рабочей температуры…",
    "Проверяю, не подменили ли пиксели на поддельные…",
    "Собираю пиксели в правильном порядке…",
    "Уговариваю алгоритм быть красивым…",
    "Протираю объектив матрицы…",
    "Вызываю духов композиции и света…",
    "Настраиваю баланс магии и здравого смысла…",
    "Делаю вид, что понимаю современное искусство…",
    "Согласовываю результат с кото-комиссией…",

    "Калибрую тени и полутона…",
    "Выравниваю реальность с ожиданиями…",
    "Проверяю, не поплыл ли горизонт…",
    "Подкручиваю эстетические коэффициенты…",
    "Оптимизирую количество красоты на пиксель…",
    "Проверяю симметрию вселенной…",
    "Соблюдаю технику художественной безопасности…",
    "Пересчитываю пропорции на салфетке…",
    "Подгоняю результат под законы жанра…",
    "Слежу, чтобы лишние конечности не появились…",
    "Фиксирую композицию до стабильно красивой…",
    "Снижаю энтропию изображения…",

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
# ----------------------------
# STATUS RENDER MODE
# ----------------------------

def _progress_bar(tick: int, length: int = PROGRESS_BAR_LEN) -> str:
    # "бегунок" туда-сюда (не знает реального прогресса, но выглядит живо)
    if length < 6:
        length = 6
    span = length - 4
    p = tick % (2 * span)
    pos = p if p <= span else (2 * span - p)
    left = "░" * pos
    mid = "▓▓▓▓"
    right = "░" * (span - pos)
    return f"[{left}{mid}{right}]"

def _spinner(tick: int) -> str:
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    return frames[tick % len(frames)]

def image_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⛔ Отмена", callback_data="imgcancel")]]
    )
FADE_FRAMES = [
    "⋯⋯⋯⋯⋯",
    "⋯⋯⋯⋯",
    "⋯⋯⋯",
    "⋯⋯",
    "⋯",
    "·",
    "\u200b",  # zero-width space: выглядит как "пусто", но Telegram принимает
]
DUST_FADE_CHARS = ["·", "⋅", "•", "✧"]


def make_dust_frame(count: int) -> str:
    """
    Возвращает строку с 'распадающимися' точками.
    Пример: '·   · ·'
    """
    if count <= 0:
        return "\u200b"  # визуально пусто, но Telegram принимает

    parts = []
    for _ in range(count):
        parts.append(random.choice(DUST_FADE_CHARS))
        # случайные промежутки — ключ к эффекту распада
        parts.append(" " * random.randint(1, 3))

    return "".join(parts).rstrip()


async def fade_out_text(bot: Bot, chat_id: int, message_id: int) -> bool:
    """
    Имитирует 'распад' текста: точки рассыпаются и исчезают.
    ВАЖНО: без reply_markup. Иначе будут жить кнопки/бардак.
    """
    start = random.randint(5, 7)

    for n in range(start, -1, -1):
        frame = make_dust_frame(n)
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=frame,
                reply_markup=None,   # <-- ключевое
            )
        except Exception as e:
            if "message is not modified" in str(e).lower():
                await asyncio.sleep(0.06)
                continue
            return False

        await asyncio.sleep(0.10)

    return True

IMAGE_FUN_VISIBLE_SEC = 2.0  # сколько висит смешной пузырь до распыления

def render_fun_phrase_only() -> str:
    emoji = random.choice(IMAGE_FUN_EMOJIS)
    if random.random() < 0.25:
        emoji += random.choice(IMAGE_FUN_EMOJIS)
    phrase = random.choice(IMAGE_FUN_PHRASES)
    return f"{emoji} {phrase}"

async def run_image_fun_only_loop(
    bot: Bot,
    chat_id: int,
    cancel_event: asyncio.Event,
) -> None:
    """
    СТРОГО:
    1) отправили смешную фразу
    2) подождали ~2 сек
    3) распылили и удалили
    4) следующая
    Никаких прогрессбаров и отдельных "генерация..." сообщений.
    """
    try:
        while not cancel_event.is_set():
            # 1) пузырь со смешной фразой
            try:
                msg = await bot.send_message(chat_id, render_fun_phrase_only())
            except Exception:
                return

            # 2) висит 2 сек
            await asyncio.sleep(IMAGE_FUN_VISIBLE_SEC)
            if cancel_event.is_set():
                try:
                    await bot.delete_message(chat_id, msg.message_id)
                except Exception:
                    pass
                return

            # 3) распыление + удаление
            try:
                await fade_out_text(bot, chat_id, msg.message_id)
            except Exception:
                pass
            try:
                await bot.delete_message(chat_id, msg.message_id)
            except Exception:
                pass

            # 4) следующая — без доп. пауз (строго как ты просишь)

    except asyncio.CancelledError:
        return


def build_models_keyboard(models: List[str]) -> InlineKeyboardMarkup:
    rows = []
    for i, m in enumerate(models):
        key = str(i)
        rows.append([InlineKeyboardButton(text=m, callback_data=f"setmodel:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Режим"), KeyboardButton(text="Сброс всего")],
    ],
    resize_keyboard=True,
)

GEN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Режим"), KeyboardButton(text="Сброс всего"), KeyboardButton(text="Сброс персонажа")],
        [KeyboardButton(text="Хочу фото")],
    ],
    resize_keyboard=True,
)

RAP_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Режим"), KeyboardButton(text="Сброс всего"), KeyboardButton(text="Сброс персонажа")],
        [KeyboardButton(text="🎤 Стиль"), KeyboardButton(text="Хочу фото")],
    ],
    resize_keyboard=True,
)

def menu_for(profile: Dict[str, str]) -> ReplyKeyboardMarkup:
    picked = int(profile.get("mode_picked") or "0")
    if picked != 1:
        return MAIN_MENU
    
    # Для рэпера — меню с кнопкой "Стиль"
    mode = (profile.get("mode") or "").strip()
    if mode == "oldschool_rep":
        return RAP_MENU
    
    return GEN_MENU

@dp.message(F.text == "Режим")
async def mode_btn(message: types.Message):
    await cmd_mode(message)

@dp.message(F.text.in_({"🎤 Стиль", "Стиль"}))
async def rap_style_btn(message: types.Message):
    user_id = message.from_user.id
    profile = get_user_profile(user_id)
    mode = (profile.get("mode") or "").strip()
    
    # Только для рэпера
    if mode != "oldschool_rep":
        await message.answer("Эта кнопка работает только в режиме Рэпера.")
        return
    
    # Получаем текущий подрежим
    st = get_mode_state(user_id, "oldschool_rep")
    current_sub = (st.get("rap_submode") or "story").strip().lower()
    
    kb = build_rap_submode_keyboard(current=current_sub)
    
    await message.answer(
        "Выбери стиль:\n"
        "• **STREET** — улица, дерзко\n"
        "• **STORY** — городские истории\n"
        "• **LYRICAL** — лирика, внутренний монолог",
        parse_mode="Markdown",
        reply_markup=kb,
    )

@dp.message(F.text.in_({"Сброс", "Сброс всего"}))
async def reset_btn(message: types.Message):
    await cmd_reset(message)

async def _reset_current_mode(user_id: int, mode: str, *, note: str, chat_id: int, username: str, first_name: str, message_id: int, text_len: int) -> str:
    now_ts = int(time.time())
    log_user_event(
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

    user_ref, conversation_ref = _repo_refs(user_id)
    DB_REPOSITORIES.reset_mode_in_conversation(user_ref, conversation_ref, mode)

    if mode == "whore":
        reset_relationship_state(DB_PATH, user_id, mode)

    return mode


@dp.message(F.text == "Сброс персонажа")
async def reset_here_btn(message: types.Message):
    user_id = message.from_user.id
    profile = get_user_profile(user_id)
    mode = (profile.get("mode") or "basic").strip()

    await _reset_current_mode(
        user_id,
        mode,
        note="scope=mode",
        chat_id=int(message.chat.id) if message.chat else 0,
        username=(message.from_user.username or ""),
        first_name=(message.from_user.first_name or ""),
        message_id=int(message.message_id),
        text_len=len((message.text or "")),
    )

    profile = get_user_profile(user_id)
    await message.answer(
        f"Ок. Сбросил историю только для режима `{mode}`.",
        parse_mode="Markdown",
        reply_markup=menu_for(profile),
    )


@dp.callback_query(F.data == "reset_current")
async def reset_current_inline(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    profile = get_user_profile(user_id)
    mode = (profile.get("mode") or "basic").strip()

    await _reset_current_mode(
        user_id,
        mode,
        note="scope=mode (inline)",
        chat_id=int(callback.message.chat.id) if callback.message and callback.message.chat else 0,
        username=(callback.from_user.username or ""),
        first_name=(callback.from_user.first_name or ""),
        message_id=int(callback.message.message_id) if callback.message else 0,
        text_len=0,
    )

    await callback.answer("Сбросил")

    # красиво убираем кнопку после нажатия
    try:
        await callback.message.edit_text(
            f"🔄 Ок. Сбросил историю только для режима `{mode}`.\nМожем начинать заново.",
            parse_mode="Markdown",
            reply_markup=None,
        )
    except Exception:
        profile2 = get_user_profile(user_id)
        await callback.message.answer(
            f"🔄 Ок. Сбросил историю только для режима `{mode}`.\nМожем начинать заново.",
            parse_mode="Markdown",
            reply_markup=menu_for(profile2),
        )


# --- backward compatibility: старые кнопки меню ---
@dp.message(F.text.in_({"Модели", "Текущая модель"}))
async def legacy_models_btn(message: types.Message):
    await message.answer(
        "Выбор моделей отключён: модель теперь жёстко привязана к режиму.\n"
        "Нажми «Режим» и выбери персонажа.",
        reply_markup=MAIN_MENU,
    )

@dp.message(F.text == "Помощь")
async def legacy_help_btn(message: types.Message):
    await message.answer(
        "Доступно: «Режим» (выбор персонажа) и «Сброс».\n"
        "Просто напиши сообщение — я отвечу.",
        reply_markup=MAIN_MENU,
    )

@dp.message(F.text == "Генерация ответа")
async def legacy_suggest_btn(message: types.Message):
    await message.answer(
        "Функция «Генерация ответа» временно отключена.\n"
        "Просто напиши, что нужно — отвечу.",
        reply_markup=MAIN_MENU,
    )

@dp.message(F.text == "Хочу фото")
async def want_photo_btn(message: types.Message):
    user_id = message.from_user.id
    profile = get_user_profile(user_id)
    # --- LOG: photo_button ---
    now_ts = int(time.time())
    log_user_event(
        ts=now_ts,
        user_id=user_id,
        chat_id=int(message.chat.id) if message.chat else 0,
        username=(message.from_user.username or ""),
        first_name=(message.from_user.first_name or ""),
        event_type="photo_button",
        mode=(profile.get("mode") or "basic").strip(),
        message_id=int(message.message_id),
        text_len=len((message.text or "")),
        ok=1,
    )

    if int(profile.get("mode_picked") or "0") != 1:
        await message.answer("Сначала выбери персонажа: нажми «Режим».", reply_markup=MAIN_MENU)
        return

    now = int(time.time())
    gate = get_photo_gate(user_id)

    cd_until = int(gate.get("image_cooldown_until_ts") or 0)
    if cd_until > now:
        left = cd_until - now
        await message.answer(f"Следующая генерация будет доступна через {left // 60 + 1} мин.")
        return

    # Включаем режим ожидания описания (следующее сообщение пользователя = промпт)
    upsert_photo_gate(
        user_id=user_id,
        score=gate["score"],
        attempts=gate["attempts"],
        last_ask_ts=now,
        cooldown_until_ts=gate["cooldown_until_ts"],
        awaiting_context=gate["awaiting_context"],
        context_asked_ts=gate["context_asked_ts"],
        awaiting_image_prompt=1,
        image_cooldown_until_ts=cd_until,
    )

    await message.answer("Ок. Напиши описание: что именно сгенерировать?")


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    user_id = message.from_user.id
    profile = get_user_profile(user_id)
    mode = (profile.get("mode") or "basic").strip()

    if mode != "whore":
        await message.answer("Команда работает только в режиме Шлюшка")
        return

    rel_state = get_relationship_state(DB_PATH, user_id, mode)
    status_text = (
        "Статус отношений с Ликой\n\n"
        f"Имя: {rel_state.user_name or 'неизвестно'}\n"
        f"Стадия: {rel_state.stage.name}\n"
        f"Очки: {rel_state.points}\n"
        f"Настроение: {rel_state.mood.value}\n"
        f"NSFW: {'да' if rel_state.nsfw_unlocked else 'нет'}\n"
    )
    if rel_state.known_facts:
        status_text += f"\nФакты о тебе: {len(rel_state.known_facts)}"

    await message.answer(status_text, parse_mode="Markdown")

# --- /backward compatibility ---


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    profile = get_user_profile(user_id)
    menu = menu_for(profile)


    await message.answer(
        "Готово. Выбери режим кнопкой «Режим» или просто напиши сообщение.",
        reply_markup=menu,
    )


MODEL_SELECTION_DISABLED_TEXT = (
    "\u0412\u044b\u0431\u043e\u0440 \u043c\u043e\u0434\u0435\u043b\u0435\u0439 \u043e\u0442\u043a\u043b\u044e\u0447\u0451\u043d: \u043c\u043e\u0434\u0435\u043b\u044c \u0442\u0435\u043f\u0435\u0440\u044c \u0436\u0451\u0441\u0442\u043a\u043e \u043f\u0440\u0438\u0432\u044f\u0437\u0430\u043d\u0430 \u043a \u0440\u0435\u0436\u0438\u043c\u0443.\n"
    "\u041d\u0430\u0436\u043c\u0438 \u00ab\u0420\u0435\u0436\u0438\u043c\u00bb \u0438 \u0432\u044b\u0431\u0435\u0440\u0438 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u0436\u0430."
)

@dp.message(Command("models"))
async def cmd_models(message: types.Message):
    await message.answer(MODEL_SELECTION_DISABLED_TEXT, reply_markup=MAIN_MENU)

@dp.message(Command("model"))
async def cmd_model(message: types.Message):
    await message.answer(MODEL_SELECTION_DISABLED_TEXT, reply_markup=MAIN_MENU)

def build_chef_submode_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="?? ?????? ??-?????????", callback_data="chefmode:home")],
        [InlineKeyboardButton(text="?? ??? ? ?????????", callback_data="chefmode:restaurant")],
        [InlineKeyboardButton(text="?? ????????? ????????", callback_data="remindctx")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_rap_submode_keyboard(current: str | None = None) -> InlineKeyboardMarkup:
    cur = (current or "").strip().lower()

    def btn(label: str, key: str) -> InlineKeyboardButton:
        mark = " ?" if cur == key else ""
        return InlineKeyboardButton(text=f"{label}{mark}", callback_data=f"rapmode:{key}")

    rows = [
        [
            btn("?? STREET", "street"),
            btn("?? STORY", "story"),
            btn("?? LYRICAL", "lyrical"),
        ],
        [InlineKeyboardButton(text="?? ????????? ????????", callback_data="remindctx")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.message(Command("mode"))
async def cmd_mode(message: types.Message):
    user_id = message.from_user.id
    profile = get_user_profile(user_id)
    current = profile.get("mode") or "basic"
    kb = build_modes_keyboard(user_id, current_mode=current)

    await message.answer(
        f"Текущий режим: `{current}`\n"
        "Выбери режим кнопкой ниже.\n\n"
        "↩️ — продолжить   🆕 — начать заново",
        parse_mode="Markdown",
        reply_markup=kb,
    )

@dp.callback_query(F.data == "remindctx")
async def cb_remindctx(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    profile = get_user_profile(user_id)
    mode = (profile.get("mode") or "basic").strip()

    text = build_context_reminder(user_id, mode)

    await callback.answer("Ок")
    # отправляем отдельным сообщением, чтобы не ломать предыдущее
    for part in chunk_text(text):
        await callback.message.answer(part)

@dp.callback_query(F.data.startswith("rapmode:"))
async def cb_rapmode(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    picked = callback.data.split(":", 1)[1].strip().lower()  # street/story/lyrical

    if picked not in ("street", "story", "lyrical"):
        await callback.answer("Неизвестный режим", show_alert=True)
        return

    # сохраняем выбор в mode_state для mode="oldschool_rep"
    st = get_mode_state(user_id, "oldschool_rep")
    st["rap_submode"] = picked
    save_mode_state(user_id, "oldschool_rep", st)

    await callback.answer("Ок")

    label = {
        "street": "STREET (уличный/дерзкий)",
        "story": "STORY (мини-истории)",
        "lyrical": "LYRICAL (лирика)",
    }[picked]

    # обновим сообщение: покажем выбранный режим и уберем клаву
    label = {
        "street": "STREET (улица)",
        "story": "STORY (истории)", 
        "lyrical": "LYRICAL (лирика)",
    }[picked]

    # Обновим сообщение и покажем правильное меню
    profile = get_user_profile(user_id)
    menu = menu_for(profile)
    
    try:
        await callback.message.edit_text(
            f"✅ Стиль: **{label}**\n"
            "Пиши тему или набросок — соберём текст.",
            parse_mode="Markdown",
            reply_markup=None,
        )
    except Exception:
        pass
    
    # Отправим меню отдельным сообщением (чтобы клавиатура обновилась)
    await callback.message.answer(
        "Готов.",
        reply_markup=menu,
    )


@dp.callback_query(F.data.startswith("setmode:"))
async def cb_setmode(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    prev_profile = get_user_profile(user_id)
    prev_mode = (prev_profile.get("mode") or "").strip()

    mode = callback.data.split(":", 1)[1].strip()

    if mode not in MODE_TO_SYSTEM_PROMPT:
        await callback.answer("Неизвестный режим", show_alert=True)
        return

    # 1) сохраняем режим
    user_ref, conversation_ref = _repo_refs(user_id)
    DB_REPOSITORIES.set_active_mode(user_ref, conversation_ref, mode)
    set_mode_picked(user_id, True)

    # --- LOG: switch_mode ---
    now_ts = int(time.time())
    log_user_event(
        ts=now_ts,
        user_id=user_id,
        chat_id=int(callback.message.chat.id) if callback.message and callback.message.chat else 0,
        username=(callback.from_user.username or ""),
        first_name=(callback.from_user.first_name or ""),
        event_type="switch_mode",
        mode=mode,              # новый текущий
        mode_from=prev_mode,    # старый
        mode_to=mode,           # новый
        message_id=int(callback.message.message_id) if callback.message else 0,
        text_len=0,
        ok=1,
    )


    await callback.answer("Режим установлен")
    profile = get_user_profile(user_id)
    menu = menu_for(profile)

    # --- SPECIAL: chef submode pick (one-time) ---
    if mode == "chef":
        st = get_mode_state(user_id, "chef")
        sub = (st.get("chef_submode") or "").strip()

        stats = get_active_dialog_stats(user_id)
        chef_has_history = int(stats.get("chef", 0)) > 0

        kb = build_chef_submode_keyboard()

        # 1) если submode ещё не выбран (обычно после "Сброс текущего" в chef) — покажем приветствие
        if not sub:
            text = (
                "Привет. Я **Шеф-повар** (20+ лет практики, высокая кухня).\n\n"
                "Выбери формат:\n"
                "• **Быстро по-домашнему** — коротко и практично.\n"
                "• **Как в ресторане** — подробно: техника, вкус, подача.\n\n"
                "Как работаем?"
            )
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
            return


        # 2) если submode выбран, но пользователь ВОЗВРАЩАЕТСЯ к повару после другого персонажа и история у повара есть
        if prev_mode and prev_mode != "chef" and chef_has_history:
            current_label = "по-домашнему" if sub == "home" else "как в ресторане"
            text = (
                f"Продолжаем **{current_label}** или переключаем формат?\n"
                "Выбери кнопкой:"
            )
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
            return
    
    # --- SPECIAL: rap submode pick (one-time + on return) ---
    if mode == "oldschool_rep":
        st = get_mode_state(user_id, "oldschool_rep")
        sub = (st.get("rap_submode") or "").strip().lower()

        stats = get_active_dialog_stats(user_id)
        rep_has_history = int(stats.get("oldschool_rep", 0)) > 0

        # если sub не выбран — дефолт story, но всё равно спросим (UX)
        if not sub:
            sub = "story"
            st["rap_submode"] = sub
            save_mode_state(user_id, "oldschool_rep", st)

        kb = build_rap_submode_keyboard(current=sub)

        # 1) если только что выбрали рэпера — предложим выбрать режим
        if prev_mode != "oldschool_rep":
            text = (
                "Привет. Я **Рэпер (олдскул)**.\n\n"
                "Выбери подрежим:\n"
                "• **STREET** — улично и дерзко\n"
                "• **STORY** — бытовые мини-истории\n"
                "• **LYRICAL** — лирика и внутренний монолог\n\n"
                "Как работаем?"
            )
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
            return

        # 2) если вернулись к рэперу и история есть — предложим переключить режим
        if prev_mode and prev_mode != "oldschool_rep" and rep_has_history:
            text = "Продолжаем в текущем подрежиме или переключаем?"
            await callback.message.answer(text, parse_mode="Markdown", reply_markup=kb)
            return
    # --- /SPECIAL ---



    # 3) иначе — ничего не спрашиваем, просто продолжим стандартным сообщением ниже
    # --- /SPECIAL ---

    desc = (MODE_TO_SHORT_DESC.get(mode) or "").strip()

    text = f"Ок. Режим теперь: `{mode}`"
    if desc:
        text += f"\n_{desc}_"
    text += "\n\nПродолжаем с прежнего места."

    await callback.message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=menu,
    )
    await callback.message.answer(
        "Если переключался и потерял нить — нажми кнопку ниже.",
        reply_markup=remind_context_kb(),
    )



@dp.callback_query(F.data.startswith("chefmode:"))
async def cb_chefmode(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    picked = callback.data.split(":", 1)[1].strip()  # home / restaurant

    if picked not in ("home", "restaurant"):
        await callback.answer("Неизвестный режим", show_alert=True)
        return

    # сохраняем выбор в mode_state для mode="chef"
    st = get_mode_state(user_id, "chef")
    st["chef_submode"] = picked
    save_mode_state(user_id, "chef", st)

    # короткое подтверждение
    label = "по-домашнему" if picked == "home" else "как в ресторане"
    await callback.answer("Ок")

    # (не обязательно, но удобно) — обновим текст сообщения и уберём кнопки
    try:
        await callback.message.edit_text(
            f"Ок, работаем **{label}**.\nНапиши, что готовим или какие продукты есть.",
            parse_mode="Markdown",
            reply_markup=None,
        )
    except Exception:
        # если edit не прошёл — просто отправим новое
        await callback.message.answer(
            f"Ок, работаем **{label}**.\nНапиши, что готовим или какие продукты есть.",
            parse_mode="Markdown",
        )


@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    user_id = message.from_user.id
    prev_profile = get_user_profile(user_id)
    prev_mode = (prev_profile.get("mode") or "basic").strip()

    log_user_event(
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
        text_len=len((message.text or "")),
        ok=1,
        note="scope=all",
    )

    unlock_chat(user_id)
    user_ref = legacy_user_ref(user_id)
    DB_REPOSITORIES.reset_user_all(user_ref)
    set_mode_picked(user_id, False)
    IMAGE_JOBS.pop(user_id, None)

    reset_relationship_state(DB_PATH, user_id, "whore")

    await message.answer(
        "\u0421\u0431\u0440\u043e\u0441 \u0441\u0434\u0435\u043b\u0430\u043b.\n"
        "\u0420\u0435\u0436\u0438\u043c: `basic`\n"
        "\u0418\u0441\u0442\u043e\u0440\u0438\u044f \u043e\u0447\u0438\u0449\u0435\u043d\u0430.",
        parse_mode="Markdown",
        reply_markup=MAIN_MENU,
    )

@dp.message(F.text)
async def on_text(message: types.Message):
    user_id = message.from_user.id
    
    user_text = (message.text or "").strip()
    if not user_text:
        return
    
    now = int(time.time())

    # текущий mode на момент сообщения (даже если пользователь не выбрал режим -> basic)
    profile_for_log = get_user_profile(user_id)
    mode_for_log = (profile_for_log.get("mode") or "basic").strip()

    # --- LOG: message ---
    log_user_event(
        ts=now,
        user_id=user_id,
        chat_id=int(message.chat.id) if message.chat else 0,
        username=(message.from_user.username or ""),
        first_name=(message.from_user.first_name or ""),
        event_type="message",
        mode=mode_for_log,
        message_id=int(message.message_id),
        text_len=len(user_text),
        ok=1,
    )


    # --- CANCEL by text (без лишних пузырей) ---
    if user_text.lower() in ("отмена", "⛔ отмена", "/cancel"):
        job = IMAGE_JOBS.get(user_id)
        if job:
            cancel_event: asyncio.Event = job["cancel_event"]
            cancel_event.set()

            gen_task: asyncio.Task | None = job.get("gen_task")
            if gen_task and not gen_task.done():
                gen_task.cancel()

            # никаких сообщений от бота (чтобы не ломать правило "только смешные фразы")
            return

    # --- PATCH: awaiting_context должен обрабатываться ДО is_photo_request ---
    photo_gate = get_photo_gate(user_id)

    # --- HARD LOCK: если уже идёт генерация, новые сообщения НЕ запускают новые генерации ---
    job = IMAGE_JOBS.get(user_id)
    if job and isinstance(job, dict):
        cancel_event = job.get("cancel_event")
        if cancel_event and not cancel_event.is_set():
            await message.answer("⏳ Генерация уже идёт. Дождись завершения или нажми «Отмена».")
            return


    # --- IMAGE GENERATION FLOW (awaiting prompt) ---
    if int(photo_gate.get("awaiting_image_prompt") or 0) == 1:
        cd_until = int(photo_gate.get("image_cooldown_until_ts") or 0)
        if cd_until > now:
            left = cd_until - now
            await message.answer(f"Кулдаун. Подожди ещё {left // 60 + 1} мин.")
            return

        # Сразу выходим из режима ожидания промпта, чтобы не запускать генерацию повторно
        upsert_photo_gate(
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

        # Регистрируем активную задачу (HARD LOCK выше начнёт игнорировать любые новые сообщения)
        cancel_event = asyncio.Event()
        IMAGE_JOBS[user_id] = {"cancel_event": cancel_event, "status_task": None, "gen_task": None}

        # 1) Параллельно крутим ТОЛЬКО смешные фразы (каждая живёт 2 сек и распыляется)
        status_task = asyncio.create_task(run_image_fun_only_loop(bot, message.chat.id, cancel_event))
        IMAGE_JOBS[user_id]["status_task"] = status_task

        # 2) Запускаем генерацию
        profile = get_user_profile(user_id)
        mode = (profile.get("mode") or "basic").strip()
        style_hint = MODE_TO_IMAGE_STYLE.get(mode, MODE_TO_IMAGE_STYLE["basic"])

        image_prompt = f"Стиль/арт-дирекшн: {style_hint}\nЗапрос пользователя: {user_text}"
        
        # --- LOG: photo_request (описание, которое пошло в генерацию) ---
        log_user_event(
            ts=now,
            user_id=user_id,
            chat_id=int(message.chat.id) if message.chat else 0,
            username=(message.from_user.username or ""),
            first_name=(message.from_user.first_name or ""),
            event_type="photo_request",
            mode=mode,
            message_id=int(message.message_id),
            text_len=len(user_text),
            photo_provider=_image_analytics_context()[0],
            photo_model=_image_analytics_context()[1],
            ok=1,
        )

        gen_task = asyncio.create_task(generate_image_backend(image_prompt))
        IMAGE_JOBS[user_id]["gen_task"] = gen_task

        try:
            img_bytes = await gen_task
        except asyncio.CancelledError:
            # Отмена — тихо останавливаем цикл фраз и выходим
            cancel_event.set()
            try:
                status_task.cancel()
            except Exception:
                pass
            IMAGE_JOBS.pop(user_id, None)
            
            # --- LOG: photo_result cancel ---
            log_user_event(
                ts=int(time.time()),
                user_id=user_id,
                chat_id=int(message.chat.id) if message.chat else 0,
                username=(message.from_user.username or ""),
                first_name=(message.from_user.first_name or ""),
                event_type="photo_result",
                mode=mode,
                message_id=int(message.message_id),
                text_len=len(user_text),
                photo_provider=_image_analytics_context()[0],
                photo_model=_image_analytics_context()[1],
                ok=0,
                note="cancelled",
            )

            return
        except Exception as e:
            logging.exception("Image generation failed (provider=%s user_id=%s): %s", _image_analytics_context()[0], user_id, e)
            cancel_event.set()
            try:
                status_task.cancel()
            except Exception:
                pass
            IMAGE_JOBS.pop(user_id, None)
            
            # --- LOG: photo_result error ---
            log_user_event(
                ts=int(time.time()),
                user_id=user_id,
                chat_id=int(message.chat.id) if message.chat else 0,
                username=(message.from_user.username or ""),
                first_name=(message.from_user.first_name or ""),
                event_type="photo_result",
                mode=mode,
                message_id=int(message.message_id),
                text_len=len(user_text),
                photo_provider=_image_analytics_context()[0],
                photo_model=_image_analytics_context()[1],
                ok=0,
                note=f"error: {type(e).__name__}",
            )

            await message.answer("Не получилось сгенерировать картинку. (см. лог ошибок)")
            return

        # Генерация закончилась — стопаем цикл фраз
        cancel_event.set()
        try:
            status_task.cancel()
        except Exception:
            pass
        IMAGE_JOBS.pop(user_id, None)

        # Отдаём картинку пользователю
        await message.answer_photo(BufferedInputFile(img_bytes, filename="image.png"))

        # --- LOG: photo_result success ---
        log_user_event(
            ts=int(time.time()),
            user_id=user_id,
            chat_id=int(message.chat.id) if message.chat else 0,
            username=(message.from_user.username or ""),
            first_name=(message.from_user.first_name or ""),
            event_type="photo_result",
            mode=mode,
            message_id=int(message.message_id),
            text_len=len(user_text),
            photo_provider=_image_analytics_context()[0],
            photo_model=_image_analytics_context()[1],
            ok=1,
            note="success",
        )


        # Кулдаун на следующее фото
        upsert_photo_gate(
            user_id=user_id,
            score=photo_gate["score"],
            attempts=photo_gate["attempts"],
            last_ask_ts=now,
            cooldown_until_ts=photo_gate["cooldown_until_ts"],
            awaiting_context=photo_gate["awaiting_context"],
            context_asked_ts=photo_gate["context_asked_ts"],
            awaiting_image_prompt=0,
            image_cooldown_until_ts=now + IMAGE_COOLDOWN_SEC,
        )
        return
    # --- /IMAGE GENERATION FLOW ---


    audio_only = is_audio_request(user_text)
   
    profile = get_user_profile(user_id)
    mode = (profile.get("mode") or "basic").strip()

    locked, reason = is_mode_locked(user_id, mode)
    if locked:
        msg = "Чат заблокирован. Нажми «Сброс персонажа», чтобы начать заново."
        if reason:
            msg = f"🚫 Чат заблокирован: 💀 {reason} 💀\n\n🔄 Нажми «Сброс персонажа», чтобы начать заново."
        await message.answer(msg, reply_markup=reset_current_kb())
        return

    model = MODE_TO_MODEL.get(mode, DEFAULT_MODEL)

    state = get_mode_state(user_id, mode)

    # Text recorded into chat history (no special mechanics for this mode)
    user_text_for_history = user_text


    append_history(user_id, mode, "user", user_text_for_history)
    history = get_history(user_id, mode)

    memory_block = format_state_block(state)
    
    if mode == "whore":
        rel_state = get_relationship_state(DB_PATH, user_id, mode)
        ghost_mood = check_ghosting(rel_state)
        if ghost_mood:
            rel_state.mood = ghost_mood

        analysis = analyze_user_message(user_text, rel_state)
        rel_state = update_relationship_from_analysis(rel_state, analysis)
        save_relationship_state(DB_PATH, rel_state)
        system_base = build_lika_system_prompt(rel_state)
    else:
        system_base = MODE_TO_SYSTEM_PROMPT.get(mode)
        if system_base is None:
            system_base = MODE_TO_SYSTEM_PROMPT["basic"]

    base = AUDIO_SYSTEM_PROMPT if (audio_only and mode != "whore") else system_base

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
            # default = home_fast
            chef_addon = (
                "\n\n[CHEF_SUBMODE=HOME_FAST]\n"
                "РАБОТАЙ В ДВЕ ФАЗЫ.\n"
                "КЛЮЧЕВОЕ ПРАВИЛО: СНАЧАЛА КОЛИЧЕСТВА, ПОТОМ РЕЦЕПТ.\n\n"

                "ФАЗА 1 — БЫСТРОЕ ПРОЕКТИРОВАНИЕ:\n"
                "- Уточни, НА СКОЛЬКО ПОРЦИЙ готовим.\n"
                "- Уточни или предложи КОЛИЧЕСТВА основных ингредиентов (в граммах/штуках).\n"
                "- Если пользователь не указал объёмы — предложи стандартные (например: 2 грудки = ~300 г).\n"
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
    style_addon = ""

    rap_addon = ""
    if mode == "oldschool_rep":
        sub = (state.get("rap_submode") or "story").strip().lower()
        if sub not in ("street", "story", "lyrical"):
            sub = "story"

        # Берём полноценный промпт подрежима из oldschool_rep.py
        from src.prompts.oldschool_rep import RAP_SUBMODE_PROMPTS, RAP_SUBMODE_DEFAULT_BPM
        
        submode_prompt = RAP_SUBMODE_PROMPTS.get(sub, RAP_SUBMODE_PROMPTS["story"])
        default_bpm = RAP_SUBMODE_DEFAULT_BPM.get(sub, 88)

        rap_addon = f'''

        {submode_prompt}

        BPM по умолчанию: {default_bpm}
        Если пользователь указал BPM явно — используй его.

        ВАЖНО:
        - Если пользователь указал "2 куплета" / "два куплета" — СРАЗУ пиши 2 куплета (без доп. вопросов).
        - Не задавай уточняющих вопросов о формате, если формат уже выбран.
        - Выводи только текст трека (без объяснений).

        '''

    style_addon = ""

    system_prompt = base + memory_block + chef_addon + rap_addon + style_addon
    messages = [{"role": "system", "content": system_prompt}] + history


    
    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(keep_typing(bot, message.chat.id, stop_event))

    try:
        temperature = MODE_TO_TEMPERATURE.get(mode)

        if temperature is None:
            temperature = MODE_TO_TEMPERATURE["basic"]

        temperature = float(temperature)

        max_tokens = int(MODE_TO_MAX_TOKENS.get(mode, MODE_TO_MAX_TOKENS.get("basic", 600)))
        freq_pen = float(MODE_TO_FREQUENCY_PENALTY.get(mode, MODE_TO_FREQUENCY_PENALTY.get("basic", 0.2)))
        
        # Переопределяем параметры только для unhinged-режима
        if mode == "unhinged":
            temperature = 1.3          # очень высокая — для дикого, непредсказуемого креатива
            max_tokens = 1000           # чтобы хватило на длинные безумные истории
            freq_pen = 0.0              # без наказания за повторы — даёт "маньячный" поток сознания
        # аудио: короче и стабильнее (как у тебя было), но через конфиги
        if audio_only and mode != "whore":
            max_tokens = 120
            temperature = min(temperature, 0.6)
            freq_pen = max(freq_pen, 0.2)

        # --- usage accumulator (tokens cost) ---
        prompt_tokens_sum = 0
        completion_tokens_sum = 0
        total_tokens_sum = 0
        tokens_source = ""

        # 1) первый проход
        reply_raw, finish_reason, usage = await call_openrouter_with_meta(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            frequency_penalty=freq_pen,
            timeout_s=90.0,
        )

        # accumulate usage from API (if present)
        pt = int((usage or {}).get("prompt_tokens") or 0)
        ct = int((usage or {}).get("completion_tokens") or 0)
        tt = int((usage or {}).get("total_tokens") or 0)
        prompt_tokens_sum += pt
        completion_tokens_sum += ct
        total_tokens_sum += tt
        if tt > 0:
            tokens_source = "api"


        reply_raw = strip_internal_thoughts(reply_raw)
        reply_raw = strip_scene_contract(reply_raw)


        # 2) если похоже на обрыв — добираем продолжение "под капотом"
        glued = reply_raw
        cont_round = 0

        while cont_round < MAX_AUTO_CONTINUATIONS and is_truncated_for_glue(glued, finish_reason):
            cont_round += 1

            cont_messages = (
                messages
                + [{"role": "assistant", "content": glued}]
                + [{"role": "user", "content": _CONTINUE_PROMPT}]
            )

            cont_text, cont_finish, cont_usage = await call_openrouter_with_meta(
                model=model,
                messages=cont_messages,
                temperature=temperature,
                max_tokens=max(220, int(max_tokens * 0.7)),
                frequency_penalty=freq_pen,
                timeout_s=90.0,
            )

            # accumulate usage from API (if present)
            pt = int((cont_usage or {}).get("prompt_tokens") or 0)
            ct = int((cont_usage or {}).get("completion_tokens") or 0)
            tt = int((cont_usage or {}).get("total_tokens") or 0)
            prompt_tokens_sum += pt
            completion_tokens_sum += ct
            total_tokens_sum += tt
            if tt > 0:
                tokens_source = "api"


            cont_text = strip_internal_thoughts(cont_text)
            cont_text = strip_scene_contract(cont_text)

            # если продолжение пустое — прекращаем
            if not (cont_text or "").strip():
                finish_reason = cont_finish
                break

            # склеиваем аккуратно (без дублей: добавим перевод строки)
            glued = (glued.rstrip() + "\n" + cont_text.lstrip()).strip()
            finish_reason = cont_finish

        # 3) финальная пост-обработка только ПОСЛЕ склейки
        reply = fix_truncated_reply(glued)
        reply = strip_internal_thoughts(reply)
        reply = strip_scene_contract(reply)
        reply = fix_truncated_reply(reply)

        # --- FINAL GUARD: prevent silent "empty reply" ---
        if not (reply or "").strip():
            logging.warning(
                "EMPTY FINAL REPLY: raw_len=%s glued_len=%s finish_reason=%r",
                len((reply_raw or "")),
                len((glued or "")),
                finish_reason,
            )
            # fallback: try to show something useful instead of silence
            fallback = (reply_raw or "").strip() or "Пустой ответ от модели. Переформулируй запрос одной фразой."
            await message.answer(fallback)
            stop_event.set()
            await typing_task
            return


        # If API didn't return usage, estimate tokens as fallback
        if total_tokens_sum <= 0:
            # для денег тебе важнее output, но можно и input оценить отдельно
            completion_tokens_sum = estimate_tokens(reply, model=model)
            prompt_tokens_sum = 0
            total_tokens_sum = completion_tokens_sum
            tokens_source = "tiktoken" if completion_tokens_sum > 0 else ""


    except Exception as e:
        # В логи — полная техническая информация
        logging.exception(
            "OpenRouter error (model=%s, user_id=%s)",
            model,
            user_id,
        )

        stop_event.set()
        await typing_task

        # Пользователю — мягкий, человеческий ответ
        if isinstance(
            e,
            (
                httpx.ConnectError,
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.PoolTimeout,
                httpx.ConnectTimeout,
            ),
        ):
            await message.answer("Ой, извини, я на секунду отвлеклась… можешь повторить?")
        else:
            await message.answer("Ой, извини, что-то пошло не так. Напиши ещё раз?")

        return
    
    # --- GAME OVER lock ---
    # --- LOG: assistant_reply (cost tracking) ---
    log_user_event(
        ts=int(time.time()),
        user_id=user_id,
        chat_id=int(message.chat.id) if message.chat else 0,
        username=(message.from_user.username or ""),
        first_name=(message.from_user.first_name or ""),
        event_type="assistant_reply",
        mode=mode,
        message_id=int(message.message_id),
        text_len=len(reply),               # символы ответа бота
        ok=1,
        llm_provider="openrouter",
        llm_model=model,
        prompt_tokens=prompt_tokens_sum,
        completion_tokens=completion_tokens_sum,
        total_tokens=total_tokens_sum,
        tokens_source=tokens_source,
    )

    # --- GAME OVER lock ---
    clean, triggered = strip_game_over_markers(reply)

    if triggered:
        lock_mode(user_id, mode, reason="GAME OVER")  # внутренний флаг, не показываем юзеру

        if clean:
            append_history(user_id, mode, "assistant", clean)

        # ТОЛЬКО эмодзи + кнопка/инструкция
        game_over_ui = (
            "💀 GAME OVER 💀\n"
            "🚫 Вас внесли в черный список.\n"
            "🔄 Нажми «Сброс персонажа», чтобы начать заново."
        )
        await message.answer(
            game_over_ui,
            parse_mode="Markdown",
            reply_markup=reset_current_kb()
        )
        return
    # --- /GAME OVER lock ---


    append_history(user_id, mode, "assistant", reply)


    # --- обновляем сюжетную память (MVP-обновление без второго вызова) ---
    try:
        # эпизод растёт каждый ход
        state["episode"] = int(state.get("episode", 1)) + 1

        # простой recap: 1-2 предложения из ответа (обрежем по длине)
        recap = reply.strip().replace("\n", " ")
        if len(recap) > 240:
            recap = recap[:240].rsplit(" ", 1)[0] + "…"
        state["recap"] = recap

        # timeline: добавим короткий пункт по ходу пользователя
        tl = state.get("timeline") or []
        user_line = user_text.strip().replace("\n", " ")
        if len(user_line) > 140:
            user_line = user_line[:140].rsplit(" ", 1)[0] + "…"
        tl.append(f"Ход: {user_line}")
        # ограничим размер
        state["timeline"] = tl[-40:]

        save_mode_state(user_id, mode, state)
    except Exception:
        logging.exception("Failed to update mode_state (user_id=%s mode=%s)", user_id, mode)
    # --- /обновление сюжетной памяти ---


    if audio_only:
             
        try:
            audio_bytes = await openai_tts(reply)
        except Exception as e:
            logging.exception("OpenAI TTS error")
            stop_event.set()
            await typing_task
            await message.answer(f"Не удалось сгенерировать аудио:\n{e}")
            return

        stop_event.set()
        await typing_task

        audio_file = BufferedInputFile(audio_bytes, filename="reply.mp3")
        await message.answer_audio(audio=audio_file, title="Lina (audio)")
        return

    stop_event.set()
    await typing_task

    for part in chunk_text(reply):
        await message.answer(part)

@dp.callback_query(F.data.startswith("setmodel:"))
async def on_set_model_callback(callback: types.CallbackQuery):
    await callback.answer("\u0412\u044b\u0431\u043e\u0440 \u043c\u043e\u0434\u0435\u043b\u0435\u0439 \u043e\u0442\u043a\u043b\u044e\u0447\u0451\u043d", show_alert=False)
    await callback.message.edit_text(
        MODEL_SELECTION_DISABLED_TEXT,
        reply_markup=None,
    )

@dp.callback_query(F.data == "imgcancel")
async def cb_imgcancel(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    job = IMAGE_JOBS.get(user_id)

    if not job:
        await callback.answer("Нечего отменять", show_alert=False)
        return

    # ставим флаг отмены
    cancel_event: asyncio.Event = job["cancel_event"]
    cancel_event.set()

    status_task: asyncio.Task | None = job.get("status_task")
    if status_task and not status_task.done():
        status_task.cancel()


    # пытаемся отменить задачу генерации (если жива)
    gen_task: asyncio.Task | None = job.get("gen_task")
    if gen_task and not gen_task.done():
        gen_task.cancel()

    # обновим статус-сообщение
    try:
        await callback.message.edit_text("⛔ Ок, отменил генерацию.", reply_markup=None)
    except Exception:
        pass

    await callback.answer("Отменено")


async def main():
    logging.info("DB_PATH=%s", DB_PATH)
    init_db()
    try:
        await dp.start_polling(bot)
    finally:
        await openrouter_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
