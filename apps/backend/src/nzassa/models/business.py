"""Entreprises, points de vente, paramètres et employés."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import Base, TenantEntity


class Business(Base, TenantEntity):
    __tablename__ = "businesses"

    legal_name: Mapped[str] = mapped_column()
    trade_name: Mapped[str] = mapped_column(index=True)
    logo_url: Mapped[str | None] = mapped_column(default=None)
    address: Mapped[str | None] = mapped_column(default=None)
    phone: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)
    industry: Mapped[str] = mapped_column(
        default="other"
    )  # beauty|hair|cosmetics|retail|services|other
    currency: Mapped[str] = mapped_column(default="XOF")
    country: Mapped[str] = mapped_column(default="CI")
    timezone: Mapped[str] = mapped_column(default="Africa/Abidjan")
    tax_id: Mapped[str | None] = mapped_column(default=None)
    tax_regime: Mapped[str | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    onboarding_completed: Mapped[bool] = mapped_column(default=False)


class BusinessSetting(Base, TenantEntity):
    """Paramètres clé/valeur typés par entreprise (reçus, numérotation, caisse...)."""

    __tablename__ = "business_settings"
    __table_args__ = (UniqueConstraint("tenant_id", "business_id", "key"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(index=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Branch(Base, TenantEntity):
    """Point de vente / établissement."""

    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    address: Mapped[str | None] = mapped_column(default=None)
    phone: Mapped[str | None] = mapped_column(default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    opening_hours: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    receipt_header: Mapped[str | None] = mapped_column(default=None)
    receipt_footer: Mapped[str | None] = mapped_column(default=None)


class Employee(Base, TenantEntity):
    """Fiche employé, éventuellement liée à un compte utilisateur."""

    __tablename__ = "employees"

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), index=True, default=None
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, default=None
    )
    first_name: Mapped[str] = mapped_column()
    last_name: Mapped[str] = mapped_column()
    phone: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)
    job_title: Mapped[str | None] = mapped_column(default=None)
    hired_on: Mapped[date | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="active")  # active | suspended | left
    avatar_url: Mapped[str | None] = mapped_column(default=None)
    can_receive_commissions: Mapped[bool] = mapped_column(default=True)
