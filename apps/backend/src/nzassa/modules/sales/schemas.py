"""Schémas des ventes, paiements et caisse."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from nzassa.models.sales import PAYMENT_METHODS

PAYMENT_PATTERN = f"^({'|'.join(PAYMENT_METHODS)})$"


class SaleItemIn(BaseModel):
    item_type: str = Field(default="product", pattern="^(product|service)$")
    product_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    employee_id: uuid.UUID | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)  # None = prix catalogue
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)


class PaymentIn(BaseModel):
    method: str = Field(pattern=PAYMENT_PATTERN)
    amount: Decimal = Field(gt=0)
    reference: str | None = None


class SaleCreate(BaseModel):
    branch_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    seller_employee_id: uuid.UUID | None = None
    items: list[SaleItemIn] = Field(min_length=1)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0)
    payments: list[PaymentIn] = []
    notes: str | None = None
    status: str = Field(default="completed", pattern="^(draft|completed)$")
    client_reference: str | None = None  # UUID client pour l'idempotence offline
    sold_at: datetime | None = None


class SalePaymentRequest(BaseModel):
    payments: list[PaymentIn] = Field(min_length=1)


class SaleCancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RefundItemIn(BaseModel):
    sale_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0)


class RefundRequest(BaseModel):
    items: list[RefundItemIn] = Field(min_length=1)
    method: str = Field(default="cash", pattern=PAYMENT_PATTERN)
    reason: str = Field(min_length=3, max_length=500)
    restock: bool = True


class SaleItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_type: str
    product_id: uuid.UUID | None
    service_id: uuid.UUID | None
    employee_id: uuid.UUID | None
    label: str
    quantity: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    refunded_quantity: Decimal


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    method: str
    amount: Decimal
    reference: str | None
    paid_at: datetime
    status: str


class SaleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID | None
    number: str
    status: str
    sold_at: datetime
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total: Decimal
    amount_paid: Decimal
    amount_due: Decimal
    notes: str | None
    client_reference: str | None
    items: list[SaleItemOut]
    payments: list[PaymentOut]


# ---------- Caisse ----------


class OpenSessionRequest(BaseModel):
    register_id: uuid.UUID
    opening_float: Decimal = Field(default=Decimal("0"), ge=0)


class CloseSessionRequest(BaseModel):
    counted_cash: Decimal = Field(ge=0)
    notes: str | None = None


class CashMovementRequest(BaseModel):
    movement_type: str = Field(pattern="^(deposit|withdrawal)$")
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=3)


class CashSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    register_id: uuid.UUID
    branch_id: uuid.UUID
    status: str
    opened_at: datetime
    closed_at: datetime | None
    opening_float: Decimal
    expected_cash: Decimal | None
    counted_cash: Decimal | None
    difference: Decimal | None
    notes: str | None
