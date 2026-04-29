from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.adapters.http.dependencies import get_app_dependencies


router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(request: Request):
    dependencies = get_app_dependencies(request)
    if not dependencies.readiness.is_ready:
        return JSONResponse(status_code=503, content={"status": "starting"})
    return {"status": "ready"}
