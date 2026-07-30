"""Tenant : racine de l'isolation des données."""

import uuid
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import Base, TimestampMixin, UUIDPkMixin


class Tenant(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column()
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    status: Mapped[str] = mapped_column(default="active")  # active | suspended | closed
    suspended_at: Mapped[datetime | None] = mapped_column(default=None)
    suspension_reason: Mapped[str | None] = mapped_column(default=None)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
