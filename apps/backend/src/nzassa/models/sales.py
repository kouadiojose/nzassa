"""Ventes, caisse, paiements, remboursements."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nzassa.models.base import MONEY, QTY, Base, TenantEntity

# Moyens de paiement supportés nativement
PAYMENT_METHODS = (
    "cash",
    "wave",
    "orange_money",
    "mtn_money",
    "moov_money",
    "card",
    "bank_transfer",
    "credit",
)


class PaymentMethod(Base, TenantEntity):
    """Moyen de paiement activable/configurable par entreprise."""

    __tablename__ = "payment_methods"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    code: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    requires_reference: Mapped[bool] = mapped_column(default=False)


class CashRegister(Base, TenantEntity):
    __tablename__ = "cash_registers"
    __table_args__ = (UniqueConstraint("tenant_id", "branch_id", "name"),)

    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)


class CashSession(Base, TenantEntity):
    __tablename__ = "cash_sessions"

    register_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cash_registers.id", ondelete="RESTRICT"), index=True
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), index=True
    )
    opened_by: Mapped[uuid.UUID] = mapped_column()
    closed_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="open", index=True)  # open | closed
    opened_at: Mapped[datetime] = mapped_column()
    closed_at: Mapped[datetime | None] = mapped_column(default=None)
    opening_float: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    expected_cash: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    counted_cash: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    difference: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    notes: Mapped[str | None] = mapped_column(default=None)


class CashMovement(Base, TenantEntity):
    """Entrée/sortie de caisse hors vente (dépôt, retrait, dépense...)."""

    __tablename__ = "cash_movements"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cash_sessions.id", ondelete="RESTRICT"), index=True
    )
    movement_type: Mapped[str] = mapped_column()  # deposit | withdrawal | sale | refund | expense
    amount: Mapped[Decimal] = mapped_column(MONEY)  # signé
    reason: Mapped[str | None] = mapped_column(default=None)
    reference_type: Mapped[str | None] = mapped_column(default=None)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(default=None)


class Sale(Base, TenantEntity):
    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number"),
        UniqueConstraint("tenant_id", "client_reference"),
        Index("ix_sales_branch_status", "branch_id", "status"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True, default=None
    )
    cash_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cash_sessions.id", ondelete="SET NULL"), index=True, default=None
    )
    seller_employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), index=True, default=None
    )
    number: Mapped[str] = mapped_column()
    # Idempotence offline-first : UUID généré par le client mobile
    client_reference: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="draft", index=True)
    # draft | completed | cancelled | refunded | partially_refunded
    sold_at: Mapped[datetime] = mapped_column(index=True)
    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    amount_paid: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    amount_due: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    coupon_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("coupons.id", ondelete="SET NULL"), default=None
    )
    notes: Mapped[str | None] = mapped_column(default=None)
    cancelled_at: Mapped[datetime | None] = mapped_column(default=None)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    cancellation_reason: Mapped[str | None] = mapped_column(default=None)
    previous_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)

    items: Mapped[list["SaleItem"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="sale", cascade="all, delete-orphan", lazy="selectin"
    )


class SaleItem(Base, TenantEntity):
    __tablename__ = "sale_items"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"), index=True
    )
    item_type: Mapped[str] = mapped_column(default="product")  # product | service
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True, default=None
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"), index=True, default=None
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="RESTRICT"), default=None
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), default=None
    )
    label: Mapped[str] = mapped_column()  # libellé figé au moment de la vente
    quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    discount_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    tax_rate: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    refunded_quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))

    sale: Mapped[Sale] = relationship(back_populates="items")


class Payment(Base, TenantEntity):
    __tablename__ = "payments"

    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales.id", ondelete="RESTRICT"), index=True, default=None
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True, default=None
    )
    method: Mapped[str] = mapped_column()  # voir PAYMENT_METHODS
    amount: Mapped[Decimal] = mapped_column(MONEY)
    reference: Mapped[str | None] = mapped_column(default=None)
    paid_at: Mapped[datetime] = mapped_column()
    received_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="confirmed")  # confirmed | reversed

    sale: Mapped[Sale | None] = relationship(back_populates="payments")


class Refund(Base, TenantEntity):
    __tablename__ = "refunds"

    sale_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)
    method: Mapped[str] = mapped_column(default="cash")
    reason: Mapped[str] = mapped_column()
    refunded_at: Mapped[datetime] = mapped_column()
    refunded_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    restock: Mapped[bool] = mapped_column(default=True)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    # [{sale_item_id, quantity}]
