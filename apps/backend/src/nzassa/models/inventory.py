"""Stock : niveaux, mouvements immuables, inventaires, transferts."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import (
    MONEY,
    QTY,
    Base,
    TenantEntity,
    TenantMixin,
    TimestampMixin,
    UUIDPkMixin,
)


class StockLevel(Base, TenantEntity):
    """Quantité courante d'un produit dans un point de vente."""

    __tablename__ = "stock_levels"
    __table_args__ = (UniqueConstraint("tenant_id", "branch_id", "product_id"),)

    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    reserved_quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    lot_number: Mapped[str | None] = mapped_column(default=None)
    expires_on: Mapped[date | None] = mapped_column(default=None)


class StockMovement(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    """Mouvement de stock IMMUABLE — jamais modifié ni supprimé.

    Les corrections passent par des mouvements de compensation.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_movements_branch_product", "branch_id", "product_id"),)

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    movement_type: Mapped[str] = mapped_column(index=True)
    # purchase_in | sale_out | adjustment | transfer_in | transfer_out | loss
    # | damage | expiry | return_in | refund_in | inventory
    quantity: Mapped[Decimal] = mapped_column(QTY)  # signée : + entrée, - sortie
    quantity_after: Mapped[Decimal] = mapped_column(QTY)
    unit_cost: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    reference_type: Mapped[str | None] = mapped_column(default=None)  # sale | purchase_order | ...
    reference_id: Mapped[uuid.UUID | None] = mapped_column(default=None, index=True)
    reason: Mapped[str | None] = mapped_column(default=None)
    performed_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class StockInventory(Base, TenantEntity):
    __tablename__ = "stock_inventories"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        default="in_progress"
    )  # in_progress | validated | cancelled
    started_at: Mapped[datetime] = mapped_column()
    validated_at: Mapped[datetime | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(default=None)


class StockInventoryItem(Base, TenantEntity):
    __tablename__ = "stock_inventory_items"
    __table_args__ = (UniqueConstraint("tenant_id", "inventory_id", "product_id"),)

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_inventories.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    expected_quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    counted_quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))


class StockTransfer(Base, TenantEntity):
    __tablename__ = "stock_transfers"

    from_branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT")
    )
    to_branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(default="pending")  # pending | completed | cancelled
    notes: Mapped[str | None] = mapped_column(default=None)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)


class StockTransferItem(Base, TenantEntity):
    __tablename__ = "stock_transfer_items"

    transfer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_transfers.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"))
    quantity: Mapped[Decimal] = mapped_column(QTY)
