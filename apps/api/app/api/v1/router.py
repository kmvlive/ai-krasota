"""API v1 роутер. Все новые endpoints регистрируются здесь."""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(users.router)
# TODO (Фаза 1 MVP): tenants, services, bookings, clients, admin
