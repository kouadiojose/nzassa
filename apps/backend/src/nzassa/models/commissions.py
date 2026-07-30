"""Commissions employés."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import MONEY, RATE, Base, TenantEntity


class EmployeeCommissionRule(Base, TenantEntity):
    __tablename__ = "employee_commission_rules"

    name: Mapped[str] = mapped_column()
    scope: Mapped[str] = mapped_column(default="all")  # all | product | service | category
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), default=None
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), default=None
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_categories.id", ondelete="CASCADE"), default=None
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), default=None
    )  # NULL = tous les employés
    commission_type: Mapped[str] = mapped_column(default="percent")  # percent | fixed
    rate: Mapped[Decimal | None] = mapped_column(RATE, default=None)  # ex. 0.1000 = 10 %
    fixed_amount: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)


class EmployeeCommission(Base, TenantEntity):
    """Commission calculée pour un employé sur une ligne de vente.

    Une commission validée (status != pending) n'est JAMAIS recalculée
    silencieusement — toute modification passe par une contestation.
    """

    __tablename__ = "employee_commissions"
    __table_args__ = (Index("ix_employee_commissions_emp_period", "employee_id", "period_date"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"))
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales.id", ondelete="SET NULL"), index=True, default=None
    )
    sale_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sale_items.id", ondelete="SET NULL"), default=None
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employee_commission_rules.id", ondelete="SET NULL"), default=None
    )
    base_amount: Mapped[Decimal] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    period_date: Mapped[date] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(default="pending", index=True)
    # pending | validated | paid | disputed | cancelled
    validated_at: Mapped[datetime | None] = mapped_column(default=None)
    validated_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    paid_at: Mapped[datetime | None] = mapped_column(default=None)
    dispute_reason: Mapped[str | None] = mapped_column(default=None)
