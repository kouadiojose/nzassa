"""Schémas du catalogue (produits, prestations, taxonomies)."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None
    kind: str = Field(default="product", pattern="^(product|service)$")


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    kind: str


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class UnitCreate(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=60)
    allow_decimal: bool = False


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    allow_decimal: bool


class TaxCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    rate: Decimal = Field(ge=0, le=1)
    is_inclusive: bool = True


class TaxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    rate: Decimal
    is_inclusive: bool
    is_active: bool


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    tax_id: uuid.UUID | None = None
    sku: str | None = Field(default=None, max_length=60)
    barcode: str | None = Field(default=None, max_length=60)
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0)
    selling_price: Decimal = Field(ge=0)
    promo_price: Decimal | None = Field(default=None, ge=0)
    low_stock_threshold: Decimal = Field(default=Decimal("0"), ge=0)
    track_stock: bool = True
    has_expiry: bool = False
    image_url: str | None = None
    branch_prices: dict[str, str] = {}


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    tax_id: uuid.UUID | None = None
    sku: str | None = None
    barcode: str | None = None
    purchase_price: Decimal | None = Field(default=None, ge=0)
    selling_price: Decimal | None = Field(default=None, ge=0)
    promo_price: Decimal | None = Field(default=None, ge=0)
    low_stock_threshold: Decimal | None = Field(default=None, ge=0)
    track_stock: bool | None = None
    has_expiry: bool | None = None
    image_url: str | None = None
    is_active: bool | None = None
    archived: bool | None = None
    branch_prices: dict[str, str] | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    category_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    unit_id: uuid.UUID | None
    tax_id: uuid.UUID | None
    sku: str | None
    barcode: str | None
    purchase_price: Decimal
    selling_price: Decimal
    promo_price: Decimal | None
    low_stock_threshold: Decimal
    track_stock: bool
    has_expiry: bool
    image_url: str | None
    is_active: bool
    archived: bool
    branch_prices: dict[str, str]


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: uuid.UUID | None = None
    tax_id: uuid.UUID | None = None
    price: Decimal = Field(ge=0)
    promo_price: Decimal | None = Field(default=None, ge=0)
    duration_minutes: int = Field(default=30, ge=5, le=600)


class ServiceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category_id: uuid.UUID | None = None
    tax_id: uuid.UUID | None = None
    price: Decimal | None = Field(default=None, ge=0)
    promo_price: Decimal | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=5, le=600)
    is_active: bool | None = None
    archived: bool | None = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    category_id: uuid.UUID | None
    tax_id: uuid.UUID | None
    price: Decimal
    promo_price: Decimal | None
    duration_minutes: int
    is_active: bool
    archived: bool
