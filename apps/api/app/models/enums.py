"""Перечисления ролей и прав (PRD §7 — Роли и права доступа)."""

import enum


class PlatformRole(str, enum.Enum):
    """Роли супер-админки платформы (PRD §7, задача «Роли платформы»).

    Super Admin — владелец, полный доступ. Остальные — админы
    с ограниченными правами; конкретные права задаются списком
    ``permissions`` в TenantMembership/PlatformAdminRecord.
    """

    SUPER_ADMIN = "super_admin"      # владелец платформы
    MODERATOR = "moderator"          # модерация салонов/контента
    BILLING = "billing"              # биллинг, подписки, тарифы
    CONTENT = "content"              # шаблоны, контент, маркетинговые материалы
    SUPPORT = "support"              # поддержка пользователей
    ANALYTICS = "analytics"          # дашборды, метрики (read-only)


class SalonRole(str, enum.Enum):
    """Роли внутри салона (PRD §7.1–7.3)."""

    TENANT_ADMIN = "tenant_admin"    # главный мастер — полный доступ к салону
    STAFF = "staff"                  # сотрудник/мастер — ограниченный доступ


class Permission(str, enum.Enum):
    """Гранулярные права для Staff (глобально настраиваются в админке платформы)."""

    VIEW_CLIENT_PHONE = "view_client_phone"   # PRD §7.3: по умолчанию запрещено
    MANAGE_BOOKINGS = "manage_bookings"
    MANAGE_OWN_SCHEDULE = "manage_own_schedule"
    VIEW_ANALYTICS = "view_analytics"
    VIEW_FINANCES = "view_finances"           # PRD §7.1: финансы — только admin
    MANAGE_SERVICES = "manage_services"
    MANAGE_STAFF = "manage_staff"              # только tenant_admin

    @classmethod
    def staff_defaults(cls) -> list["Permission"]:
        """Права «по умолчанию» для сотрудника (без просмотра телефонов клиентов)."""
        return [cls.MANAGE_BOOKINGS, cls.MANAGE_OWN_SCHEDULE]
