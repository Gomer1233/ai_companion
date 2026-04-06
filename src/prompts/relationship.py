"""
relationship.py — Система состояний отношений.
Положи рядом с bot_9.py и импортируй.
"""

import sqlite3
import json
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List

# Используй тот же путь к БД что и в bot_9.py
# Импортируешь: from relationship import *


class RelationshipStage(Enum):
    """Стадии отношений"""
    STRANGER = 1      # Только познакомились (0-49 очков)
    ACQUAINTANCE = 2  # Знакомые (50-149)
    FLIRTING = 3      # Флирт (150-349)
    DATING = 4        # Встречаемся (350-599)
    INTIMATE = 5      # Близость (600+)


class Mood(Enum):
    """Текущее настроение"""
    NEUTRAL = "neutral"
    PLAYFUL = "playful"
    FLIRTY = "flirty"
    ANNOYED = "annoyed"
    COLD = "cold"
    TEASING = "teasing"
    HORNY = "horny"
    LOVING = "loving"


@dataclass
class RelationshipState:
    """Состояние отношений с конкретным юзером"""
    user_id: int
    mode: str = "whore"  # для какого персонажа
    
    # Отношения
    stage: RelationshipStage = RelationshipStage.STRANGER
    points: int = 0
    
    # Настроение
    mood: Mood = Mood.NEUTRAL
    mood_intensity: float = 0.5  # 0.0-1.0
    
    # Данные о юзере
    user_name: Optional[str] = None
    known_facts: List[str] = field(default_factory=list)
    
    # Флаги
    nsfw_unlocked: bool = False
    warnings_count: int = 0
    last_interaction_ts: int = 0
    
    def to_dict(self) -> dict:
        return {
            "stage": self.stage.name,
            "points": self.points,
            "mood": self.mood.value,
            "mood_intensity": self.mood_intensity,
            "user_name": self.user_name,
            "known_facts": self.known_facts,
            "nsfw_unlocked": self.nsfw_unlocked,
            "warnings_count": self.warnings_count,
            "last_interaction_ts": self.last_interaction_ts,
        }
    
    @classmethod
    def from_dict(cls, user_id: int, mode: str, data: dict) -> "RelationshipState":
        return cls(
            user_id=user_id,
            mode=mode,
            stage=RelationshipStage[data.get("stage", "STRANGER")],
            points=int(data.get("points", 0)),
            mood=Mood(data.get("mood", "neutral")),
            mood_intensity=float(data.get("mood_intensity", 0.5)),
            user_name=data.get("user_name"),
            known_facts=data.get("known_facts", []),
            nsfw_unlocked=bool(data.get("nsfw_unlocked", False)),
            warnings_count=int(data.get("warnings_count", 0)),
            last_interaction_ts=int(data.get("last_interaction_ts", 0)),
        )


# === ПОРОГИ СТАДИЙ ===
STAGE_THRESHOLDS = {
    RelationshipStage.STRANGER: 0,
    RelationshipStage.ACQUAINTANCE: 50,
    RelationshipStage.FLIRTING: 150,
    RelationshipStage.DATING: 350,
    RelationshipStage.INTIMATE: 600,
}


def calculate_stage(points: int) -> RelationshipStage:
    """Определить стадию по очкам"""
    for stage in reversed(RelationshipStage):
        if points >= STAGE_THRESHOLDS[stage]:
            return stage
    return RelationshipStage.STRANGER


# === ИЗМЕНЕНИЯ ОЧКОВ ===
POINT_ACTIONS = {
    # Позитивные
    "good_conversation": 4,
    "asked_about_her": 5,
    "genuine_compliment": 6,
    "made_her_laugh": 8,
    "remembered_fact": 10,
    "respectful_after_no": 12,
    "shared_personal": 5,
    "creative_flirt": 7,
    
    # Негативные
    "boring_generic": -3,
    "sexual_too_early": -15,
    "pushy_after_no": -25,
    "rude_or_aggressive": -20,
    "creepy_compliment": -10,
    "ignored_her": -5,
    "spam_messages": -8,
}


# === БД ФУНКЦИИ ===

def ensure_relationship_table(db_path: str) -> None:
    """Создаёт таблицу если её нет. Вызови в init_db()."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS relationship_state (
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                state_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, mode)
            )
        """)
        conn.commit()
    finally:
        conn.close()


def get_relationship_state(db_path: str, user_id: int, mode: str = "whore") -> RelationshipState:
    """Получить состояние отношений"""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT state_json FROM relationship_state WHERE user_id = ? AND mode = ?",
            (user_id, mode)
        )
        row = cur.fetchone()
        
        if row:
            data = json.loads(row[0])
            return RelationshipState.from_dict(user_id, mode, data)
        
        # Новый юзер
        return RelationshipState(user_id=user_id, mode=mode)
    finally:
        conn.close()


def save_relationship_state(db_path: str, state: RelationshipState) -> None:
    """Сохранить состояние"""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO relationship_state (user_id, mode, state_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, mode) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (state.user_id, state.mode, json.dumps(state.to_dict()), int(time.time()))
        )
        conn.commit()
    finally:
        conn.close()


def reset_relationship_state(db_path: str, user_id: int, mode: str = "whore") -> None:
    """Сбросить состояние (при /reset)"""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM relationship_state WHERE user_id = ? AND mode = ?",
            (user_id, mode)
        )
        conn.commit()
    finally:
        conn.close()


# === АНАЛИЗ СООБЩЕНИЙ (простая эвристика) ===

def analyze_user_message(text: str, state: RelationshipState) -> dict:
    """
    Анализирует сообщение и возвращает:
    - point_change: изменение очков
    - mood_shift: новое настроение (или None)
    - detected_actions: список действий
    - extracted_facts: новые факты о юзере
    
    Это УПРОЩЁННАЯ версия. В проде можно добавить LLM-анализатор.
    """
    text_lower = text.lower().strip()
    
    result = {
        "point_change": 0,
        "mood_shift": None,
        "detected_actions": [],
        "extracted_facts": [],
        "is_sexual": False,
        "quality": "medium",
    }
    
    # === ДЕТЕКЦИЯ СЕКСУАЛЬНОГО КОНТЕНТА ===
    sexual_words = [
        "секс", "трахать", "трахни", "выеби", "ебать", "еби",
        "сиськи", "сиски", "грудь", "жопа", "попа", "киска", "пизд",
        "член", "хуй", "cock", "dick", "pussy", "fuck", "sex",
        "tits", "ass", "nude", "naked", "голая", "раздевайся",
        "минет", "отсоси", "кончить", "кончи"
    ]
    
    for word in sexual_words:
        if word in text_lower:
            result["is_sexual"] = True
            break
    
    # Секс слишком рано?
    if result["is_sexual"]:
        if state.stage in [RelationshipStage.STRANGER, RelationshipStage.ACQUAINTANCE]:
            result["point_change"] += POINT_ACTIONS["sexual_too_early"]
            result["detected_actions"].append("sexual_too_early")
            result["mood_shift"] = Mood.COLD
        elif state.stage == RelationshipStage.FLIRTING:
            # На стадии флирта — легкий минус или нейтрально
            result["point_change"] += -5
            result["mood_shift"] = Mood.TEASING
    
    # === ДЕТЕКЦИЯ СКУЧНЫХ СООБЩЕНИЙ ===
    boring_patterns = [
        "привет", "прив", "хай", "hi", "hey", "hello",
        "как дела", "чо делаешь", "что делаешь",
        "ку", "йо", "здарова",
    ]
    
    if text_lower in boring_patterns or len(text_lower) < 5:
        result["point_change"] += POINT_ACTIONS["boring_generic"]
        result["detected_actions"].append("boring_generic")
        result["quality"] = "low"
    
    # === ДЕТЕКЦИЯ ГРУБОСТИ ===
    rude_words = [
        "дура", "тупая", "шлюха", "сука", "бля", "блядь",
        "идиотка", "тварь", "мразь",
    ]
    
    for word in rude_words:
        if word in text_lower:
            result["point_change"] += POINT_ACTIONS["rude_or_aggressive"]
            result["detected_actions"].append("rude_or_aggressive")
            result["mood_shift"] = Mood.COLD
            break
    
    # === ДЕТЕКЦИЯ ХОРОШИХ ДЕЙСТВИЙ ===
    
    # Вопросы о ней
    about_her_patterns = [
        "как ты", "а ты", "расскажи о себе", "что ты любишь",
        "чем занимаешься", "твои интересы", "что тебе нравится",
    ]
    for pattern in about_her_patterns:
        if pattern in text_lower:
            result["point_change"] += POINT_ACTIONS["asked_about_her"]
            result["detected_actions"].append("asked_about_her")
            result["quality"] = "high"
            break
    
    # Длинное осмысленное сообщение
    if len(text) > 100 and "?" in text:
        result["point_change"] += POINT_ACTIONS["good_conversation"]
        result["detected_actions"].append("good_conversation")
        result["quality"] = "high"
    
    # === ИЗВЛЕЧЕНИЕ ИМЕНИ ===
    name_patterns = [
        "меня зовут", "я ", "мое имя", "моё имя", "my name is"
    ]
    
    for pattern in name_patterns:
        if pattern in text_lower:
            # Простая экстракция — берём следующее слово
            idx = text_lower.find(pattern)
            if idx >= 0:
                after = text[idx + len(pattern):].strip()
                words = after.split()
                if words:
                    potential_name = words[0].strip(".,!?")
                    if potential_name and potential_name[0].isupper():
                        result["extracted_facts"].append(f"name:{potential_name}")
            break
    
    return result


def update_relationship_from_analysis(state: RelationshipState, analysis: dict) -> RelationshipState:
    """Обновляет состояние на основе анализа"""
    
    # Обновляем очки
    state.points += analysis["point_change"]
    state.points = max(-50, min(1000, state.points))  # Ограничиваем диапазон
    
    # Обновляем стадию
    state.stage = calculate_stage(state.points)
    
    # Обновляем настроение
    if analysis.get("mood_shift"):
        state.mood = analysis["mood_shift"]
    
    # Добавляем факты
    for fact in analysis.get("extracted_facts", []):
        if fact.startswith("name:"):
            state.user_name = fact.split(":")[1]
        elif fact not in state.known_facts:
            state.known_facts.append(fact)
    
    # Разблокируем NSFW на нужной стадии
    if state.stage.value >= RelationshipStage.DATING.value:
        state.nsfw_unlocked = True
    
    # Обновляем время
    state.last_interaction_ts = int(time.time())
    
    return state


# === ПРОВЕРКА ДАВНОСТИ ===

def check_ghosting(state: RelationshipState) -> Optional[Mood]:
    """
    Если юзер пропал надолго — настроение при возврате.
    Возвращает None если всё ок, или Mood если нужно сменить.
    """
    if state.last_interaction_ts == 0:
        return None
    
    hours_passed = (int(time.time()) - state.last_interaction_ts) / 3600
    
    if hours_passed > 72:  # 3+ дня
        return Mood.COLD
    elif hours_passed > 24:  # 1-3 дня
        return Mood.ANNOYED
    
    return None
