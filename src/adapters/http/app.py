from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.http.dependencies import AppDependencies
from src.adapters.http.routes.api import router as api_router
from src.adapters.http.routes.health import router as health_router
from src.adapters.http.routes.session import router as session_router


def create_app(dependencies: AppDependencies) -> FastAPI:
    app = FastAPI()
    app.state.dependencies = dependencies

    if dependencies.settings.http_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(dependencies.settings.http_cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    app.include_router(health_router)
    app.include_router(session_router)
    app.include_router(api_router)

    return app
