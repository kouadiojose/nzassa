"""Fournisseurs et achats."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import MONEY, QTY, Base, TenantEntity


class Supplier(Base, TenantEntity):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(index=True)
    phone: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)
    address: Mapped[str | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)


class SupplierContact(Base, TenantEntity):
    __tablename__ = "supplier_contacts"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column()
    phone: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)
    role: Mapped[str | None] = mapped_column(default=None)


class PurchaseOrder(Base, TenantEntity):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("tenant_id", "number"),)

    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    number: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="draft", index=True)
    # draft | ordered | partially_received | received | cancelled
    ordered_at: Mapped[datetime | None] = mapped_column(default=None)
    expected_on: Mapped[date | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(default=None)
    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    amount_paid: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))


class PurchaseOrderItem(Base, TenantEntity):
    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[Decimal] = mapped_column(QTY)
    received_quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    unit_cost: Mapped[Decimal] = mapped_column(MONEY)
    line_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))


class PurchaseReceipt(Base, TenantEntity):
    """Réception (totale ou partielle) d'une commande d'achat."""

    __tablename__ = "purchase_receipts"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    received_at: Mapped[datetime] = mapped_column()
    received_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(default=None)


class SupplierPayment(Base, TenantEntity):
    __tablename__ = "supplier_payments"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="SET NULL"), index=True, default=None
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)
    method: Mapped[str] = mapped_column(default="cash")
    paid_at: Mapped[datetime] = mapped_column()
    reference: Mapped[str | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(default=None)
