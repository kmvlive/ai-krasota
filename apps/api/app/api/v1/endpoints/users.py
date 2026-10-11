"""Управление пользователями и ролями (PRD §7).

  GET    /users/me/memberships            — мои салоны и роли
  POST   /tenants/{id}/staff              — добавить сотрудника (только Tenant Admin)
  PATCH  /tenants/{id}/staff/{user_id}    — изменить роль/права (PRD §7.3)
  DELETE /tenants/{id}/staff/{user_id}    — удалить сотрудника
  POST   /admin/platform-admins           — назначить админа платформы (Super Admin)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import SuperAdminUser, CurrentUser, _as_uuid, require_tenant_admin
from app.models.enums import Permission, PlatformRole, SalonRole
from app.models.role import PlatformAdminRecord, UserTenantMembership
from app.models.user import User
from app.schemas.auth import MembershipOut

router = APIRouter(tags=["users & roles"])


class AddStaffRequest(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=120)
    permissions: list[str] | None = None  # None → права по умолчанию для Staff


class UpdateStaffRequest(BaseModel):
    role: SalonRole | None = None
    permissions: list[Permission] | None = None
    is_active: bool | None = None


class PlatformAdminRequest(BaseModel):
    user_id: uuid.UUID
    role: PlatformRole
    allowed_tenants: list[uuid.UUID] | None = None


@router.get("/users/me/memberships", response_model=list[MembershipOut])
async def my_memberships(user: CurrentUser, db: AsyncSession = Depends(get_db)) -> list[MembershipOut]:
    res = await db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.user_id == user.id, UserTenantMembership.is_active.is_(True)
        )
    )
    return [MembershipOut.model_validate(m) for m in res.scalars().all()]


@router.post(
    "/tenants/{tenant_id}/staff",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_tenant_admin)],
)
async def add_staff(
    tenant_id: uuid.UUID, payload: AddStaffRequest, db: AsyncSession = Depends(get_db)
) -> MembershipOut:
    """Главный мастер добавляет сотрудника (PRD §7.2)."""
    existing_user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()

    if existing_user:
        dup = (
            await db.execute(
                select(UserTenantMembership).where(
                    UserTenantMembership.user_id == existing_user.id,
                    UserTenantMembership.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Сотрудник уже в салоне")
        user = existing_user
    else:
        # Сотрудник без аккаунта — создаём приглашённый аккаунт (пароль задаст сам при первом входе)
        user = User(email=payload.email.lower(), name=payload.name, password_hash="!", is_active=True)
        db.add(user)
        await db.flush()

    membership = UserTenantMembership(
        user_id=user.id,
        tenant_id=tenant_id,
        role=SalonRole.STAFF,
        permissions=payload.permissions or [p.value for p in Permission.staff_defaults()],
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return MembershipOut.model_validate(membership)


@router.patch(
    "/tenants/{tenant_id}/staff/{user_id}",
    response_model=MembershipOut,
    dependencies=[Depends(require_tenant_admin)],
)
async def update_staff(
    tenant_id: uuid.UUID, user_id: uuid.UUID, payload: UpdateStaffRequest, db: AsyncSession = Depends(get_db)
) -> MembershipOut:
    """Настройка роли и field-level прав сотрудника (PRD §7.3, §15.4)."""
    res = await db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.tenant_id == tenant_id, UserTenantMembership.user_id == user_id
        )
    )
    membership = res.scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    if payload.role is not None:
        membership.role = payload.role
    if payload.permissions is not None:
        membership.permissions = [p.value for p in payload.permissions]
    if payload.is_active is not None:
        membership.is_active = payload.is_active
    await db.commit()
    await db.refresh(membership)
    return MembershipOut.model_validate(membership)


@router.delete(
    "/tenants/{tenant_id}/staff/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_tenant_admin)],
)
async def remove_staff(tenant_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    res = await db.execute(
        select(UserTenantMembership).where(
            UserTenantMembership.tenant_id == tenant_id, UserTenantMembership.user_id == user_id
        )
    )
    membership = res.scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    if membership.role == SalonRole.TENANT_ADMIN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Нельзя удалить главного мастера салона")
    membership.is_active = False  # мягкое удаление — история записей сохраняется
    await db.commit()


@router.post(
    "/admin/platform-admins",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def create_platform_admin(
    payload: PlatformAdminRequest,
    _superadmin: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Назначение админа с ограниченными правами (модератор/биллинг/контент/поддержка/аналитика).

    Доступно только Super Admin — владельцу платформы (PRD §7).
    """
    target = await db.get(User, _as_uuid(payload.user_id))
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    existing = (
        await db.execute(
            select(PlatformAdminRecord).where(PlatformAdminRecord.user_id == _as_uuid(payload.user_id))
        )
    ).scalar_one_or_none()
    if existing:
        existing.role = payload.role
        existing.allowed_tenants = payload.allowed_tenants
        existing.is_active = True
        await db.commit()
        return {"id": str(existing.id), "role": existing.role, "updated": True}
    record = PlatformAdminRecord(
        user_id=payload.user_id, role=payload.role, allowed_tenants=payload.allowed_tenants
    )
    db.add(record)
    await db.commit()
    return {"id": str(record.id), "role": record.role, "updated": False}
