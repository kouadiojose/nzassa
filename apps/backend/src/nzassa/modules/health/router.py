"""Health checks."""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from nzassa import __version__
from nzassa.core.database import get_session_factory
from nzassa.core.redis import get_redis
from nzassa.core.responses import ok

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, Any]:
    return ok({"status": "up", "version": __version__})


@router.get("/health/ready")
async def readiness() -> dict[str, Any]:
    checks: dict[str, str] = {}
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "up"
    except Exception:
        checks["database"] = "down"
    try:
        await get_redis().ping()
        checks["redis"] = "up"
    except Exception:
        checks["redis"] = "down"
    healthy = all(v == "up" for v in checks.values())
    return ok({"status": "ready" if healthy else "degraded", "checks": checks})
