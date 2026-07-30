"""Système : audit, fichiers, synchronisation offline, feature flags."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import Base, TimestampMixin, UUIDPkMixin


class AuditLog(Base, UUIDPkMixin, TimestampMixin):
    """Journal d'audit append-only."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_entity", "tenant_id", "entity_type", "entity_id"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(index=True, default=None)
    user_id: Mapped[uuid.UUID | None] = mapped_column(index=True, default=None)
    action: Mapped[str] = mapped_column(index=True)  # ex. sale.cancel, auth.login
    entity_type: Mapped[str | None] = mapped_column(default=None)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    ip_address: Mapped[str | None] = mapped_column(default=None)
    correlation_id: Mapped[str | None] = mapped_column(default=None)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class FileAttachment(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "file_attachments"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(index=True, default=None)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    filename: Mapped[str] = mapped_column()
    content_type: Mapped[str] = mapped_column()
    size_bytes: Mapped[int] = mapped_column()
    storage_backend: Mapped[str] = mapped_column(default="local")
    storage_path: Mapped[str] = mapped_column()
    entity_type: Mapped[str | None] = mapped_column(default=None)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(default=None)


class SyncOperation(Base, UUIDPkMixin, TimestampMixin):
    """Opération de synchronisation offline reçue d'un client mobile."""

    __tablename__ = "sync_operations"
    __table_args__ = (UniqueConstraint("tenant_id", "client_operation_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    device_session_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    client_operation_id: Mapped[str] = mapped_column()  # UUID généré côté client
    operation_type: Mapped[str] = (
        mapped_column()
    )  # create_sale | create_expense | create_customer | ...
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(default="pending", index=True)
    # pending | applied | conflict | failed
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    error_message: Mapped[str | None] = mapped_column(default=None)
    applied_at: Mapped[datetime | None] = mapped_column(default=None)


class FeatureFlag(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "feature_flags"

    code: Mapped[str] = mapped_column(unique=True, index=True)
    description: Mapped[str | None] = mapped_column(default=None)
    is_enabled: Mapped[bool] = mapped_column(default=False)
    tenant_overrides: Mapped[dict[str, bool]] = mapped_column(JSONB, default=dict)
    # tenant_id (str) -> bool
