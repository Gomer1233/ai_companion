from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request, status

from src.adapters.http.dependencies import require_session
from src.core.chat_service import MiniAppChatError, MiniAppChatService, build_default_chat_responder
from src.config.persona_audit import build_alpha_launch_catalog
from src.core.monetization import MonetizationService, Tier


router = APIRouter(prefix="/api")


@router.get("/me")
def me(request: Request) -> dict[str, str | int]:
    session = require_session(request)
    return {
        "user_id": session.user_ref.value,
        "session_expires_at": session.expires_at,
    }


@router.get("/characters")
def characters(request: Request) -> dict[str, list[dict[str, object]]]:
    session = require_session(request)
    dependencies = request.app.state.dependencies
    service = MonetizationService(dependencies.repositories)
    now_ts = int(time.time())
    return {
        "items": [
            {
                "id": item.id,
                "mode": item.mode,
                "title": item.title,
                "category": item.category,
                "default_tier": item.default_tier,
                "access": {
                    "allowed": (decision := service.can_use_persona(session.user_ref, item.mode, now_ts)).allowed,
                    "reasons": list(decision.reasons),
                },
            }
            for item in build_alpha_launch_catalog()
        ],
    }


@router.get("/entitlements")
def entitlements(request: Request) -> dict[str, object]:
    session = require_session(request)
    dependencies = request.app.state.dependencies
    snapshot = MonetizationService(dependencies.repositories).get_access_snapshot(session.user_ref, now_ts=int(time.time()))
    return {
        "tier": snapshot.effective_tier.value,
        "tier_expires_at": snapshot.tier_expires_at,
        "has_premium": snapshot.effective_tier == Tier.PREMIUM,
        "explicit_consent": snapshot.explicit_consent,
        "consent_required": not snapshot.explicit_consent,
        "blocked_reasons": list(snapshot.blocked_reasons),
    }


@router.post("/consent/explicit")
def explicit_consent(request: Request, payload: dict[str, bool]) -> dict[str, object]:
    session = require_session(request)
    if payload.get("accepted") is not True:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="explicit_consent_required")
    dependencies = request.app.state.dependencies
    now_ts = int(time.time())
    dependencies.repositories.set_explicit_consent(session.user_ref, accepted_at=now_ts, source="mini_app")
    snapshot = MonetizationService(dependencies.repositories).get_access_snapshot(session.user_ref, now_ts=now_ts)
    return {
        "tier": snapshot.effective_tier.value,
        "tier_expires_at": snapshot.tier_expires_at,
        "has_premium": snapshot.effective_tier == Tier.PREMIUM,
        "explicit_consent": snapshot.explicit_consent,
        "consent_required": not snapshot.explicit_consent,
        "blocked_reasons": list(snapshot.blocked_reasons),
    }


@router.get("/usage")
def usage(request: Request) -> dict[str, object]:
    dependencies = request.app.state.dependencies
    session = require_session(request)
    snapshot = MonetizationService(dependencies.repositories).get_access_snapshot(session.user_ref, now_ts=int(time.time()))
    return {
        "history_limit": dependencies.repositories.history_limit,
        "image_cooldown_sec": dependencies.settings.image_cooldown_sec,
        "messages": {
            "used": snapshot.usage.messages_used,
            "limit": snapshot.limits.messages_per_day,
            "reset_at": snapshot.usage.reset_at,
        },
        "explicit_images": {
            "used": snapshot.usage.explicit_images_used,
            "limit": snapshot.limits.explicit_images_per_day,
            "reset_at": snapshot.usage.reset_at,
        },
    }


@router.get("/miniapp/chats")
def miniapp_chats(request: Request) -> dict[str, list[dict[str, object]]]:
    session = require_session(request)
    dependencies = request.app.state.dependencies
    service = MonetizationService(dependencies.repositories)
    chat_service = _miniapp_chat_service(request)
    now_ts = int(time.time())
    return {
        "items": [
            {
                "id": item.id,
                "mode": item.mode,
                "title": item.title,
                "category": item.category,
                "default_tier": item.default_tier,
                "access": {
                    "allowed": (decision := service.can_use_persona(session.user_ref, item.mode, now_ts)).allowed,
                    "reasons": list(decision.reasons),
                },
                "last_message": chat_service.last_message(session.user_ref, item.mode),
                "unread_count": 0,
            }
            for item in build_alpha_launch_catalog()
        ],
    }


@router.get("/miniapp/chats/{character_id}/messages")
def miniapp_chat_messages(character_id: str, request: Request) -> dict[str, list[dict[str, object]]]:
    session = require_session(request)
    item = _catalog_item_or_404(character_id)
    messages = _miniapp_chat_service(request).list_messages(session.user_ref, item.mode)
    return {"items": messages}


@router.post("/miniapp/chats/{character_id}/messages")
async def miniapp_send_message(character_id: str, request: Request, payload: dict[str, str]) -> dict[str, object]:
    session = require_session(request)
    item = _catalog_item_or_404(character_id)
    try:
        return await _miniapp_chat_service(request).send_message(
            user_ref=session.user_ref,
            mode=item.mode,
            text=payload.get("text", ""),
        )
    except MiniAppChatError as exc:
        if exc.code == "empty_message":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.code) from exc
        if exc.code == "persona_locked":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=exc.code) from exc
        if exc.code == "usage_limit_exceeded":
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.code) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.code) from exc


@router.get("/jobs/{job_id}")
def job_detail(job_id: str, request: Request) -> dict[str, str | int | None]:
    session = require_session(request)
    dependencies = request.app.state.dependencies
    job = dependencies.repositories.load_job(job_id)
    is_operator = False
    try:
        is_operator = int(session.user_ref.value) in dependencies.settings.operator_telegram_ids
    except ValueError:
        is_operator = False
    if job is None or (job.user_ref != session.user_ref and not is_operator):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "job_type": job.job_type.value,
        "mode": job.mode,
        "progress": job.progress,
        "error_code": job.error_code,
        "result_ref": job.result_ref,
    }


def _catalog_item_or_404(character_id: str):
    for item in build_alpha_launch_catalog():
        if item.id == character_id:
            return item
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="character_not_found")


def _miniapp_chat_service(request: Request) -> MiniAppChatService:
    dependencies = request.app.state.dependencies
    responder = dependencies.chat_responder or build_default_chat_responder(dependencies.settings)
    return MiniAppChatService(
        repositories=dependencies.repositories,
        monetization=MonetizationService(dependencies.repositories),
        responder=responder,
    )
