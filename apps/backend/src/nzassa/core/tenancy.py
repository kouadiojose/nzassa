"""Aides d'accès aux données avec isolation multi-tenant systématique."""

import uuid
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from nzassa.core.errors import NotFoundError
from nzassa.models.base import Base


def tenant_query[M: Base](
    model: type[M], tenant_id: uuid.UUID, *, include_deleted: bool = False
) -> Select[Any]:
    """SELECT filtré par tenant (et non supprimé logiquement si applicable)."""
    query = select(model).where(model.tenant_id == tenant_id)  # type: ignore[attr-defined]
    if not include_deleted and hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))  # type: ignore[attr-defined]
    return query


async def get_tenant_entity[M: Base](
    db: AsyncSession,
    model: type[M],
    entity_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> M:
    """Charge une entité en vérifiant son appartenance au tenant.

    Une entité d'un autre tenant renvoie NOT_FOUND (jamais 403 : on ne révèle
    pas l'existence de données d'autres entreprises).
    """
    query = tenant_query(model, tenant_id, include_deleted=include_deleted).where(
        model.id == entity_id  # type: ignore[attr-defined]
    )
    entity = (await db.execute(query)).scalar_one_or_none()
    if entity is None:
        raise NotFoundError()
    return entity  # type: ignore[no-any-return]
