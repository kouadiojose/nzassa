"""Endpoints fournisseurs et achats (commandes, réceptions, paiements)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import BusinessRuleError, ConflictError, NotFoundError
from nzassa.core.money import ZERO, money
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.business import Branch
from nzassa.models.catalog import Product
from nzassa.models.suppliers import (
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReceipt,
    Supplier,
    SupplierPayment,
)
from nzassa.modules.businesses.router import get_current_business
from nzassa.modules.inventory import service as stock_service

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

Page = Annotated[PageParams, Depends(page_params)]


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    notes: str | None = None


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    address: str | None
    notes: str | None
    is_active: bool


class OrderItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)


class OrderCreate(BaseModel):
    branch_id: uuid.UUID
    supplier_id: uuid.UUID
    items: list[OrderItemIn] = Field(min_length=1)
    expected_on: date | None = None
    notes: str | None = None


class ReceiveItemIn(BaseModel):
    item_id: uuid.UUID
    quantity: Decimal = Field(gt=0)


class ReceiveRequest(BaseModel):
    items: list[ReceiveItemIn] = Field(min_length=1)
    notes: str | None = None


class SupplierPaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = "cash"
    reference: str | None = None
    notes: str | None = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    quantity: Decimal
    received_quantity: Decimal
    unit_cost: Decimal
    line_total: Decimal


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    supplier_id: uuid.UUID
    number: str
    status: str
    expected_on: date | None
    subtotal: Decimal
    total: Decimal
    amount_paid: Decimal
    notes: str | None


@router.get("", dependencies=[require_permissions("suppliers.read")])
async def list_suppliers(db: Db, ctx: Ctx, params: Page) -> dict[str, Any]:
    query = tenant_query(Supplier, ctx.require_tenant())
    if params.search:
        query = query.where(Supplier.name.ilike(f"%{params.search}%"))
    items, meta = await paginate(db, query, params, default_sort=Supplier.created_at)
    return ok([SupplierOut.model_validate(s).model_dump(mode="json") for s in items], **meta)


@router.post("", status_code=201, dependencies=[require_permissions("suppliers.create")])
async def create_supplier(payload: SupplierCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    business = await get_current_business(db, ctx)
    duplicate = (
        await db.execute(tenant_query(Supplier, tenant_id).where(Supplier.name == payload.name))
    ).first()
    if duplicate:
        raise ConflictError("Un fournisseur avec ce nom existe déjà")
    supplier = Supplier(
        tenant_id=tenant_id, business_id=business.id, created_by=ctx.user.id, **payload.model_dump()
    )
    db.add(supplier)
    await db.flush()
    return ok(
        SupplierOut.model_validate(supplier).model_dump(mode="json"), message="Fournisseur créé"
    )


async def _next_po_number(db: Db, tenant_id: uuid.UUID) -> str:
    from sqlalchemy import text

    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": f"po_number:{tenant_id}"}
    )
    count = (
        await db.execute(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.tenant_id == tenant_id)
        )
    ).scalar_one()
    return f"BC-{datetime.now(UTC).year}-{count + 1:05d}"


@router.get("/orders", dependencies=[require_permissions("suppliers.read")])
async def list_orders(db: Db, ctx: Ctx, params: Page, status: str | None = None) -> dict[str, Any]:
    query = tenant_query(PurchaseOrder, ctx.require_tenant())
    if status:
        query = query.where(PurchaseOrder.status == status)
    items, meta = await paginate(db, query, params, default_sort=PurchaseOrder.created_at)
    return ok([OrderOut.model_validate(o).model_dump(mode="json") for o in items], **meta)


@router.post("/orders", status_code=201, dependencies=[require_permissions("suppliers.order")])
async def create_order(payload: OrderCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_tenant_entity(db, Branch, payload.branch_id, tenant_id)
    await get_tenant_entity(db, Supplier, payload.supplier_id, tenant_id)
    order = PurchaseOrder(
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        supplier_id=payload.supplier_id,
        number=await _next_po_number(db, tenant_id),
        status="ordered",
        ordered_at=datetime.now(UTC),
        expected_on=payload.expected_on,
        notes=payload.notes,
        created_by=ctx.user.id,
    )
    db.add(order)
    await db.flush()
    subtotal = ZERO
    for item_in in payload.items:
        product = await get_tenant_entity(db, Product, item_in.product_id, tenant_id)
        line_total = money(item_in.unit_cost * item_in.quantity)
        subtotal += line_total
        db.add(
            PurchaseOrderItem(
                tenant_id=tenant_id,
                purchase_order_id=order.id,
                product_id=product.id,
                quantity=item_in.quantity,
                unit_cost=money(item_in.unit_cost),
                line_total=line_total,
            )
        )
    order.subtotal = money(subtotal)
    order.total = money(subtotal)
    await record_audit(
        db,
        action="suppliers.order",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="purchase_order",
        entity_id=order.id,
    )
    return ok(OrderOut.model_validate(order).model_dump(mode="json"), message="Commande créée")


@router.get("/orders/{order_id}", dependencies=[require_permissions("suppliers.read")])
async def get_order(order_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    order = await get_tenant_entity(db, PurchaseOrder, order_id, tenant_id)
    items = (
        (
            await db.execute(
                tenant_query(PurchaseOrderItem, tenant_id).where(
                    PurchaseOrderItem.purchase_order_id == order.id
                )
            )
        )
        .scalars()
        .all()
    )
    data = OrderOut.model_validate(order).model_dump(mode="json")
    data["items"] = [OrderItemOut.model_validate(i).model_dump(mode="json") for i in items]
    return ok(data)


@router.post("/orders/{order_id}/receive", dependencies=[require_permissions("suppliers.receive")])
async def receive_order(
    order_id: uuid.UUID, payload: ReceiveRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    """Réception (partielle ou totale) : met à jour le stock au coût d'achat."""
    tenant_id = ctx.require_tenant()
    order = await get_tenant_entity(db, PurchaseOrder, order_id, tenant_id)
    if order.status not in ("ordered", "partially_received"):
        raise BusinessRuleError("Cette commande ne peut pas être réceptionnée")
    items = {
        i.id: i
        for i in (
            await db.execute(
                tenant_query(PurchaseOrderItem, tenant_id).where(
                    PurchaseOrderItem.purchase_order_id == order.id
                )
            )
        )
        .scalars()
        .all()
    }
    receipt = PurchaseReceipt(
        tenant_id=tenant_id,
        purchase_order_id=order.id,
        received_at=datetime.now(UTC),
        received_by=ctx.user.id,
        notes=payload.notes,
        created_by=ctx.user.id,
    )
    db.add(receipt)
    for entry in payload.items:
        item = items.get(entry.item_id)
        if item is None:
            raise NotFoundError("Ligne de commande introuvable")
        remaining = item.quantity - item.received_quantity
        if entry.quantity > remaining:
            raise BusinessRuleError(
                "Quantité reçue supérieure à la quantité restante",
                details={"item_id": str(item.id), "remaining": str(remaining)},
            )
        item.received_quantity = item.received_quantity + entry.quantity
        await stock_service.apply_movement(
            db,
            tenant_id=tenant_id,
            branch_id=order.branch_id,
            product_id=item.product_id,
            movement_type="purchase_in",
            quantity=entry.quantity,
            unit_cost=item.unit_cost,
            reference_type="purchase_order",
            reference_id=order.id,
            performed_by=ctx.user.id,
        )
        # Met à jour le prix d'achat du produit avec le dernier coût connu
        product = await db.get(Product, item.product_id)
        if product is not None:
            product.purchase_price = item.unit_cost

    fully_received = all(i.received_quantity >= i.quantity for i in items.values())
    order.status = "received" if fully_received else "partially_received"
    await record_audit(
        db,
        action="suppliers.receive",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="purchase_order",
        entity_id=order.id,
    )
    return ok(
        OrderOut.model_validate(order).model_dump(mode="json"), message="Réception enregistrée"
    )


@router.post("/orders/{order_id}/payments", dependencies=[require_permissions("suppliers.pay")])
async def pay_order(
    order_id: uuid.UUID, payload: SupplierPaymentRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    order = await get_tenant_entity(db, PurchaseOrder, order_id, tenant_id)
    amount = money(payload.amount)
    if order.amount_paid + amount > order.total:
        raise BusinessRuleError(
            "Le paiement dépasse le montant de la commande",
            details={"remaining": str(order.total - order.amount_paid)},
        )
    db.add(
        SupplierPayment(
            tenant_id=tenant_id,
            supplier_id=order.supplier_id,
            purchase_order_id=order.id,
            amount=amount,
            method=payload.method,
            paid_at=datetime.now(UTC),
            reference=payload.reference,
            notes=payload.notes,
            created_by=ctx.user.id,
        )
    )
    order.amount_paid = money(order.amount_paid + amount)
    return ok(OrderOut.model_validate(order).model_dump(mode="json"), message="Paiement enregistré")


@router.get("/debts/summary", dependencies=[require_permissions("suppliers.read")])
async def supplier_debts(db: Db, ctx: Ctx) -> dict[str, Any]:
    """Dettes fournisseurs = commandes reçues non intégralement payées."""
    tenant_id = ctx.require_tenant()
    rows = (
        await db.execute(
            select(
                PurchaseOrder.supplier_id,
                func.sum(PurchaseOrder.total - PurchaseOrder.amount_paid),
            )
            .where(
                PurchaseOrder.tenant_id == tenant_id,
                PurchaseOrder.status.in_(["partially_received", "received"]),
                PurchaseOrder.total > PurchaseOrder.amount_paid,
            )
            .group_by(PurchaseOrder.supplier_id)
        )
    ).all()
    return ok({str(supplier_id): str(money(total)) for supplier_id, total in rows})
