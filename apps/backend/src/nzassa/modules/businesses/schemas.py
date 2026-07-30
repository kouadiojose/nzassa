"""Schémas du module entreprises / points de vente."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BusinessUpdate(BaseModel):
    legal_name: str | None = Field(default=None, min_length=2, max_length=160)
    trade_name: str | None = Field(default=None, min_length=2, max_length=160)
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    industry: str | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    timezone: str | None = None
    tax_id: str | None = None
    tax_regime: str | None = None
    logo_url: str | None = None
    onboarding_completed: bool | None = None


class BusinessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legal_name: str
    trade_name: str
    logo_url: str | None
    address: str | None
    phone: str | None
    email: str | None
    industry: str
    currency: str
    country: str
    timezone: str
    tax_id: str | None
    tax_regime: str | None
    is_active: bool
    onboarding_completed: bool
    created_at: datetime


class BranchCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=120)
    address: str | None = None
    phone: str | None = None
    opening_hours: dict[str, Any] = {}
    receipt_header: str | None = None
    receipt_footer: str | None = None


class BranchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = None
    phone: str | None = None
    opening_hours: dict[str, Any] | None = None
    receipt_header: str | None = None
    receipt_footer: str | None = None
    is_active: bool | None = None


class BranchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    code: str
    name: str
    address: str | None
    phone: str | None
    is_active: bool
    opening_hours: dict[str, Any]
    receipt_header: str | None
    receipt_footer: str | None


class SettingUpsert(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    value: dict[str, Any]
