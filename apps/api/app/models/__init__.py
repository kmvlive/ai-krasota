"""Реестр ORM-моделей: импорт всех моделей регистрирует их в Base.metadata (для Alembic)."""

from app.models.base import TenantMixin, TimestampMixin  # noqa: F401
from app.models.enums import Permission, PlatformRole, SalonRole  # noqa: F401
from app.models.role import DeviceSession, PlatformAdminRecord, UserTenantMembership  # noqa: F401
from app.models.tenant import Service, Tenant  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "TenantMixin",
    "TimestampMixin",
    "Permission",
    "PlatformRole",
    "SalonRole",
    "User",
    "UserTenantMembership",
    "DeviceSession",
    "PlatformAdminRecord",
    "Tenant",
    "Service",
]
