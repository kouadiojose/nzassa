"""Endpoints entreprise, points de vente et paramètres."""

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import ConflictError, NotFoundError
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.business import Branch, Business, BusinessSetting
from nzassa.modules.businesses.schemas import (
    BranchCreate,
    BranchOut,
    BranchUpdate,
    BusinessOut,
    BusinessUpdate,
    SettingUpsert,
)

router = APIRouter(prefix="/business", tags=["business"])


async def get_current_business(db: Db, ctx: Ctx) -> Business:
    tenant_id = ctx.require_tenant()
    business = (await db.execute(tenant_query(Business, tenant_id).limit(1))).scalars().first()
    if business is None:
        raise NotFoundError("Entreprise introuvable")
    return business  # type: ignore[no-any-return]


@router.get("", dependencies=[require_permissions("business.read")])
async def get_business(db: Db, ctx: Ctx) -> dict[str, Any]:
    business = await get_current_business(db, ctx)
    return ok(BusinessOut.model_validate(business).model_dump(mode="json"))


@router.patch("", dependencies=[require_permissions("business.update")])
async def update_business(payload: BusinessUpdate, db: Db, ctx: Ctx) -> dict[str, Any]:
    business = await get_current_business(db, ctx)
    changes = payload.model_dump(exclude_unset=True)
    before = {k: str(getattr(business, k)) for k in changes}
    for key, value in changes.items():
        setattr(business, key, value)
    business.updated_by = ctx.user.id
    await record_audit(
        db,
        action="business.update",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        entity_type="business",
        entity_id=business.id,
        before=before,
        after={k: str(v) for k, v in changes.items()},
    )
    return ok(BusinessOut.model_validate(business).model_dump(mode="json"))


@router.get("/branches", dependencies=[require_permissions("business.read")])
async def list_branches(db: Db, ctx: Ctx) -> dict[str, Any]:
    branches = (
        (await db.execute(tenant_query(Branch, ctx.require_tenant()).order_by(Branch.created_at)))
        .scalars()
        .all()
    )
    return ok([BranchOut.model_validate(b).model_dump(mode="json") for b in branches])


@router.post(
    "/branches", status_code=201, dependencies=[require_permissions("business.manage_branches")]
)
async def create_branch(payload: BranchCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    business = await get_current_business(db, ctx)
    duplicate = (
        await db.execute(tenant_query(Branch, tenant_id).where(Branch.code == payload.code.upper()))
    ).first()
    if duplicate:
        raise ConflictError("Un point de vente avec ce code existe déjà")
    from nzassa.modules.subscriptions.service import enforce_limit

    await enforce_limit(db, tenant_id, "max_branches")
    branch = Branch(
        tenant_id=tenant_id,
        business_id=business.id,
        created_by=ctx.user.id,
        **{**payload.model_dump(), "code": payload.code.upper()},
    )
    db.add(branch)
    await db.flush()
    await record_audit(
        db,
        action="branch.create",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="branch",
        entity_id=branch.id,
    )
    return ok(
        BranchOut.model_validate(branch).model_dump(mode="json"), message="Point de vente créé"
    )


@router.patch(
    "/branches/{branch_id}", dependencies=[require_permissions("business.manage_branches")]
)
async def update_branch(
    branch_id: uuid.UUID, payload: BranchUpdate, db: Db, ctx: Ctx
) -> dict[str, Any]:
    branch = await get_tenant_entity(db, Branch, branch_id, ctx.require_tenant())
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(branch, key, value)
    branch.updated_by = ctx.user.id
    await record_audit(
        db,
        action="branch.update",
        tenant_id=ctx.tenant_id,
        user_id=ctx.user.id,
        entity_type="branch",
        entity_id=branch.id,
    )
    return ok(BranchOut.model_validate(branch).model_dump(mode="json"))


@router.get("/settings", dependencies=[require_permissions("settings.read")])
async def list_settings(db: Db, ctx: Ctx) -> dict[str, Any]:
    settings_rows = (
        (await db.execute(tenant_query(BusinessSetting, ctx.require_tenant()))).scalars().all()
    )
    return ok({s.key: s.value for s in settings_rows})


@router.put("/settings", dependencies=[require_permissions("settings.update")])
async def upsert_setting(payload: SettingUpsert, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    business = await get_current_business(db, ctx)
    existing = (
        await db.execute(
            select(BusinessSetting).where(
                BusinessSetting.tenant_id == tenant_id, BusinessSetting.key == payload.key
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            BusinessSetting(
                tenant_id=tenant_id,
                business_id=business.id,
                key=payload.key,
                value=payload.value,
                created_by=ctx.user.id,
            )
        )
    else:
        existing.value = payload.value
        existing.updated_by = ctx.user.id
    await record_audit(
        db,
        action="settings.update",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        after={"key": payload.key},
    )
    return ok(message="Paramètre enregistré")
