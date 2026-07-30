"""Tests assistant IA, Super Admin et facturation."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from tests.conftest import register_and_login
from tests.helpers import (
    create_customer,
    create_product,
    get_main_branch,
    open_cash_session,
    stock_in,
)


@pytest.fixture
async def shop(client: AsyncClient) -> dict[str, Any]:
    owner = await register_and_login(client, email="ai@nzassa.ci", business_name="AI Shop")
    headers = owner["headers"]
    branch = await get_main_branch(client, headers)
    product = await create_product(client, headers)  # Parfum Clarins 50ml à 25 000
    await stock_in(client, headers, branch["id"], product["id"], "10")
    customer = await create_customer(client, headers)
    return {"headers": headers, "branch": branch, "product": product, "customer": customer}


async def test_assistant_parses_sale_and_requires_confirmation(
    client: AsyncClient, shop: dict[str, Any]
) -> None:
    resp = await client.post(
        "/assistant/command",
        json={
            "text": (
                "J'ai vendu trois parfums Clarins à 25 000 FCFA chacun. "
                "Le client a payé 50 000 FCFA par Wave."
            ),
            "branch_id": shop["branch"]["id"],
            "customer_id": shop["customer"]["id"],
        },
        headers=shop["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["requires_confirmation"] is True
    assert data["action_type"] == "create_sale"
    sale = data["sale"]
    assert sale["items"][0]["quantity"] == "3"
    assert sale["items"][0]["unit_price"] == "25000"
    assert sale["payments"] == [{"method": "wave", "amount": "50000"}]

    # AUCUNE vente n'existe avant confirmation
    sales = (await client.get("/sales", headers=shop["headers"])).json()["meta"]["total"]
    assert sales == 0

    # Confirmation explicite -> la vente est créée avec dette de 25 000
    confirm = await client.post(
        f"/assistant/proposals/{data['proposal_id']}/confirm", headers=shop["headers"]
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["data"]["total"] == "75000.00"

    debts = (await client.get("/debts", headers=shop["headers"])).json()["data"]
    assert debts[0]["balance"] == "25000.00"

    # Une proposition confirmée ne peut pas être rejouée
    again = await client.post(
        f"/assistant/proposals/{data['proposal_id']}/confirm", headers=shop["headers"]
    )
    assert again.status_code == 422


async def test_assistant_reject_proposal(client: AsyncClient, shop: dict[str, Any]) -> None:
    resp = await client.post(
        "/assistant/command",
        json={"text": "2 parfums clarins à 25000", "branch_id": shop["branch"]["id"]},
        headers=shop["headers"],
    )
    assert resp.status_code == 200, resp.text
    proposal_id = resp.json()["data"]["proposal_id"]
    reject = await client.post(
        f"/assistant/proposals/{proposal_id}/reject", headers=shop["headers"]
    )
    assert reject.status_code == 200
    confirm = await client.post(
        f"/assistant/proposals/{proposal_id}/confirm", headers=shop["headers"]
    )
    assert confirm.status_code == 422


async def test_assistant_answers_question(client: AsyncClient, shop: dict[str, Any]) -> None:
    resp = await client.post(
        "/assistant/ask",
        json={"question": "Comment va mon activité ?"},
        headers=shop["headers"],
    )
    assert resp.status_code == 200
    assert "Chiffre d'affaires" in resp.json()["data"]["answer"]


async def _superadmin_headers(client: AsyncClient) -> dict[str, str]:
    from nzassa.core.database import get_session_factory
    from nzassa.core.security import hash_password
    from nzassa.models.auth import User

    async with get_session_factory()() as db:
        db.add(
            User(
                email="root@nzassa.app",
                password_hash=hash_password("Root#2026Secure"),
                first_name="Root",
                last_name="Admin",
                is_superadmin=True,
            )
        )
        await db.commit()
    login = await client.post(
        "/auth/login", json={"email": "root@nzassa.app", "password": "Root#2026Secure"}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['data']['tokens']['access_token']}"}


async def test_superadmin_space_isolated_and_functional(
    client: AsyncClient, shop: dict[str, Any]
) -> None:
    # Un propriétaire d'entreprise n'accède PAS au super admin
    denied = await client.get("/superadmin/dashboard", headers=shop["headers"])
    assert denied.status_code == 403

    sa_headers = await _superadmin_headers(client)
    dashboard = (await client.get("/superadmin/dashboard", headers=sa_headers)).json()["data"]
    assert dashboard["tenants_total"] >= 1

    tenants = (await client.get("/superadmin/tenants", headers=sa_headers)).json()["data"]
    tenant_id = tenants[0]["id"]

    detail = (await client.get(f"/superadmin/tenants/{tenant_id}", headers=sa_headers)).json()[
        "data"
    ]
    assert detail["subscription"]["plan"] == "essential"

    # Suspension / réactivation
    suspend = await client.post(
        f"/superadmin/tenants/{tenant_id}/suspend",
        json={"reason": "Impayé"},
        headers=sa_headers,
    )
    assert suspend.status_code == 200
    activate = await client.post(f"/superadmin/tenants/{tenant_id}/activate", headers=sa_headers)
    assert activate.status_code == 200

    # Feature flags
    flag = await client.put(
        "/superadmin/feature-flags",
        json={"code": "online_booking", "is_enabled": True},
        headers=sa_headers,
    )
    assert flag.status_code == 200
    flags = (await client.get("/superadmin/feature-flags", headers=sa_headers)).json()["data"]
    assert flags[0]["code"] == "online_booking"

    # Journaux d'audit
    logs = (await client.get("/superadmin/audit-logs", headers=sa_headers)).json()["data"]
    assert any(log["action"] == "superadmin.tenant_suspend" for log in logs)


async def test_invoice_from_sale_and_credit_note(client: AsyncClient, shop: dict[str, Any]) -> None:
    await open_cash_session(client, shop["headers"])
    sale = (
        await client.post(
            "/sales",
            json={
                "branch_id": shop["branch"]["id"],
                "customer_id": shop["customer"]["id"],
                "items": [
                    {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "2"}
                ],
                "payments": [{"method": "cash", "amount": "50000"}],
            },
            headers=shop["headers"],
        )
    ).json()["data"]

    invoice = await client.post(f"/invoices/from-sale/{sale['id']}", headers=shop["headers"])
    assert invoice.status_code == 201, invoice.text
    inv = invoice.json()["data"]
    assert inv["number"].startswith("FAC-")
    assert inv["total"] == "50000.00"
    assert inv["fiscal_status"] == "not_submitted"

    # Double facturation interdite
    dup = await client.post(f"/invoices/from-sale/{sale['id']}", headers=shop["headers"])
    assert dup.status_code == 409

    # Soumission fiscale (connecteur SIMULÉ en test/dev)
    fiscal = await client.post(f"/invoices/{inv['id']}/submit-fiscal", headers=shop["headers"])
    assert fiscal.status_code == 200
    assert fiscal.json()["data"]["connector"] == "simulated-dev"
    assert fiscal.json()["data"]["fiscal_reference"].startswith("SIM-FNE-")

    # Avoir partiel
    note = await client.post(
        f"/invoices/{inv['id']}/credit-notes",
        json={"amount": "10000", "reason": "Geste commercial"},
        headers=shop["headers"],
    )
    assert note.status_code == 201
    assert note.json()["data"]["number"].startswith("AV-")


async def test_demo_seed_runs(client: AsyncClient) -> None:
    """Le seeder de démonstration s'exécute et crée les données attendues."""
    from nzassa.seeds.demo import DEMO_OWNER_EMAIL, DEMO_PASSWORD, seed

    await seed()
    login = await client.post(
        "/auth/login", json={"email": DEMO_OWNER_EMAIL, "password": DEMO_PASSWORD}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['data']['tokens']['access_token']}"}

    products = (await client.get("/catalog/products", headers=headers)).json()["meta"]["total"]
    assert products == 5
    branches = (await client.get("/business/branches", headers=headers)).json()["data"]
    assert len(branches) == 2
    levels = (await client.get("/stock/levels", headers=headers)).json()["data"]
    assert all(lvl["quantity"] == "50.000" for lvl in levels)

    # Idempotence
    await seed()


_ = update  # évite import inutilisé si le test évolue
