from __future__ import annotations

from aiogram import types

from src.core.contracts import InboundEvent, InboundEventType, UserRef


def telegram_user_ref(user_id: int) -> UserRef:
    return UserRef(str(user_id))


def resolve_conversation_for_user(repositories, user_id: int):
    user_ref = telegram_user_ref(user_id)
    conversation = repositories.load_active_conversation_for_user(user_ref)
    if conversation is not None:
        return conversation
    return repositories.ensure_default_conversation(user_ref)


def parse_message_event(
    message: types.Message,
    repositories,
    *,
    event_type: InboundEventType,
    mode: str | None = None,
    text: str | None = None,
    job_id: str | None = None,
    payload: dict | None = None,
) -> InboundEvent:
    if message.from_user is None:
        raise ValueError("message.from_user is required")
    user_ref = telegram_user_ref(message.from_user.id)
    conversation = resolve_conversation_for_user(repositories, message.from_user.id)
    resolved_text = text if text is not None else (message.text or None)
    return InboundEvent(
        event_type=event_type,
        user_ref=user_ref,
        conversation_ref=conversation.conversation_ref,
        mode=mode,
        text=resolved_text,
        job_id=job_id,
        payload=payload or {},
    )


def parse_callback_event(
    callback: types.CallbackQuery,
    repositories,
    *,
    event_type: InboundEventType,
    mode: str | None = None,
    text: str | None = None,
    job_id: str | None = None,
    payload: dict | None = None,
) -> InboundEvent:
    user_ref = telegram_user_ref(callback.from_user.id)
    conversation = resolve_conversation_for_user(repositories, callback.from_user.id)
    return InboundEvent(
        event_type=event_type,
        user_ref=user_ref,
        conversation_ref=conversation.conversation_ref,
        mode=mode,
        text=text,
        job_id=job_id,
        payload=payload or {},
    )


def parse_user_text_event(message: types.Message, repositories) -> InboundEvent:
    return parse_message_event(message, repositories, event_type=InboundEventType.USER_TEXT)


def parse_request_image_event(message: types.Message, repositories) -> InboundEvent:
    return parse_message_event(message, repositories, event_type=InboundEventType.REQUEST_IMAGE)


def parse_reset_user_all_event(message: types.Message, repositories) -> InboundEvent:
    return parse_message_event(message, repositories, event_type=InboundEventType.RESET_USER_ALL)


def parse_reset_mode_event(message: types.Message, repositories, mode: str) -> InboundEvent:
    return parse_message_event(
        message,
        repositories,
        event_type=InboundEventType.RESET_MODE_IN_CONVERSATION,
        mode=mode,
    )


def parse_reset_mode_callback_event(callback: types.CallbackQuery, repositories, mode: str) -> InboundEvent:
    return parse_callback_event(
        callback,
        repositories,
        event_type=InboundEventType.RESET_MODE_IN_CONVERSATION,
        mode=mode,
    )


def parse_switch_mode_callback_event(callback: types.CallbackQuery, repositories) -> InboundEvent:
    if callback.data is None:
        raise ValueError("callback.data is required")
    mode = callback.data.split(':', 1)[1].strip()
    return parse_callback_event(
        callback,
        repositories,
        event_type=InboundEventType.SWITCH_MODE,
        mode=mode,
        payload={'callback_data': callback.data},
    )


def parse_context_reminder_callback_event(callback: types.CallbackQuery, repositories, mode: str) -> InboundEvent:
    return parse_callback_event(
        callback,
        repositories,
        event_type=InboundEventType.REQUEST_CONTEXT_REMINDER,
        mode=mode,
        payload={'callback_data': callback.data},
    )


def parse_cancel_job_callback_event(callback: types.CallbackQuery, repositories, job_id: str) -> InboundEvent:
    return parse_callback_event(
        callback,
        repositories,
        event_type=InboundEventType.CANCEL_JOB,
        job_id=job_id,
        payload={'callback_data': callback.data},
    )
