"""Endpoints d'abonnement côté entreprise."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import NotFoundError
from nzassa.core.responses import ok
from nzassa.models.subscriptions import SubscriptionInvoice, SubscriptionPlan
from nzassa.modules.subscriptions import service as subs_service
from nzassa.modules.subscriptions.payments import get_payment_provider

router = APIRouter(prefix="/subscription", tags=["subscription"])


class ChangePlanRequest(BaseModel):
    plan_code: str = Field(pattern="^(essential|professional|enterprise)$")
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|yearly)$")


def _plan_out(plan: SubscriptionPlan) -> dict[str, Any]:
    return {
        "id": str(plan.id),
        "code": plan.code,
        "name": plan.name,
        "description": plan.description,
        "monthly_price": str(plan.monthly_price),
        "yearly_price": str(plan.yearly_price) if plan.yearly_price else None,
        "currency": plan.currency,
        "trial_days": plan.trial_days,
        "limits": plan.limits,
    }


@router.get("/plans")
async def list_plans(db: Db) -> dict[str, Any]:
    await subs_service.seed_plans(db)
    plans = (
        (
            await db.execute(
                select(SubscriptionPlan)
                .where(SubscriptionPlan.is_active.is_(True))
                .order_by(SubscriptionPlan.sort_order)
            )
        )
        .scalars()
        .all()
    )
    return ok([_plan_out(p) for p in plans])


@router.get("", dependencies=[require_permissions("subscription.read")])
async def current_subscription(db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    subscription = await subs_service.get_active_subscription(db, tenant_id)
    if subscription is None:
        return ok(None, message="Aucun abonnement")
    plan = await db.get(SubscriptionPlan, subscription.plan_id)
    now = datetime.now(UTC)
    return ok(
        {
            "id": str(subscription.id),
            "status": subscription.status,
            "billing_cycle": subscription.billing_cycle,
            "plan": _plan_out(plan) if plan else None,
            "trial_ends_at": subscription.trial_ends_at.isoformat()
            if subscription.trial_ends_at
            else None,
            "current_period_end": subscription.current_period_end.isoformat(),
            "is_expired": subscription.current_period_end < now
            and subscription.status not in ("active", "trialing"),
            "limits": await subs_service.get_limits(db, tenant_id),
        }
    )


@router.post("/change-plan", dependencies=[require_permissions("subscription.manage")])
async def change_plan(payload: ChangePlanRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    subscription = await subs_service.get_active_subscription(db, tenant_id)
    if subscription is None:
        raise NotFoundError("Aucun abonnement actif")
    plan = (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == payload.plan_code))
    ).scalar_one_or_none()
    if plan is None:
        raise NotFoundError("Plan introuvable")

    await subs_service.change_plan(db, subscription, plan, payload.billing_cycle)

    # Facture d'abonnement + intention de paiement via l'abstraction
    amount = plan.yearly_price if payload.billing_cycle == "yearly" else plan.monthly_price
    number = f"SUB-{datetime.now(UTC):%Y%m%d}-{str(uuid.uuid4())[:8].upper()}"
    invoice = SubscriptionInvoice(
        tenant_id=tenant_id,
        subscription_id=subscription.id,
        number=number,
        amount=amount or plan.monthly_price,
        currency=plan.currency,
        status="pending",
    )
    db.add(invoice)
    provider = get_payment_provider()
    intent = await provider.create_payment(
        invoice_number=number,
        amount=invoice.amount,
        currency=invoice.currency,
        customer_email=ctx.user.email,
    )
    invoice.payment_provider = provider.name
    invoice.payment_reference = intent.reference
    await record_audit(
        db,
        action="subscription.change_plan",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        after={"plan": plan.code, "cycle": payload.billing_cycle},
    )
    return ok(
        {
            "invoice_number": number,
            "amount": str(invoice.amount),
            "payment_status": intent.status,
            "checkout_url": intent.checkout_url,
        },
        message="Plan modifié — facture en attente de règlement",
    )


@router.get("/invoices", dependencies=[require_permissions("subscription.read")])
async def list_invoices(db: Db, ctx: Ctx) -> dict[str, Any]:
    invoices = (
        (
            await db.execute(
                select(SubscriptionInvoice)
                .where(SubscriptionInvoice.tenant_id == ctx.require_tenant())
                .order_by(SubscriptionInvoice.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return ok(
        [
            {
                "id": str(i.id),
                "number": i.number,
                "amount": str(i.amount),
                "currency": i.currency,
                "status": i.status,
                "paid_at": i.paid_at.isoformat() if i.paid_at else None,
                "created_at": i.created_at.isoformat(),
            }
            for i in invoices
        ]
    )
