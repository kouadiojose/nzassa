"""Endpoints créances clients : suivi, règlements, relances, passage en perte."""

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
from nzassa.core.money import ZERO, money
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.customers import Customer, CustomerDebt, DebtPayment
from nzassa.models.sales import Sale
from nzassa.modules.sales import service as sales_service
from nzassa.modules.sales.schemas import PaymentIn

router = APIRouter(prefix="/debts", tags=["debts"])

Page = Annotated[PageParams, Depends(page_params)]


class DebtOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    customer_id: uuid.UUID
    sale_id: uuid.UUID | None
    original_amount: Decimal
    balance: Decimal
    due_date: date | None
    status: str
    promised_payment_date: date | None


class DebtPaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = Field(default="cash")
    reference: str | None = None


class DebtPromiseRequest(BaseModel):
    promised_payment_date: date


class WriteOffRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


@router.get("", dependencies=[require_permissions("debts.read")])
async def list_debts(
    db: Db,
    ctx: Ctx,
    params: Page,
    customer_id: uuid.UUID | None = None,
    status: str | None = None,
    overdue: bool = False,
) -> dict[str, Any]:
    query = tenant_query(CustomerDebt, ctx.require_tenant())
    if customer_id:
        query = query.where(CustomerDebt.customer_id == customer_id)
    if status:
        query = query.where(CustomerDebt.status == status)
    if overdue:
        query = query.where(
            CustomerDebt.status.in_(["open", "partially_paid"]),
            CustomerDebt.due_date.is_not(None),
            CustomerDebt.due_date < date.today(),
        )
    items, meta = await paginate(db, query, params, default_sort=CustomerDebt.created_at)
    return ok([DebtOut.model_validate(d).model_dump(mode="json") for d in items], **meta)


@router.get("/summary", dependencies=[require_permissions("debts.read")])
async def debts_summary(db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    total_open = (
        await db.execute(
            select(func.coalesce(func.sum(CustomerDebt.balance), 0)).where(
                CustomerDebt.tenant_id == tenant_id,
                CustomerDebt.status.in_(["open", "partially_paid"]),
            )
        )
    ).scalar_one()
    overdue = (
        await db.execute(
            select(func.coalesce(func.sum(CustomerDebt.balance), 0)).where(
                CustomerDebt.tenant_id == tenant_id,
                CustomerDebt.status.in_(["open", "partially_paid"]),
                CustomerDebt.due_date.is_not(None),
                CustomerDebt.due_date < date.today(),
            )
        )
    ).scalar_one()
    return ok({"total_open": str(total_open), "total_overdue": str(overdue)})


@router.post("/{debt_id}/payments", dependencies=[require_permissions("debts.collect")])
async def pay_debt(
    debt_id: uuid.UUID, payload: DebtPaymentRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    debt = await get_tenant_entity(db, CustomerDebt, debt_id, tenant_id)
    if debt.status not in ("open", "partially_paid"):
        raise BusinessRuleError("Cette créance n'est pas ouverte")
    amount = money(payload.amount)
    if amount > debt.balance:
        raise BusinessRuleError(
            "Le règlement dépasse le solde de la créance", details={"balance": str(debt.balance)}
        )
    if debt.sale_id is not None:
        # Passe par le service ventes pour garder vente + dette + caisse cohérentes
        sale = await get_tenant_entity(db, Sale, debt.sale_id, tenant_id)
        await sales_service.add_payments(
            db,
            tenant_id=tenant_id,
            user=ctx.user,
            sale=sale,
            payments=[PaymentIn(method=payload.method, amount=amount, reference=payload.reference)],
        )
    else:
        debt.balance = money(debt.balance - amount)
        debt.status = "paid" if debt.balance <= 0 else "partially_paid"
        db.add(
            DebtPayment(
                tenant_id=tenant_id,
                debt_id=debt.id,
                amount=amount,
                method=payload.method,
                paid_at=datetime.now(UTC),
                received_by=ctx.user.id,
                reference=payload.reference,
            )
        )
    await db.flush()
    await db.refresh(debt)
    return ok(DebtOut.model_validate(debt).model_dump(mode="json"), message="Règlement enregistré")


@router.post("/{debt_id}/promise", dependencies=[require_permissions("debts.collect")])
async def record_promise(
    debt_id: uuid.UUID, payload: DebtPromiseRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    debt = await get_tenant_entity(db, CustomerDebt, debt_id, ctx.require_tenant())
    debt.promised_payment_date = payload.promised_payment_date
    debt.updated_by = ctx.user.id
    return ok(DebtOut.model_validate(debt).model_dump(mode="json"), message="Promesse enregistrée")


@router.post("/{debt_id}/write-off", dependencies=[require_permissions("debts.write_off")])
async def write_off_debt(
    debt_id: uuid.UUID, payload: WriteOffRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    debt = await get_tenant_entity(db, CustomerDebt, debt_id, tenant_id)
    if debt.status not in ("open", "partially_paid"):
        raise BusinessRuleError("Cette créance n'est pas ouverte")
    debt.status = "written_off"
    debt.written_off_at = datetime.now(UTC)
    debt.written_off_by = ctx.user.id
    debt.write_off_reason = payload.reason
    debt.balance = ZERO
    await record_audit(
        db,
        action="debts.write_off",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="customer_debt",
        entity_id=debt.id,
        after={"reason": payload.reason},
    )
    return ok(message="Créance passée en perte")


@router.get("/{debt_id}/reminder-message", dependencies=[require_permissions("debts.collect")])
async def reminder_message(debt_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    """Génère un message de relance prêt à partager (WhatsApp/SMS)."""
    tenant_id = ctx.require_tenant()
    debt = await get_tenant_entity(db, CustomerDebt, debt_id, tenant_id)
    customer = await get_tenant_entity(db, Customer, debt.customer_id, tenant_id)
    message = (
        f"Bonjour {customer.full_name}, nous vous rappelons qu'un solde de "
        f"{debt.balance:,.0f} FCFA reste dû"
    )
    if debt.due_date:
        message += f" (échéance : {debt.due_date:%d/%m/%Y})"
    message += ". Merci de passer régler à votre convenance. À bientôt !"
    wa_phone = (customer.phone or "").replace("+", "").replace(" ", "")
    return ok(
        {
            "message": message,
            "whatsapp_url": f"https://wa.me/{wa_phone}?text={message}" if wa_phone else None,
        }
    )
