"""Logs structurés (structlog) avec correlation ID."""

import logging
import sys
from contextvars import ContextVar

import structlog

from nzassa.core.config import get_settings

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="-")


def _add_context(
    logger: object, method_name: str, event_dict: structlog.typing.EventDict
) -> structlog.typing.EventDict:
    event_dict["correlation_id"] = correlation_id_var.get()
    tenant = tenant_id_var.get()
    if tenant != "-":
        event_dict["tenant_id"] = tenant
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )
    renderer: structlog.typing.Processor
    if settings.is_production:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
