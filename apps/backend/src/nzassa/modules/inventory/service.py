"""Service de stock — source de vérité des mouvements.

Chaque changement de quantité passe par `apply_movement`, qui :
1. verrouille la ligne de stock (SELECT ... FOR UPDATE) ;
2. contrôle les stocks négatifs ;
3. écrit un mouvement IMMUABLE dans le grand livre ;
4. met à jour le niveau courant.
"""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nzassa.core.errors import InsufficientStockError
from nzassa.models.catalog import Product
from nzassa.models.inventory import StockLevel, StockMovement

ENTRY_TYPES = {"purchase_in", "transfer_in", "return_in", "refund_in", "adjustment", "inventory"}
EXIT_TYPES = {"sale_out", "transfer_out", "loss", "damage", "expiry", "adjustment", "inventory"}


async def get_or_create_level(
    db: AsyncSession, tenant_id: uuid.UUID, branch_id: uuid.UUID, product_id: uuid.UUID
) -> StockLevel:
    level = (
        await db.execute(
            select(StockLevel)
            .where(
                StockLevel.tenant_id == tenant_id,
                StockLevel.branch_id == branch_id,
                StockLevel.product_id == product_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if level is None:
        level = StockLevel(
            tenant_id=tenant_id,
            branch_id=branch_id,
            product_id=product_id,
            quantity=Decimal("0"),
        )
        db.add(level)
        await db.flush()
    return level


async def apply_movement(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    product_id: uuid.UUID,
    movement_type: str,
    quantity: Decimal,
    unit_cost: Decimal | None = None,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    reason: str | None = None,
    performed_by: uuid.UUID | None = None,
    allow_negative: bool = False,
    extra: dict[str, Any] | None = None,
) -> StockMovement:
    """Applique un mouvement signé (+ entrée / - sortie) et retourne l'écriture."""
    level = await get_or_create_level(db, tenant_id, branch_id, product_id)
    new_quantity = level.quantity + quantity
    if new_quantity < 0 and not allow_negative:
        raise InsufficientStockError(
            details={
                "product_id": str(product_id),
                "available": str(level.quantity),
                "requested": str(-quantity),
            }
        )
    level.quantity = new_quantity
    movement = StockMovement(
        tenant_id=tenant_id,
        branch_id=branch_id,
        product_id=product_id,
        movement_type=movement_type,
        quantity=quantity,
        quantity_after=new_quantity,
        unit_cost=unit_cost,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
        performed_by=performed_by,
        extra=extra or {},
    )
    db.add(movement)
    return movement


async def deduct_for_sale(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    product: Product,
    quantity: Decimal,
    sale_id: uuid.UUID,
    performed_by: uuid.UUID | None,
) -> None:
    if not product.track_stock:
        return
    await apply_movement(
        db,
        tenant_id=tenant_id,
        branch_id=branch_id,
        product_id=product.id,
        movement_type="sale_out",
        quantity=-quantity,
        unit_cost=product.purchase_price,
        reference_type="sale",
        reference_id=sale_id,
        performed_by=performed_by,
    )


async def restock_for_reversal(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    product_id: uuid.UUID,
    quantity: Decimal,
    reference_type: str,
    reference_id: uuid.UUID,
    performed_by: uuid.UUID | None,
    reason: str,
) -> None:
    await apply_movement(
        db,
        tenant_id=tenant_id,
        branch_id=branch_id,
        product_id=product_id,
        movement_type="refund_in" if reference_type == "refund" else "return_in",
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
        performed_by=performed_by,
    )
