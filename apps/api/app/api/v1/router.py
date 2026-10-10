"""API v1 роутер. Все новые endpoints регистрируются здесь."""

from fastapi import APIRouter

from app.api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
# TODO (Фаза 1 MVP): auth, tenants, services, bookings, clients, admin
