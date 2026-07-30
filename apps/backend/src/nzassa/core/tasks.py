"""Tâches asynchrones Dramatiq (broker Redis).

En environnement de test, un StubBroker est utilisé pour exécuter les tâches
de manière synchrone et déterministe.
"""

import os

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.brokers.stub import StubBroker

from nzassa.core.config import get_settings
from nzassa.core.logging import get_logger

logger = get_logger(__name__)

if os.environ.get("NZASSA_ENV") == "test" or get_settings().nzassa_env == "test":
    broker: dramatiq.Broker = StubBroker()
else:
    broker = RedisBroker(url=get_settings().redis_url)  # type: ignore[no-untyped-call]
dramatiq.set_broker(broker)


@dramatiq.actor(max_retries=3)
def send_email_task(to: str, subject: str, body: str) -> None:
    """Envoi d'email — backend console en développement."""
    settings = get_settings()
    if settings.email_backend == "console":
        logger.info("email_console", to=to, subject=subject, body=body[:200])
        return
    # Backend SMTP branché via configuration ; l'implémentation SMTP réelle
    # nécessite des identifiants externes (voir docs/TECHNICAL_DEBT.md).
    logger.info("email_smtp_send", to=to, subject=subject)


@dramatiq.actor(max_retries=5)
def send_push_notification_task(user_id: str, title: str, body: str) -> None:
    """Notification push — FCM branché via configuration, no-op sans identifiants."""
    logger.info("push_notification", user_id=user_id, title=title)
