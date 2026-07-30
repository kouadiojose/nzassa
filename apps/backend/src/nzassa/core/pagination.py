"""Pagination, tri et recherche standardisés."""

from dataclasses import dataclass
from typing import Any

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class PageParams:
    page: int
    per_page: int
    sort_by: str | None
    sort_dir: str
    search: str | None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


def page_params(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=200),
    sort_by: str | None = Query(None),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, max_length=200),
) -> PageParams:
    return PageParams(
        page=page, per_page=per_page, sort_by=sort_by, sort_dir=sort_dir, search=search
    )


async def paginate(
    db: AsyncSession,
    query: Select[Any],
    params: PageParams,
    *,
    sortable: dict[str, Any] | None = None,
    default_sort: Any = None,
) -> tuple[list[Any], dict[str, Any]]:
    """Applique tri + pagination et retourne (items, meta)."""
    count_query = select(func.count()).select_from(query.order_by(None).subquery())
    total = (await db.execute(count_query)).scalar_one()

    sort_col = None
    if params.sort_by and sortable and params.sort_by in sortable:
        sort_col = sortable[params.sort_by]
    elif default_sort is not None:
        sort_col = default_sort
    if sort_col is not None:
        query = query.order_by(sort_col.desc() if params.sort_dir == "desc" else sort_col.asc())

    rows = (await db.execute(query.offset(params.offset).limit(params.per_page))).scalars().all()
    meta = {
        "page": params.page,
        "per_page": params.per_page,
        "total": total,
        "total_pages": (total + params.per_page - 1) // params.per_page if total else 0,
    }
    return list(rows), meta
