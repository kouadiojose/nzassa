"""Tests des modules P1 : rendez-vous, commissions, achats, abonnements, sync, rapports."""

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
    owner = await register_and_login(client, email="p1@nzassa.ci", business_name="P1 Shop")
    headers = owner["headers"]
    branch = await get_main_branch(client, headers)
    product = await create_product(client, headers)
    await stock_in(client, headers, branch["id"], product["id"], "20")
    customer = await create_customer(client, headers)
    return {"headers": headers, "branch": branch, "product": product, "customer": customer}


async def _create_service(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    resp = await client.post(
        "/catalog/services",
        json={"name": "Coiffure tresses", "price": "10000", "duration_minutes": 60},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _get_employee_id(client: AsyncClient, headers: dict[str, str]) -> str:
    employees = (await client.get("/employees", headers=headers)).json()["data"]
    return employees[0]["id"]


async def test_appointment_lifecycle_and_conflicts(
    client: AsyncClient, shop: dict[str, Any]
) -> None:
    service = await _create_service(client, shop["headers"])
    employee_id = await _get_employee_id(client, shop["headers"])

    resp = await client.post(
        "/appointments",
        json={
            "branch_id": shop["branch"]["id"],
            "customer_id": shop["customer"]["id"],
            "employee_id": employee_id,
            "starts_at": "2026-08-01T10:00:00Z",
            "service_ids": [service["id"]],
        },
        headers=shop["headers"],
    )
    assert resp.status_code == 201, resp.text
    appointment = resp.json()["data"]
    assert appointment["status"] == "pending"
    assert appointment["ends_at"] == "2026-08-01T11:00:00Z"

    # Conflit : même employé, créneau chevauchant
    conflict = await client.post(
        "/appointments",
        json={
            "branch_id": shop["branch"]["id"],
            "employee_id": employee_id,
            "starts_at": "2026-08-01T10:30:00Z",
            "service_ids": [service["id"]],
        },
        headers=shop["headers"],
    )
    assert conflict.status_code == 409

    # Transitions de statut
    for status in ("confirmed", "arrived", "in_progress"):
        resp = await client.post(
            f"/appointments/{appointment['id']}/status",
            json={"status": status},
            headers=shop["headers"],
        )
        assert resp.status_code == 200, resp.text

    # Transition invalide
    bad = await client.post(
        f"/appointments/{appointment['id']}/status",
        json={"status": "pending"},
        headers=shop["headers"],
    )
    assert bad.status_code == 422

    # Conversion en vente (brouillon)
    convert = await client.post(
        f"/appointments/{appointment['id']}/convert-to-sale", headers=shop["headers"]
    )
    assert convert.status_code == 200, convert.text
    assert convert.json()["data"]["total"] == "10000.00"


async def test_commission_accrual_validate_pay(client: AsyncClient, shop: dict[str, Any]) -> None:
    employee_id = await _get_employee_id(client, shop["headers"])

    # Règle : 10 % sur tout
    rule = await client.post(
        "/commissions/rules",
        json={"name": "Com globale 10%", "commission_type": "percent", "rate": "0.10"},
        headers=shop["headers"],
    )
    assert rule.status_code == 201, rule.text

    await open_cash_session(client, shop["headers"])
    sale = await client.post(
        "/sales",
        json={
            "branch_id": shop["branch"]["id"],
            "items": [
                {
                    "item_type": "product",
                    "product_id": shop["product"]["id"],
                    "quantity": "2",
                    "employee_id": employee_id,
                }
            ],
            "payments": [{"method": "cash", "amount": "50000"}],
        },
        headers=shop["headers"],
    )
    assert sale.status_code == 201, sale.text

    commissions = (await client.get("/commissions", headers=shop["headers"])).json()["data"]
    assert len(commissions) == 1
    commission = commissions[0]
    assert commission["amount"] == "5000.00"  # 10 % de 50 000
    assert commission["status"] == "pending"

    validated = await client.post(
        f"/commissions/{commission['id']}/validate", headers=shop["headers"]
    )
    assert validated.json()["data"]["status"] == "validated"

    paid = await client.post(f"/commissions/{commission['id']}/pay", headers=shop["headers"])
    assert paid.json()["data"]["status"] == "paid"

    # Une commission payée ne peut plus être validée/contestée
    again = await client.post(f"/commissions/{commission['id']}/validate", headers=shop["headers"])
    assert again.status_code == 422


async def test_purchase_order_receive_updates_stock(
    client: AsyncClient, shop: dict[str, Any]
) -> None:
    supplier = await client.post(
        "/suppliers",
        json={"name": "Cosmétiques CI Distribution", "phone": "+2252722334455"},
        headers=shop["headers"],
    )
    assert supplier.status_code == 201, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    order = await client.post(
        "/suppliers/orders",
        json={
            "branch_id": shop["branch"]["id"],
            "supplier_id": supplier_id,
            "items": [
                {"product_id": shop["product"]["id"], "quantity": "10", "unit_cost": "14000"}
            ],
        },
        headers=shop["headers"],
    )
    assert order.status_code == 201, order.text
    assert order.json()["data"]["total"] == "140000.00"
    order_id = order.json()["data"]["id"]

    detail = (await client.get(f"/suppliers/orders/{order_id}", headers=shop["headers"])).json()[
        "data"
    ]
    item_id = detail["items"][0]["id"]

    # Réception partielle
    receive = await client.post(
        f"/suppliers/orders/{order_id}/receive",
        json={"items": [{"item_id": item_id, "quantity": "6"}]},
        headers=shop["headers"],
    )
    assert receive.status_code == 200, receive.text
    assert receive.json()["data"]["status"] == "partially_received"

    levels = (
        await client.get(
            "/stock/levels", params={"branch_id": shop["branch"]["id"]}, headers=shop["headers"]
        )
    ).json()["data"]
    assert levels[0]["quantity"] == "26.000"  # 20 + 6

    # Paiement fournisseur partiel
    pay = await client.post(
        f"/suppliers/orders/{order_id}/payments",
        json={"amount": "100000", "method": "bank_transfer"},
        headers=shop["headers"],
    )
    assert pay.status_code == 200
    assert pay.json()["data"]["amount_paid"] == "100000.00"

    # La dette fournisseur existe dès la réception partielle : 140 000 - 100 000
    debts = (await client.get("/suppliers/debts/summary", headers=shop["headers"])).json()["data"]
    assert debts[supplier_id] == "40000.00"

    # Réception du solde
    await client.post(
        f"/suppliers/orders/{order_id}/receive",
        json={"items": [{"item_id": item_id, "quantity": "4"}]},
        headers=shop["headers"],
    )
    debts = (await client.get("/suppliers/debts/summary", headers=shop["headers"])).json()["data"]
    assert debts[supplier_id] == "40000.00"


async def test_subscription_plans_and_current(client: AsyncClient) -> None:
    plans = (await client.get("/subscription/plans")).json()["data"]
    codes = [p["code"] for p in plans]
    assert codes == ["essential", "professional", "enterprise"]

    owner = await register_and_login(client, email="subs@nzassa.ci", business_name="Subs Shop")
    current = (await client.get("/subscription", headers=owner["headers"])).json()["data"]
    assert current["status"] == "trialing"
    assert current["plan"]["code"] == "essential"

    changed = await client.post(
        "/subscription/change-plan",
        json={"plan_code": "professional", "billing_cycle": "monthly"},
        headers=owner["headers"],
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["payment_status"] == "requires_manual_confirmation"

    invoices = (await client.get("/subscription/invoices", headers=owner["headers"])).json()["data"]
    assert len(invoices) == 1
    assert invoices[0]["status"] == "pending"


async def test_subscription_branch_limit_enforced(client: AsyncClient) -> None:
    """Le plan Essentiel limite à 1 point de vente."""
    owner = await register_and_login(client, email="limit@nzassa.ci", business_name="Limit Shop")
    resp = await client.post(
        "/business/branches",
        json={"code": "PDV2", "name": "Deuxième point de vente"},
        headers=owner["headers"],
    )
    assert resp.status_code == 402
    assert resp.json()["error"]["code"] == "SUBSCRIPTION_LIMIT_REACHED"


async def test_sync_push_idempotent_and_pull(client: AsyncClient, shop: dict[str, Any]) -> None:
    operations = {
        "operations": [
            {
                "client_operation_id": "op-0001-sale",
                "operation_type": "create_sale",
                "payload": {
                    "branch_id": shop["branch"]["id"],
                    "items": [
                        {
                            "item_type": "product",
                            "product_id": shop["product"]["id"],
                            "quantity": "1",
                        }
                    ],
                    "payments": [{"method": "cash", "amount": "25000"}],
                },
            },
            {
                "client_operation_id": "op-0002-customer",
                "operation_type": "create_customer",
                "payload": {"first_name": "Fatou", "phone": "+2250101010101"},
            },
            {
                "client_operation_id": "op-0003-expense",
                "operation_type": "create_expense",
                "payload": {
                    "branch_id": shop["branch"]["id"],
                    "label": "Taxi livraison",
                    "amount": "2000",
                    "expense_date": "2026-07-29",
                },
            },
        ]
    }
    first = await client.post("/sync/push", json=operations, headers=shop["headers"])
    assert first.status_code == 200, first.text
    assert first.json()["data"]["applied"] == 3

    # Rejouer le même lot : aucune nouvelle écriture
    second = await client.post("/sync/push", json=operations, headers=shop["headers"])
    assert second.json()["data"]["applied"] == 3
    assert all(r.get("duplicate") for r in second.json()["data"]["results"])

    sales = (await client.get("/sales", headers=shop["headers"])).json()["meta"]["total"]
    assert sales == 1

    # Pull incrémental
    pull = (await client.get("/sync/pull", headers=shop["headers"])).json()["data"]
    assert len(pull["products"]) == 1
    assert any(c["phone"] == "+2250101010101" for c in pull["customers"])
    assert pull["server_time"]

    pull_empty = (
        await client.get(
            "/sync/pull", params={"since": pull["server_time"]}, headers=shop["headers"]
        )
    ).json()["data"]
    assert pull_empty["products"] == []


async def test_dashboard_report(client: AsyncClient, shop: dict[str, Any]) -> None:
    await open_cash_session(client, shop["headers"])
    await client.post(
        "/sales",
        json={
            "branch_id": shop["branch"]["id"],
            "items": [
                {"item_type": "product", "product_id": shop["product"]["id"], "quantity": "2"}
            ],
            "payments": [{"method": "cash", "amount": "50000"}],
        },
        headers=shop["headers"],
    )
    await client.post(
        "/expenses",
        json={
            "branch_id": shop["branch"]["id"],
            "label": "Loyer",
            "amount": "10000",
            "expense_date": "2026-07-30",
            "payment_method": "bank_transfer",
        },
        headers=shop["headers"],
    )
    dashboard = (await client.get("/reports/dashboard", headers=shop["headers"])).json()["data"]
    assert dashboard["revenue"] == "50000.00"
    assert dashboard["expenses"] == "10000.00"
    assert dashboard["gross_margin"] == "20000.00"  # 50 000 - 2 x 15 000
    assert dashboard["estimated_profit"] == "10000.00"
    assert dashboard["stock_value"] == "270000.00"  # 18 restants x 15 000

    top = (await client.get("/reports/top-products", headers=shop["headers"])).json()["data"]
    assert top[0]["label"] == "Parfum Clarins 50ml"

    methods = (await client.get("/reports/payment-methods", headers=shop["headers"])).json()["data"]
    assert methods[0]["method"] == "cash"


async def test_notifications_preferences(client: AsyncClient, shop: dict[str, Any]) -> None:
    resp = await client.get("/notifications", headers=shop["headers"])
    assert resp.status_code == 200

    pref = await client.put(
        "/notifications/preferences",
        json={
            "notification_type": "low_stock",
            "internal_enabled": True,
            "push_enabled": False,
            "email_enabled": True,
        },
        headers=shop["headers"],
    )
    assert pref.status_code == 200
    prefs = (await client.get("/notifications/preferences", headers=shop["headers"])).json()["data"]
    assert prefs[0]["notification_type"] == "low_stock"
    assert prefs[0]["email_enabled"] is True
