"""Модель пользователя платформы (PRD §7, §15; регистрация мастера — PRD §2.1)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class User(Base, TimestampMixin):
    """Аккаунт мастера/сотрудника/админa платформы.

    Один человек, работающий в 3 салонах, имеет 3 отдельных аккаунта-тенанта
    (PRD §7.4); единый «мастер-паспорт» — в backlog (PRD §7.5), поэтому
    привязка к салону здесь одна (membership.tenant_id).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))  # bcrypt (PRD §15.2)
    name: Mapped[str] = mapped_column(String(120))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)

    # 2FA: TOTP (PRD §15.1)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text)  # AES-256 at rest (PRD §15.2)
    recovery_codes_hash: Mapped[str | None] = mapped_column(Text)    # bcrypt-список одноразовых кодов

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["UserTenantMembership"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["DeviceSession"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
