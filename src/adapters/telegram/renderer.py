from __future__ import annotations

from typing import Any, Mapping

from aiogram.types import BufferedInputFile
from aiogram.types.input_file import FSInputFile

from src.core.contracts import CoreResponse, OutboundItemType


async def render_core_response(
    target,
    response: CoreResponse,
    *,
    reply_markup=None,
    parse_mode: str | None = None,
) -> None:
    first_text = True
    for item in response.items:
        item_reply_markup = reply_markup if first_text and item.item_type == OutboundItemType.TEXT else None
        if item.item_type == OutboundItemType.TEXT:
            await target.answer(item.text or '', reply_markup=item_reply_markup, parse_mode=parse_mode)
            first_text = False
            continue

        if item.item_type == OutboundItemType.IMAGE:
            payload = dict(item.payload)
            if 'bytes' in payload:
                filename = payload.get('filename', 'image.png')
                await target.answer_photo(
                    BufferedInputFile(payload['bytes'], filename=filename),
                    reply_markup=item_reply_markup,
                )
            elif 'path' in payload:
                await target.answer_photo(FSInputFile(payload['path']), reply_markup=item_reply_markup)
            elif item.text:
                await target.answer(item.text, reply_markup=item_reply_markup, parse_mode=parse_mode)
            first_text = False
            continue

        if item.item_type == OutboundItemType.AUDIO:
            payload = dict(item.payload)
            if 'bytes' in payload:
                filename = payload.get('filename', 'audio.mp3')
                await target.answer_audio(
                    BufferedInputFile(payload['bytes'], filename=filename),
                    reply_markup=item_reply_markup,
                )
            elif 'path' in payload:
                await target.answer_audio(FSInputFile(payload['path']), reply_markup=item_reply_markup)
            elif item.text:
                await target.answer(item.text, reply_markup=item_reply_markup, parse_mode=parse_mode)
            first_text = False
            continue

        if item.item_type in {OutboundItemType.ACTION, OutboundItemType.PROGRESS, OutboundItemType.DEFERRED_RESULT}:
            text = item.text or payload_to_text(item.payload)
            if text:
                await target.answer(text, reply_markup=item_reply_markup, parse_mode=parse_mode)
            first_text = False


def payload_to_text(payload: Mapping[str, Any]) -> str:
    if not payload:
        return ''
    if 'text' in payload:
        return str(payload['text'])
    if 'status' in payload and 'job_id' in payload:
        return f"job={payload['job_id']} status={payload['status']}"
    return ''
