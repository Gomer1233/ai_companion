from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def _get_str(env: Mapping[str, str], key: str, default: str = "") -> str:
    return env.get(key, default).strip()


def _get_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    return int(raw.strip())


def _get_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    return float(raw.strip())


def _get_bool(env: Mapping[str, str], key: str, default: bool = False) -> bool:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_csv_set(env: Mapping[str, str], key: str, default: str = "") -> set[str]:
    raw = env.get(key, default)
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _get_csv_tuple(env: Mapping[str, str], key: str, default: str = "") -> tuple[str, ...]:
    raw = env.get(key, default)
    return tuple(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    telegram_token: str
    openrouter_api_key: str
    openai_api_key: str
    modelslab_api_key: str
    modelslab_model_id: str
    modelslab_lora_model: str
    modelslab_width: int
    modelslab_height: int
    modelslab_steps: int
    modelslab_guidance: float
    modelslab_negative_prompt: str
    modelslab_scheduler: str
    modelslab_enhance_prompt: bool
    openai_image_model: str
    openai_image_size: str
    image_cooldown_sec: int
    openai_tts_model: str
    openai_tts_voice: str
    openai_tts_format: str
    elevenlabs_api_key: str
    elevenlabs_voice_id: str
    elevenlabs_model_id: str
    elevenlabs_output_format: str
    image_backend_provider: str
    openrouter_image_model: str
    openrouter_image_model_default: str
    openrouter_site_url: str
    openrouter_app_name: str
    tog_api_key: str
    tog_base_url: str
    tog_image_model: str
    tog_width: int
    tog_height: int
    prompt_translation_enabled: bool
    prompt_translation_target_lang: str
    prompt_translation_for: set[str]
    prompt_translation_engine: str
    translation_model: str
    prompt_translation_debug: bool
    bot_db_path: str
    default_model: str
    judge_model_whore: str
    judge_max_tokens: int
    history_limit: int
    max_auto_continuations: int
    report_xlsx: str
    http_host: str
    http_port: int
    http_cors_origins: tuple[str, ...]
    http_session_ttl_sec: int
    http_telegram_init_max_age_sec: int
    http_session_rate_limit_window_sec: int
    http_session_rate_limit_max_attempts: int

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        project_root: Path | None = None,
    ) -> "Settings":
        source = env or os.environ
        root = project_root or Path(__file__).resolve().parents[2]
        return cls(
            project_root=root,
            telegram_token=_get_str(source, "TELEGRAM_TOKEN"),
            openrouter_api_key=_get_str(source, "OPENROUTER_API_KEY"),
            openai_api_key=_get_str(source, "OPENAI_API_KEY"),
            modelslab_api_key=_get_str(source, "MODELSLAB_API_KEY"),
            modelslab_model_id=_get_str(source, "MODELSLAB_MODEL_ID"),
            modelslab_lora_model=_get_str(source, "MODELSLAB_LORA_MODEL"),
            modelslab_width=_get_int(source, "MODELSLAB_WIDTH", 1024),
            modelslab_height=_get_int(source, "MODELSLAB_HEIGHT", 1024),
            modelslab_steps=_get_int(source, "MODELSLAB_STEPS", 30),
            modelslab_guidance=_get_float(source, "MODELSLAB_GUIDANCE", 7.5),
            modelslab_negative_prompt=_get_str(source, "MODELSLAB_NEGATIVE_PROMPT"),
            modelslab_scheduler=_get_str(source, "MODELSLAB_SCHEDULER", "DPMSolverMultistepScheduler"),
            modelslab_enhance_prompt=_get_bool(source, "MODELSLAB_ENHANCE_PROMPT", False),
            openai_image_model=_get_str(source, "OPENAI_IMAGE_MODEL", "gpt-image-1"),
            openai_image_size=_get_str(source, "OPENAI_IMAGE_SIZE", "1024x1024"),
            image_cooldown_sec=_get_int(source, "IMAGE_COOLDOWN_SEC", 300),
            openai_tts_model=_get_str(source, "OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            openai_tts_voice=_get_str(source, "OPENAI_TTS_VOICE", "alloy"),
            openai_tts_format=_get_str(source, "OPENAI_TTS_FORMAT", "mp3"),
            elevenlabs_api_key=_get_str(source, "ELEVENLABS_API_KEY"),
            elevenlabs_voice_id=_get_str(source, "ELEVENLABS_VOICE_ID"),
            elevenlabs_model_id=_get_str(source, "ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
            elevenlabs_output_format=_get_str(source, "ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128"),
            image_backend_provider=_get_str(source, "IMAGE_BACKEND_PROVIDER", "openrouter").lower(),
            openrouter_image_model=_get_str(source, "OPENROUTER_IMAGE_MODEL", "sourceful/riverflow-v2-max-preview"),
            openrouter_image_model_default=_get_str(
                source,
                "OPENROUTER_IMAGE_MODEL_DEFAULT",
                "sourceful/riverflow-v2-max-preview",
            ),
            openrouter_site_url=_get_str(source, "OPENROUTER_SITE_URL", "http://localhost"),
            openrouter_app_name=_get_str(source, "OPENROUTER_APP_NAME", "tg-model-tester"),
            tog_api_key=_get_str(source, "TOG_API_KEY"),
            tog_base_url=_get_str(source, "TOG_BASE_URL", "https://api.together.xyz/v1"),
            tog_image_model=_get_str(source, "TOG_IMAGE_MODEL", "black-forest-labs/FLUX.1.1-pro"),
            tog_width=_get_int(source, "TOG_WIDTH", 1024),
            tog_height=_get_int(source, "TOG_HEIGHT", 1024),
            prompt_translation_enabled=_get_bool(source, "PROMPT_TRANSLATION_ENABLED", False),
            prompt_translation_target_lang=_get_str(source, "PROMPT_TRANSLATION_TARGET_LANG", "en"),
            prompt_translation_for=_get_csv_set(source, "PROMPT_TRANSLATION_FOR", "modelslab"),
            prompt_translation_engine=_get_str(source, "PROMPT_TRANSLATION_ENGINE", "openai").lower(),
            translation_model=_get_str(source, "TRANSLATION_MODEL", "gpt-4o-mini"),
            prompt_translation_debug=_get_bool(source, "PROMPT_TRANSLATION_DEBUG", False),
            bot_db_path=_get_str(source, "BOT_DB_PATH", str(root / "bot_state.db")),
            default_model=_get_str(source, "DEFAULT_MODEL", "openai/gpt-4o-mini"),
            judge_model_whore=_get_str(source, "JUDGE_MODEL_WHORE", "openai/gpt-4o-mini"),
            judge_max_tokens=_get_int(source, "JUDGE_MAX_TOKENS", 220),
            history_limit=_get_int(source, "HISTORY_LIMIT", 12),
            max_auto_continuations=_get_int(source, "MAX_AUTO_CONTINUATIONS", 2),
            report_xlsx=_get_str(source, "REPORT_XLSX", "user_report.xlsx"),
            http_host=_get_str(source, "HTTP_HOST", "0.0.0.0"),
            http_port=_get_int(source, "HTTP_PORT", 8000),
            http_cors_origins=_get_csv_tuple(source, "HTTP_CORS_ORIGINS"),
            http_session_ttl_sec=_get_int(source, "HTTP_SESSION_TTL_SEC", 3600),
            http_telegram_init_max_age_sec=_get_int(source, "HTTP_TELEGRAM_INIT_MAX_AGE_SEC", 90),
            http_session_rate_limit_window_sec=_get_int(source, "HTTP_SESSION_RATE_LIMIT_WINDOW_SEC", 60),
            http_session_rate_limit_max_attempts=_get_int(source, "HTTP_SESSION_RATE_LIMIT_MAX_ATTEMPTS", 5),
        )
