from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from src.adapters.http.dependencies import require_session
from src.config.modes import MODE_CATALOG


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
def entitlements(request: Request) -> dict[str, bool]:
    require_session(request)
    return {
        "has_premium": False,
        "consent_required": False,
    }


@router.get("/usage")
def usage(request: Request) -> dict[str, int]:
    dependencies = request.app.state.dependencies
    require_session(request)
    return {
        "history_limit": dependencies.repositories.history_limit,
        "image_cooldown_sec": dependencies.settings.image_cooldown_sec,
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
