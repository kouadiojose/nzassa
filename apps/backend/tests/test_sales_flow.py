"""Tests du parcours de vente complet : caisse, stock, paiements, crédit, annulation."""

from typing import Any

import pytest
from httpx import AsyncClient

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
    """Tenant avec produit en stock, client et caisse ouverte."""
    owner = await register_and_login(client, email="shop@nzassa.ci", business_name="Boutique Test")
    headers = owner["headers"]
    branch = await get_main_branch(client, headers)
    product = await create_product(client, headers)
    await stock_in(client, headers, branch["id"], product["id"], "10")
    customer = await create_customer(client, headers)
    session = await open_cash_session(client, headers)
    return {
        "headers": headers,
        "branch": branch,
        "product": product,
        "customer": customer,
        "session": session,
    }


async def test_full_sale_cash(client: AsyncClient, shop: dict[str, Any]) -> None:
    resp = await client.post(
        "/sales",
        json={
            "branch_id": shop["branch"]["id"],
            "customer_id": shop["customer"]["id"],
            "items": [
                {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "3"}
            ],
            "payments": [{"method": "cash", "amount": "75000"}],
        },
        headers=shop["headers"],
    )
    assert resp.status_code == 201, resp.text
    sale = resp.json()["data"]
    assert sale["status"] == "completed"
    assert sale["total"] == "75000.00"
    assert sale["amount_paid"] == "75000.00"
    assert sale["amount_due"] == "0.00"
    assert sale["number"].startswith("V-")

    # Stock déduit : 10 - 3 = 7
    levels = (
        await client.get(
            "/stock/levels",
            params={"branch_id": shop["branch"]["id"]},
            headers=shop["headers"],
        )
    ).json()["data"]
    assert levels[0]["quantity"] == "7.000"

    # La caisse contient le fond initial + la vente
    session = (
        await client.get(f"/cash/sessions/{shop['session']['id']}", headers=shop["headers"])
    ).json()["data"]
    assert session["current_cash"] == "85000.00"  # 10 000 + 75 000


async def test_partial_payment_creates_debt_then_settles(
    client: AsyncClient, shop: dict[str, Any]
) -> None:
    # Vente de 50 000 payée 30 000 par Wave -> dette 20 000
    resp = await client.post(
        "/sales",
        json={
            "branch_id": shop["branch"]["id"],
            "customer_id": shop["customer"]["id"],
            "items": [
                {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "2"}
            ],
            "payments": [{"method": "wave", "amount": "30000"}],
        },
        headers=shop["headers"],
    )
    assert resp.status_code == 201, resp.text
    sale = resp.json()["data"]
    assert sale["amount_due"] == "20000.00"

    debts = (await client.get("/debts", headers=shop["headers"])).json()["data"]
    assert len(debts) == 1
    debt = debts[0]
    assert debt["balance"] == "20000.00"
    assert debt["status"] == "open"

    # Règlement partiel 10 000
    resp = await client.post(
        f"/debts/{debt['id']}/payments",
        json={"amount": "10000", "method": "orange_money"},
        headers=shop["headers"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["balance"] == "10000.00"
    assert resp.json()["data"]["status"] == "partially_paid"

    # Solde final
    resp = await client.post(
        f"/debts/{debt['id']}/payments",
        json={"amount": "10000", "method": "cash"},
        headers=shop["headers"],
    )
    assert resp.json()["data"]["status"] == "paid"

    sale_after = (await client.get(f"/sales/{sale['id']}", headers=shop["headers"])).json()["data"]
    assert sale_after["amount_due"] == "0.00"
    assert sale_after["amount_paid"] == "50000.00"


async def test_credit_sale_without_customer_rejected(
    client: AsyncClient, shop: dict[str, Any]
) -> None:
    resp = await client.post(
        "/sales",
        json={
            "branch_id": shop["branch"]["id"],
            "items": [
                {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "1"}
            ],
            "payments": [],
        },
        headers=shop["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


async def test_insufficient_stock_rejected(client: AsyncClient, shop: dict[str, Any]) -> None:
    resp = await client.post(
        "/sales",
        json={
            "branch_id": shop["branch"]["id"],
            "items": [
                {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "999"}
            ],
            "payments": [{"method": "wave", "amount": "24975000"}],
        },
        headers=shop["headers"],
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INSUFFICIENT_STOCK"


async def test_overpayment_rejected(client: AsyncClient, shop: dict[str, Any]) -> None:
    resp = await client.post(
        "/sales",
        json={
            "branch_id": shop["branch"]["id"],
            "items": [
                {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "1"}
            ],
            "payments": [{"method": "cash", "amount": "30000"}],
        },
        headers=shop["headers"],
    )
    assert resp.status_code == 422


async def test_cancel_sale_restocks_and_records_reason(
    client: AsyncClient, shop: dict[str, Any]
) -> None:
    sale = (
        await client.post(
            "/sales",
            json={
                "branch_id": shop["branch"]["id"],
                "items": [
                    {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "4"}
                ],
                "payments": [{"method": "mtn_money", "amount": "100000"}],
            },
            headers=shop["headers"],
        )
    ).json()["data"]

    resp = await client.post(
        f"/sales/{sale['id']}/cancel",
        json={"reason": "Erreur de saisie du caissier"},
        headers=shop["headers"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "cancelled"

    # Stock réintégré : 10 - 4 + 4 = 10
    levels = (
        await client.get(
            "/stock/levels", params={"branch_id": shop["branch"]["id"]}, headers=shop["headers"]
        )
    ).json()["data"]
    assert levels[0]["quantity"] == "10.000"

    # Le grand livre contient le mouvement de compensation
    movements = (
        await client.get(
            "/stock/movements",
            params={"product_id": shop["product"]["id"]},
            headers=shop["headers"],
        )
    ).json()["data"]
    types = [m["movement_type"] for m in movements]
    assert "return_in" in types
    assert "sale_out" in types


async def test_refund_partial_restock(client: AsyncClient, shop: dict[str, Any]) -> None:
    sale = (
        await client.post(
            "/sales",
            json={
                "branch_id": shop["branch"]["id"],
                "items": [
                    {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "3"}
                ],
                "payments": [{"method": "cash", "amount": "75000"}],
            },
            headers=shop["headers"],
        )
    ).json()["data"]

    resp = await client.post(
        f"/sales/{sale['id']}/refunds",
        json={
            "items": [{"sale_item_id": sale["items"][0]["id"], "quantity": "1"}],
            "method": "cash",
            "reason": "Produit défectueux",
        },
        headers=shop["headers"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["amount"] == "25000.00"
    assert resp.json()["data"]["sale_status"] == "partially_refunded"

    levels = (
        await client.get(
            "/stock/levels", params={"branch_id": shop["branch"]["id"]}, headers=shop["headers"]
        )
    ).json()["data"]
    assert levels[0]["quantity"] == "8.000"  # 10 - 3 + 1


async def test_cash_session_close_computes_difference(
    client: AsyncClient, shop: dict[str, Any]
) -> None:
    await client.post(
        "/sales",
        json={
            "branch_id": shop["branch"]["id"],
            "items": [
                {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "1"}
            ],
            "payments": [{"method": "cash", "amount": "25000"}],
        },
        headers=shop["headers"],
    )
    resp = await client.post(
        f"/cash/sessions/{shop['session']['id']}/close",
        json={"counted_cash": "34000"},  # attendu : 35 000 -> écart -1 000
        headers=shop["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["expected_cash"] == "35000.00"
    assert data["difference"] == "-1000.00"
    assert data["status"] == "closed"


async def test_cash_sale_requires_open_session(client: AsyncClient) -> None:
    owner = await register_and_login(
        client, email="nosession@nzassa.ci", business_name="Sans Caisse"
    )
    headers = owner["headers"]
    branch = await get_main_branch(client, headers)
    product = await create_product(client, headers)
    await stock_in(client, headers, branch["id"], product["id"])
    resp = await client.post(
        "/sales",
        json={
            "branch_id": branch["id"],
            "items": [{"item_type": "product", "product_id": product["id"], "quantity": "1"}],
            "payments": [{"method": "cash", "amount": "25000"}],
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "CASH_SESSION_REQUIRED"


async def test_offline_idempotency_same_client_reference(
    client: AsyncClient, shop: dict[str, Any]
) -> None:
    payload = {
        "branch_id": shop["branch"]["id"],
        "items": [{"item_type": "product", "product_id": shop["product"]["id"], "quantity": "1"}],
        "payments": [{"method": "wave", "amount": "25000"}],
        "client_reference": "11111111-2222-3333-4444-555555555555",
    }
    first = await client.post("/sales", json=payload, headers=shop["headers"])
    second = await client.post("/sales", json=payload, headers=shop["headers"])
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["id"] == second.json()["data"]["id"]

    # Le stock n'a été déduit qu'une seule fois
    levels = (
        await client.get(
            "/stock/levels", params={"branch_id": shop["branch"]["id"]}, headers=shop["headers"]
        )
    ).json()["data"]
    assert levels[0]["quantity"] == "9.000"


async def test_expense_flow_with_cash(client: AsyncClient, shop: dict[str, Any]) -> None:
    resp = await client.post(
        "/expenses",
        json={
            "branch_id": shop["branch"]["id"],
            "label": "Achat de fournitures",
            "amount": "5000",
            "expense_date": "2026-07-30",
            "payment_method": "cash",
        },
        headers=shop["headers"],
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["status"] == "approved"

    # La caisse reflète la sortie : 10 000 - 5 000
    session = (
        await client.get(f"/cash/sessions/{shop['session']['id']}", headers=shop["headers"])
    ).json()["data"]
    assert session["current_cash"] == "5000.00"


async def test_loyalty_points_awarded(client: AsyncClient, shop: dict[str, Any]) -> None:
    await client.post(
        "/sales",
        json={
            "branch_id": shop["branch"]["id"],
            "customer_id": shop["customer"]["id"],
            "items": [
                {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "3"}
            ],
            "payments": [{"method": "cash", "amount": "75000"}],
        },
        headers=shop["headers"],
    )
    customer = (
        await client.get(f"/customers/{shop['customer']['id']}", headers=shop["headers"])
    ).json()["data"]
    assert customer["stats"]["loyalty_points"] == 75  # 75 000 / 1 000
