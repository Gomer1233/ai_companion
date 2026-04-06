from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.adapters.telegram.parser import (
    parse_cancel_job_callback_event,
    parse_context_reminder_callback_event,
    parse_reset_user_all_event,
    parse_switch_mode_callback_event,
    parse_user_text_event,
    resolve_conversation_for_user,
)
from src.adapters.telegram.renderer import render_core_response
from src.adapters.telegram.routing import classify_callback_data, classify_menu_text
from src.core.contracts import (
    ConversationRecord,
    ConversationRef,
    ConversationStatus,
    CoreResponse,
    InboundEventType,
    OutboundItem,
    OutboundItemType,
    UserRef,
)


class FakeRepositories:
    def __init__(self, conversation: ConversationRecord | None = None) -> None:
        self._conversation = conversation
        self.ensure_calls: list[str] = []

    def load_active_conversation_for_user(self, user_ref: UserRef):
        return self._conversation

    def ensure_default_conversation(self, user_ref: UserRef):
        self.ensure_calls.append(user_ref.value)
        self._conversation = ConversationRecord(
            user_ref=user_ref,
            conversation_ref=ConversationRef(f"conv-{user_ref.value}-default"),
            active_mode='basic',
            status=ConversationStatus.ACTIVE,
            is_default=True,
        )
        return self._conversation


class FakeMessage:
    def __init__(self, text: str = 'hello', user_id: int = 1) -> None:
        self.text = text
        self.from_user = SimpleNamespace(id=user_id, username='user', first_name='User')
        self.chat = SimpleNamespace(id=900)
        self.message_id = 7
        self.answers: list[dict] = []
        self.photos: list[dict] = []
        self.audios: list[dict] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append({'text': text, **kwargs})

    async def answer_photo(self, photo, **kwargs) -> None:
        self.photos.append({'photo': photo, **kwargs})

    async def answer_audio(self, audio, **kwargs) -> None:
        self.audios.append({'audio': audio, **kwargs})


class FakeCallback:
    def __init__(self, data: str, user_id: int = 1) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=user_id, username='user', first_name='User')
        self.message = FakeMessage(user_id=user_id)


@pytest.mark.asyncio
async def test_renderer_preserves_item_order() -> None:
    target = FakeMessage()
    response = CoreResponse(
        items=[
            OutboundItem(item_type=OutboundItemType.TEXT, text='first'),
            OutboundItem(item_type=OutboundItemType.PROGRESS, text='second'),
            OutboundItem(item_type=OutboundItemType.DEFERRED_RESULT, text='third'),
        ]
    )

    await render_core_response(target, response, reply_markup='menu')

    assert [item['text'] for item in target.answers] == ['first', 'second', 'third']
    assert target.answers[0]['reply_markup'] == 'menu'
    assert target.answers[1].get('reply_markup') is None


def test_parser_uses_existing_active_conversation() -> None:
    conversation = ConversationRecord(
        user_ref=UserRef('1'),
        conversation_ref=ConversationRef('conv-1-existing'),
        active_mode='chef',
        status=ConversationStatus.ACTIVE,
    )
    repositories = FakeRepositories(conversation)
    event = parse_user_text_event(FakeMessage('hello', user_id=1), repositories)

    assert event.event_type == InboundEventType.USER_TEXT
    assert event.conversation_ref == conversation.conversation_ref
    assert repositories.ensure_calls == []


def test_parser_creates_default_conversation_when_missing() -> None:
    repositories = FakeRepositories()
    conversation = resolve_conversation_for_user(repositories, 5)
    event = parse_reset_user_all_event(FakeMessage('/reset', user_id=5), repositories)

    assert conversation.is_default is True
    assert repositories.ensure_calls == ['5']
    assert event.user_ref == UserRef('5')


def test_callback_parser_maps_switch_mode_and_cancel_job() -> None:
    repositories = FakeRepositories()
    switch_event = parse_switch_mode_callback_event(FakeCallback('setmode:chef', user_id=8), repositories)
    cancel_event = parse_cancel_job_callback_event(FakeCallback('imgcancel', user_id=8), repositories, 'job-1')
    reminder_event = parse_context_reminder_callback_event(FakeCallback('remindctx', user_id=8), repositories, 'chef')

    assert switch_event.event_type == InboundEventType.SWITCH_MODE
    assert switch_event.mode == 'chef'
    assert cancel_event.event_type == InboundEventType.CANCEL_JOB
    assert cancel_event.job_id == 'job-1'
    assert reminder_event.event_type == InboundEventType.REQUEST_CONTEXT_REMINDER
    assert reminder_event.mode == 'chef'


def test_routing_classifies_menu_and_callbacks() -> None:
    assert classify_menu_text('\u0420\u0435\u0436\u0438\u043c') == 'mode'
    assert classify_menu_text('\u0421\u0431\u0440\u043e\u0441 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u0436\u0430') == 'reset_mode'
    assert classify_callback_data('setmode:basic') == 'switch_mode'
    assert classify_callback_data('remindctx') == 'context_reminder'
    assert classify_callback_data('imgcancel') == 'cancel_image_job'
