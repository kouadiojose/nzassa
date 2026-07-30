"""Synchronisation hors connexion.

- `POST /sync/push` : le mobile envoie un lot d'opérations créées hors ligne.
  Chaque opération porte un `client_operation_id` (UUID généré côté client) qui
  garantit l'idempotence : rejouer un lot ne crée jamais de doublon.
- `GET /sync/pull` : synchronisation incrémentale (delta depuis `since`).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import AppError
from nzassa.core.logging import get_logger
from nzassa.core.responses import ok
from nzassa.core.tenancy import tenant_query
from nzassa.models.catalog import Product, Service
from nzassa.models.customers import Customer
from nzassa.models.system import SyncOperation
from nzassa.modules.customers.router import CustomerCreate
from nzassa.modules.expenses.router import ExpenseCreate
from nzassa.modules.sales import service as sales_service
from nzassa.modules.sales.schemas import SaleCreate

logger = get_logger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])

SUPPORTED_OPERATIONS = {"create_sale", "create_expense", "create_customer"}


class SyncOperationIn(BaseModel):
    client_operation_id: str = Field(min_length=8, max_length=64)
    operation_type: str
    payload: dict[str, Any]


class SyncPushRequest(BaseModel):
    operations: list[SyncOperationIn] = Field(min_length=1, max_length=100)


async def _apply_operation(db: Db, ctx: Ctx, operation: SyncOperation) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    payload = dict(operation.payload)
    payload.setdefault("client_reference", operation.client_operation_id)

    if operation.operation_type == "create_sale":
        sale_payload = SaleCreate.model_validate(payload)
        sale = await sales_service.create_sale(
            db,
            tenant_id=tenant_id,
            user=ctx.user,
            payload=sale_payload,
            require_cash_session=False,  # les ventes offline n'exigent pas de session
        )
        return {"entity": "sale", "id": str(sale.id), "number": sale.number}

    if operation.operation_type == "create_expense":
        from nzassa.core.money import money
        from nzassa.core.tenancy import get_tenant_entity
        from nzassa.models.business import Branch
        from nzassa.models.expenses import Expense

        expense_payload = ExpenseCreate.model_validate(payload)
        existing = (
            await db.execute(
                select(Expense).where(Expense.client_reference == expense_payload.client_reference)
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {"entity": "expense", "id": str(existing.id)}
        await get_tenant_entity(db, Branch, expense_payload.branch_id, tenant_id)
        expense = Expense(
            tenant_id=tenant_id,
            created_by=ctx.user.id,
            status="approved",
            **{**expense_payload.model_dump(), "amount": money(expense_payload.amount)},
        )
        db.add(expense)
        await db.flush()
        return {"entity": "expense", "id": str(expense.id)}

    if operation.operation_type == "create_customer":
        customer_payload = CustomerCreate.model_validate(payload)
        if customer_payload.phone:
            existing_customer = (
                (
                    await db.execute(
                        tenant_query(Customer, tenant_id).where(
                            Customer.phone == customer_payload.phone
                        )
                    )
                )
                .scalars()
                .first()
            )
            if existing_customer is not None:
                return {"entity": "customer", "id": str(existing_customer.id), "deduplicated": True}
        from nzassa.modules.businesses.router import get_current_business

        business = await get_current_business(db, ctx)
        customer = Customer(
            tenant_id=tenant_id,
            business_id=business.id,
            created_by=ctx.user.id,
            **customer_payload.model_dump(exclude={"client_reference"}),
        )
        db.add(customer)
        await db.flush()
        return {"entity": "customer", "id": str(customer.id)}

    raise AppError(f"Type d'opération non supporté : {operation.operation_type}")


@router.post("/push", dependencies=[require_permissions("sales.create")])
async def push_operations(payload: SyncPushRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    results: list[dict[str, Any]] = []
    for op_in in payload.operations:
        # Idempotence : opération déjà appliquée -> on renvoie le résultat stocké
        existing = (
            await db.execute(
                select(SyncOperation).where(
                    SyncOperation.tenant_id == tenant_id,
                    SyncOperation.client_operation_id == op_in.client_operation_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None and existing.status == "applied":
            results.append(
                {
                    "client_operation_id": op_in.client_operation_id,
                    "status": "applied",
                    "result": existing.result,
                    "duplicate": True,
                }
            )
            continue

        operation = existing or SyncOperation(
            tenant_id=tenant_id,
            user_id=ctx.user.id,
            device_session_id=ctx.session_id,
            client_operation_id=op_in.client_operation_id,
            operation_type=op_in.operation_type,
            payload=op_in.payload,
        )
        if existing is None:
            db.add(operation)
            await db.flush()

        if op_in.operation_type not in SUPPORTED_OPERATIONS:
            operation.status = "failed"
            operation.error_message = "Type d'opération non supporté"
            results.append(
                {
                    "client_operation_id": op_in.client_operation_id,
                    "status": "failed",
                    "error": operation.error_message,
                }
            )
            continue

        try:
            result = await _apply_operation(db, ctx, operation)
            operation.status = "applied"
            operation.result = result
            operation.applied_at = datetime.now(UTC)
            results.append(
                {
                    "client_operation_id": op_in.client_operation_id,
                    "status": "applied",
                    "result": result,
                }
            )
        except AppError as exc:
            operation.status = "conflict" if exc.status_code == 409 else "failed"
            operation.error_message = exc.message
            operation.result = {"error_code": exc.code, "details": exc.details}
            results.append(
                {
                    "client_operation_id": op_in.client_operation_id,
                    "status": operation.status,
                    "error": exc.message,
                    "error_code": exc.code,
                }
            )
    applied = sum(1 for r in results if r["status"] == "applied")
    return ok(
        {"results": results, "applied": applied, "total": len(results)},
        message=f"{applied}/{len(results)} opérations appliquées",
    )


@router.get("/pull", dependencies=[require_permissions("products.read")])
async def pull_changes(
    db: Db, ctx: Ctx, since: datetime | None = None, limit: int = 500
) -> dict[str, Any]:
    """Delta incrémental des données référentielles pour le cache offline mobile."""
    tenant_id = ctx.require_tenant()
    limit = min(limit, 1000)
    now = datetime.now(UTC)

    def _since(query: Any, model: Any) -> Any:
        return query.where(model.updated_at > since) if since else query

    products = (
        (
            await db.execute(
                _since(tenant_query(Product, tenant_id, include_deleted=True), Product).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    services = (
        (
            await db.execute(
                _since(tenant_query(Service, tenant_id, include_deleted=True), Service).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    customers = (
        (
            await db.execute(
                _since(tenant_query(Customer, tenant_id, include_deleted=True), Customer).limit(
                    limit
                )
            )
        )
        .scalars()
        .all()
    )
    return ok(
        {
            "server_time": now.isoformat(),
            "products": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "sku": p.sku,
                    "barcode": p.barcode,
                    "selling_price": str(p.selling_price),
                    "promo_price": str(p.promo_price) if p.promo_price else None,
                    "track_stock": p.track_stock,
                    "is_active": p.is_active and not p.archived,
                    "updated_at": p.updated_at.isoformat(),
                }
                for p in products
            ],
            "services": [
                {
                    "id": str(s.id),
                    "name": s.name,
                    "price": str(s.price),
                    "duration_minutes": s.duration_minutes,
                    "is_active": s.is_active and not s.archived,
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in services
            ],
            "customers": [
                {
                    "id": str(c.id),
                    "first_name": c.first_name,
                    "last_name": c.last_name,
                    "phone": c.phone,
                    "is_active": c.is_active,
                    "updated_at": c.updated_at.isoformat(),
                }
                for c in customers
            ],
        }
    )


_ = uuid.uuid4  # uuid utilisé par les modèles importés
