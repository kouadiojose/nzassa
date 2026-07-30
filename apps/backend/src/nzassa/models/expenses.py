"""Dépenses."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import MONEY, Base, TenantEntity


class ExpenseCategory(Base, TenantEntity):
    __tablename__ = "expense_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    name: Mapped[str] = mapped_column()
    approval_threshold: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)


class Expense(Base, TenantEntity):
    __tablename__ = "expenses"

    branch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("branches.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="SET NULL"), index=True, default=None
    )
    label: Mapped[str] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(MONEY)
    expense_date: Mapped[date] = mapped_column(index=True)
    payee: Mapped[str | None] = mapped_column(default=None)
    payment_method: Mapped[str] = mapped_column(default="cash")
    receipt_file_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="approved", index=True)
    # pending_approval | approved | rejected | cancelled
    approved_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    is_recurring: Mapped[bool] = mapped_column(default=False)
    recurrence_rule: Mapped[str | None] = mapped_column(default=None)  # ex. monthly
    client_reference: Mapped[str | None] = mapped_column(default=None, unique=True)
    notes: Mapped[str | None] = mapped_column(default=None)
