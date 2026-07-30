"""Clients, dettes clients, fidélité."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import MONEY, Base, TenantEntity


class Customer(Base, TenantEntity):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("tenant_id", "phone"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    first_name: Mapped[str] = mapped_column(index=True)
    last_name: Mapped[str | None] = mapped_column(default=None, index=True)
    phone: Mapped[str | None] = mapped_column(default=None, index=True)
    email: Mapped[str | None] = mapped_column(default=None)
    address: Mapped[str | None] = mapped_column(default=None)
    gender: Mapped[str | None] = mapped_column(default=None)  # facultatif
    birth_date: Mapped[date | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(default=None)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    marketing_consent: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(MONEY, default=None)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name or ''}".strip()


class CustomerTag(Base, TenantEntity):
    __tablename__ = "customer_tags"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    name: Mapped[str] = mapped_column()
    color: Mapped[str | None] = mapped_column(default=None)


class CustomerDebt(Base, TenantEntity):
    """Créance client (issue d'une vente à crédit)."""

    __tablename__ = "customer_debts"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), index=True
    )
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales.id", ondelete="SET NULL"), index=True, default=None
    )
    original_amount: Mapped[Decimal] = mapped_column(MONEY)
    balance: Mapped[Decimal] = mapped_column(MONEY)
    due_date: Mapped[date | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="open", index=True)
    # open | partially_paid | paid | written_off
    promised_payment_date: Mapped[date | None] = mapped_column(default=None)
    written_off_at: Mapped[datetime | None] = mapped_column(default=None)
    written_off_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    write_off_reason: Mapped[str | None] = mapped_column(default=None)


class DebtPayment(Base, TenantEntity):
    __tablename__ = "debt_payments"

    debt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_debts.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(MONEY)
    method: Mapped[str] = mapped_column(default="cash")
    paid_at: Mapped[datetime] = mapped_column()
    received_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    reference: Mapped[str | None] = mapped_column(default=None)


class LoyaltyAccount(Base, TenantEntity):
    __tablename__ = "loyalty_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "customer_id"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    points_balance: Mapped[int] = mapped_column(default=0)
    lifetime_points: Mapped[int] = mapped_column(default=0)
    tier: Mapped[str] = mapped_column(default="bronze")  # bronze | silver | gold


class LoyaltyTransaction(Base, TenantEntity):
    __tablename__ = "loyalty_transactions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loyalty_accounts.id", ondelete="CASCADE"), index=True
    )
    points: Mapped[int] = mapped_column()  # + acquisition, - utilisation
    transaction_type: Mapped[str] = mapped_column()  # earn | redeem | adjust | expire
    reference_type: Mapped[str | None] = mapped_column(default=None)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    notes: Mapped[str | None] = mapped_column(default=None)


class Reward(Base, TenantEntity):
    __tablename__ = "rewards"

    name: Mapped[str] = mapped_column()
    points_cost: Mapped[int] = mapped_column()
    reward_type: Mapped[str] = mapped_column(
        default="discount"
    )  # discount | free_product | free_service
    value: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
