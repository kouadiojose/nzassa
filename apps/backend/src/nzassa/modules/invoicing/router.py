"""Endpoints facturation : factures, avoirs, connecteur fiscal."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import BusinessRuleError, ConflictError
from nzassa.core.money import money
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.invoicing import CreditNote, Invoice, InvoiceItem
from nzassa.models.sales import Sale
from nzassa.modules.invoicing.fiscal import get_fiscal_connector

router = APIRouter(prefix="/invoices", tags=["invoices"])

Page = Annotated[PageParams, Depends(page_params)]


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sale_id: uuid.UUID | None
    customer_id: uuid.UUID | None
    number: str
    status: str
    issued_at: datetime | None
    subtotal: Decimal
    tax_amount: Decimal
    total: Decimal
    currency: str
    fiscal_status: str
    fiscal_reference: str | None


class CreditNoteRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=3, max_length=500)


async def _next_number(db: Db, tenant_id: uuid.UUID, prefix: str, model: Any) -> str:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"{prefix}:{tenant_id}"},
    )
    count = (
        await db.execute(
            select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
        )
    ).scalar_one()
    return f"{prefix}-{datetime.now(UTC).year}-{count + 1:06d}"


@router.get("", dependencies=[require_permissions("invoices.read")])
async def list_invoices(
    db: Db, ctx: Ctx, params: Page, status: str | None = None
) -> dict[str, Any]:
    query = tenant_query(Invoice, ctx.require_tenant())
    if status:
        query = query.where(Invoice.status == status)
    if params.search:
        query = query.where(Invoice.number.ilike(f"%{params.search}%"))
    items, meta = await paginate(db, query, params, default_sort=Invoice.created_at)
    return ok([InvoiceOut.model_validate(i).model_dump(mode="json") for i in items], **meta)


@router.post(
    "/from-sale/{sale_id}", status_code=201, dependencies=[require_permissions("invoices.create")]
)
async def create_invoice_from_sale(sale_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    sale = await get_tenant_entity(db, Sale, sale_id, tenant_id)
    if sale.status not in ("completed", "partially_refunded"):
        raise BusinessRuleError("Seule une vente validée peut être facturée")
    existing = (
        await db.execute(tenant_query(Invoice, tenant_id).where(Invoice.sale_id == sale.id))
    ).first()
    if existing:
        raise ConflictError("Cette vente est déjà facturée")

    invoice = Invoice(
        tenant_id=tenant_id,
        sale_id=sale.id,
        customer_id=sale.customer_id,
        number=await _next_number(db, tenant_id, "FAC", Invoice),
        status="issued",
        issued_at=datetime.now(UTC),
        subtotal=sale.subtotal,
        tax_amount=sale.tax_amount,
        total=sale.total,
        created_by=ctx.user.id,
    )
    db.add(invoice)
    await db.flush()
    await db.refresh(sale, ["items"])
    for item in sale.items:
        db.add(
            InvoiceItem(
                tenant_id=tenant_id,
                invoice_id=invoice.id,
                label=item.label,
                quantity=item.quantity,
                unit_price=item.unit_price,
                tax_rate=item.tax_rate,
                tax_amount=item.tax_amount,
                line_total=item.line_total,
            )
        )
    await record_audit(
        db,
        action="invoices.create",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="invoice",
        entity_id=invoice.id,
    )
    return ok(InvoiceOut.model_validate(invoice).model_dump(mode="json"), message="Facture émise")


@router.post("/{invoice_id}/submit-fiscal", dependencies=[require_permissions("invoices.create")])
async def submit_fiscal(invoice_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    invoice = await get_tenant_entity(db, Invoice, invoice_id, tenant_id)
    if invoice.status != "issued":
        raise BusinessRuleError("Seule une facture émise peut être soumise")
    connector = get_fiscal_connector()
    result = await connector.submit_invoice(invoice)
    invoice.fiscal_status = "accepted" if result.accepted else "not_submitted"
    invoice.fiscal_reference = result.reference
    invoice.fiscal_payload = {"connector": connector.name, "message": result.message}
    return ok(
        {
            "fiscal_status": invoice.fiscal_status,
            "fiscal_reference": invoice.fiscal_reference,
            "connector": connector.name,
            "message": result.message,
        }
    )


@router.post("/{invoice_id}/cancel", dependencies=[require_permissions("invoices.cancel")])
async def cancel_invoice(invoice_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    invoice = await get_tenant_entity(db, Invoice, invoice_id, ctx.require_tenant())
    if invoice.status == "cancelled":
        raise ConflictError("Facture déjà annulée")
    invoice.status = "cancelled"
    invoice.updated_by = ctx.user.id
    await record_audit(
        db,
        action="invoices.cancel",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        entity_type="invoice",
        entity_id=invoice.id,
    )
    return ok(message="Facture annulée")


@router.post(
    "/{invoice_id}/credit-notes",
    status_code=201,
    dependencies=[require_permissions("invoices.create")],
)
async def create_credit_note(
    invoice_id: uuid.UUID, payload: CreditNoteRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    invoice = await get_tenant_entity(db, Invoice, invoice_id, tenant_id)
    if invoice.status != "issued":
        raise BusinessRuleError("Un avoir ne peut être créé que sur une facture émise")
    amount = money(payload.amount)
    if amount > invoice.total:
        raise BusinessRuleError("L'avoir dépasse le montant de la facture")
    note = CreditNote(
        tenant_id=tenant_id,
        invoice_id=invoice.id,
        number=await _next_number(db, tenant_id, "AV", CreditNote),
        amount=amount,
        reason=payload.reason,
        issued_at=datetime.now(UTC),
        created_by=ctx.user.id,
    )
    db.add(note)
    await db.flush()
    return ok(
        {"id": str(note.id), "number": note.number, "amount": str(note.amount)},
        message="Avoir émis",
    )
