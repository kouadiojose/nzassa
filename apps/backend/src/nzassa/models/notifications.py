"""Notifications internes, push, email + préférences."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin


class Notification(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    notification_type: Mapped[str] = mapped_column(index=True)
    # low_stock | product_expired | appointment_reminder | debt_due | payment_received
    # | subscription_expiring | sale_cancelled | refund | large_expense | invitation
    # | suspicious_activity
    title: Mapped[str] = mapped_column()
    body: Mapped[str] = mapped_column()
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    channel: Mapped[str] = mapped_column(default="internal")  # internal | push | email
    status: Mapped[str] = mapped_column(default="pending", index=True)
    # pending | sent | failed
    sent_at: Mapped[datetime | None] = mapped_column(default=None)
    read_at: Mapped[datetime | None] = mapped_column(default=None)
    retry_count: Mapped[int] = mapped_column(default=0)


class NotificationPreference(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "notification_type"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    notification_type: Mapped[str] = mapped_column()
    internal_enabled: Mapped[bool] = mapped_column(default=True)
    push_enabled: Mapped[bool] = mapped_column(default=True)
    email_enabled: Mapped[bool] = mapped_column(default=False)
