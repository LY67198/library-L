from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.appointments import router as appointments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.books import router as books_router
from app.api.v1.health import router as health_router
from app.api.v1.seats import router as seats_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(books_router)
api_router.include_router(seats_router)
api_router.include_router(appointments_router)
api_router.include_router(health_router)