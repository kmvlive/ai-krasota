"""Аутентификация и пользователи (PRD §2.1, §7, §15).

Эндпоинты:
  POST /auth/register      — регистрация мастера (триал 14 дней, карта не нужна)
  POST /auth/login         — вход; при новом устройстве/2FA требует код
  POST /auth/2fa/verify    — подтверждение TOTP-кода на шаге логина
  POST /auth/refresh       — ротация refresh-токена (длинные сессии)
  POST /auth/logout        — выход с текущего устройства
  POST /auth/logout-all    — «выйти со всех устройств» (PRD §15.1)
  GET  /auth/devices       — список активных устройств
  DELETE /auth/devices/{id}— отзыв одной сессии
  POST /auth/2fa/setup     — включение 2FA (QR для Google Authenticator)
  POST /auth/2fa/disable   — выключение 2FA в настройках
  GET  /auth/me            — текущий пользователь + роли
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import (
    CurrentUser,
    LoginRateLimiter,
    _as_uuid,
    get_pending_2fa_user,
    clear_auth_cookies,
    get_platform_admin_role,
    jti_hash,
    set_auth_cookies,
)
from app.core.security import (
    create_token,
    decode_token,
    generate_recovery_codes,
    generate_totp_secret,
    hash_password,
    totp_provisioning_uri,
    verify_password,
    verify_totp_code,
)
from app.models.role import DeviceSession, UserTenantMembership
from app.models.user import User
from app.schemas.auth import (
    DeviceOut,
    LoginRequest,
    LoginResult,
    LogoutAllResponse,
    MeResponse,
    MembershipOut,
    RegisterRequest,
    TokenPair,
    TwoFactorVerifyRequest,
    TwoFASetupResponse,
    UserOut,
)

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])

# pending-2FA: короткоживущий токен между шагом пароля и шагом кода
PENDING_TTL_SECONDS = 300


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _device_label(request: Request) -> str:
    ua = (request.headers.get("User-Agent") or "")[:200]
    return ua or "unknown"


def _token_pair(tokens: dict[str, str]) -> TokenPair:
    """internal-ключи access/refresh → публичная схема OAuth-style."""
    return TokenPair(access_token=tokens["access"], refresh_token=tokens["refresh"])


async def _issue_session(
    db: AsyncSession, user: User, request: Request, mark_seen: bool = False
) -> dict[str, str]:
    """Создаёт DeviceSession + пару токенов. jti refresh-токена — id сессии."""
    access = create_token(user.id, "access")
    refresh = create_token(user.id, "refresh")
    payload = decode_token(refresh, "refresh")
    assert payload is not None
    session = DeviceSession(
        user_id=user.id,
        token_jti_hash=jti_hash(payload["jti"]),
        device_label=_device_label(request),
        ip_address=_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        is_new_device=not mark_seen,
        last_seen_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    return {"access": access, "refresh": refresh}


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    """Регистрация мастера (PRD §2.1). Аккаунт создаётся без салона —
    салон появится на шаге онбординг-визарда (§2.2)."""
    exists = await db.execute(select(User.id).where(User.email == payload.email.lower()))
    if exists.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email уже зарегистрирован")
    if payload.phone:
        exists_phone = await db.execute(select(User.id).where(User.phone == payload.phone))
        if exists_phone.scalar_one_or_none():
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Телефон уже зарегистрирован")

    user = User(
        email=payload.email.lower(),
        phone=payload.phone,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=LoginResult)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResult:
    limiter = LoginRateLimiter(
        key=f"login:{payload.email}:{_client_ip(request)}",
        limit=settings.LOGIN_ATTEMPTS_LIMIT,
        window_seconds=settings.LOGIN_ATTEMPTS_WINDOW_SECONDS,
    )
    if await limiter.is_blocked():
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много попыток входа. Подождите несколько минут.",
        )

    res = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = res.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        await limiter.record_failure()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Аккаунт отключён")

    known_device = await db.execute(
        select(DeviceSession.id).where(
            DeviceSession.user_id == user.id,
            DeviceSession.device_label == _device_label(request),
            DeviceSession.ip_address == _client_ip(request),
            DeviceSession.revoked_at.is_(None),
        )
    )
    new_device = known_device.scalar_one_or_none() is None

    # 2FA требуется, если включена ИЛИ вход с нового устройства (PRD §15.1)
    if user.two_factor_enabled or new_device:
        extra: dict = {
            "purpose": "2fa_pending",
            "exp": int(datetime.now(timezone.utc).timestamp()) + PENDING_TTL_SECONDS,
        }
        # пароль уже проверен — повторный ввод на шаге verify не требуется;
        # при первом включении 2FA это же подтверждает владение паролем
        extra["password_ok"] = True
        pending = create_token(user.id, "access", extra)
        await limiter.reset()
        response.headers["X-Pending-2FA"] = pending
        return LoginResult(requires_2fa=True, new_device=new_device, tokens=None)

    tokens = await _issue_session(db, user, request)
    await limiter.reset()
    set_auth_cookies(response.headers, tokens)
    return LoginResult(requires_2fa=False, new_device=False, tokens=_token_pair(tokens))


def _pending_payload(request: Request) -> dict:
    token = request.headers.get("X-Pending-2FA") or ""
    pending = decode_token(token, "access")
    if not pending or pending.get("purpose") != "2fa_pending":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Требуется повторный вход")
    return pending


@router.post("/2fa/verify", response_model=LoginResult)
async def verify_2fa(
    payload: TwoFactorVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResult:
    """Шаг 2 логина: TOTP-код (+ пароль, если он ещё не подтверждён на шаге login)."""
    pending = _pending_payload(request)
    user = await db.get(User, _as_uuid(pending["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Аккаунт отключён")

    need_password = not pending.get("password_ok")
    if need_password and (not payload.password or not verify_password(payload.password, user.password_hash)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный пароль")

    ok = False
    if user.two_factor_enabled and user.totp_secret_encrypted:
        # TODO: расшифровать секрет из AES-256 at rest (PRD §15.2); сейчас — base32 as-is
        ok = verify_totp_code(user.totp_secret_encrypted, payload.code)
    if not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Неверный код подтверждения")

    tokens = await _issue_session(db, user, request, mark_seen=True)
    set_auth_cookies(response.headers, tokens)
    return LoginResult(requires_2fa=False, new_device=False, tokens=_token_pair(tokens))


@router.post("/refresh", response_model=TokenPair)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> TokenPair:
    """Ротация refresh-токена — мастер не логинится заново неделями (PRD §15.1)."""
    from app.core.deps import REFRESH_COOKIE

    token = request.cookies.get(REFRESH_COOKIE) or (
        request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    )
    payload = decode_token(token or "", "refresh")
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Сессия истекла")
    res = await db.execute(
        select(DeviceSession).where(
            DeviceSession.token_jti_hash == jti_hash(payload["jti"]),
            DeviceSession.revoked_at.is_(None),
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Сессия отозвана")
    user = await db.get(User, _as_uuid(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Аккаунт отключён")

    session.revoked_at = datetime.now(timezone.utc)  # одноразовый refresh
    tokens = await _issue_session(db, user, request, mark_seen=True)
    set_auth_cookies(response.headers, tokens)
    return _token_pair(tokens)


@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    from app.core.deps import REFRESH_COOKIE

    token = request.cookies.get(REFRESH_COOKIE)
    payload = decode_token(token or "", "refresh")
    if payload:
        await db.execute(
            update(DeviceSession)
            .where(DeviceSession.token_jti_hash == jti_hash(payload["jti"]))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.commit()
    clear_auth_cookies(response.headers)
    return {"ok": True}


@router.post("/logout-all", response_model=LogoutAllResponse)
async def logout_all(user: CurrentUser, response: Response, db: AsyncSession = Depends(get_db)) -> LogoutAllResponse:
    """«Выйти со всех устройств» (PRD §15.1)."""
    result = await db.execute(
        update(DeviceSession)
        .where(DeviceSession.user_id == user.id, DeviceSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()
    clear_auth_cookies(response.headers)
    return LogoutAllResponse(revoked_sessions=result.rowcount or 0)


@router.get("/devices", response_model=list[DeviceOut])
async def list_devices(
    request: Request, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[DeviceOut]:
    """Список активных устройств мастера (PRD §15.1)."""
    from app.core.deps import REFRESH_COOKIE

    current_jti = None
    payload = decode_token(request.cookies.get(REFRESH_COOKIE) or "", "refresh")
    if payload:
        current_jti = jti_hash(payload["jti"])
    res = await db.execute(
        select(DeviceSession)
        .where(DeviceSession.user_id == user.id, DeviceSession.revoked_at.is_(None))
        .order_by(DeviceSession.last_seen_at.desc())
    )
    devices = []
    for s in res.scalars().all():
        out = DeviceOut.model_validate(s)
        out.is_current = s.token_jti_hash == current_jti
        devices.append(out)
    return devices


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device(
    device_id: uuid.UUID, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    res = await db.execute(
        select(DeviceSession).where(
            DeviceSession.id == device_id,
            DeviceSession.user_id == user.id,
            DeviceSession.revoked_at.is_(None),
        )
    )
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Устройство не найдено")
    session.revoked_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_2fa(
    user: User = Depends(get_pending_2fa_user),
    db: AsyncSession = Depends(get_db),
) -> TwoFASetupResponse:
    """Включение 2FA: генерируем TOTP-секрет + коды восстановления (PRD §15.1).

    Доступно на шаге pending-2FA сразу после успешной проверки пароля
    (сценарий «включить 2FA при входе с нового устройства»).
    """
    secret = generate_totp_secret()
    codes = generate_recovery_codes()
    user.totp_secret_encrypted = secret  # TODO: AES-256 at rest (PRD §15.2)
    user.recovery_codes_hash = hash_password(",".join(codes))
    await db.commit()
    return TwoFASetupResponse(
        secret=secret,
        provisioning_uri=totp_provisioning_uri(secret, user.email),
        recovery_codes=codes,
    )


@router.post("/2fa/enable", response_model=UserOut)
async def enable_2fa(
    payload: TwoFactorVerifyRequest,
    user: User = Depends(get_pending_2fa_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Подтверждение кода из приложения — финальный шаг включения 2FA."""
    if not user.totp_secret_encrypted or not verify_totp_code(user.totp_secret_encrypted, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Код не подтверждён")
    user.two_factor_enabled = True
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/2fa/disable", response_model=UserOut)
async def disable_2fa(
    payload: TwoFactorVerifyRequest, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> User:
    """Выключение 2FA в настройках — только с действующим кодом."""
    if not user.two_factor_enabled:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="2FA уже выключена")
    if not user.totp_secret_encrypted or not verify_totp_code(user.totp_secret_encrypted, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Требуется верный TOTP-код")
    user.two_factor_enabled = False
    user.totp_secret_encrypted = None
    user.recovery_codes_hash = None
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser, db: AsyncSession = Depends(get_db)) -> MeResponse:
    memberships_res = await db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user.id, UserTenantMembership.is_active.is_(True)
        )
    )
    admin_record = await get_platform_admin_role(db, user.id)
    return MeResponse(
        user=UserOut.model_validate(user),
        memberships=[MembershipOut.model_validate(m) for m in memberships_res.scalars().all()],
        platform_role=admin_record.role if admin_record else None,
    )
