"""Endpoints du catalogue : produits, prestations, catégories, marques, unités, taxes."""

import csv
import io
import secrets
import uuid
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import ConflictError, ValidationAppError
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.business import Business
from nzassa.models.catalog import (
    Product,
    ProductBrand,
    ProductCategory,
    Service,
    Tax,
    Unit,
)
from nzassa.modules.businesses.router import get_current_business
from nzassa.modules.catalog.schemas import (
    BrandCreate,
    BrandOut,
    CategoryCreate,
    CategoryOut,
    ProductCreate,
    ProductOut,
    ProductUpdate,
    ServiceCreate,
    ServiceOut,
    ServiceUpdate,
    TaxCreate,
    TaxOut,
    UnitCreate,
    UnitOut,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])

Page = Annotated[PageParams, Depends(page_params)]


# ---------- Taxonomies ----------


@router.get("/categories", dependencies=[require_permissions("products.read")])
async def list_categories(db: Db, ctx: Ctx) -> dict[str, Any]:
    rows = (
        (
            await db.execute(
                tenant_query(ProductCategory, ctx.require_tenant()).order_by(ProductCategory.name)
            )
        )
        .scalars()
        .all()
    )
    return ok([CategoryOut.model_validate(c).model_dump(mode="json") for c in rows])


@router.post("/categories", status_code=201, dependencies=[require_permissions("products.create")])
async def create_category(payload: CategoryCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    category = ProductCategory(
        tenant_id=ctx.require_tenant(), created_by=ctx.user.id, **payload.model_dump()
    )
    db.add(category)
    await db.flush()
    return ok(CategoryOut.model_validate(category).model_dump(mode="json"))


@router.get("/brands", dependencies=[require_permissions("products.read")])
async def list_brands(db: Db, ctx: Ctx) -> dict[str, Any]:
    rows = (
        (
            await db.execute(
                tenant_query(ProductBrand, ctx.require_tenant()).order_by(ProductBrand.name)
            )
        )
        .scalars()
        .all()
    )
    return ok([BrandOut.model_validate(b).model_dump(mode="json") for b in rows])


@router.post("/brands", status_code=201, dependencies=[require_permissions("products.create")])
async def create_brand(payload: BrandCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    brand = ProductBrand(
        tenant_id=ctx.require_tenant(), created_by=ctx.user.id, **payload.model_dump()
    )
    db.add(brand)
    await db.flush()
    return ok(BrandOut.model_validate(brand).model_dump(mode="json"))


@router.get("/units", dependencies=[require_permissions("products.read")])
async def list_units(db: Db, ctx: Ctx) -> dict[str, Any]:
    rows = (
        (await db.execute(tenant_query(Unit, ctx.require_tenant()).order_by(Unit.code)))
        .scalars()
        .all()
    )
    return ok([UnitOut.model_validate(u).model_dump(mode="json") for u in rows])


@router.post("/units", status_code=201, dependencies=[require_permissions("products.create")])
async def create_unit(payload: UnitCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    unit = Unit(tenant_id=ctx.require_tenant(), created_by=ctx.user.id, **payload.model_dump())
    db.add(unit)
    await db.flush()
    return ok(UnitOut.model_validate(unit).model_dump(mode="json"))


@router.get("/taxes", dependencies=[require_permissions("products.read")])
async def list_taxes(db: Db, ctx: Ctx) -> dict[str, Any]:
    rows = (
        (await db.execute(tenant_query(Tax, ctx.require_tenant()).order_by(Tax.name)))
        .scalars()
        .all()
    )
    return ok([TaxOut.model_validate(t).model_dump(mode="json") for t in rows])


@router.post("/taxes", status_code=201, dependencies=[require_permissions("settings.update")])
async def create_tax(payload: TaxCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    tax = Tax(tenant_id=ctx.require_tenant(), created_by=ctx.user.id, **payload.model_dump())
    db.add(tax)
    await db.flush()
    return ok(TaxOut.model_validate(tax).model_dump(mode="json"))


# ---------- Produits ----------


async def _check_product_uniqueness(
    db: Db,
    tenant_id: uuid.UUID,
    sku: str | None,
    barcode: str | None,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if not sku and not barcode:
        return
    conditions = []
    if sku:
        conditions.append(Product.sku == sku)
    if barcode:
        conditions.append(Product.barcode == barcode)
    query = tenant_query(Product, tenant_id).where(or_(*conditions))
    if exclude_id:
        query = query.where(Product.id != exclude_id)
    if (await db.execute(query.limit(1))).first():
        raise ConflictError("SKU ou code-barres déjà utilisé")


@router.get("/products", dependencies=[require_permissions("products.read")])
async def list_products(
    db: Db,
    ctx: Ctx,
    params: Page,
    category_id: uuid.UUID | None = None,
    archived: bool = False,
    barcode: str | None = None,
) -> dict[str, Any]:
    query = tenant_query(Product, ctx.require_tenant()).where(Product.archived == archived)
    if category_id:
        query = query.where(Product.category_id == category_id)
    if barcode:
        query = query.where(Product.barcode == barcode)
    if params.search:
        like = f"%{params.search}%"
        query = query.where(
            or_(Product.name.ilike(like), Product.sku.ilike(like), Product.barcode.ilike(like))
        )
    items, meta = await paginate(
        db,
        query,
        params,
        sortable={
            "name": Product.name,
            "selling_price": Product.selling_price,
            "created_at": Product.created_at,
        },
        default_sort=Product.created_at,
    )
    return ok([ProductOut.model_validate(p).model_dump(mode="json") for p in items], **meta)


@router.post("/products", status_code=201, dependencies=[require_permissions("products.create")])
async def create_product(payload: ProductCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    business = await get_current_business(db, ctx)
    from nzassa.modules.subscriptions.service import enforce_limit

    await enforce_limit(db, tenant_id, "max_products")
    await _check_product_uniqueness(db, tenant_id, payload.sku, payload.barcode)
    data = payload.model_dump()
    if not data.get("sku"):
        data["sku"] = f"P-{secrets.token_hex(4).upper()}"
    product = Product(tenant_id=tenant_id, business_id=business.id, created_by=ctx.user.id, **data)
    db.add(product)
    await db.flush()
    await record_audit(
        db,
        action="products.create",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="product",
        entity_id=product.id,
    )
    return ok(ProductOut.model_validate(product).model_dump(mode="json"), message="Produit créé")


@router.get("/products/{product_id}", dependencies=[require_permissions("products.read")])
async def get_product(product_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    product = await get_tenant_entity(db, Product, product_id, ctx.require_tenant())
    return ok(ProductOut.model_validate(product).model_dump(mode="json"))


@router.patch("/products/{product_id}", dependencies=[require_permissions("products.update")])
async def update_product(
    product_id: uuid.UUID, payload: ProductUpdate, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    product = await get_tenant_entity(db, Product, product_id, tenant_id)
    changes = payload.model_dump(exclude_unset=True)
    if "sku" in changes or "barcode" in changes:
        await _check_product_uniqueness(
            db, tenant_id, changes.get("sku"), changes.get("barcode"), exclude_id=product.id
        )
    for key, value in changes.items():
        setattr(product, key, value)
    product.updated_by = ctx.user.id
    return ok(ProductOut.model_validate(product).model_dump(mode="json"))


@router.post(
    "/products/{product_id}/archive", dependencies=[require_permissions("products.archive")]
)
async def archive_product(product_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    product = await get_tenant_entity(db, Product, product_id, ctx.require_tenant())
    product.archived = True
    product.is_active = False
    product.updated_by = ctx.user.id
    await record_audit(
        db,
        action="products.archive",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        entity_type="product",
        entity_id=product.id,
    )
    return ok(message="Produit archivé")


EXPORT_COLUMNS = [
    "name",
    "sku",
    "barcode",
    "purchase_price",
    "selling_price",
    "low_stock_threshold",
    "track_stock",
    "description",
]


@router.get("/products/export/csv", dependencies=[require_permissions("products.export")])
async def export_products_csv(db: Db, ctx: Ctx) -> StreamingResponse:
    products = (
        (await db.execute(tenant_query(Product, ctx.require_tenant()).order_by(Product.name)))
        .scalars()
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for p in products:
        writer.writerow([getattr(p, col) for col in EXPORT_COLUMNS])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=produits.csv"},
    )


@router.post("/products/import/csv", dependencies=[require_permissions("products.import")])
async def import_products_csv(file: UploadFile, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    business = await get_current_business(db, ctx)
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    created, errors = 0, []
    for line_no, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"line": line_no, "error": "nom manquant"})
            continue
        try:
            selling_price = Decimal(row.get("selling_price") or "0")
            purchase_price = Decimal(row.get("purchase_price") or "0")
        except InvalidOperation:
            errors.append({"line": line_no, "error": "prix invalide"})
            continue
        sku = (row.get("sku") or "").strip() or f"P-{secrets.token_hex(4).upper()}"
        barcode = (row.get("barcode") or "").strip() or None
        try:
            await _check_product_uniqueness(db, tenant_id, sku, barcode)
        except ConflictError:
            errors.append({"line": line_no, "error": "SKU/code-barres en double"})
            continue
        db.add(
            Product(
                tenant_id=tenant_id,
                business_id=business.id,
                created_by=ctx.user.id,
                name=name,
                sku=sku,
                barcode=barcode,
                selling_price=selling_price,
                purchase_price=purchase_price,
                description=(row.get("description") or None),
            )
        )
        created += 1
    await db.flush()
    if created == 0 and errors:
        raise ValidationAppError("Aucune ligne importée", details={"errors": errors})
    return ok({"created": created, "errors": errors}, message=f"{created} produits importés")


# ---------- Prestations ----------


@router.get("/services", dependencies=[require_permissions("products.read")])
async def list_services(db: Db, ctx: Ctx, params: Page) -> dict[str, Any]:
    query = tenant_query(Service, ctx.require_tenant()).where(Service.archived.is_(False))
    if params.search:
        query = query.where(Service.name.ilike(f"%{params.search}%"))
    items, meta = await paginate(
        db,
        query,
        params,
        sortable={"name": Service.name, "price": Service.price},
        default_sort=Service.created_at,
    )
    return ok([ServiceOut.model_validate(s).model_dump(mode="json") for s in items], **meta)


@router.post("/services", status_code=201, dependencies=[require_permissions("products.create")])
async def create_service(payload: ServiceCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    business = await get_current_business(db, ctx)
    service = Service(
        tenant_id=ctx.require_tenant(),
        business_id=business.id,
        created_by=ctx.user.id,
        **payload.model_dump(),
    )
    db.add(service)
    await db.flush()
    return ok(
        ServiceOut.model_validate(service).model_dump(mode="json"), message="Prestation créée"
    )


@router.patch("/services/{service_id}", dependencies=[require_permissions("products.update")])
async def update_service(
    service_id: uuid.UUID, payload: ServiceUpdate, db: Db, ctx: Ctx
) -> dict[str, Any]:
    service = await get_tenant_entity(db, Service, service_id, ctx.require_tenant())
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, key, value)
    service.updated_by = ctx.user.id
    return ok(ServiceOut.model_validate(service).model_dump(mode="json"))


__all__ = ["Business", "router"]
