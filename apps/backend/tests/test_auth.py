"""Tests d'authentification et de sécurité."""

from typing import Any

from httpx import AsyncClient

from tests.conftest import REGISTER_PAYLOAD, register_and_login


async def test_register_creates_tenant_and_owner(client: AsyncClient) -> None:
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["tenant_id"]
    assert data["user"]["email"] == REGISTER_PAYLOAD["email"]
    assert data["tokens"]["access_token"]
    assert data["tokens"]["refresh_token"]


async def test_register_duplicate_email_rejected(client: AsyncClient) -> None:
    await client.post("/auth/register", json=REGISTER_PAYLOAD)
    resp = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


async def test_login_success_and_me(client: AsyncClient, owner: dict[str, Any]) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "*" in data["permissions"]  # propriétaire = accès complet

    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {data['tokens']['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["data"]["user"]["email"] == REGISTER_PAYLOAD["email"]


async def test_login_wrong_password(client: AsyncClient, owner: dict[str, Any]) -> None:
    resp = await client.post(
        "/auth/login", json={"email": REGISTER_PAYLOAD["email"], "password": "Mauvais#123456"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


async def test_account_lockout_after_failed_attempts(
    client: AsyncClient, owner: dict[str, Any]
) -> None:
    for _ in range(5):
        await client.post(
            "/auth/login", json={"email": REGISTER_PAYLOAD["email"], "password": "Mauvais#123456"}
        )
    resp = await client.post(
        "/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
    )
    assert resp.status_code == 423
    assert resp.json()["error"]["code"] == "AUTH_ACCOUNT_LOCKED"


async def test_refresh_rotation_and_reuse_detection(
    client: AsyncClient, owner: dict[str, Any]
) -> None:
    refresh1 = owner["tokens"]["refresh_token"]
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh1})
    assert resp.status_code == 200
    refresh2 = resp.json()["data"]["refresh_token"]
    assert refresh2 != refresh1

    # Réutilisation du token consommé -> révocation de la session entière
    reuse = await client.post("/auth/refresh", json={"refresh_token": refresh1})
    assert reuse.status_code == 401

    # Le token 2 (de la même session révoquée) est également invalide
    after = await client.post("/auth/refresh", json={"refresh_token": refresh2})
    assert after.status_code == 401


async def test_logout_revokes_refresh(client: AsyncClient, owner: dict[str, Any]) -> None:
    resp = await client.post(
        "/auth/logout",
        json={"refresh_token": owner["tokens"]["refresh_token"]},
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    reuse = await client.post(
        "/auth/refresh", json={"refresh_token": owner["tokens"]["refresh_token"]}
    )
    assert reuse.status_code == 401


async def test_protected_route_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_change_password(client: AsyncClient, owner: dict[str, Any]) -> None:
    resp = await client.post(
        "/auth/change-password",
        json={
            "current_password": REGISTER_PAYLOAD["password"],
            "new_password": "NouveauPass#2026",
        },
        headers=owner["headers"],
    )
    assert resp.status_code == 200
    relogin = await client.post(
        "/auth/login", json={"email": REGISTER_PAYLOAD["email"], "password": "NouveauPass#2026"}
    )
    assert relogin.status_code == 200


async def test_sessions_listing_and_revocation(client: AsyncClient, owner: dict[str, Any]) -> None:
    resp = await client.get("/auth/sessions", headers=owner["headers"])
    assert resp.status_code == 200
    sessions = resp.json()["data"]
    assert len(sessions) >= 1


async def test_two_tenants_same_email_forbidden_globally(client: AsyncClient) -> None:
    await register_and_login(client)
    resp = await client.post(
        "/auth/register", json={**REGISTER_PAYLOAD, "business_name": "Autre Boutique"}
    )
    assert resp.status_code == 409
