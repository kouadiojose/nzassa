"""Endpoints rapports et tableau de bord (agrégations SQL optimisées)."""

import csv
import io
import uuid
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import Select, func, select

from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.money import money
from nzassa.core.responses import ok
from nzassa.models.catalog import Product
from nzassa.models.customers import CustomerDebt
from nzassa.models.expenses import Expense
from nzassa.models.inventory import StockLevel
from nzassa.models.sales import Payment, Sale, SaleItem

router = APIRouter(prefix="/reports", tags=["reports"])


def _sales_between(tenant_id: uuid.UUID, date_from: date, date_to: date) -> Select[Any]:
    return select(Sale).where(
        Sale.tenant_id == tenant_id,
        Sale.status.in_(["completed", "partially_refunded", "refunded"]),
        func.date(Sale.sold_at) >= date_from,
        func.date(Sale.sold_at) <= date_to,
    )


@router.get("/dashboard", dependencies=[require_permissions("reports.read")])
async def dashboard(
    db: Db,
    ctx: Ctx,
    date_from: date | None = None,
    date_to: date | None = None,
    branch_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))

    sale_filter = [
        Sale.tenant_id == tenant_id,
        Sale.status.in_(["completed", "partially_refunded", "refunded"]),
        func.date(Sale.sold_at) >= date_from,
        func.date(Sale.sold_at) <= date_to,
    ]
    expense_filter = [
        Expense.tenant_id == tenant_id,
        Expense.status == "approved",
        Expense.expense_date >= date_from,
        Expense.expense_date <= date_to,
    ]
    if branch_id:
        sale_filter.append(Sale.branch_id == branch_id)
        expense_filter.append(Expense.branch_id == branch_id)

    revenue, sales_count = (
        await db.execute(
            select(func.coalesce(func.sum(Sale.total), 0), func.count()).where(*sale_filter)
        )
    ).one()
    expenses_total = (
        await db.execute(select(func.coalesce(func.sum(Expense.amount), 0)).where(*expense_filter))
    ).scalar_one()
    # Marge brute = ventes produits - coût d'achat des produits vendus
    cogs = (
        await db.execute(
            select(func.coalesce(func.sum(Product.purchase_price * SaleItem.quantity), 0))
            .select_from(SaleItem)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .join(Product, Product.id == SaleItem.product_id)
            .where(*sale_filter, SaleItem.item_type == "product")
        )
    ).scalar_one()
    open_debts = (
        await db.execute(
            select(func.coalesce(func.sum(CustomerDebt.balance), 0)).where(
                CustomerDebt.tenant_id == tenant_id,
                CustomerDebt.status.in_(["open", "partially_paid"]),
            )
        )
    ).scalar_one()
    stock_value = (
        await db.execute(
            select(func.coalesce(func.sum(StockLevel.quantity * Product.purchase_price), 0))
            .select_from(StockLevel)
            .join(Product, Product.id == StockLevel.product_id)
            .where(StockLevel.tenant_id == tenant_id)
        )
    ).scalar_one()
    low_stock_count = (
        await db.execute(
            select(func.count())
            .select_from(StockLevel)
            .join(Product, Product.id == StockLevel.product_id)
            .where(
                StockLevel.tenant_id == tenant_id,
                Product.track_stock.is_(True),
                StockLevel.quantity <= Product.low_stock_threshold,
            )
        )
    ).scalar_one()

    gross_margin = money(revenue) - money(cogs)
    return ok(
        {
            "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
            "revenue": str(money(revenue)),
            "sales_count": sales_count,
            "expenses": str(money(expenses_total)),
            "gross_margin": str(gross_margin),
            "estimated_profit": str(gross_margin - money(expenses_total)),
            "open_debts": str(money(open_debts)),
            "stock_value": str(money(stock_value)),
            "low_stock_count": low_stock_count,
        }
    )


@router.get("/sales-by-day", dependencies=[require_permissions("reports.read")])
async def sales_by_day(
    db: Db, ctx: Ctx, date_from: date | None = None, date_to: date | None = None
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))
    rows = (
        await db.execute(
            select(
                func.date(Sale.sold_at).label("day"),
                func.coalesce(func.sum(Sale.total), 0),
                func.count(),
            )
            .where(
                Sale.tenant_id == tenant_id,
                Sale.status.in_(["completed", "partially_refunded", "refunded"]),
                func.date(Sale.sold_at) >= date_from,
                func.date(Sale.sold_at) <= date_to,
            )
            .group_by(func.date(Sale.sold_at))
            .order_by(func.date(Sale.sold_at))
        )
    ).all()
    return ok(
        [
            {"day": str(day), "revenue": str(money(total)), "count": count}
            for day, total, count in rows
        ]
    )


@router.get("/top-products", dependencies=[require_permissions("reports.read")])
async def top_products(
    db: Db, ctx: Ctx, date_from: date | None = None, date_to: date | None = None, limit: int = 10
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))
    rows = (
        await db.execute(
            select(
                SaleItem.label,
                func.sum(SaleItem.quantity),
                func.sum(SaleItem.line_total),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                Sale.tenant_id == tenant_id,
                Sale.status.in_(["completed", "partially_refunded"]),
                func.date(Sale.sold_at) >= date_from,
                func.date(Sale.sold_at) <= date_to,
            )
            .group_by(SaleItem.label)
            .order_by(func.sum(SaleItem.line_total).desc())
            .limit(min(limit, 50))
        )
    ).all()
    return ok(
        [
            {"label": label, "quantity": str(qty), "revenue": str(money(total))}
            for label, qty, total in rows
        ]
    )


@router.get("/sales-by-employee", dependencies=[require_permissions("reports.read")])
async def sales_by_employee(
    db: Db, ctx: Ctx, date_from: date | None = None, date_to: date | None = None
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))
    rows = (
        await db.execute(
            select(Sale.seller_employee_id, func.sum(Sale.total), func.count())
            .where(
                Sale.tenant_id == tenant_id,
                Sale.status.in_(["completed", "partially_refunded"]),
                func.date(Sale.sold_at) >= date_from,
                func.date(Sale.sold_at) <= date_to,
            )
            .group_by(Sale.seller_employee_id)
        )
    ).all()
    return ok(
        [
            {
                "employee_id": str(emp_id) if emp_id else None,
                "revenue": str(money(total)),
                "count": count,
            }
            for emp_id, total, count in rows
        ]
    )


@router.get("/payment-methods", dependencies=[require_permissions("reports.read")])
async def payment_methods_report(
    db: Db, ctx: Ctx, date_from: date | None = None, date_to: date | None = None
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))
    rows = (
        await db.execute(
            select(Payment.method, func.sum(Payment.amount), func.count())
            .where(
                Payment.tenant_id == tenant_id,
                Payment.status == "confirmed",
                func.date(Payment.paid_at) >= date_from,
                func.date(Payment.paid_at) <= date_to,
            )
            .group_by(Payment.method)
        )
    ).all()
    return ok(
        [
            {"method": method, "total": str(money(total)), "count": count}
            for method, total, count in rows
        ]
    )


@router.get("/sales/export/csv", dependencies=[require_permissions("reports.export")])
async def export_sales_csv(
    db: Db, ctx: Ctx, date_from: date | None = None, date_to: date | None = None
) -> StreamingResponse:
    tenant_id = ctx.require_tenant()
    date_to = date_to or date.today()
    date_from = date_from or (date_to - timedelta(days=29))
    sales = (
        (await db.execute(_sales_between(tenant_id, date_from, date_to).order_by(Sale.sold_at)))
        .scalars()
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["numero", "date", "statut", "total", "paye", "reste_du"])
    for s in sales:
        writer.writerow(
            [s.number, s.sold_at.isoformat(), s.status, s.total, s.amount_paid, s.amount_due]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ventes.csv"},
    )
