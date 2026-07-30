"""Gestion des plans et abonnements SaaS."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nzassa.core.errors import SubscriptionLimitError
from nzassa.models.auth import User
from nzassa.models.business import Branch
from nzassa.models.catalog import Product
from nzassa.models.subscriptions import Subscription, SubscriptionPlan

DEFAULT_PLANS: list[dict[str, Any]] = [
    {
        "code": "essential",
        "name": "Essentiel",
        "description": "Un point de vente, deux utilisateurs, l'essentiel pour démarrer.",
        "monthly_price": Decimal("5000"),
        "yearly_price": Decimal("50000"),
        "trial_days": 14,
        "limits": {"max_branches": 1, "max_users": 2, "max_products": 200},
        "sort_order": 1,
    },
    {
        "code": "professional",
        "name": "Professionnel",
        "description": "Rendez-vous, commissions, créances, fidélité et rapports avancés.",
        "monthly_price": Decimal("15000"),
        "yearly_price": Decimal("150000"),
        "trial_days": 14,
        "limits": {"max_branches": 3, "max_users": 10, "max_products": 5000},
        "sort_order": 2,
    },
    {
        "code": "enterprise",
        "name": "Entreprise",
        "description": "Multi-établissements, rôles personnalisés, API et assistance prioritaire.",
        "monthly_price": Decimal("40000"),
        "yearly_price": Decimal("400000"),
        "trial_days": 14,
        "limits": {"max_branches": 999, "max_users": 999, "max_products": 100000},
        "sort_order": 3,
    },
]


async def seed_plans(db: AsyncSession) -> None:
    """Crée les plans initiaux (idempotent)."""
    existing = {code for (code,) in (await db.execute(select(SubscriptionPlan.code))).all()}
    for plan_data in DEFAULT_PLANS:
        if plan_data["code"] not in existing:
            db.add(SubscriptionPlan(**plan_data))
    await db.flush()


async def get_active_subscription(db: AsyncSession, tenant_id: uuid.UUID) -> Subscription | None:
    return (
        (
            await db.execute(
                select(Subscription)
                .where(Subscription.tenant_id == tenant_id)
                .order_by(Subscription.created_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )


async def get_limits(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, int]:
    subscription = await get_active_subscription(db, tenant_id)
    if subscription is None:
        return dict(DEFAULT_PLANS[0]["limits"])
    plan = await db.get(SubscriptionPlan, subscription.plan_id)
    return dict(plan.limits) if plan else dict(DEFAULT_PLANS[0]["limits"])


async def enforce_limit(
    db: AsyncSession, tenant_id: uuid.UUID, limit_key: str, *, adding: int = 1
) -> None:
    """Vérifie une limite du plan avant création d'une ressource."""
    limits = await get_limits(db, tenant_id)
    maximum = limits.get(limit_key)
    if maximum is None:
        return
    model = {
        "max_branches": Branch,
        "max_users": User,
        "max_products": Product,
    }.get(limit_key)
    if model is None:
        return
    current = (
        await db.execute(
            select(func.count()).select_from(model).where(model.tenant_id == tenant_id)  # type: ignore[attr-defined]
        )
    ).scalar_one()
    if current + adding > maximum:
        raise SubscriptionLimitError(
            details={"limit": limit_key, "maximum": maximum, "current": current}
        )


async def change_plan(
    db: AsyncSession, subscription: Subscription, new_plan: SubscriptionPlan, billing_cycle: str
) -> Subscription:
    """Upgrade/downgrade : prend effet immédiatement, période recalculée."""
    now = datetime.now(UTC)
    subscription.plan_id = new_plan.id
    subscription.billing_cycle = billing_cycle
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=365 if billing_cycle == "yearly" else 30)
    return subscription
