"""Catalogue des permissions et rôles système.

`sync_rbac` est idempotent : il crée/complète les permissions et rôles
système partagés (tenant_id NULL).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nzassa.models.auth import Permission, Role, RolePermission

# module -> actions
PERMISSION_CATALOG: dict[str, list[str]] = {
    "business": ["read", "update", "manage_branches"],
    "users": ["read", "invite", "update", "manage_roles"],
    "employees": ["read", "create", "update"],
    "products": ["read", "create", "update", "archive", "import", "export"],
    "stock": ["read", "in", "out", "adjust", "transfer", "inventory"],
    "suppliers": ["read", "create", "update", "order", "receive", "pay"],
    "customers": ["read", "create", "update", "export"],
    "sales": ["read", "create", "cancel", "refund"],
    "cash": ["read", "open", "close", "movement"],
    "debts": ["read", "collect", "write_off"],
    "expenses": ["read", "create", "approve", "cancel"],
    "appointments": ["read", "create", "update", "cancel"],
    "commissions": ["read", "manage_rules", "validate", "pay"],
    "loyalty": ["read", "manage"],
    "promotions": ["read", "manage"],
    "reports": ["read", "export"],
    "settings": ["read", "update"],
    "subscription": ["read", "manage"],
    "invoices": ["read", "create", "cancel"],
    "audit": ["read"],
    "assistant": ["use"],
}

# Rôles système initiaux -> permissions (le propriétaire a tout via "*")
SYSTEM_ROLES: dict[str, tuple[str, list[str]]] = {
    "owner": ("Propriétaire", ["*"]),
    "admin": ("Administrateur", ["*"]),
    "manager": (
        "Gérant",
        [
            "business.read",
            "users.read",
            "employees.*",
            "products.*",
            "stock.*",
            "suppliers.*",
            "customers.*",
            "sales.*",
            "cash.*",
            "debts.*",
            "expenses.*",
            "appointments.*",
            "commissions.read",
            "commissions.validate",
            "loyalty.*",
            "promotions.*",
            "reports.*",
            "settings.read",
            "invoices.*",
            "assistant.use",
        ],
    ),
    "cashier": (
        "Caissier",
        [
            "products.read",
            "customers.read",
            "customers.create",
            "sales.read",
            "sales.create",
            "cash.*",
            "debts.read",
            "debts.collect",
            "expenses.read",
            "expenses.create",
            "assistant.use",
        ],
    ),
    "seller": (
        "Vendeur",
        [
            "products.read",
            "customers.read",
            "customers.create",
            "sales.read",
            "sales.create",
            "appointments.read",
            "appointments.create",
            "assistant.use",
        ],
    ),
    "employee": (
        "Employé",
        ["products.read", "customers.read", "appointments.read", "commissions.read"],
    ),
    "accountant": (
        "Comptable",
        [
            "sales.read",
            "expenses.read",
            "expenses.approve",
            "debts.read",
            "suppliers.read",
            "reports.*",
            "invoices.read",
            "cash.read",
            "audit.read",
        ],
    ),
    "viewer": ("Lecteur", ["business.read", "products.read", "sales.read", "reports.read"]),
}


def _expand(patterns: list[str]) -> set[str]:
    """Résout les motifs `module.*` vers les permissions concrètes."""
    result: set[str] = set()
    for pattern in patterns:
        if pattern == "*":
            result.add("*")
            continue
        module, action = pattern.split(".", 1)
        if action == "*":
            result.update(f"{module}.{a}" for a in PERMISSION_CATALOG.get(module, []))
        else:
            result.add(pattern)
    return result


async def sync_rbac(db: AsyncSession) -> None:
    """Crée les permissions et rôles système manquants (idempotent)."""
    existing = {
        code: pid for pid, code in (await db.execute(select(Permission.id, Permission.code))).all()
    }
    for module, actions in PERMISSION_CATALOG.items():
        for action in actions:
            code = f"{module}.{action}"
            if code not in existing:
                perm = Permission(id=uuid.uuid4(), code=code, name=code, module=module)
                db.add(perm)
                existing[code] = perm.id
    # Permission spéciale "*" (accès complet)
    if "*" not in existing:
        star = Permission(id=uuid.uuid4(), code="*", name="Accès complet", module="system")
        db.add(star)
        existing["*"] = star.id
    await db.flush()

    role_rows = (
        await db.execute(select(Role).where(Role.is_system.is_(True), Role.tenant_id.is_(None)))
    ).scalars()
    roles_by_code = {r.code: r for r in role_rows}
    for code, (name, patterns) in SYSTEM_ROLES.items():
        role = roles_by_code.get(code)
        if role is None:
            role = Role(code=code, name=name, is_system=True, tenant_id=None)
            db.add(role)
            await db.flush()
            roles_by_code[code] = role
        wanted = _expand(patterns)
        current = {
            perm_code
            for (perm_code,) in (
                await db.execute(
                    select(Permission.code)
                    .join(RolePermission, RolePermission.permission_id == Permission.id)
                    .where(RolePermission.role_id == role.id)
                )
            ).all()
        }
        for perm_code in wanted - current:
            db.add(RolePermission(role_id=role.id, permission_id=existing[perm_code]))
    await db.flush()


async def get_system_role(db: AsyncSession, code: str) -> Role:
    role = (
        await db.execute(
            select(Role).where(
                Role.code == code, Role.is_system.is_(True), Role.tenant_id.is_(None)
            )
        )
    ).scalar_one_or_none()
    if role is None:
        await sync_rbac(db)
        role = (
            await db.execute(
                select(Role).where(
                    Role.code == code, Role.is_system.is_(True), Role.tenant_id.is_(None)
                )
            )
        ).scalar_one()
    return role


def role_id_of(role: Role) -> uuid.UUID:
    return role.id
