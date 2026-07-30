"""Schémas du module stock."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StockLevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal
    reserved_quantity: Decimal


class StockEntryRequest(BaseModel):
    branch_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal | None = Field(default=None, ge=0)
    reason: str | None = None


class StockExitRequest(BaseModel):
    branch_id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    movement_type: str = Field(pattern="^(loss|damage|expiry)$")
    reason: str = Field(min_length=3)


class StockAdjustRequest(BaseModel):
    branch_id: uuid.UUID
    product_id: uuid.UUID
    counted_quantity: Decimal = Field(ge=0)
    reason: str = Field(min_length=3)


class StockTransferRequest(BaseModel):
    from_branch_id: uuid.UUID
    to_branch_id: uuid.UUID
    items: list["TransferItemIn"] = Field(min_length=1)
    notes: str | None = None


class TransferItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    product_id: uuid.UUID
    movement_type: str
    quantity: Decimal
    quantity_after: Decimal
    unit_cost: Decimal | None
    reference_type: str | None
    reference_id: uuid.UUID | None
    reason: str | None
    created_at: datetime
