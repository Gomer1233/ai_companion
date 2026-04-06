# ИНСТРУКЦИЯ: Интеграция системы состояний в bot_9.py

## Шаг 1: Скопируй файлы

Положи рядом с `bot_9.py`:
- `relationship.py`
- `lika_prompt.py`

## Шаг 2: Добавь импорты (в начало bot_9.py)

```python
# После остальных импортов добавь:
from relationship import (
    ensure_relationship_table,
    get_relationship_state,
    save_relationship_state,
    reset_relationship_state,
    analyze_user_message,
    update_relationship_from_analysis,
    check_ghosting,
    RelationshipStage,
    Mood,
)
from lika_prompt import build_lika_system_prompt
```

## Шаг 3: Инициализация таблицы (в функции init_db)

Найди функцию `init_db()` (примерно строка 531) и добавь в конец:

```python
def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        # ... весь существующий код ...
        
        # ДОБАВЬ ЭТО В КОНЕЦ (перед conn.commit()):
        ensure_relationship_table(DB_PATH)
        
        conn.commit()
    finally:
        conn.close()
```

## Шаг 4: Модифицируй обработчик сообщений

Найди место где обрабатывается режим "whore" (примерно строка 2760-2830).

БЫЛО:
```python
    system_base = MODE_TO_SYSTEM_PROMPT.get(mode)
    if system_base is None:
        system_base = MODE_TO_SYSTEM_PROMPT["basic"]

    base = AUDIO_SYSTEM_PROMPT if (audio_only and mode != "whore") else system_base
```

СТАЛО:
```python
    # === ДИНАМИЧЕСКИЙ ПРОМПТ ДЛЯ WHORE ===
    if mode == "whore":
        # Получаем состояние отношений
        rel_state = get_relationship_state(DB_PATH, user_id, mode)
        
        # Проверяем не пропадал ли юзер
        ghost_mood = check_ghosting(rel_state)
        if ghost_mood:
            rel_state.mood = ghost_mood
        
        # Анализируем текущее сообщение
        analysis = analyze_user_message(user_text, rel_state)
        
        # Обновляем состояние
        rel_state = update_relationship_from_analysis(rel_state, analysis)
        
        # Сохраняем
        save_relationship_state(DB_PATH, rel_state)
        
        # Строим динамический промпт
        system_base = build_lika_system_prompt(rel_state)
    else:
        system_base = MODE_TO_SYSTEM_PROMPT.get(mode)
        if system_base is None:
            system_base = MODE_TO_SYSTEM_PROMPT["basic"]

    base = AUDIO_SYSTEM_PROMPT if (audio_only and mode != "whore") else system_base
```

## Шаг 5: Добавь команду /status для дебага

Добавь новый хендлер (где-нибудь рядом с другими командами):

```python
@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Показывает текущее состояние отношений (для дебага)"""
    user_id = message.from_user.id
    profile = get_user_profile(user_id)
    mode = (profile.get("mode") or "basic").strip()
    
    if mode != "whore":
        await message.answer("Команда работает только в режиме Лика")
        return
    
    rel_state = get_relationship_state(DB_PATH, user_id, mode)
    
    status_text = (
        f"📊 **Статус отношений**\n\n"
        f"👤 Имя: {rel_state.user_name or 'неизвестно'}\n"
        f"💕 Стадия: {rel_state.stage.name}\n"
        f"🎯 Очки: {rel_state.points}\n"
        f"😊 Настроение: {rel_state.mood.value}\n"
        f"🔥 NSFW: {'✅' if rel_state.nsfw_unlocked else '❌'}\n"
        f"📝 Факты: {len(rel_state.known_facts)}"
    )
    
    await message.answer(status_text, parse_mode="Markdown")
```

## Шаг 6: Модифицируй сброс персонажа

Найди где обрабатывается сброс персонажа и добавь сброс состояния:

```python
# Где-то в обработчике сброса добавь:
reset_relationship_state(DB_PATH, user_id, mode)
```

---

## Проверка

После изменений:

1. Запусти бота
2. Напиши `/start`, выбери режим "Лика"  
3. Напиши "привет" — должна отреагировать скучающе
4. Напиши что-то интересное, задай вопрос о ней
5. Напиши `/status` — увидишь текущие очки и стадию
6. Попробуй написать что-то пошлое — должна отшить
7. Продолжай общаться, следи как меняются очки

---

## Тонкая настройка

Если нужно изменить:

**Скорость прогрессии** — меняй `POINT_ACTIONS` в `relationship.py`
**Пороги стадий** — меняй `STAGE_THRESHOLDS` в `relationship.py`
**Характер Лики** — меняй `BASE_PERSONA` в `lika_prompt.py`
**Поведение на стадиях** — меняй `STAGE_INSTRUCTIONS` в `lika_prompt.py`

---

## Частые проблемы

**Бот не запускается:**
- Проверь что файлы лежат в той же папке
- Проверь импорты

**Состояние не сохраняется:**
- Проверь что `ensure_relationship_table(DB_PATH)` вызывается
- Посмотри файл БД — должна появиться таблица `relationship_state`

**Поведение странное:**
- Добавь логирование в `analyze_user_message`
- Проверь что `build_lika_system_prompt` вызывается
