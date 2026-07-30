"""Gestion des membres (utilisateurs), employés et rôles du tenant."""

import secrets
import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import delete, select

from nzassa.core.audit import record_audit
from nzassa.core.config import get_settings
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import BusinessRuleError, ConflictError, NotFoundError
from nzassa.core.rbac import get_system_role
from nzassa.core.responses import ok
from nzassa.core.security import hash_password
from nzassa.core.tasks import send_email_task
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.auth import Role, User, UserBranch, UserRole
from nzassa.models.business import Branch, Business, Employee
from nzassa.modules.users.schemas import (
    EmployeeCreate,
    EmployeeOut,
    EmployeeUpdate,
    InviteUserRequest,
    MemberOut,
    UpdateMemberRequest,
)

router = APIRouter(tags=["users"])


async def _roles_of(db: Db, user_id: uuid.UUID) -> list[str]:
    rows = await db.execute(
        select(Role.code)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return sorted(code for (code,) in rows.all())


@router.get("/members", dependencies=[require_permissions("users.read")])
async def list_members(db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    users = (
        (
            await db.execute(
                select(User)
                .where(User.tenant_id == tenant_id, User.deleted_at.is_(None))
                .order_by(User.created_at)
            )
        )
        .scalars()
        .all()
    )
    employees = {
        e.user_id: e
        for e in (await db.execute(tenant_query(Employee, tenant_id))).scalars().all()
        if e.user_id
    }
    result = []
    for user in users:
        member = MemberOut.model_validate(user)
        member.roles = await _roles_of(db, user.id)
        emp = employees.get(user.id)
        if emp:
            member.employee_id = emp.id
            member.job_title = emp.job_title
            member.branch_id = emp.branch_id
        result.append(member.model_dump(mode="json"))
    return ok(result)


@router.post("/members/invite", status_code=201, dependencies=[require_permissions("users.invite")])
async def invite_member(payload: InviteUserRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    email = payload.email.lower()
    existing = (
        await db.execute(select(User.id).where(User.email == email, User.deleted_at.is_(None)))
    ).first()
    if existing:
        raise ConflictError("Un compte existe déjà avec cet email")

    business = (await db.execute(tenant_query(Business, tenant_id).limit(1))).scalars().first()
    if business is None:
        raise NotFoundError("Entreprise introuvable")
    if payload.branch_id is not None:
        await get_tenant_entity(db, Branch, payload.branch_id, tenant_id)

    initial_password = payload.password or secrets.token_urlsafe(10)
    user = User(
        tenant_id=tenant_id,
        email=email,
        phone=payload.phone,
        password_hash=hash_password(initial_password),
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    db.add(user)
    await db.flush()

    role = await get_system_role(db, payload.role_code)
    db.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=tenant_id))

    employee = Employee(
        tenant_id=tenant_id,
        business_id=business.id,
        branch_id=payload.branch_id,
        user_id=user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        email=email,
        job_title=payload.job_title,
        created_by=ctx.user.id,
    )
    db.add(employee)
    if payload.branch_id is not None:
        db.add(
            UserBranch(
                tenant_id=tenant_id, user_id=user.id, branch_id=payload.branch_id, is_default=True
            )
        )

    send_email_task.send(
        email,
        "Invitation à rejoindre N'Zassa Business",
        f"Vous avez été invité à rejoindre {business.trade_name}. "
        "Connectez-vous avec le mot de passe initial fourni par votre administrateur.",
    )
    await record_audit(
        db,
        action="users.invite",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="user",
        entity_id=user.id,
        after={"email": email, "role": payload.role_code},
    )
    data: dict[str, Any] = {"user_id": str(user.id), "employee_id": str(employee.id)}
    # Le mot de passe initial n'est renvoyé qu'en environnement de non-production
    if not get_settings().is_production and payload.password is None:
        data["initial_password"] = initial_password
    return ok(data, message="Invitation créée")


@router.patch("/members/{user_id}", dependencies=[require_permissions("users.update")])
async def update_member(
    user_id: uuid.UUID, payload: UpdateMemberRequest, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    user = (
        await db.execute(
            select(User).where(
                User.id == user_id, User.tenant_id == tenant_id, User.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise NotFoundError()

    changes = payload.model_dump(exclude_unset=True)
    if "is_active" in changes and user.id == ctx.user.id and changes["is_active"] is False:
        raise BusinessRuleError("Impossible de désactiver son propre compte")

    for key in ("first_name", "last_name", "phone", "is_active"):
        if key in changes and changes[key] is not None:
            setattr(user, key, changes[key])

    employee = (
        (await db.execute(tenant_query(Employee, tenant_id).where(Employee.user_id == user.id)))
        .scalars()
        .first()
    )
    if employee is not None:
        for key in ("first_name", "last_name", "phone", "job_title"):
            if key in changes and changes[key] is not None:
                setattr(employee, key, changes[key])
        if "branch_id" in changes:
            if changes["branch_id"] is not None:
                await get_tenant_entity(db, Branch, changes["branch_id"], tenant_id)
            employee.branch_id = changes["branch_id"]

    if changes.get("role_code"):
        current_roles = await _roles_of(db, user.id)
        if "owner" in current_roles:
            raise BusinessRuleError("Le rôle du propriétaire ne peut pas être modifié")
        role = await get_system_role(db, changes["role_code"])
        await db.execute(delete(UserRole).where(UserRole.user_id == user.id))
        db.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=tenant_id))

    await record_audit(
        db,
        action="users.update",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="user",
        entity_id=user.id,
        after=changes and {k: str(v) for k, v in changes.items()},
    )
    member = MemberOut.model_validate(user)
    member.roles = await _roles_of(db, user.id)
    return ok(member.model_dump(mode="json"))


@router.get("/employees", dependencies=[require_permissions("employees.read")])
async def list_employees(db: Db, ctx: Ctx) -> dict[str, Any]:
    employees = (
        (
            await db.execute(
                tenant_query(Employee, ctx.require_tenant()).order_by(Employee.created_at)
            )
        )
        .scalars()
        .all()
    )
    return ok([EmployeeOut.model_validate(e).model_dump(mode="json") for e in employees])


@router.post("/employees", status_code=201, dependencies=[require_permissions("employees.create")])
async def create_employee(payload: EmployeeCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    business = (await db.execute(tenant_query(Business, tenant_id).limit(1))).scalars().first()
    if business is None:
        raise NotFoundError("Entreprise introuvable")
    if payload.branch_id is not None:
        await get_tenant_entity(db, Branch, payload.branch_id, tenant_id)
    employee = Employee(
        tenant_id=tenant_id,
        business_id=business.id,
        created_by=ctx.user.id,
        **payload.model_dump(),
    )
    db.add(employee)
    await db.flush()
    return ok(EmployeeOut.model_validate(employee).model_dump(mode="json"), message="Employé créé")


@router.patch("/employees/{employee_id}", dependencies=[require_permissions("employees.update")])
async def update_employee(
    employee_id: uuid.UUID, payload: EmployeeUpdate, db: Db, ctx: Ctx
) -> dict[str, Any]:
    employee = await get_tenant_entity(db, Employee, employee_id, ctx.require_tenant())
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(employee, key, value)
    employee.updated_by = ctx.user.id
    return ok(EmployeeOut.model_validate(employee).model_dump(mode="json"))
