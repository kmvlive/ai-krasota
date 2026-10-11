"""FastAPI-зависимости аутентификации: cookies-JWT, роли, rate limiting (PRD §7, §15)."""

import uuid as uuid_module
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_token, jti_hash
from app.models.enums import Permission, SalonRole
from app.models.role import DeviceSession, PlatformAdminRecord, UserTenantMembership
from app.models.user import User

settings = get_settings()

ACCESS_COOKIE = "ak_access"
REFRESH_COOKIE = "ak_refresh"


def _as_uuid(value: Any) -> Any:
    """UUID-строку → uuid.UUID (SqlAlchemy Uuid на SQLite требует UUID-объект)."""
    if isinstance(value, str):
        try:
            return uuid_module.UUID(value)
        except ValueError:
            return value
    return value

_bearer = HTTPBearer(auto_error=False)


def _access_cookie(request: Request) -> str | None:
    """HttpOnly access-cookie (ставится nginx/browser, PRD §15.1)."""
    return request.cookies.get(ACCESS_COOKIE)


def _extract_token(request: Request, cookie_value: str | None) -> str | None:
    """Сначала HttpOnly cookie (браузер), затем Authorization: Bearer (моб./PWA)."""
    if cookie_value:
        return cookie_value
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ").strip()
    return None


async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    cookie_token: Annotated[str | None, Depends(_access_cookie)],
) -> User:
    token = _extract_token(request, cookie_token)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    payload = decode_token(token, "access")
    # pending-2FA токены (purpose=2fa_pending) не дают доступа к API — только к
    # /auth/2fa/*; остальные purpose считаем невалидными
    if not payload or (payload.get("purpose") and payload["purpose"] != "2fa_pending"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Сессия истекла")
    # UUID-строку из JWT приводим к uuid.UUID — иначе Uuid-колонка на SQLite
    # падает с "'str' object has no attribute 'hex'" (asyncpg принимает и str)
    user = await db.get(User, _as_uuid(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Аккаунт отключён")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_pending_2fa_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    cookie_token: Annotated[str | None, Depends(_access_cookie)],
) -> User:
    """Принимает ТОЛЬКО pending-2FA токен (login с нового устройства).

    Используется на /auth/2fa/setup и /auth/2fa/enable — сценарий «включить
    2FA сразу при входе». Обычный access-токен здесь не подходит.
    """
    token = _extract_token(request, cookie_token) or request.headers.get("X-Pending-2FA", "")
    payload = decode_token(token, "access")
    if not payload or payload.get("purpose") != "2fa_pending":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Требуется повторный вход")
    user = await db.get(User, _as_uuid(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Аккаунт отключён")
    return user


async def get_optional_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    cookie_token: Annotated[str | None, Depends(_access_cookie)],
) -> User | None:
    """Как get_current_user, но без токена возвращает None (для двухпутевых эндпоинтов)."""
    token = _extract_token(request, cookie_token)
    if not token:
        return None
    payload = decode_token(token, "access")
    if not payload or (payload.get("purpose") and payload["purpose"] != "2fa_pending"):
        return None
    user = await db.get(User, _as_uuid(payload["sub"]))
    if not user or not user.is_active:
        return None
    return user


def set_auth_cookies(response_headers: Any, tokens: dict[str, str]) -> None:
    """HttpOnly + SameSite=Lax, Max-Age = длинные сессии 30–90 дней (PRD §15.1)."""
    max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    response_headers.append(
        "set-cookie",
        f"{ACCESS_COOKIE}={tokens['access']}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age={1800}",
    )
    response_headers.append(
        "set-cookie",
        f"{REFRESH_COOKIE}={tokens['refresh']}; HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth; Max-Age={max_age}",
    )


def clear_auth_cookies(response_headers: Any) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response_headers.append("set-cookie", f"{name}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0")


# ---------- Проверка членства/ролей ----------

async def get_membership(db: AsyncSession, user_id: Any, tenant_id: Any) -> UserTenantMembership | None:
    res = await db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == _as_uuid(user_id),
            UserTenantMembership.tenant_id == _as_uuid(tenant_id),
            UserTenantMembership.is_active.is_(True),
        )
    )
    return res.scalar_one_or_none()


def require_tenant_role(*roles: SalonRole):
    """Зависимость: пользователь должен состоять в салоне с одной из ролей.

    tenant_id берётся из query/path параметра ``tenant_id`` или заголовка
    X-Tenant-Id (nginx ставит его из субдомена салона).
    """

    async def dep(
        request: Request,
        user: CurrentUser,
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> UserTenantMembership:
        tenant_id = request.headers.get("X-Tenant-Id") or request.query_params.get("tenant_id")
        if not tenant_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Не указан салон (заголовок X-Tenant-Id)")
        membership = await get_membership(db, user.id, tenant_id)
        if not membership or membership.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Нет доступа к салону")
        return membership

    return dep


require_tenant_admin = require_tenant_role(SalonRole.TENANT_ADMIN)
require_any_salon_member = require_tenant_role(SalonRole.TENANT_ADMIN, SalonRole.STAFF)


def has_permission(membership: UserTenantMembership, permission: Permission) -> bool:
    """Field-level права сотрудников (PRD §7.3, §15.4). Admin — все права."""
    if membership.role == SalonRole.TENANT_ADMIN:
        return True
    return permission.value in membership.permissions


def require_superadmin(user: CurrentUser) -> User:
    """Доступ в супер-админку платформы (PRD §7 — роли платформы)."""
    if not user.is_superadmin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Только для Super Admin")
    return user


SuperAdminUser = Annotated[User, Depends(require_superadmin)]


async def get_platform_admin_role(db: AsyncSession, user_id: Any) -> PlatformAdminRecord | None:
    res = await db.execute(
        select(PlatformAdminRecord).where(
            PlatformAdminRecord.user_id == _as_uuid(user_id), PlatformAdminRecord.is_active.is_(True)
        )
    )
    return res.scalar_one_or_none()


# ---------- Rate limiting (защита от брутфорса, PRD §15) ----------


class LoginRateLimiter:
    """Счётчик неудачных попыток входа в Redis: ключ на email+IP.

    При недоступности Redis считаем, что лимит не превышен (fail-open только
    для UI-лимитера; сами токены это не отменяет).
    """

    def __init__(self, key: str, limit: int, window_seconds: int) -> None:
        self.key = f"rl:{key}"
        self.limit = limit
        self.window = window_seconds

    async def is_blocked(self) -> bool:
        if not settings.RATELIMIT_ENABLED:
            return False
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.REDIS_URL)
            try:
                count = await r.incr(self.key)
                if count == 1:
                    await r.expire(self.key, self.window)
                return count > self.limit
            finally:
                await r.aclose()
        except Exception:  # pragma: no cover — сеть/Redis недоступны
            return False

    async def record_failure(self) -> None:
        """Явный инкремент счётчика после неудачной попытки."""
        if not settings.RATELIMIT_ENABLED:
            return
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.REDIS_URL)
            try:
                count = await r.incr(self.key)
                if count == 1:
                    await r.expire(self.key, self.window)
            finally:
                await r.aclose()
        except Exception:  # pragma: no cover
            pass

    async def reset(self) -> None:
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.REDIS_URL)
            try:
                await r.delete(self.key)
            finally:
                await r.aclose()
        except Exception:  # pragma: no cover
            pass


def login_limiter(request: Request, payload: dict | None = None) -> LoginRateLimiter:
    ip = request.client.host if request.client else "unknown"
    email = (payload or {}).get("email", "anon")
    return LoginRateLimiter(
        key=f"login:{email}:{ip}",
        limit=settings.LOGIN_ATTEMPTS_LIMIT,
        window_seconds=settings.LOGIN_ATTEMPTS_WINDOW_SECONDS,
    )
