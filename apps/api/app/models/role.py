"""Ролевые модели: членство в салоне, устройства/сессии, админы платформы (PRD §7, §15.1)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.enums import PlatformRole, SalonRole


class UserTenantMembership(Base, TimestampMixin):
    """Роль пользователя в конкретном салоне (PRD §7.1–7.2).

    Изоляция салонов: у мастера, работающего в 3 салонах, — 3 записи
    с разными tenant_id; данные не пересекаются (PRD §7.4).
    """

    __tablename__ = "user_tenant_memberships"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[SalonRole] = mapped_column(String(32), default=SalonRole.STAFF)
    # Гранулярные права Staff поверх роли (PRD §7.3, настраиваются глобально в админке)
    permissions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship(back_populates="memberships")  # noqa: F821
    tenant: Mapped["Tenant"] = relationship()  # noqa: F821


class DeviceSession(Base, TimestampMixin):
    """Активное устройство/сессия (PRD §15.1).

    refresh-токен хранится хэшем; jti из JWT совпадает с ``token_jti_hash`` —
    так реализуются «выйти со всех устройств» и отзыв одной сессии.
    """

    __tablename__ = "device_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_jti_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256(jti)
    device_label: Mapped[str | None] = mapped_column(String(255))  # "iPhone Safari"
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    is_new_device: Mapped[bool] = mapped_column(Boolean, default=True)  # триггер 2FA-проверки
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="sessions")  # noqa: F821


class PlatformAdminRecord(Base, TimestampMixin):
    """Ограниченные администраторы супер-админки платформы (PRD §7).

    Super Admin помечается флагом users.is_superadmin; здесь — остальные
    роли (модератор, биллинг, контент, поддержка, аналитика) с явным
    списком разрешений.
    """

    __tablename__ = "platform_admin_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    role: Mapped[PlatformRole] = mapped_column(String(32), default=PlatformRole.SUPPORT)
    allowed_tenants: Mapped[list[uuid.UUID] | None] = mapped_column(
        JSONB
    )  # None = все салоны; список — доступ к отдельным
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user: Mapped["User"] = relationship()  # noqa: F821
