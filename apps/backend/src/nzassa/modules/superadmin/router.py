"""Espace Super Administration — isolé de l'espace entreprise.

Toutes les routes exigent `is_superadmin` (utilisateur système sans tenant).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_superadmin
from nzassa.core.errors import ConflictError, NotFoundError
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.models.auth import User
from nzassa.models.business import Business
from nzassa.models.sales import Sale
from nzassa.models.subscriptions import Subscription, SubscriptionInvoice, SubscriptionPlan
from nzassa.models.system import AuditLog, FeatureFlag, SyncOperation
from nzassa.models.tenant import Tenant

router = APIRouter(prefix="/superadmin", tags=["superadmin"], dependencies=[require_superadmin()])

Page = Annotated[PageParams, Depends(page_params)]


class SuspendRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class PlanUpdate(BaseModel):
    name: str | None = None
    monthly_price: Decimal | None = Field(default=None, ge=0)
    yearly_price: Decimal | None = Field(default=None, ge=0)
    trial_days: int | None = Field(default=None, ge=0, le=90)
    limits: dict[str, int] | None = None
    is_active: bool | None = None


class FlagUpsert(BaseModel):
    code: str = Field(min_length=2, max_length=80)
    description: str | None = None
    is_enabled: bool = False
    tenant_overrides: dict[str, bool] = {}


class ConfirmInvoiceRequest(BaseModel):
    payment_reference: str | None = None


@router.get("/dashboard")
async def global_dashboard(db: Db) -> dict[str, Any]:
    tenants_total = (await db.execute(select(func.count()).select_from(Tenant))).scalar_one()
    tenants_active = (
        await db.execute(select(func.count()).select_from(Tenant).where(Tenant.status == "active"))
    ).scalar_one()
    users_total = (
        await db.execute(select(func.count()).select_from(User).where(User.deleted_at.is_(None)))
    ).scalar_one()
    sales_total = (await db.execute(select(func.count()).select_from(Sale))).scalar_one()
    subs_rows = (
        await db.execute(select(Subscription.status, func.count()).group_by(Subscription.status))
    ).all()
    subs_by_status: dict[str, int] = {status: count for status, count in subs_rows}
    pending_invoices = (
        await db.execute(
            select(func.count())
            .select_from(SubscriptionInvoice)
            .where(SubscriptionInvoice.status == "pending")
        )
    ).scalar_one()
    failed_syncs = (
        await db.execute(
            select(func.count()).select_from(SyncOperation).where(SyncOperation.status == "failed")
        )
    ).scalar_one()
    return ok(
        {
            "tenants_total": tenants_total,
            "tenants_active": tenants_active,
            "users_total": users_total,
            "sales_total": sales_total,
            "subscriptions_by_status": subs_by_status,
            "pending_subscription_invoices": pending_invoices,
            "failed_sync_operations": failed_syncs,
        }
    )


@router.get("/tenants")
async def list_tenants(db: Db, params: Page, status: str | None = None) -> dict[str, Any]:
    query = select(Tenant)
    if status:
        query = query.where(Tenant.status == status)
    if params.search:
        query = query.where(Tenant.name.ilike(f"%{params.search}%"))
    items, meta = await paginate(db, query, params, default_sort=Tenant.created_at)
    return ok(
        [
            {
                "id": str(t.id),
                "name": t.name,
                "slug": t.slug,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
            }
            for t in items
        ],
        **meta,
    )


@router.get("/tenants/{tenant_id}")
async def tenant_detail(tenant_id: uuid.UUID, db: Db) -> dict[str, Any]:
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant introuvable")
    business = (
        (await db.execute(select(Business).where(Business.tenant_id == tenant_id).limit(1)))
        .scalars()
        .first()
    )
    users_count = (
        await db.execute(select(func.count()).select_from(User).where(User.tenant_id == tenant_id))
    ).scalar_one()
    sales_count = (
        await db.execute(select(func.count()).select_from(Sale).where(Sale.tenant_id == tenant_id))
    ).scalar_one()
    subscription = (
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
    plan = await db.get(SubscriptionPlan, subscription.plan_id) if subscription else None
    return ok(
        {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "status": tenant.status,
            "suspension_reason": tenant.suspension_reason,
            "business": {
                "trade_name": business.trade_name if business else None,
                "industry": business.industry if business else None,
                "country": business.country if business else None,
            },
            "users_count": users_count,
            "sales_count": sales_count,
            "subscription": {
                "status": subscription.status if subscription else None,
                "plan": plan.code if plan else None,
                "period_end": subscription.current_period_end.isoformat() if subscription else None,
            },
        }
    )


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    tenant_id: uuid.UUID, payload: SuspendRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant introuvable")
    if tenant.status == "suspended":
        raise ConflictError("Tenant déjà suspendu")
    tenant.status = "suspended"
    tenant.suspended_at = datetime.now(UTC)
    tenant.suspension_reason = payload.reason
    await record_audit(
        db,
        action="superadmin.tenant_suspend",
        user_id=ctx.user.id,
        entity_type="tenant",
        entity_id=tenant.id,
        after={"reason": payload.reason},
    )
    return ok(message="Tenant suspendu")


@router.post("/tenants/{tenant_id}/activate")
async def activate_tenant(tenant_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant introuvable")
    tenant.status = "active"
    tenant.suspended_at = None
    tenant.suspension_reason = None
    await record_audit(
        db,
        action="superadmin.tenant_activate",
        user_id=ctx.user.id,
        entity_type="tenant",
        entity_id=tenant.id,
    )
    return ok(message="Tenant activé")


@router.patch("/plans/{plan_code}")
async def update_plan(plan_code: str, payload: PlanUpdate, db: Db, ctx: Ctx) -> dict[str, Any]:
    plan = (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == plan_code))
    ).scalar_one_or_none()
    if plan is None:
        raise NotFoundError("Plan introuvable")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    await record_audit(
        db,
        action="superadmin.plan_update",
        user_id=ctx.user.id,
        entity_type="subscription_plan",
        entity_id=plan.id,
    )
    return ok(message="Plan mis à jour")


@router.post("/subscription-invoices/{invoice_id}/confirm-payment")
async def confirm_subscription_payment(
    invoice_id: uuid.UUID, payload: ConfirmInvoiceRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    """Activation manuelle d'un abonnement après règlement vérifié hors ligne."""
    invoice = await db.get(SubscriptionInvoice, invoice_id)
    if invoice is None:
        raise NotFoundError("Facture introuvable")
    if invoice.status == "paid":
        raise ConflictError("Facture déjà réglée")
    invoice.status = "paid"
    invoice.paid_at = datetime.now(UTC)
    if payload.payment_reference:
        invoice.payment_reference = payload.payment_reference
    subscription = await db.get(Subscription, invoice.subscription_id)
    if subscription is not None:
        subscription.status = "active"
    await record_audit(
        db,
        action="superadmin.subscription_payment_confirm",
        user_id=ctx.user.id,
        entity_type="subscription_invoice",
        entity_id=invoice.id,
    )
    return ok(message="Paiement confirmé, abonnement activé")


@router.get("/audit-logs")
async def list_audit_logs(
    db: Db,
    params: Page,
    tenant_id: uuid.UUID | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    query = select(AuditLog)
    if tenant_id:
        query = query.where(AuditLog.tenant_id == tenant_id)
    if action:
        query = query.where(AuditLog.action.ilike(f"{action}%"))
    items, meta = await paginate(db, query, params, default_sort=AuditLog.created_at)
    return ok(
        [
            {
                "id": str(log.id),
                "action": log.action,
                "tenant_id": str(log.tenant_id) if log.tenant_id else None,
                "user_id": str(log.user_id) if log.user_id else None,
                "entity_type": log.entity_type,
                "entity_id": str(log.entity_id) if log.entity_id else None,
                "created_at": log.created_at.isoformat(),
            }
            for log in items
        ],
        **meta,
    )


@router.get("/feature-flags")
async def list_flags(db: Db) -> dict[str, Any]:
    flags = (await db.execute(select(FeatureFlag))).scalars().all()
    return ok(
        [
            {
                "code": f.code,
                "description": f.description,
                "is_enabled": f.is_enabled,
                "tenant_overrides": f.tenant_overrides,
            }
            for f in flags
        ]
    )


@router.put("/feature-flags")
async def upsert_flag(payload: FlagUpsert, db: Db, ctx: Ctx) -> dict[str, Any]:
    flag = (
        await db.execute(select(FeatureFlag).where(FeatureFlag.code == payload.code))
    ).scalar_one_or_none()
    if flag is None:
        flag = FeatureFlag(**payload.model_dump())
        db.add(flag)
    else:
        flag.description = payload.description
        flag.is_enabled = payload.is_enabled
        flag.tenant_overrides = payload.tenant_overrides
    await record_audit(
        db,
        action="superadmin.feature_flag",
        user_id=ctx.user.id,
        after={"code": payload.code, "enabled": payload.is_enabled},
    )
    return ok(message="Feature flag enregistré")
