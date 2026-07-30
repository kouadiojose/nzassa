"""Catalogue : produits, prestations, catégories, marques, variantes, unités, taxes."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import MONEY, QTY, RATE, Base, TenantEntity


class ProductCategory(Base, TenantEntity):
    __tablename__ = "product_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    name: Mapped[str] = mapped_column()
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_categories.id", ondelete="SET NULL"), default=None
    )
    kind: Mapped[str] = mapped_column(default="product")  # product | service


class ProductBrand(Base, TenantEntity):
    __tablename__ = "product_brands"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    name: Mapped[str] = mapped_column()


class Unit(Base, TenantEntity):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    code: Mapped[str] = mapped_column()  # ex. pcs, kg, L
    name: Mapped[str] = mapped_column()
    allow_decimal: Mapped[bool] = mapped_column(default=False)


class Tax(Base, TenantEntity):
    __tablename__ = "taxes"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    name: Mapped[str] = mapped_column()  # ex. TVA 18%
    rate: Mapped[Decimal] = mapped_column(RATE)  # 0.1800
    is_inclusive: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Product(Base, TenantEntity):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku"),
        UniqueConstraint("tenant_id", "barcode"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(index=True)
    description: Mapped[str | None] = mapped_column(default=None)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_categories.id", ondelete="SET NULL"), index=True, default=None
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_brands.id", ondelete="SET NULL"), default=None
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("units.id", ondelete="SET NULL"), default=None
    )
    tax_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("taxes.id", ondelete="SET NULL"), default=None
    )
    sku: Mapped[str | None] = mapped_column(default=None, index=True)
    barcode: Mapped[str | None] = mapped_column(default=None, index=True)
    purchase_price: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    selling_price: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    promo_price: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    low_stock_threshold: Mapped[Decimal] = mapped_column(QTY, default=Decimal("0"))
    track_stock: Mapped[bool] = mapped_column(default=True)
    has_expiry: Mapped[bool] = mapped_column(default=False)
    image_url: Mapped[str | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    archived: Mapped[bool] = mapped_column(default=False)
    branch_prices: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)  # branch_id -> prix


class ProductVariant(Base, TenantEntity):
    __tablename__ = "product_variants"
    __table_args__ = (UniqueConstraint("tenant_id", "product_id", "name"),)

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column()  # ex. 50ml, Rouge
    sku: Mapped[str | None] = mapped_column(default=None)
    barcode: Mapped[str | None] = mapped_column(default=None)
    purchase_price: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    selling_price: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)


class Service(Base, TenantEntity):
    """Prestation de service (coiffure, soin...)."""

    __tablename__ = "services"

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(index=True)
    description: Mapped[str | None] = mapped_column(default=None)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_categories.id", ondelete="SET NULL"), default=None
    )
    tax_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("taxes.id", ondelete="SET NULL"), default=None
    )
    price: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    promo_price: Mapped[Decimal | None] = mapped_column(MONEY, default=None)
    duration_minutes: Mapped[int] = mapped_column(default=30)
    is_active: Mapped[bool] = mapped_column(default=True)
    archived: Mapped[bool] = mapped_column(default=False)
