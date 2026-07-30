"""Endpoints commissions : règles, calcul, validation, paiement, contestation."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import BusinessRuleError
from nzassa.core.money import money
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.business import Employee
from nzassa.models.commissions import EmployeeCommission, EmployeeCommissionRule

router = APIRouter(prefix="/commissions", tags=["commissions"])

Page = Annotated[PageParams, Depends(page_params)]


class RuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scope: str = Field(default="all", pattern="^(all|product|service|category)$")
    product_id: uuid.UUID | None = None
    service_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    employee_id: uuid.UUID | None = None
    commission_type: str = Field(default="percent", pattern="^(percent|fixed)$")
    rate: Decimal | None = Field(default=None, ge=0, le=1)
    fixed_amount: Decimal | None = Field(default=None, ge=0)


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    scope: str
    product_id: uuid.UUID | None
    service_id: uuid.UUID | None
    category_id: uuid.UUID | None
    employee_id: uuid.UUID | None
    commission_type: str
    rate: Decimal | None
    fixed_amount: Decimal | None
    is_active: bool


class CommissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    sale_id: uuid.UUID | None
    base_amount: Decimal
    amount: Decimal
    period_date: date
    status: str
    dispute_reason: str | None


class DisputeRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


@router.get("/rules", dependencies=[require_permissions("commissions.read")])
async def list_rules(db: Db, ctx: Ctx) -> dict[str, Any]:
    rules = (
        (await db.execute(tenant_query(EmployeeCommissionRule, ctx.require_tenant())))
        .scalars()
        .all()
    )
    return ok([RuleOut.model_validate(r).model_dump(mode="json") for r in rules])


@router.post(
    "/rules", status_code=201, dependencies=[require_permissions("commissions.manage_rules")]
)
async def create_rule(payload: RuleCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    if payload.commission_type == "percent" and payload.rate is None:
        raise BusinessRuleError("Un taux est requis pour une commission en pourcentage")
    if payload.commission_type == "fixed" and payload.fixed_amount is None:
        raise BusinessRuleError("Un montant fixe est requis pour une commission fixe")
    rule = EmployeeCommissionRule(
        tenant_id=ctx.require_tenant(), created_by=ctx.user.id, **payload.model_dump()
    )
    db.add(rule)
    await db.flush()
    return ok(RuleOut.model_validate(rule).model_dump(mode="json"), message="Règle créée")


@router.patch("/rules/{rule_id}", dependencies=[require_permissions("commissions.manage_rules")])
async def toggle_rule(rule_id: uuid.UUID, is_active: bool, db: Db, ctx: Ctx) -> dict[str, Any]:
    rule = await get_tenant_entity(db, EmployeeCommissionRule, rule_id, ctx.require_tenant())
    rule.is_active = is_active
    rule.updated_by = ctx.user.id
    return ok(RuleOut.model_validate(rule).model_dump(mode="json"))


@router.get("", dependencies=[require_permissions("commissions.read")])
async def list_commissions(
    db: Db,
    ctx: Ctx,
    params: Page,
    employee_id: uuid.UUID | None = None,
    status: str | None = None,
    period_from: date | None = None,
    period_to: date | None = None,
) -> dict[str, Any]:
    query = tenant_query(EmployeeCommission, ctx.require_tenant())
    if employee_id:
        query = query.where(EmployeeCommission.employee_id == employee_id)
    if status:
        query = query.where(EmployeeCommission.status == status)
    if period_from:
        query = query.where(EmployeeCommission.period_date >= period_from)
    if period_to:
        query = query.where(EmployeeCommission.period_date <= period_to)
    items, meta = await paginate(db, query, params, default_sort=EmployeeCommission.created_at)
    return ok([CommissionOut.model_validate(c).model_dump(mode="json") for c in items], **meta)


@router.get("/summary", dependencies=[require_permissions("commissions.read")])
async def commissions_summary(
    db: Db, ctx: Ctx, period_from: date | None = None, period_to: date | None = None
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    query = (
        select(
            EmployeeCommission.employee_id,
            EmployeeCommission.status,
            func.sum(EmployeeCommission.amount),
        )
        .where(EmployeeCommission.tenant_id == tenant_id)
        .group_by(EmployeeCommission.employee_id, EmployeeCommission.status)
    )
    if period_from:
        query = query.where(EmployeeCommission.period_date >= period_from)
    if period_to:
        query = query.where(EmployeeCommission.period_date <= period_to)
    rows = (await db.execute(query)).all()
    employees = {
        e.id: f"{e.first_name} {e.last_name}"
        for e in (await db.execute(tenant_query(Employee, tenant_id))).scalars().all()
    }
    summary: dict[str, dict[str, Any]] = {}
    for employee_id, status, total in rows:
        entry = summary.setdefault(
            str(employee_id),
            {"employee_name": employees.get(employee_id, "?"), "by_status": {}},
        )
        entry["by_status"][status] = str(money(total))
    return ok(summary)


@router.post(
    "/{commission_id}/validate", dependencies=[require_permissions("commissions.validate")]
)
async def validate_commission(commission_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    commission = await get_tenant_entity(
        db, EmployeeCommission, commission_id, ctx.require_tenant()
    )
    if commission.status != "pending":
        raise BusinessRuleError("Seule une commission en attente peut être validée")
    commission.status = "validated"
    commission.validated_at = datetime.now(UTC)
    commission.validated_by = ctx.user.id
    await record_audit(
        db,
        action="commissions.validate",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        entity_type="employee_commission",
        entity_id=commission.id,
    )
    return ok(CommissionOut.model_validate(commission).model_dump(mode="json"))


@router.post("/{commission_id}/pay", dependencies=[require_permissions("commissions.pay")])
async def pay_commission(commission_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    commission = await get_tenant_entity(
        db, EmployeeCommission, commission_id, ctx.require_tenant()
    )
    if commission.status != "validated":
        raise BusinessRuleError("Seule une commission validée peut être payée")
    commission.status = "paid"
    commission.paid_at = datetime.now(UTC)
    await record_audit(
        db,
        action="commissions.pay",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        entity_type="employee_commission",
        entity_id=commission.id,
        after={"amount": str(commission.amount)},
    )
    return ok(CommissionOut.model_validate(commission).model_dump(mode="json"))


@router.post("/{commission_id}/dispute", dependencies=[require_permissions("commissions.read")])
async def dispute_commission(
    commission_id: uuid.UUID, payload: DisputeRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    commission = await get_tenant_entity(
        db, EmployeeCommission, commission_id, ctx.require_tenant()
    )
    if commission.status not in ("pending", "validated"):
        raise BusinessRuleError("Cette commission ne peut plus être contestée")
    commission.status = "disputed"
    commission.dispute_reason = payload.reason
    await record_audit(
        db,
        action="commissions.dispute",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        entity_type="employee_commission",
        entity_id=commission.id,
        after={"reason": payload.reason},
    )
    return ok(CommissionOut.model_validate(commission).model_dump(mode="json"))
