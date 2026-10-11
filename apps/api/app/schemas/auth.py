"""Pydantic-схемы аутентификации и пользователей (PRD §2.1, §7, §15)."""

import uuid
from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import PlatformRole, SalonRole


class UserBase(BaseModel):
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    avatar_url: str | None = None


class RegisterRequest(UserBase):
    """Регистрация мастера (PRD §2.1 — «Попробовать 14 дней бесплатно», карта не нужна)."""

    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isdigit() for c in v):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")
        if not any(c.isalpha() for c in v):
            raise ValueError("Пароль должен содержать хотя бы одну букву")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TwoFactorVerifyRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    password: str | None = None  # требуется только на шаге verify при входе


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    phone: str | None
    name: str
    avatar_url: str | None
    is_active: bool
    is_superadmin: bool
    two_factor_enabled: bool
    last_login_at: datetime | None
    created_at: datetime


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    role: SalonRole
    permissions: list[str]


class MeResponse(BaseModel):
    user: UserOut
    memberships: list[MembershipOut] = []
    platform_role: PlatformRole | None = None


class TokenPair(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(validation_alias=AliasChoices("access_token", "access"))
    refresh_token: str = Field(validation_alias=AliasChoices("refresh_token", "refresh"))
    token_type: str = "bearer"


class LoginResult(BaseModel):
    """Ответ логина: если требуется 2FA — токены не выдаём до подтверждения кода."""

    requires_2fa: bool = False
    new_device: bool = False
    tokens: TokenPair | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_label: str | None
    ip_address: str | None
    last_seen_at: datetime | None
    expires_at: datetime
    is_current: bool = False


class TwoFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str  # otpauth:// для QR-кода в Google Authenticator
    recovery_codes: list[str]


class LogoutAllResponse(BaseModel):
    revoked_sessions: int
