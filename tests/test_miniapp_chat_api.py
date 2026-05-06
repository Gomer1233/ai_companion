from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import pytest

from src.core.chat_service import build_default_chat_responder
from src.core.contracts import UserRef
from src.core.monetization import MonetizationService
from tests.test_http_api import _issue_token, _make_client


def _auth_headers(client: TestClient, telegram_token: str, user_id: int) -> dict[str, str]:
    token = _issue_token(client, telegram_token, user_id)
    return {"Authorization": f"Bearer {token}"}


def test_miniapp_chats_and_messages_are_session_protected(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)
    headers = _auth_headers(client, deps.settings.telegram_token, 501)

    unauthorized = client.get("/api/miniapp/chats")
    chats = client.get("/api/miniapp/chats", headers=headers)
    messages = client.get("/api/miniapp/chats/basic/messages", headers=headers)

    assert unauthorized.status_code == 401
    assert chats.status_code == 200
    basic = next(item for item in chats.json()["items"] if item["id"] == "basic")
    assert basic["mode"] == "basic"
    assert basic["title"] == "AI Assistant"
    assert basic["access"] == {"allowed": True, "reasons": []}
    assert basic["last_message"] is None
    assert basic["unread_count"] == 0
    assert messages.status_code == 200
    assert messages.json() == {"items": []}


def test_miniapp_text_send_persists_per_persona_history_and_usage_once(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)
    object.__setattr__(deps, "chat_responder", lambda *, mode, messages, user_text: f"{mode} reply to {user_text}")
    headers = _auth_headers(client, deps.settings.telegram_token, 502)

    sent = client.post(
        "/api/miniapp/chats/basic/messages",
        headers=headers,
        json={"text": "hello from mini app"},
    )
    basic_messages = client.get("/api/miniapp/chats/basic/messages", headers=headers)
    brainstorm_messages = client.get("/api/miniapp/chats/brainstorm/messages", headers=headers)
    usage = client.get("/api/usage", headers=headers)

    assert sent.status_code == 200
    assert sent.json()["user_message"]["content"] == "hello from mini app"
    assert sent.json()["assistant_message"]["content"] == "basic reply to hello from mini app"
    assert sent.json()["usage"]["messages"]["used"] == 1
    assert basic_messages.json()["items"] == [
        {"id": 1, "role": "user", "content": "hello from mini app", "created_at": sent.json()["user_message"]["created_at"]},
        {
            "id": 2,
            "role": "assistant",
            "content": "basic reply to hello from mini app",
            "created_at": sent.json()["assistant_message"]["created_at"],
        },
    ]
    assert brainstorm_messages.status_code == 200
    assert brainstorm_messages.json() == {"items": []}
    assert usage.json()["messages"]["used"] == 1


def test_miniapp_send_rejects_empty_locked_and_quota_without_usage(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)
    calls: list[str] = []
    object.__setattr__(
        deps,
        "chat_responder",
        lambda *, mode, messages, user_text: calls.append(user_text) or "reply",
    )
    headers = _auth_headers(client, deps.settings.telegram_token, 503)
    service = MonetizationService(deps.repositories)
    now_ts = int(time.time())
    for _ in range(30):
        service.record_message_usage(UserRef("503"), now_ts=now_ts)

    empty = client.post("/api/miniapp/chats/basic/messages", headers=headers, json={"text": "  "})
    locked = client.post("/api/miniapp/chats/coach/messages", headers=headers, json={"text": "coach me"})
    explicit = client.post("/api/miniapp/chats/whore/messages", headers=headers, json={"text": "hello"})
    limited = client.post("/api/miniapp/chats/basic/messages", headers=headers, json={"text": "hello"})
    usage = client.get("/api/usage", headers=headers)

    assert empty.status_code == 400
    assert empty.json() == {"detail": "empty_message"}
    assert locked.status_code == 403
    assert locked.json() == {"detail": "persona_locked"}
    assert explicit.status_code == 403
    assert explicit.json() == {"detail": "persona_locked"}
    assert limited.status_code == 429
    assert limited.json() == {"detail": "usage_limit_exceeded"}
    assert usage.json()["messages"]["used"] == 30
    assert calls == []


def test_miniapp_unknown_chat_returns_404(tmp_path: Path) -> None:
    client, deps = _make_client(tmp_path)
    headers = _auth_headers(client, deps.settings.telegram_token, 504)

    response = client.get("/api/miniapp/chats/not-a-character/messages", headers=headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "character_not_found"}


@pytest.mark.asyncio
async def test_miniapp_explicit_text_policy_blocks_llm_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _client, deps = _make_client(tmp_path)
    llm = AsyncMock(return_value=("blocked bypass", "stop", {"total_tokens": 1}))
    monkeypatch.setattr("src.core.chat_service.call_openrouter_with_meta", llm)

    class BlockingPolicy:
        def authorize_explicit(self, request):
            return SimpleNamespace(allowed=False, reasons=("provider_not_allowed",))

    responder = build_default_chat_responder(deps.settings, access_policy=BlockingPolicy())

    with pytest.raises(RuntimeError, match="Explicit text request blocked"):
        await responder(mode="whore", messages=[{"role": "user", "content": "hello"}], user_text="hello")

    llm.assert_not_awaited()
