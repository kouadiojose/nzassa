"""Service de notifications multi-canal.

Canaux actuels : interne (in-app), push (FCM via tâche), email.
Interfaces prêtes pour SMS et WhatsApp Business API (voir NotificationChannel).
"""

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nzassa.core.logging import get_logger
from nzassa.core.tasks import send_email_task, send_push_notification_task
from nzassa.models.auth import User
from nzassa.models.notifications import Notification, NotificationPreference

logger = get_logger(__name__)


class NotificationChannel(ABC):
    """Interface de canal — implémenter pour ajouter SMS, WhatsApp, etc."""

    name: str = "abstract"

    @abstractmethod
    async def send(self, notification: Notification, user: User) -> bool: ...


class InternalChannel(NotificationChannel):
    name = "internal"

    async def send(self, notification: Notification, user: User) -> bool:
        return True  # persistée en base = livrée


class PushChannel(NotificationChannel):
    name = "push"

    async def send(self, notification: Notification, user: User) -> bool:
        send_push_notification_task.send(str(user.id), notification.title, notification.body)
        return True


class EmailChannel(NotificationChannel):
    name = "email"

    async def send(self, notification: Notification, user: User) -> bool:
        send_email_task.send(user.email, notification.title, notification.body)
        return True


CHANNELS: dict[str, NotificationChannel] = {
    c.name: c for c in (InternalChannel(), PushChannel(), EmailChannel())
}


async def _channel_enabled(
    db: AsyncSession, user_id: uuid.UUID, notification_type: str, channel: str
) -> bool:
    pref = (
        await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id,
                NotificationPreference.notification_type == notification_type,
            )
        )
    ).scalar_one_or_none()
    if pref is None:
        return channel in ("internal", "push")  # défauts
    return {
        "internal": pref.internal_enabled,
        "push": pref.push_enabled,
        "email": pref.email_enabled,
    }.get(channel, False)


async def notify(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    notification_type: str,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> list[Notification]:
    """Crée et envoie une notification sur tous les canaux activés."""
    user = await db.get(User, user_id)
    if user is None:
        return []
    created: list[Notification] = []
    for channel_name, channel in CHANNELS.items():
        if not await _channel_enabled(db, user_id, notification_type, channel_name):
            continue
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            channel=channel_name,
        )
        db.add(notification)
        try:
            sent = await channel.send(notification, user)
            notification.status = "sent" if sent else "failed"
            notification.sent_at = datetime.now(UTC)
        except Exception:
            logger.exception("notification_channel_failed", channel=channel_name)
            notification.status = "failed"
            notification.retry_count += 1
        created.append(notification)
    return created
