"""Utilisateurs, rôles, permissions, sessions et sécurité des connexions."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import (
    Base,
    TenantMixin,
    TimestampMixin,
    UUIDPkMixin,
)


class User(Base, UUIDPkMixin, TimestampMixin):
    """Compte de connexion. tenant_id nullable : les super admins n'ont pas de tenant."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email"),
        UniqueConstraint("tenant_id", "phone"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), index=True, default=None
    )
    email: Mapped[str] = mapped_column(index=True)
    phone: Mapped[str | None] = mapped_column(default=None, index=True)
    password_hash: Mapped[str] = mapped_column()
    first_name: Mapped[str] = mapped_column()
    last_name: Mapped[str] = mapped_column()
    avatar_url: Mapped[str | None] = mapped_column(default=None)
    language: Mapped[str] = mapped_column(default="fr")
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superadmin: Mapped[bool] = mapped_column(default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(default=None)
    phone_verified_at: Mapped[datetime | None] = mapped_column(default=None)
    locked_until: Mapped[datetime | None] = mapped_column(default=None)
    failed_login_count: Mapped[int] = mapped_column(default=0)
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Role(Base, UUIDPkMixin, TimestampMixin):
    """Rôle. tenant_id NULL = rôle système partagé (Propriétaire, Caissier...)."""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, default=None
    )
    code: Mapped[str] = mapped_column(index=True)
    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)
    is_system: Mapped[bool] = mapped_column(default=False)


class Permission(Base, UUIDPkMixin):
    """Permission granulaire, ex. `sales.create`, `stock.adjust`."""

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str] = mapped_column()
    module: Mapped[str] = mapped_column(index=True)


class RolePermission(Base, UUIDPkMixin):
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id"),)

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), index=True
    )


class UserRole(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, default=None
    )


class UserBranch(Base, UUIDPkMixin, TimestampMixin, TenantMixin):
    """Affectation d'un utilisateur à un point de vente."""

    __tablename__ = "user_branches"
    __table_args__ = (UniqueConstraint("user_id", "branch_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), index=True
    )
    is_default: Mapped[bool] = mapped_column(default=False)


class DeviceSession(Base, UUIDPkMixin, TimestampMixin):
    """Session par appareil — support de la révocation ciblée."""

    __tablename__ = "device_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True, default=None
    )
    device_name: Mapped[str | None] = mapped_column(default=None)
    device_type: Mapped[str] = mapped_column(default="web")  # web | android | ios
    ip_address: Mapped[str | None] = mapped_column(default=None)
    user_agent: Mapped[str | None] = mapped_column(default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


class RefreshToken(Base, UUIDPkMixin, TimestampMixin):
    """Refresh token rotatif — seule l'empreinte SHA-256 est stockée."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("device_sessions.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column()
    used_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(default=None)


class LoginAttempt(Base, UUIDPkMixin):
    __tablename__ = "login_attempts"

    email: Mapped[str] = mapped_column(index=True)
    ip_address: Mapped[str | None] = mapped_column(default=None)
    user_agent: Mapped[str | None] = mapped_column(default=None)
    success: Mapped[bool] = mapped_column(default=False)
    attempted_at: Mapped[datetime] = mapped_column(index=True)
