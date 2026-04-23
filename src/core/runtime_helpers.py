from __future__ import annotations

import asyncio
import json
import logging
import re
from inspect import isawaitable
from typing import Any, Dict, List

import httpx


async def call_openrouter_with_meta(
    *,
    client: httpx.AsyncClient,
    api_key: str,
    site_url: str,
    app_name: str,
    url: str,
    model: str,
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 700,
    frequency_penalty: float = 0.0,
    timeout_s: float = 60.0,
) -> tuple[str, str, Dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": site_url,
        "X-Title": app_name,
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "frequency_penalty": frequency_penalty,
    }

    response = await client.post(url, headers=headers, json=payload)
    if response.status_code >= 400:
        try:
            err = response.json()
        except Exception:
            err = {"error": {"message": response.text}}
        msg = err.get("error", {}).get("message", response.text)
        raise RuntimeError(f"OpenRouter HTTP {response.status_code}: {msg}")

    data = response.json()
    content = (data["choices"][0]["message"]["content"] or "")
    finish_reason = (data["choices"][0].get("finish_reason") or "")
    usage = data.get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}
    return content, finish_reason, usage


async def keep_typing(bot: Any, chat_id: int, stop_event: asyncio.Event) -> None:
    try:
        while not stop_event.is_set():
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(4)
    except Exception:
        logging.exception("Typing indicator error")


def chunk_text(text: str, chunk_size: int = 3800) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= 4000:
        return [text]

    parts: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        block = paragraph.strip() + "\n\n"
        if len(current) + len(block) <= chunk_size:
            current += block
            continue

        if current.strip():
            parts.append(current.strip())
            current = ""

        if len(block) > chunk_size:
            sentences = re.split(r"(?<=[.!?\u2026])\s+", paragraph.strip())
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                addition = sentence + " "
                if len(current) + len(addition) <= chunk_size:
                    current += addition
                else:
                    if current.strip():
                        parts.append(current.strip())
                    current = addition
            current = current.strip() + "\n\n"
        else:
            current = block

    if current.strip():
        parts.append(current.strip())
    return parts


def extract_json_object(text: str) -> dict | None:
    if not text:
        return None

    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()

    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def strip_internal_thoughts(text: str) -> str:
    if not text:
        return text

    bad_markers = [
        "analyze the user's input",
        "analyze the persona",
        "determine the response strategy",
        "drafting the response",
        "internal monologue",
        "final selection",
        "response strategy",
    ]

    low = text.lower()
    if any(marker in low for marker in bad_markers):
        lines = text.splitlines()
        out: list[str] = []
        for line in lines:
            low_line = line.lower()
            if any(marker in low_line for marker in bad_markers):
                break
            out.append(line)
        return "\n".join(out).strip()

    return text.strip()


def is_truncated_for_glue(text: str, finish_reason: str) -> bool:
    if (finish_reason or "").lower() == "length":
        return True
    trimmed = (text or "").rstrip()
    if not trimmed:
        return False
    return not trimmed.endswith((".", "!", "?", "\u2026"))


def fix_truncated_reply(text: str) -> str:
    if not text:
        return text

    trimmed = text.rstrip()
    bad_endings = (
        " в", " на", " у", " о", " об", " про", " для", " тебе", " вам", " ему", " ей", " им",
        " чтобы", " потому", " и", " или", " но", " а",
        ":", "—", "-", "(", "«", "“", '"',
    )
    low = trimmed.lower()
    if any(low.endswith(ending) for ending in bad_endings):
        parts = trimmed.rsplit(" ", 1)
        if len(parts) == 2:
            return parts[0].rstrip() + "…"
        return trimmed + "…"
    if trimmed.endswith(("•", "-", "—")):
        return trimmed.rstrip("•-— ").rstrip() + "…"
    return trimmed


def estimate_tokens(text: str, model: str = "") -> int:
    text = text or ""
    if not text:
        return 0
    try:
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")
        except Exception:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Keep analytics useful in lean runtime/test environments without tiktoken.
        return max(1, len(text) // 4)


_SCENE_CONTRACT_RE = re.compile(r"\[\[?SCENE_CONTRACT\]\]?\s*\n?\s*\{.*?\}", re.DOTALL)


def strip_scene_contract(text: str) -> str:
    if not text:
        return text
    return _SCENE_CONTRACT_RE.sub("", text).strip()


async def maybe_await(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value
