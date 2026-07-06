from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from backend.config.settings import AppSettings
from backend.router.health_router import router as health_router
from backend.router.research_router import router as research_router
from backend.router.chat_router import router as chat_router
from backend.router.book_router import router as book_router
from backend.router.auth_router import router as auth_router
from backend.router.seat_router import router as seat_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(messagew)s",
)


def create_app() -> FastAPI:
    settings = AppSettings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(research_router)
    app.include_router(chat_router)
    app.include_router(book_router)
    app.include_router(auth_router)
    app.include_router(seat_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    runtime_settings = AppSettings()
    uvicorn.run(
        "app_main:app",
        host=runtime_settings.host,
        port=runtime_settings.port,
        reload=runtime_settings.app_env == "development",
    )

