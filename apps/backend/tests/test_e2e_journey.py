"""Parcours end-to-end prioritaire complet (12 étapes) via l'API réelle."""

from httpx import AsyncClient

from tests.conftest import register_and_login


async def test_full_business_journey(client: AsyncClient) -> None:
    # 1. Création d'une entreprise
    owner = await register_and_login(
        client, email="parcours@nzassa.ci", business_name="Parcours Complet SARL"
    )
    headers = owner["headers"]

    # 2. Connexion (déjà couverte par register ; re-vérifie explicitement)
    login = await client.post(
        "/auth/login", json={"email": "parcours@nzassa.ci", "password": "MotDePasse#2026"}
    )
    assert login.status_code == 200

    branch = next(
        b for b in (await client.get("/business/branches", headers=headers)).json()["data"]
    )

    # 3. Création d'un produit + une prestation
    product = (
        await client.post(
            "/catalog/products",
            json={"name": "Parfum Signature", "selling_price": "20000", "purchase_price": "12000"},
            headers=headers,
        )
    ).json()["data"]
    service = (
        await client.post(
            "/catalog/services",
            json={"name": "Brushing", "price": "8000", "duration_minutes": 45},
            headers=headers,
        )
    ).json()["data"]

    # 4. Entrée en stock
    entry = await client.post(
        "/stock/entries",
        json={"branch_id": branch["id"], "product_id": product["id"], "quantity": "15"},
        headers=headers,
    )
    assert entry.status_code == 201

    # 5. Création d'un client
    customer = (
        await client.post(
            "/customers",
            json={"first_name": "Aïcha", "last_name": "Cissé", "phone": "+2250777777777"},
            headers=headers,
        )
    ).json()["data"]

    # Ouverture de caisse (prérequis vente espèces)
    register = (await client.get("/cash/registers", headers=headers)).json()["data"][0]
    session = (
        await client.post(
            "/cash/sessions/open",
            json={"register_id": register["id"], "opening_float": "5000"},
            headers=headers,
        )
    ).json()["data"]

    # 6. Vente (produit + prestation) — 7. paiement partiel (crédit)
    employee = (await client.get("/employees", headers=headers)).json()["data"][0]
    sale = (
        await client.post(
            "/sales",
            json={
                "branch_id": branch["id"],
                "customer_id": customer["id"],
                "items": [
                    {
                        "item_type": "product",
                        "product_id": product["id"],
                        "quantity": "2",
                        "employee_id": employee["id"],
                    },
                    {
                        "item_type": "service",
                        "service_id": service["id"],
                        "employee_id": employee["id"],
                    },
                ],
                "payments": [{"method": "cash", "amount": "30000"}],
            },
            headers=headers,
        )
    ).json()["data"]
    assert sale["total"] == "48000.00"  # 2 x 20 000 + 8 000
    assert sale["amount_due"] == "18000.00"

    # 8. Règlement de la dette
    debt = (await client.get("/debts", headers=headers)).json()["data"][0]
    settled = await client.post(
        f"/debts/{debt['id']}/payments",
        json={"amount": "18000", "method": "wave"},
        headers=headers,
    )
    assert settled.json()["data"]["status"] == "paid"

    # 9. Création d'un rendez-vous
    appointment = await client.post(
        "/appointments",
        json={
            "branch_id": branch["id"],
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "starts_at": "2026-08-05T09:00:00Z",
            "service_ids": [service["id"]],
        },
        headers=headers,
    )
    assert appointment.status_code == 201

    # 10. Calcul d'une commission (règle 10 % créée avant une seconde vente)
    await client.post(
        "/commissions/rules",
        json={"name": "10% employé", "commission_type": "percent", "rate": "0.10"},
        headers=headers,
    )
    await client.post(
        "/sales",
        json={
            "branch_id": branch["id"],
            "items": [
                {
                    "item_type": "product",
                    "product_id": product["id"],
                    "quantity": "1",
                    "employee_id": employee["id"],
                }
            ],
            "payments": [{"method": "cash", "amount": "20000"}],
        },
        headers=headers,
    )
    commissions = (await client.get("/commissions", headers=headers)).json()["data"]
    assert any(c["amount"] == "2000.00" for c in commissions)

    # 11. Fermeture de caisse (5 000 + 30 000 + 20 000 = 55 000 attendus)
    closed = (
        await client.post(
            f"/cash/sessions/{session['id']}/close",
            json={"counted_cash": "55000"},
            headers=headers,
        )
    ).json()["data"]
    assert closed["expected_cash"] == "55000.00"
    assert closed["difference"] == "0.00"

    # 12. Consultation d'un rapport
    dashboard = (await client.get("/reports/dashboard", headers=headers)).json()["data"]
    assert dashboard["revenue"] == "68000.00"
    assert dashboard["sales_count"] == 2

    # Bonus : reçu PDF de la première vente
    receipt = await client.get(f"/sales/{sale['id']}/receipt.pdf", headers=headers)
    assert receipt.status_code == 200
    assert receipt.headers["content-type"] == "application/pdf"
    assert receipt.content[:5] == b"%PDF-"
