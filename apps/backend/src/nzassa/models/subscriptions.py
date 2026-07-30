"""Abonnements SaaS : plans, fonctionnalités, limites, factures."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import MONEY, Base, TenantMixin, TimestampMixin, UUIDPkMixin


class SubscriptionPlan(Base, UUIDPkMixin, TimestampMixin):
    """Plan global (pas de tenant_id : géré par le Super Admin)."""

    __tablename__ = "subscription_plans"

    code: Mapped[str] = mapped_column(
        unique=True, index=True
    )  # essential | professional | enterprise
    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)
    monthly_price: Mapped[Decimal] = mapped_column(MONEY)
    yearly_price: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    currency: Mapped[str] = mapped_column(default="XOF")
    trial_days: Mapped[int] = mapped_column(default=14)
    limits: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # ex. {"max_branches": 1, "max_users": 2, "max_products": 200}
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)


class Feature(Base, UUIDPkMixin):
    __tablename__ = "features"

    code: Mapped[str] = mapped_column(unique=True, index=True)  # ex. appointments, commissions
    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)


class PlanFeature(Base, UUIDPkMixin):
    __tablename__ = "plan_features"
    __table_args__ = (UniqueConstraint("plan_id", "feature_id"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="CASCADE"), index=True
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("features.id", ondelete="CASCADE"), index=True
    )


class Subscription(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(default="trialing", index=True)
    # trialing | active | past_due | suspended | cancelled | expired
    billing_cycle: Mapped[str] = mapped_column(default="monthly")  # monthly | yearly
    trial_ends_at: Mapped[datetime | None] = mapped_column(default=None)
    current_period_start: Mapped[datetime] = mapped_column()
    current_period_end: Mapped[datetime] = mapped_column()
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(default=None)
    cancelled_at: Mapped[datetime | None] = mapped_column(default=None)


class SubscriptionInvoice(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "subscription_invoices"
    __table_args__ = (UniqueConstraint("number"),)

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="RESTRICT"), index=True
    )
    number: Mapped[str] = mapped_column()
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(default="XOF")
    status: Mapped[str] = mapped_column(default="pending")  # pending | paid | failed | void
    due_date: Mapped[datetime | None] = mapped_column(default=None)
    paid_at: Mapped[datetime | None] = mapped_column(default=None)
    payment_provider: Mapped[str | None] = mapped_column(default=None)
    payment_reference: Mapped[str | None] = mapped_column(default=None)
