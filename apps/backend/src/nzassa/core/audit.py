"""Journal d'audit append-only."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nzassa.core.logging import correlation_id_var
from nzassa.models.system import AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_address: str | None = None,
    **extra: Any,
) -> None:
    db.add(
        AuditLog(
            action=action,
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            ip_address=ip_address,
            correlation_id=correlation_id_var.get(),
            extra=extra,
        )
    )
