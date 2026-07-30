"""Endpoints notifications : liste, lecture, préférences."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, update

from nzassa.core.deps import Ctx, Db
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.models.notifications import Notification, NotificationPreference

router = APIRouter(prefix="/notifications", tags=["notifications"])

Page = Annotated[PageParams, Depends(page_params)]


class PreferenceUpsert(BaseModel):
    notification_type: str
    internal_enabled: bool = True
    push_enabled: bool = True
    email_enabled: bool = False


@router.get("")
async def list_notifications(
    db: Db, ctx: Ctx, params: Page, unread_only: bool = False
) -> dict[str, Any]:
    query = select(Notification).where(
        Notification.user_id == ctx.user.id, Notification.channel == "internal"
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    items, meta = await paginate(db, query, params, default_sort=Notification.created_at)
    return ok(
        [
            {
                "id": str(n.id),
                "type": n.notification_type,
                "title": n.title,
                "body": n.body,
                "data": n.data,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
            }
            for n in items
        ],
        **meta,
    )


@router.post("/{notification_id}/read")
async def mark_read(notification_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == ctx.user.id)
        .values(read_at=datetime.now(UTC))
    )
    return ok(message="Notification lue")


@router.post("/read-all")
async def mark_all_read(db: Db, ctx: Ctx) -> dict[str, Any]:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == ctx.user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    return ok(message="Toutes les notifications sont lues")


@router.get("/preferences")
async def list_preferences(db: Db, ctx: Ctx) -> dict[str, Any]:
    prefs = (
        (
            await db.execute(
                select(NotificationPreference).where(NotificationPreference.user_id == ctx.user.id)
            )
        )
        .scalars()
        .all()
    )
    return ok(
        [
            {
                "notification_type": p.notification_type,
                "internal_enabled": p.internal_enabled,
                "push_enabled": p.push_enabled,
                "email_enabled": p.email_enabled,
            }
            for p in prefs
        ]
    )


@router.put("/preferences")
async def upsert_preference(payload: PreferenceUpsert, db: Db, ctx: Ctx) -> dict[str, Any]:
    pref = (
        await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == ctx.user.id,
                NotificationPreference.notification_type == payload.notification_type,
            )
        )
    ).scalar_one_or_none()
    if pref is None:
        db.add(
            NotificationPreference(
                tenant_id=ctx.require_tenant(),
                user_id=ctx.user.id,
                **payload.model_dump(),
            )
        )
    else:
        pref.internal_enabled = payload.internal_enabled
        pref.push_enabled = payload.push_enabled
        pref.email_enabled = payload.email_enabled
    return ok(message="Préférence enregistrée")
