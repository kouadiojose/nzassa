"""Endpoints dépenses (catégories, création, approbation, annulation)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import ConflictError
from nzassa.core.money import money
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.business import Branch
from nzassa.models.expenses import Expense, ExpenseCategory
from nzassa.models.sales import CashMovement, CashSession

router = APIRouter(prefix="/expenses", tags=["expenses"])

Page = Annotated[PageParams, Depends(page_params)]


class ExpenseCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    approval_threshold: Decimal | None = Field(default=None, ge=0)


class ExpenseCreate(BaseModel):
    branch_id: uuid.UUID
    category_id: uuid.UUID | None = None
    label: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0)
    expense_date: date
    payee: str | None = None
    payment_method: str = "cash"
    is_recurring: bool = False
    recurrence_rule: str | None = Field(default=None, pattern="^(daily|weekly|monthly|yearly)$")
    notes: str | None = None
    client_reference: str | None = None


class ExpenseUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    label: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    expense_date: date | None = None
    payee: str | None = None
    payment_method: str | None = None
    notes: str | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    category_id: uuid.UUID | None
    label: str
    amount: Decimal
    expense_date: date
    payee: str | None
    payment_method: str
    status: str
    is_recurring: bool
    recurrence_rule: str | None
    notes: str | None


@router.get("/categories", dependencies=[require_permissions("expenses.read")])
async def list_categories(db: Db, ctx: Ctx) -> dict[str, Any]:
    rows = (
        (
            await db.execute(
                tenant_query(ExpenseCategory, ctx.require_tenant()).order_by(ExpenseCategory.name)
            )
        )
        .scalars()
        .all()
    )
    return ok(
        [
            {
                "id": str(c.id),
                "name": c.name,
                "approval_threshold": str(c.approval_threshold) if c.approval_threshold else None,
            }
            for c in rows
        ]
    )


@router.post("/categories", status_code=201, dependencies=[require_permissions("expenses.create")])
async def create_category(payload: ExpenseCategoryCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    category = ExpenseCategory(
        tenant_id=ctx.require_tenant(), created_by=ctx.user.id, **payload.model_dump()
    )
    db.add(category)
    await db.flush()
    return ok({"id": str(category.id), "name": category.name})


@router.get("", dependencies=[require_permissions("expenses.read")])
async def list_expenses(
    db: Db,
    ctx: Ctx,
    params: Page,
    branch_id: uuid.UUID | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    query = tenant_query(Expense, ctx.require_tenant())
    if branch_id:
        query = query.where(Expense.branch_id == branch_id)
    if status:
        query = query.where(Expense.status == status)
    if date_from:
        query = query.where(Expense.expense_date >= date_from)
    if date_to:
        query = query.where(Expense.expense_date <= date_to)
    if params.search:
        query = query.where(Expense.label.ilike(f"%{params.search}%"))
    items, meta = await paginate(
        db,
        query,
        params,
        sortable={"expense_date": Expense.expense_date, "amount": Expense.amount},
        default_sort=Expense.expense_date,
    )
    return ok([ExpenseOut.model_validate(e).model_dump(mode="json") for e in items], **meta)


@router.post("", status_code=201, dependencies=[require_permissions("expenses.create")])
async def create_expense(payload: ExpenseCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    # Idempotence offline
    if payload.client_reference:
        existing = (
            await db.execute(
                select(Expense).where(Expense.client_reference == payload.client_reference)
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.tenant_id != tenant_id:
                raise ConflictError("Référence client déjà utilisée")
            return ok(ExpenseOut.model_validate(existing).model_dump(mode="json"))

    await get_tenant_entity(db, Branch, payload.branch_id, tenant_id)
    status = "approved"
    if payload.category_id is not None:
        category = await get_tenant_entity(db, ExpenseCategory, payload.category_id, tenant_id)
        if (
            category.approval_threshold is not None
            and payload.amount >= category.approval_threshold
            and not ctx.has("expenses.approve")
        ):
            status = "pending_approval"

    expense = Expense(
        tenant_id=tenant_id,
        created_by=ctx.user.id,
        status=status,
        **{**payload.model_dump(), "amount": money(payload.amount)},
    )
    db.add(expense)
    await db.flush()

    # Sortie de caisse si payée en espèces et session ouverte
    if status == "approved" and payload.payment_method == "cash":
        session = (
            (
                await db.execute(
                    tenant_query(CashSession, tenant_id).where(
                        CashSession.branch_id == payload.branch_id, CashSession.status == "open"
                    )
                )
            )
            .scalars()
            .first()
        )
        if session is not None:
            db.add(
                CashMovement(
                    tenant_id=tenant_id,
                    session_id=session.id,
                    movement_type="expense",
                    amount=-money(payload.amount),
                    reference_type="expense",
                    reference_id=expense.id,
                    reason=payload.label,
                )
            )
    await record_audit(
        db,
        action="expenses.create",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="expense",
        entity_id=expense.id,
        after={"amount": str(expense.amount), "status": status},
    )
    return ok(
        ExpenseOut.model_validate(expense).model_dump(mode="json"), message="Dépense enregistrée"
    )


@router.patch("/{expense_id}", dependencies=[require_permissions("expenses.create")])
async def update_expense(
    expense_id: uuid.UUID, payload: ExpenseUpdate, db: Db, ctx: Ctx
) -> dict[str, Any]:
    expense = await get_tenant_entity(db, Expense, expense_id, ctx.require_tenant())
    if expense.status == "cancelled":
        raise ConflictError("Une dépense annulée ne peut plus être modifiée")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, key, money(value) if key == "amount" else value)
    expense.updated_by = ctx.user.id
    return ok(ExpenseOut.model_validate(expense).model_dump(mode="json"))


@router.post("/{expense_id}/approve", dependencies=[require_permissions("expenses.approve")])
async def approve_expense(expense_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    expense = await get_tenant_entity(db, Expense, expense_id, ctx.require_tenant())
    if expense.status != "pending_approval":
        raise ConflictError("Cette dépense n'est pas en attente d'approbation")
    expense.status = "approved"
    expense.approved_by = ctx.user.id
    await record_audit(
        db,
        action="expenses.approve",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        entity_type="expense",
        entity_id=expense.id,
    )
    return ok(
        ExpenseOut.model_validate(expense).model_dump(mode="json"), message="Dépense approuvée"
    )


@router.post("/{expense_id}/cancel", dependencies=[require_permissions("expenses.cancel")])
async def cancel_expense(expense_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    expense = await get_tenant_entity(db, Expense, expense_id, tenant_id)
    if expense.status == "cancelled":
        raise ConflictError("Dépense déjà annulée")
    was_approved_cash = expense.status == "approved" and expense.payment_method == "cash"
    expense.status = "cancelled"
    expense.updated_by = ctx.user.id
    if was_approved_cash:
        session = (
            (
                await db.execute(
                    tenant_query(CashSession, tenant_id).where(
                        CashSession.branch_id == expense.branch_id, CashSession.status == "open"
                    )
                )
            )
            .scalars()
            .first()
        )
        if session is not None:
            db.add(
                CashMovement(
                    tenant_id=tenant_id,
                    session_id=session.id,
                    movement_type="deposit",
                    amount=money(expense.amount),
                    reference_type="expense_cancellation",
                    reference_id=expense.id,
                    reason=f"Annulation dépense : {expense.label}",
                )
            )
    await record_audit(
        db,
        action="expenses.cancel",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="expense",
        entity_id=expense.id,
    )
    return ok(message="Dépense annulée")


_ = datetime.now(UTC)  # évite un import inutilisé si non utilisé ailleurs
