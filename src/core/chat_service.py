from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

import httpx

from src.app.settings import Settings
from src.core.access_policy import AccessPolicyService, ExplicitCapability, ExplicitPolicyInput
from src.core.contracts import ConversationRecord, ConversationRef, UserRef
from src.core.monetization import MonetizationService
from src.core.runtime_helpers import (
    call_openrouter_with_meta,
    fix_truncated_reply,
    maybe_await,
    strip_internal_thoughts,
    strip_scene_contract,
)

ChatResponder = Callable[..., str | Awaitable[str]]


@dataclass(frozen=True, slots=True)
class MiniAppChatError(Exception):
    code: str


def miniapp_conversation_ref(user_ref: UserRef, mode: str) -> ConversationRef:
    user_part = _stable_ref_part(user_ref.value)
    mode_part = _stable_ref_part(mode)
    return ConversationRef(f"miniapp:{user_part}:{mode_part}")


def ensure_miniapp_conversation(repositories: Any, user_ref: UserRef, mode: str) -> ConversationRecord:
    conversation_ref = miniapp_conversation_ref(user_ref, mode)
    existing = repositories.load_conversation(user_ref, conversation_ref)
    if existing is not None:
        return existing
    return repositories.create_conversation(
        user_ref,
        active_mode=mode,
        is_default=False,
        conversation_ref=conversation_ref,
    )


class MiniAppChatService:
    def __init__(
        self,
        *,
        repositories: Any,
        monetization: MonetizationService,
        responder: ChatResponder,
        now_fn: Callable[[], int] | None = None,
    ) -> None:
        self.repositories = repositories
        self.monetization = monetization
        self.responder = responder
        self.now_fn = now_fn or (lambda: int(time.time()))

    def list_messages(self, user_ref: UserRef, mode: str) -> list[dict[str, Any]]:
        conversation = ensure_miniapp_conversation(self.repositories, user_ref, mode)
        return self.repositories.load_history_records(user_ref, conversation.conversation_ref, mode)

    def last_message(self, user_ref: UserRef, mode: str) -> dict[str, Any] | None:
        conversation_ref = miniapp_conversation_ref(user_ref, mode)
        conversation = self.repositories.load_conversation(user_ref, conversation_ref)
        if conversation is None:
            return None
        messages = self.repositories.load_history_records(user_ref, conversation.conversation_ref, mode)
        return messages[-1] if messages else None

    async def send_message(
        self,
        *,
        user_ref: UserRef,
        mode: str,
        text: str,
    ) -> dict[str, Any]:
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            raise MiniAppChatError("empty_message")

        now_ts = self.now_fn()
        persona_decision = self.monetization.can_use_persona(user_ref, mode, now_ts)
        if not persona_decision.allowed:
            raise MiniAppChatError("persona_locked")

        message_decision = self.monetization.can_send_message(user_ref, now_ts)
        if not message_decision.allowed:
            raise MiniAppChatError("usage_limit_exceeded")

        conversation = ensure_miniapp_conversation(self.repositories, user_ref, mode)
        history = self.repositories.load_history_records(user_ref, conversation.conversation_ref, mode)
        responder_messages = [_message_payload(item) for item in history] + [{"role": "user", "content": cleaned_text}]

        assistant_text = await maybe_await(
            self.responder(mode=mode, messages=responder_messages, user_text=cleaned_text)
        )
        assistant_text = (assistant_text or "").strip()
        if not assistant_text:
            raise MiniAppChatError("assistant_empty")

        self.repositories.append_history(
            user_ref,
            conversation.conversation_ref,
            mode,
            "user",
            cleaned_text,
            created_at=now_ts,
        )
        history_after_user = self.repositories.load_history_records(user_ref, conversation.conversation_ref, mode)
        user_message = history_after_user[-1]

        assistant_ts = self.now_fn()
        self.repositories.append_history(
            user_ref,
            conversation.conversation_ref,
            mode,
            "assistant",
            assistant_text,
            created_at=assistant_ts,
        )
        updated_history = self.repositories.load_history_records(user_ref, conversation.conversation_ref, mode)
        assistant_message = updated_history[-1]
        used = self.monetization.record_message_usage(user_ref, now_ts=self.now_fn())
        snapshot = self.monetization.get_access_snapshot(user_ref, now_ts=self.now_fn())
        return {
            "user_message": user_message,
            "assistant_message": assistant_message,
            "usage": {
                "messages": {
                    "used": used,
                    "limit": snapshot.limits.messages_per_day,
                    "reset_at": snapshot.usage.reset_at,
                }
            },
        }


def build_default_chat_responder(
    settings: Settings,
    *,
    access_policy: AccessPolicyService | None = None,
) -> ChatResponder:
    resolved_access_policy = access_policy or AccessPolicyService.alpha_default()

    async def responder(*, mode: str, messages: list[dict[str, str]], user_text: str) -> str:
        from src.config.modes import MODE_TO_MODEL, MODE_TO_SYSTEM_PROMPT, MODE_TO_TEMPERATURE

        system_prompt = MODE_TO_SYSTEM_PROMPT.get(mode) or MODE_TO_SYSTEM_PROMPT["basic"]
        model = MODE_TO_MODEL.get(mode, settings.default_model)
        text_decision = resolved_access_policy.authorize_explicit(
            ExplicitPolicyInput(
                mode=mode,
                capability=ExplicitCapability.TEXT,
                provider="openrouter",
                model=model,
            )
        )
        if not text_decision.allowed:
            raise RuntimeError(f"Explicit text request blocked: {', '.join(text_decision.reasons)}")

        temperature = float(MODE_TO_TEMPERATURE.get(mode, MODE_TO_TEMPERATURE.get("basic", 0.7)))
        async with httpx.AsyncClient(timeout=90.0) as client:
            reply, finish_reason, _usage = await call_openrouter_with_meta(
                client=client,
                api_key=settings.openrouter_api_key,
                site_url=settings.openrouter_site_url,
                app_name=settings.openrouter_app_name,
                url="https://openrouter.ai/api/v1/chat/completions",
                model=model,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                temperature=temperature,
                max_tokens=700,
                frequency_penalty=0.2,
                timeout_s=90.0,
            )
        reply = strip_internal_thoughts(reply)
        reply = strip_scene_contract(reply)
        return fix_truncated_reply(reply)

    return responder


def _stable_ref_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    if not cleaned:
        raise ValueError("Mini App conversation ref part must be non-empty")
    return cleaned


def _message_payload(message: Mapping[str, Any]) -> dict[str, str]:
    return {"role": str(message["role"]), "content": str(message["content"])}
