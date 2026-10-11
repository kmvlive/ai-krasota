"""auth: users, memberships, device sessions, platform admins

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("recovery_codes_hash", sa.Text(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_unique_constraint("uq_users_phone", "users", ["phone"])

    op.create_table(
        "user_tenant_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="staff"),
        sa.Column("permissions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
    )
    op.create_index("ix_memberships_user_id", "user_tenant_memberships", ["user_id"])
    op.create_index("ix_memberships_tenant_id", "user_tenant_memberships", ["tenant_id"])

    op.create_table(
        "device_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_jti_hash", sa.String(64), nullable=False),
        sa.Column("device_label", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("is_new_device", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_jti_hash", name="uq_device_session_jti"),
    )
    op.create_index("ix_device_sessions_user_id", "device_sessions", ["user_id"])

    op.create_table(
        "platform_admin_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="support"),
        sa.Column("allowed_tenants", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Multi-tenancy: RLS для членств в салонах (данные салона изолированы, PRD §7.4)
    op.execute("ALTER TABLE user_tenant_memberships ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON user_tenant_memberships
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
        """
    )


def downgrade() -> None:
    op.drop_table("platform_admin_records")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON user_tenant_memberships")
    op.drop_table("user_tenant_memberships")
    op.drop_table("device_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
