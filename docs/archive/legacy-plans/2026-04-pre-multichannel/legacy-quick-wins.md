# Быстрые улучшения (можно сделать за 1-2 часа)

## 1. Исправить баг в config/modes.py

**Проблема**: В строке 97 используется `"ngrok-4.1-fast"` вместо `"x-ai/grok-4.1-fast"`

```python
# Было:
model="ngrok-4.1-fast",

# Должно быть:
model="x-ai/grok-4.1-fast",
```

## 2. Добавить проверку на существование БД перед запуском

В `main.py` и `bot_lika.py` добавить проверку:

```python
if not Path(DB_PATH).parent.exists():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
```

## 3. Вынести константы в отдельный файл

Создать `src/config/constants.py`:

```python
# Константы для работы бота
HISTORY_LIMIT_DEFAULT = 12
MAX_AUTO_CONTINUATIONS_DEFAULT = 2
IMAGE_COOLDOWN_SEC_DEFAULT = 300
PHOTO_MIN_GAP_SEC = 6
PHOTO_COOLDOWN_SEC = 90
```

## 4. Добавить валидацию переменных окружения

Создать `src/config/validators.py`:

```python
from pydantic import BaseSettings, Field

class Settings(BaseSettings):
    telegram_token: str = Field(..., env="TELEGRAM_TOKEN")
    openrouter_api_key: str = Field(..., env="OPENROUTER_API_KEY")
    bot_db_path: str = Field(default="bot_state.db", env="BOT_DB_PATH")
    
    class Config:
        env_file = ".env"
```

## 5. Исправить дублирование импортов

В `main.py` и `bot_lika.py` есть дублирование `from pathlib import Path` (строки 13 и 26).

## 6. Добавить обработку KeyboardInterrupt

В функции `main()` добавить:

```python
async def main():
    logging.info("DB_PATH=%s", DB_PATH)
    init_db()
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    finally:
        await openrouter_client.aclose()
```

## 7. Улучшить сообщения об ошибках

Вместо:
```python
raise RuntimeError("Missing env TELEGRAM_TOKEN")
```

Использовать:
```python
raise RuntimeError(
    "Missing required environment variable: TELEGRAM_TOKEN\n"
    "Please create .env file based on .env.example"
)
```

## 8. Добавить версионирование

Создать `src/__version__.py`:

```python
__version__ = "1.0.0"
```

И использовать в логах при старте.

## 9. Исправить пути в export_user_report.py

Жестко прописанный путь:
```python
REPORTS_DIR = Path(r"D:\projects\bot_companion\Lina_AI\logs")
```

Должно быть:
```python
PROJECT_ROOT = Path(__file__).parent.parent
REPORTS_DIR = PROJECT_ROOT / "logs"
```

## 10. Добавить .env валидацию при старте

Проверять наличие обязательных переменных при запуске и выдавать понятные ошибки.
