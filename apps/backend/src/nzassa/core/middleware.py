"""Middlewares : correlation ID, headers de sécurité, rate limiting Redis."""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from nzassa.core.config import get_settings
from nzassa.core.errors import RateLimitedError
from nzassa.core.logging import correlation_id_var, get_logger
from nzassa.core.redis import get_redis

logger = get_logger(__name__)

CallNext = Callable[[Request], Awaitable[Response]]


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
        correlation_id_var.set(correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cache-Control", "no-store")
        return response


async def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> None:
    """Compteur glissant simple par fenêtre fixe dans Redis."""
    redis = get_redis()
    try:
        current = await redis.incr(f"rl:{key}")
        if current == 1:
            await redis.expire(f"rl:{key}", window_seconds)
        if current > limit:
            raise RateLimitedError()
    except RateLimitedError:
        raise
    except Exception:
        logger.warning("rate_limit_backend_unavailable", key=key)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        settings = get_settings()
        if request.url.path.startswith(settings.api_v1_prefix):
            client_ip = request.client.host if request.client else "unknown"
            is_auth = "/auth/" in request.url.path
            limit = (
                settings.auth_rate_limit_per_minute if is_auth else settings.rate_limit_per_minute
            )
            scope = "auth" if is_auth else "api"
            try:
                await check_rate_limit(f"{scope}:{client_ip}", limit)
            except RateLimitedError:
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "message": "Trop de requêtes, veuillez réessayer plus tard",
                        "error": {"code": "RATE_LIMITED", "details": {}},
                    },
                )
        return await call_next(request)
