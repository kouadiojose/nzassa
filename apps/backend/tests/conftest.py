"""Fixtures de test — base PostgreSQL réelle, Redis réel, broker Dramatiq stub."""

import os

os.environ.setdefault("NZASSA_ENV", "test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/9")
os.environ.setdefault("AUTH_RATE_LIMIT_PER_MINUTE", "100000")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from nzassa.core.database import get_engine, get_session_factory
from nzassa.core.redis import get_redis
from nzassa.main import app
from nzassa.models import Base


@pytest.fixture(scope="session", autouse=True)
async def _setup_database() -> AsyncIterator[None]:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_state() -> AsyncIterator[None]:
    yield
    # Nettoyage après chaque test : TRUNCATE de toutes les tables + flush Redis
    engine = get_engine()
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    await get_redis().flushdb()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c


@pytest.fixture
async def db() -> AsyncIterator[Any]:
    async with get_session_factory()() as session:
        yield session
        await session.commit()


REGISTER_PAYLOAD = {
    "business_name": "Institut Belle Afrique",
    "industry": "beauty",
    "first_name": "Awa",
    "last_name": "Koné",
    "email": "awa@belleafrique.ci",
    "phone": "+2250701020304",
    "password": "MotDePasse#2026",
}


async def register_and_login(
    client: AsyncClient, *, email: str = REGISTER_PAYLOAD["email"], business_name: str | None = None
) -> dict[str, Any]:
    """Crée un tenant et retourne {token, tenant_id, user, headers}."""
    payload = {**REGISTER_PAYLOAD, "email": email}
    if business_name:
        payload["business_name"] = business_name
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    token = data["tokens"]["access_token"]
    return {
        "tenant_id": data["tenant_id"],
        "user": data["user"],
        "tokens": data["tokens"],
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
async def owner(client: AsyncClient) -> dict[str, Any]:
    return await register_and_login(client)
