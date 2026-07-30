"""Facturation (préparée pour la Facture Normalisée Électronique de Côte d'Ivoire)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nzassa.models.base import MONEY, QTY, Base, TenantEntity


class Invoice(Base, TenantEntity):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "number"),)

    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales.id", ondelete="SET NULL"), index=True, default=None
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True, default=None
    )
    number: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="draft", index=True)
    # draft | issued | cancelled
    issued_at: Mapped[datetime | None] = mapped_column(default=None)
    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(default="XOF")
    pdf_file_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    # Connecteur fiscal (FNE CI) — renseigné uniquement par un vrai connecteur agréé
    fiscal_status: Mapped[str] = mapped_column(default="not_submitted")
    # not_submitted | submitted | accepted | rejected
    fiscal_reference: Mapped[str | None] = mapped_column(default=None)
    fiscal_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)

    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", lazy="selectin"
    )


class InvoiceItem(Base, TenantEntity):
    __tablename__ = "invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column()
    quantity: Mapped[Decimal] = mapped_column(QTY, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(MONEY)
    tax_rate: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    tax_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class CreditNote(Base, TenantEntity):
    """Avoir sur facture."""

    __tablename__ = "credit_notes"
    __table_args__ = (UniqueConstraint("tenant_id", "number"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), index=True
    )
    number: Mapped[str] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(MONEY)
    reason: Mapped[str] = mapped_column()
    issued_at: Mapped[datetime] = mapped_column()
