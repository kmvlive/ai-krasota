"""Безопасность: bcrypt-пароли, JWT access/refresh, TOTP 2FA (PRD §15.1, §15.2)."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import pyotp
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# Пароли: bcrypt (PRD §15.2)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    # bcrypt принимает не более 72 байт — обрезаем явно, чтобы не ловить
    # ValueError на новых версиях библиотеки bcrypt>=4.1
    return pwd_context.verify(plain[:72], hashed)


def create_token(
    subject_id: uuid.UUID | str,
    token_type: TokenType = "access",
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Выдаёт JWT. access — короткоживущий, refresh — длинный (30–90 дней, PRD §15.1)."""
    now = datetime.now(timezone.utc)
    if token_type == "access":
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {
        "sub": str(subject_id),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": uuid.uuid4().hex,  # id сессии — для отзыва «выйти со всех устройств»
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any] | None:
    """Проверяет подпись, срок жизни и тип токена. Возвращает payload или None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


# ---------- TOTP 2FA (PRD §15.1) ----------

def generate_totp_secret() -> str:
    """Новый base32-секрет для Google Authenticator."""
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, account_name: str) -> str:
    """otpauth:// URI — из него клиент рисует QR-код."""
    return pyotp.TOTP(secret).provisioning_uri(
        name=account_name, issuer_name=settings.PROJECT_NAME
    )


def verify_totp_code(secret: str, code: str) -> bool:
    """Проверка 6-значного кода с допуском ±1 окно (2 шага вперёд/назад)."""
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(count: int = 8) -> list[str]:
    """Одноразовые коды восстановления на случай потери телефона."""
    return [f"{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:4]}" for _ in range(count)]


# ---------- отзыва сессий ----------

def jti_hash(jti: str) -> str:
    """sha256 от jti refresh-токена — ключ DeviceSession.token_jti_hash."""
    return hashlib.sha256(jti.encode()).hexdigest()
