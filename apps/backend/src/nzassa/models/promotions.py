"""Promotions et coupons."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import MONEY, Base, TenantEntity


class Promotion(Base, TenantEntity):
    __tablename__ = "promotions"

    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column(default=None)
    discount_type: Mapped[str] = mapped_column(default="percent")  # percent | fixed
    discount_value: Mapped[Decimal] = mapped_column(MONEY)
    starts_at: Mapped[datetime | None] = mapped_column(default=None)
    ends_at: Mapped[datetime | None] = mapped_column(default=None)
    scope: Mapped[str] = mapped_column(default="all")  # all | products | categories | customers
    product_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    category_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    customer_ids: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    is_birthday_promo: Mapped[bool] = mapped_column(default=False)
    max_uses: Mapped[int | None] = mapped_column(default=None)
    used_count: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class Coupon(Base, TenantEntity):
    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    code: Mapped[str] = mapped_column(index=True)
    discount_type: Mapped[str] = mapped_column(default="percent")
    discount_value: Mapped[Decimal] = mapped_column(MONEY)
    min_amount: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    max_uses: Mapped[int | None] = mapped_column(default=None)
    used_count: Mapped[int] = mapped_column(default=0)
    max_uses_per_customer: Mapped[int | None] = mapped_column(default=None)
    starts_at: Mapped[datetime | None] = mapped_column(default=None)
    ends_at: Mapped[datetime | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    promotion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("promotions.id", ondelete="SET NULL"), default=None
    )
