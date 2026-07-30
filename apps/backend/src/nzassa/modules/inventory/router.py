"""Endpoints du stock."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import BusinessRuleError
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.business import Branch
from nzassa.models.catalog import Product
from nzassa.models.inventory import StockLevel, StockMovement, StockTransfer, StockTransferItem
from nzassa.modules.inventory import service as stock_service
from nzassa.modules.inventory.schemas import (
    MovementOut,
    StockAdjustRequest,
    StockEntryRequest,
    StockExitRequest,
    StockLevelOut,
    StockTransferRequest,
)

router = APIRouter(prefix="/stock", tags=["stock"])

Page = Annotated[PageParams, Depends(page_params)]


@router.get("/levels", dependencies=[require_permissions("stock.read")])
async def list_levels(
    db: Db, ctx: Ctx, params: Page, branch_id: uuid.UUID | None = None, low_stock: bool = False
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    query = tenant_query(StockLevel, tenant_id)
    if branch_id:
        query = query.where(StockLevel.branch_id == branch_id)
    if low_stock:
        query = query.join(Product, Product.id == StockLevel.product_id).where(
            StockLevel.quantity <= Product.low_stock_threshold, Product.track_stock.is_(True)
        )
    items, meta = await paginate(db, query, params, default_sort=StockLevel.updated_at)
    return ok([StockLevelOut.model_validate(lvl).model_dump(mode="json") for lvl in items], **meta)


@router.get("/movements", dependencies=[require_permissions("stock.read")])
async def list_movements(
    db: Db,
    ctx: Ctx,
    params: Page,
    branch_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    query = select(StockMovement).where(StockMovement.tenant_id == ctx.require_tenant())
    if branch_id:
        query = query.where(StockMovement.branch_id == branch_id)
    if product_id:
        query = query.where(StockMovement.product_id == product_id)
    items, meta = await paginate(db, query, params, default_sort=StockMovement.created_at)
    return ok([MovementOut.model_validate(m).model_dump(mode="json") for m in items], **meta)


@router.post("/entries", status_code=201, dependencies=[require_permissions("stock.in")])
async def stock_entry(payload: StockEntryRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_tenant_entity(db, Branch, payload.branch_id, tenant_id)
    product = await get_tenant_entity(db, Product, payload.product_id, tenant_id)
    movement = await stock_service.apply_movement(
        db,
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        product_id=product.id,
        movement_type="purchase_in",
        quantity=payload.quantity,
        unit_cost=payload.unit_cost if payload.unit_cost is not None else product.purchase_price,
        reason=payload.reason,
        performed_by=ctx.user.id,
    )
    await db.flush()
    return ok(
        MovementOut.model_validate(movement).model_dump(mode="json"), message="Entrée enregistrée"
    )


@router.post("/exits", status_code=201, dependencies=[require_permissions("stock.out")])
async def stock_exit(payload: StockExitRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_tenant_entity(db, Branch, payload.branch_id, tenant_id)
    product = await get_tenant_entity(db, Product, payload.product_id, tenant_id)
    movement = await stock_service.apply_movement(
        db,
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        product_id=product.id,
        movement_type=payload.movement_type,
        quantity=-payload.quantity,
        reason=payload.reason,
        performed_by=ctx.user.id,
    )
    await db.flush()
    await record_audit(
        db,
        action=f"stock.{payload.movement_type}",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="product",
        entity_id=product.id,
        after={"quantity": str(payload.quantity), "reason": payload.reason},
    )
    return ok(
        MovementOut.model_validate(movement).model_dump(mode="json"), message="Sortie enregistrée"
    )


@router.post("/adjustments", status_code=201, dependencies=[require_permissions("stock.adjust")])
async def stock_adjust(payload: StockAdjustRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    """Ajustement : fixe la quantité comptée, le delta est journalisé."""
    tenant_id = ctx.require_tenant()
    await get_tenant_entity(db, Branch, payload.branch_id, tenant_id)
    product = await get_tenant_entity(db, Product, payload.product_id, tenant_id)
    level = await stock_service.get_or_create_level(db, tenant_id, payload.branch_id, product.id)
    delta = payload.counted_quantity - level.quantity
    if delta == 0:
        return ok(message="Aucun écart constaté")
    movement = await stock_service.apply_movement(
        db,
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        product_id=product.id,
        movement_type="adjustment",
        quantity=delta,
        reason=payload.reason,
        performed_by=ctx.user.id,
        allow_negative=True,
    )
    await db.flush()
    await record_audit(
        db,
        action="stock.adjust",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="product",
        entity_id=product.id,
        before={"quantity": str(level.quantity - delta)},
        after={"quantity": str(payload.counted_quantity), "reason": payload.reason},
    )
    return ok(
        MovementOut.model_validate(movement).model_dump(mode="json"),
        message="Ajustement enregistré",
    )


@router.post("/transfers", status_code=201, dependencies=[require_permissions("stock.transfer")])
async def stock_transfer(payload: StockTransferRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    if payload.from_branch_id == payload.to_branch_id:
        raise BusinessRuleError("Les points de vente source et destination doivent différer")
    await get_tenant_entity(db, Branch, payload.from_branch_id, tenant_id)
    await get_tenant_entity(db, Branch, payload.to_branch_id, tenant_id)

    from datetime import UTC, datetime

    transfer = StockTransfer(
        tenant_id=tenant_id,
        from_branch_id=payload.from_branch_id,
        to_branch_id=payload.to_branch_id,
        status="completed",
        notes=payload.notes,
        completed_at=datetime.now(UTC),
        created_by=ctx.user.id,
    )
    db.add(transfer)
    await db.flush()

    for item in payload.items:
        product = await get_tenant_entity(db, Product, item.product_id, tenant_id)
        db.add(
            StockTransferItem(
                tenant_id=tenant_id,
                transfer_id=transfer.id,
                product_id=product.id,
                quantity=item.quantity,
            )
        )
        await stock_service.apply_movement(
            db,
            tenant_id=tenant_id,
            branch_id=payload.from_branch_id,
            product_id=product.id,
            movement_type="transfer_out",
            quantity=-item.quantity,
            reference_type="stock_transfer",
            reference_id=transfer.id,
            performed_by=ctx.user.id,
        )
        await stock_service.apply_movement(
            db,
            tenant_id=tenant_id,
            branch_id=payload.to_branch_id,
            product_id=product.id,
            movement_type="transfer_in",
            quantity=item.quantity,
            reference_type="stock_transfer",
            reference_id=transfer.id,
            performed_by=ctx.user.id,
        )
    await record_audit(
        db,
        action="stock.transfer",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="stock_transfer",
        entity_id=transfer.id,
    )
    return ok({"transfer_id": str(transfer.id)}, message="Transfert effectué")
