"""Dépendances FastAPI : utilisateur courant, tenant, permissions.

L'isolation multi-tenant est appliquée ici : `CurrentContext.tenant_id`
provient du token vérifié, jamais d'un paramètre client. Tous les services
DOIVENT filtrer leurs requêtes par ce tenant_id.
"""

import uuid
from dataclasses import dataclass, field
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nzassa.core.database import get_db
from nzassa.core.errors import (
    AccountDisabledError,
    PermissionDeniedError,
    TokenError,
)
from nzassa.core.logging import tenant_id_var
from nzassa.core.security import decode_access_token
from nzassa.models.auth import Permission, RolePermission, User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class CurrentContext:
    """Contexte d'exécution d'une requête authentifiée."""

    user: User
    tenant_id: uuid.UUID | None
    session_id: uuid.UUID
    is_superadmin: bool
    permissions: set[str] = field(default_factory=set)

    def require_tenant(self) -> uuid.UUID:
        if self.tenant_id is None:
            raise PermissionDeniedError("Cette opération nécessite un contexte entreprise")
        return self.tenant_id

    def has(self, permission: str) -> bool:
        return self.is_superadmin or "*" in self.permissions or permission in self.permissions


async def _load_permissions(db: AsyncSession, user_id: uuid.UUID) -> set[str]:
    rows = await db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user_id)
    )
    return {code for (code,) in rows.all()}


async def get_current_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CurrentContext:
    if credentials is None:
        raise TokenError("Authentification requise")
    payload = decode_access_token(credentials.credentials)
    user = await db.get(User, uuid.UUID(payload["sub"]))
    if user is None or user.deleted_at is not None:
        raise TokenError()
    if not user.is_active:
        raise AccountDisabledError()

    tenant_id = uuid.UUID(payload["tid"]) if payload.get("tid") else None
    # Défense en profondeur : le tenant du token doit correspondre à celui de l'utilisateur
    if user.tenant_id is not None and tenant_id != user.tenant_id:
        raise TokenError()
    if tenant_id:
        tenant_id_var.set(str(tenant_id))

    permissions = await _load_permissions(db, user.id)
    return CurrentContext(
        user=user,
        tenant_id=tenant_id,
        session_id=uuid.UUID(payload["sid"]),
        is_superadmin=bool(payload.get("sa")) and user.is_superadmin,
        permissions=permissions,
    )


Ctx = Annotated[CurrentContext, Depends(get_current_context)]
Db = Annotated[AsyncSession, Depends(get_db)]


def require_permissions(*required: str) -> Any:
    """Guard de permissions : `dependencies=[require_permissions("sales.create")]`."""

    async def checker(ctx: Ctx) -> CurrentContext:
        for perm in required:
            if not ctx.has(perm):
                raise PermissionDeniedError(details={"missing_permission": perm})
        return ctx

    return Depends(checker)


def require_superadmin() -> Any:
    async def checker(ctx: Ctx) -> CurrentContext:
        if not ctx.is_superadmin:
            raise PermissionDeniedError("Réservé au Super Admin")
        return ctx

    return Depends(checker)
