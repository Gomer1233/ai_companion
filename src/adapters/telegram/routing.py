from __future__ import annotations


MENU_TEXT_ROUTE = {
    "Режим": "mode",
    "Сброс": "reset_all",
    "Сброс всего": "reset_all",
    "Сброс персонажа": "reset_mode",
    "Хочу фото": "request_image",
    "Модели": "disabled_models",
    "Текущая модель": "disabled_models",
    "Помощь": "legacy_help",
    "Генерация ответа": "legacy_suggest",
    "🎤 Стиль": "rap_submode_menu",
    "Стиль": "rap_submode_menu",
}


def classify_menu_text(text: str | None) -> str | None:
    if not text:
        return None
    return MENU_TEXT_ROUTE.get(text.strip())


CALLBACK_ROUTES = (
    ("setmode:", "switch_mode"),
    ("chefmode:", "chef_submode"),
    ("rapmode:", "rap_submode"),
    ("setmodel:", "legacy_model_selection"),
)


def classify_callback_data(data: str | None) -> str | None:
    if not data:
        return None
    normalized = data.strip()
    if normalized == "remindctx":
        return "context_reminder"
    if normalized == "reset_current":
        return "reset_current_mode"
    if normalized == "imgcancel":
        return "cancel_image_job"
    for prefix, route in CALLBACK_ROUTES:
        if normalized.startswith(prefix):
            return route
    return None
