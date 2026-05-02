from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException, Request, status

from src.adapters.http.dependencies import require_session
from src.config.modes import MODE_CATALOG
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
def characters(request: Request) -> dict[str, list[dict[str, str]]]:
    require_session(request)
    return {
        "items": [{"id": mode, "title": title} for title, mode in MODE_CATALOG],
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


@router.get("/jobs/{job_id}")
def job_detail(job_id: str, request: Request) -> dict[str, str | int | None]:
    session = require_session(request)
    dependencies = request.app.state.dependencies
    job = dependencies.repositories.load_job(job_id)
    if job is None or job.user_ref != session.user_ref:
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
