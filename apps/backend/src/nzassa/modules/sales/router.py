"""Endpoints ventes et caisse."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import BusinessRuleError, ConflictError, NotFoundError
from nzassa.core.money import ZERO, money
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.business import Branch, Business
from nzassa.models.sales import CashMovement, CashRegister, CashSession, Sale
from nzassa.modules.sales import service as sales_service
from nzassa.modules.sales.receipts import build_receipt_pdf
from nzassa.modules.sales.schemas import (
    CashMovementRequest,
    CashSessionOut,
    CloseSessionRequest,
    OpenSessionRequest,
    RefundRequest,
    SaleCancelRequest,
    SaleCreate,
    SaleOut,
    SalePaymentRequest,
)

router = APIRouter(tags=["sales"])

Page = Annotated[PageParams, Depends(page_params)]


# ---------- Ventes ----------


@router.get("/sales", dependencies=[require_permissions("sales.read")])
async def list_sales(
    db: Db,
    ctx: Ctx,
    params: Page,
    branch_id: uuid.UUID | None = None,
    status: str | None = None,
    customer_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    query = tenant_query(Sale, ctx.require_tenant())
    if branch_id:
        query = query.where(Sale.branch_id == branch_id)
    if status:
        query = query.where(Sale.status == status)
    if customer_id:
        query = query.where(Sale.customer_id == customer_id)
    if params.search:
        query = query.where(Sale.number.ilike(f"%{params.search}%"))
    items, meta = await paginate(
        db,
        query,
        params,
        sortable={"sold_at": Sale.sold_at, "total": Sale.total},
        default_sort=Sale.sold_at,
    )
    return ok([SaleOut.model_validate(s).model_dump(mode="json") for s in items], **meta)


@router.post("/sales", status_code=201, dependencies=[require_permissions("sales.create")])
async def create_sale(payload: SaleCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    sale = await sales_service.create_sale(
        db, tenant_id=ctx.require_tenant(), user=ctx.user, payload=payload
    )
    return ok(SaleOut.model_validate(sale).model_dump(mode="json"), message="Vente enregistrée")


@router.get("/sales/{sale_id}", dependencies=[require_permissions("sales.read")])
async def get_sale(sale_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    sale = await get_tenant_entity(db, Sale, sale_id, ctx.require_tenant())
    return ok(SaleOut.model_validate(sale).model_dump(mode="json"))


@router.post("/sales/{sale_id}/payments", dependencies=[require_permissions("sales.create")])
async def pay_sale(
    sale_id: uuid.UUID, payload: SalePaymentRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    sale = await get_tenant_entity(db, Sale, sale_id, tenant_id)
    sale = await sales_service.add_payments(
        db, tenant_id=tenant_id, user=ctx.user, sale=sale, payments=payload.payments
    )
    return ok(SaleOut.model_validate(sale).model_dump(mode="json"), message="Paiement enregistré")


@router.post("/sales/{sale_id}/cancel", dependencies=[require_permissions("sales.cancel")])
async def cancel_sale(
    sale_id: uuid.UUID, payload: SaleCancelRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    sale = await get_tenant_entity(db, Sale, sale_id, tenant_id)
    sale = await sales_service.cancel_sale(
        db, tenant_id=tenant_id, user=ctx.user, sale=sale, reason=payload.reason
    )
    return ok(SaleOut.model_validate(sale).model_dump(mode="json"), message="Vente annulée")


@router.post("/sales/{sale_id}/refunds", dependencies=[require_permissions("sales.refund")])
async def refund_sale(
    sale_id: uuid.UUID, payload: RefundRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    sale = await get_tenant_entity(db, Sale, sale_id, tenant_id)
    refund = await sales_service.refund_sale(
        db, tenant_id=tenant_id, user=ctx.user, sale=sale, payload=payload
    )
    return ok(
        {"refund_id": str(refund.id), "amount": str(refund.amount), "sale_status": sale.status},
        message="Remboursement effectué",
    )


@router.get("/sales/{sale_id}/receipt.pdf", dependencies=[require_permissions("sales.read")])
async def sale_receipt(sale_id: uuid.UUID, db: Db, ctx: Ctx) -> Response:
    tenant_id = ctx.require_tenant()
    sale = await get_tenant_entity(db, Sale, sale_id, tenant_id)
    branch = await get_tenant_entity(db, Branch, sale.branch_id, tenant_id)
    business = (await db.execute(tenant_query(Business, tenant_id).limit(1))).scalars().first()
    if business is None:
        raise NotFoundError()
    pdf_bytes = build_receipt_pdf(sale, business, branch)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=recu-{sale.number}.pdf"},
    )


# ---------- Caisse ----------


@router.get("/cash/registers", dependencies=[require_permissions("cash.read")])
async def list_registers(db: Db, ctx: Ctx) -> dict[str, Any]:
    registers = (await db.execute(tenant_query(CashRegister, ctx.require_tenant()))).scalars().all()
    return ok(
        [
            {
                "id": str(r.id),
                "branch_id": str(r.branch_id),
                "name": r.name,
                "is_active": r.is_active,
            }
            for r in registers
        ]
    )


@router.get("/cash/sessions", dependencies=[require_permissions("cash.read")])
async def list_sessions(
    db: Db, ctx: Ctx, params: Page, status: str | None = None
) -> dict[str, Any]:
    query = tenant_query(CashSession, ctx.require_tenant())
    if status:
        query = query.where(CashSession.status == status)
    items, meta = await paginate(db, query, params, default_sort=CashSession.opened_at)
    return ok([CashSessionOut.model_validate(s).model_dump(mode="json") for s in items], **meta)


@router.post(
    "/cash/sessions/open", status_code=201, dependencies=[require_permissions("cash.open")]
)
async def open_session(payload: OpenSessionRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    register = await get_tenant_entity(db, CashRegister, payload.register_id, tenant_id)
    existing = (
        await db.execute(
            tenant_query(CashSession, tenant_id).where(
                CashSession.register_id == register.id, CashSession.status == "open"
            )
        )
    ).first()
    if existing:
        raise ConflictError("Une session est déjà ouverte sur cette caisse")
    session = CashSession(
        tenant_id=tenant_id,
        register_id=register.id,
        branch_id=register.branch_id,
        opened_by=ctx.user.id,
        opened_at=datetime.now(UTC),
        opening_float=money(payload.opening_float),
        created_by=ctx.user.id,
    )
    db.add(session)
    await db.flush()
    await record_audit(
        db,
        action="cash.open",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="cash_session",
        entity_id=session.id,
    )
    return ok(
        CashSessionOut.model_validate(session).model_dump(mode="json"), message="Caisse ouverte"
    )


async def _session_cash_total(db: Db, tenant_id: uuid.UUID, session: CashSession) -> Decimal:
    movements_sum = (
        await db.execute(
            select(func.coalesce(func.sum(CashMovement.amount), 0)).where(
                CashMovement.tenant_id == tenant_id, CashMovement.session_id == session.id
            )
        )
    ).scalar_one()
    return money(session.opening_float + Decimal(movements_sum))


@router.post("/cash/sessions/{session_id}/close", dependencies=[require_permissions("cash.close")])
async def close_session(
    session_id: uuid.UUID, payload: CloseSessionRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    session = await get_tenant_entity(db, CashSession, session_id, tenant_id)
    if session.status != "open":
        raise ConflictError("Cette session est déjà fermée")
    expected = await _session_cash_total(db, tenant_id, session)
    session.status = "closed"
    session.closed_at = datetime.now(UTC)
    session.closed_by = ctx.user.id
    session.expected_cash = expected
    session.counted_cash = money(payload.counted_cash)
    session.difference = money(payload.counted_cash - expected)
    session.notes = payload.notes
    await record_audit(
        db,
        action="cash.close",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="cash_session",
        entity_id=session.id,
        after={"expected": str(expected), "counted": str(payload.counted_cash)},
    )
    return ok(
        CashSessionOut.model_validate(session).model_dump(mode="json"), message="Caisse fermée"
    )


@router.post(
    "/cash/sessions/{session_id}/movements",
    status_code=201,
    dependencies=[require_permissions("cash.movement")],
)
async def add_cash_movement(
    session_id: uuid.UUID, payload: CashMovementRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    session = await get_tenant_entity(db, CashSession, session_id, tenant_id)
    if session.status != "open":
        raise BusinessRuleError("La session de caisse est fermée")
    amount = money(payload.amount)
    if payload.movement_type == "withdrawal":
        current = await _session_cash_total(db, tenant_id, session)
        if amount > current:
            raise BusinessRuleError(
                "Retrait supérieur au fonds de caisse", details={"available": str(current)}
            )
        amount = -amount
    db.add(
        CashMovement(
            tenant_id=tenant_id,
            session_id=session.id,
            movement_type=payload.movement_type,
            amount=amount,
            reason=payload.reason,
            created_by=ctx.user.id,
        )
    )
    await record_audit(
        db,
        action=f"cash.{payload.movement_type}",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="cash_session",
        entity_id=session.id,
        after={"amount": str(amount)},
    )
    return ok(message="Mouvement enregistré")


@router.get("/cash/sessions/{session_id}", dependencies=[require_permissions("cash.read")])
async def get_session(session_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    session = await get_tenant_entity(db, CashSession, session_id, tenant_id)
    data = CashSessionOut.model_validate(session).model_dump(mode="json")
    data["current_cash"] = str(await _session_cash_total(db, tenant_id, session))
    movements = (
        (
            await db.execute(
                tenant_query(CashMovement, tenant_id)
                .where(CashMovement.session_id == session.id)
                .order_by(CashMovement.created_at)
            )
        )
        .scalars()
        .all()
    )
    data["movements"] = [
        {
            "id": str(m.id),
            "movement_type": m.movement_type,
            "amount": str(m.amount),
            "reason": m.reason,
            "created_at": m.created_at.isoformat(),
        }
        for m in movements
    ]
    return ok(data)


__all__ = ["ZERO", "router"]
