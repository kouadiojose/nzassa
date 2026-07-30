"""Endpoints clients (fiche, recherche, historique, dettes, fidélité)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, or_, select

from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import ConflictError
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.customers import Customer, CustomerDebt, LoyaltyAccount
from nzassa.models.sales import Sale
from nzassa.modules.businesses.router import get_current_business

router = APIRouter(prefix="/customers", tags=["customers"])

Page = Annotated[PageParams, Depends(page_params)]


class CustomerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    address: str | None = None
    gender: str | None = Field(default=None, pattern="^(male|female|other)$")
    birth_date: date | None = None
    notes: str | None = None
    tags: list[str] = []
    marketing_consent: bool = False
    credit_limit: Decimal | None = Field(default=None, ge=0)
    client_reference: str | None = None  # idempotence offline


class CustomerUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = None
    gender: str | None = Field(default=None, pattern="^(male|female|other)$")
    birth_date: date | None = None
    notes: str | None = None
    tags: list[str] | None = None
    marketing_consent: bool | None = None
    credit_limit: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str | None
    phone: str | None
    email: str | None
    address: str | None
    gender: str | None
    birth_date: date | None
    notes: str | None
    tags: list[str]
    marketing_consent: bool
    is_active: bool
    credit_limit: Decimal | None


@router.get("", dependencies=[require_permissions("customers.read")])
async def list_customers(
    db: Db, ctx: Ctx, params: Page, phone: str | None = None
) -> dict[str, Any]:
    query = tenant_query(Customer, ctx.require_tenant())
    if phone:
        query = query.where(Customer.phone == phone)
    if params.search:
        like = f"%{params.search}%"
        query = query.where(
            or_(
                Customer.first_name.ilike(like),
                Customer.last_name.ilike(like),
                Customer.phone.ilike(like),
            )
        )
    items, meta = await paginate(
        db,
        query,
        params,
        sortable={"first_name": Customer.first_name, "created_at": Customer.created_at},
        default_sort=Customer.created_at,
    )
    return ok([CustomerOut.model_validate(c).model_dump(mode="json") for c in items], **meta)


@router.post("", status_code=201, dependencies=[require_permissions("customers.create")])
async def create_customer(payload: CustomerCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    business = await get_current_business(db, ctx)
    if payload.phone:
        duplicate = (
            await db.execute(
                tenant_query(Customer, tenant_id).where(Customer.phone == payload.phone)
            )
        ).first()
        if duplicate:
            raise ConflictError("Un client existe déjà avec ce numéro de téléphone")
    data = payload.model_dump(exclude={"client_reference"})
    customer = Customer(
        tenant_id=tenant_id, business_id=business.id, created_by=ctx.user.id, **data
    )
    db.add(customer)
    await db.flush()
    return ok(CustomerOut.model_validate(customer).model_dump(mode="json"), message="Client créé")


@router.get("/{customer_id}", dependencies=[require_permissions("customers.read")])
async def get_customer(customer_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    customer = await get_tenant_entity(db, Customer, customer_id, tenant_id)
    total_purchases = (
        await db.execute(
            select(func.coalesce(func.sum(Sale.total), 0)).where(
                Sale.tenant_id == tenant_id,
                Sale.customer_id == customer.id,
                Sale.status == "completed",
            )
        )
    ).scalar_one()
    open_debt = (
        await db.execute(
            select(func.coalesce(func.sum(CustomerDebt.balance), 0)).where(
                CustomerDebt.tenant_id == tenant_id,
                CustomerDebt.customer_id == customer.id,
                CustomerDebt.status.in_(["open", "partially_paid"]),
            )
        )
    ).scalar_one()
    loyalty = (
        await db.execute(
            tenant_query(LoyaltyAccount, tenant_id).where(LoyaltyAccount.customer_id == customer.id)
        )
    ).scalar_one_or_none()
    data = CustomerOut.model_validate(customer).model_dump(mode="json")
    data["stats"] = {
        "total_purchases": str(total_purchases),
        "open_debt": str(open_debt),
        "loyalty_points": loyalty.points_balance if loyalty else 0,
        "loyalty_tier": loyalty.tier if loyalty else None,
    }
    return ok(data)


@router.patch("/{customer_id}", dependencies=[require_permissions("customers.update")])
async def update_customer(
    customer_id: uuid.UUID, payload: CustomerUpdate, db: Db, ctx: Ctx
) -> dict[str, Any]:
    customer = await get_tenant_entity(db, Customer, customer_id, ctx.require_tenant())
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, key, value)
    customer.updated_by = ctx.user.id
    return ok(CustomerOut.model_validate(customer).model_dump(mode="json"))


@router.get("/{customer_id}/sales", dependencies=[require_permissions("customers.read")])
async def customer_sales(customer_id: uuid.UUID, db: Db, ctx: Ctx, params: Page) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_tenant_entity(db, Customer, customer_id, tenant_id)
    query = tenant_query(Sale, tenant_id).where(Sale.customer_id == customer_id)
    items, meta = await paginate(db, query, params, default_sort=Sale.sold_at)
    return ok(
        [
            {
                "id": str(s.id),
                "number": s.number,
                "status": s.status,
                "total": str(s.total),
                "amount_paid": str(s.amount_paid),
                "amount_due": str(s.amount_due),
                "sold_at": s.sold_at.isoformat(),
            }
            for s in items
        ],
        **meta,
    )
