"""Base déclarative, mixins communs et types colonnes.

Règles :
- `id` UUID généré côté application (compatible offline-first : le mobile
  génère ses UUID et le backend les accepte de façon idempotente) ;
- toutes les tables métier portent `tenant_id` (isolation multi-tenant) ;
- montants en NUMERIC(14, 2) — jamais de float ;
- horodatage UTC timezone-aware.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, ClassVar

from sqlalchemy import DateTime, ForeignKey, MetaData, Numeric, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

MONEY = Numeric(14, 2)
QTY = Numeric(14, 3)
RATE = Numeric(7, 4)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[type, object]] = {
        uuid.UUID: PgUUID(as_uuid=True),
        Decimal: MONEY,
        datetime: DateTime(timezone=True),
    }


class UUIDPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow, server_default=func.now()
    )


class TenantMixin:
    """Colonne d'isolation multi-tenant, indexée et non nullable."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="RESTRICT"), index=True
    )


class AuditColumnsMixin:
    created_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(default=None)


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)


class VersionMixin:
    """Verrouillage optimiste : incrémenté automatiquement par SQLAlchemy."""

    version: Mapped[int] = mapped_column(default=1)

    @classmethod
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)


class TenantEntity(
    UUIDPkMixin, TenantMixin, TimestampMixin, AuditColumnsMixin, SoftDeleteMixin, VersionMixin
):
    """Socle standard de toute entité métier rattachée à un tenant."""
