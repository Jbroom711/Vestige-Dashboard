"""FastAPI entry point. Run with:

    uvicorn app.main:app --reload --port 8007
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import capital, dashboard, fees, planned_capital, profiles, returns, voice


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vestige Dashboard API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(profiles.router)
    app.include_router(returns.router)
    app.include_router(capital.router)
    app.include_router(fees.router)
    app.include_router(planned_capital.router)
    app.include_router(dashboard.router)
    app.include_router(voice.router)

    return app


app = create_app()
