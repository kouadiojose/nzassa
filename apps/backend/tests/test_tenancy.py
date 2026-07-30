"""Tests d'isolation multi-tenant — un tenant ne voit JAMAIS les données d'un autre."""

from typing import Any

from httpx import AsyncClient

from tests.conftest import register_and_login
from tests.helpers import create_customer, create_product


async def test_products_are_isolated_between_tenants(client: AsyncClient) -> None:
    tenant_a = await register_and_login(client, email="a@tenant-a.ci", business_name="Tenant A")
    tenant_b = await register_and_login(client, email="b@tenant-b.ci", business_name="Tenant B")

    product = await create_product(client, tenant_a["headers"], name="Produit secret A")

    # Liste : B ne voit pas le produit de A
    resp = await client.get("/catalog/products", headers=tenant_b["headers"])
    names = [p["name"] for p in resp.json()["data"]]
    assert "Produit secret A" not in names

    # Accès direct par id : NOT_FOUND (pas 403, pour ne rien révéler)
    resp = await client.get(f"/catalog/products/{product['id']}", headers=tenant_b["headers"])
    assert resp.status_code == 404

    # Modification interdite
    resp = await client.patch(
        f"/catalog/products/{product['id']}",
        json={"name": "piraté"},
        headers=tenant_b["headers"],
    )
    assert resp.status_code == 404


async def test_customers_are_isolated_between_tenants(client: AsyncClient) -> None:
    tenant_a = await register_and_login(client, email="a2@tenant-a.ci", business_name="Tenant A2")
    tenant_b = await register_and_login(client, email="b2@tenant-b.ci", business_name="Tenant B2")

    customer = await create_customer(client, tenant_a["headers"])
    resp = await client.get(f"/customers/{customer['id']}", headers=tenant_b["headers"])
    assert resp.status_code == 404

    # Le même téléphone est autorisé dans un autre tenant (unicité par tenant)
    resp = await client.post(
        "/customers",
        json={"first_name": "Autre", "phone": customer["phone"]},
        headers=tenant_b["headers"],
    )
    assert resp.status_code == 201


async def test_sales_are_isolated_between_tenants(client: AsyncClient) -> None:
    tenant_a = await register_and_login(client, email="a3@tenant-a.ci", business_name="Tenant A3")
    tenant_b = await register_and_login(client, email="b3@tenant-b.ci", business_name="Tenant B3")

    from tests.helpers import get_main_branch, stock_in

    branch = await get_main_branch(client, tenant_a["headers"])
    product = await create_product(client, tenant_a["headers"])
    await stock_in(client, tenant_a["headers"], branch["id"], product["id"])

    sale_resp = await client.post(
        "/sales",
        json={
            "branch_id": branch["id"],
            "items": [{"item_type": "product", "product_id": product["id"], "quantity": "1"}],
            "payments": [{"method": "wave", "amount": "25000"}],
        },
        headers=tenant_a["headers"],
    )
    assert sale_resp.status_code == 201, sale_resp.text
    sale_id = sale_resp.json()["data"]["id"]

    resp = await client.get(f"/sales/{sale_id}", headers=tenant_b["headers"])
    assert resp.status_code == 404

    resp = await client.get("/sales", headers=tenant_b["headers"])
    assert resp.json()["data"] == []


async def _member_headers(
    client: AsyncClient, owner: dict[str, Any], role_code: str, email: str
) -> dict[str, str]:
    invite = await client.post(
        "/members/invite",
        json={
            "email": email,
            "first_name": "Test",
            "last_name": "Membre",
            "role_code": role_code,
            "password": "Password#2026",
        },
        headers=owner["headers"],
    )
    assert invite.status_code == 201, invite.text
    login = await client.post("/auth/login", json={"email": email, "password": "Password#2026"})
    assert login.status_code == 200, login.text
    token = login.json()["data"]["tokens"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_permissions_enforced_by_role(client: AsyncClient) -> None:
    owner = await register_and_login(client, email="perm@tenant.ci", business_name="Perm Tenant")

    seller_headers = await _member_headers(client, owner, "seller", "vendeur@tenant.ci")

    # Le vendeur peut lire les produits
    resp = await client.get("/catalog/products", headers=seller_headers)
    assert resp.status_code == 200

    # ... mais pas en créer
    resp = await client.post(
        "/catalog/products",
        json={"name": "Interdit", "selling_price": "1000"},
        headers=seller_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "PERMISSION_DENIED"

    # ... ni approuver des dépenses ou passer des créances en perte
    resp = await client.get("/debts", headers=seller_headers)
    assert resp.status_code == 403


async def test_viewer_cannot_modify_anything(client: AsyncClient) -> None:
    owner = await register_and_login(client, email="view@tenant.ci", business_name="View Tenant")
    viewer_headers = await _member_headers(client, owner, "viewer", "lecteur@tenant.ci")

    resp = await client.get("/catalog/products", headers=viewer_headers)
    assert resp.status_code == 200

    resp = await client.post("/customers", json={"first_name": "X"}, headers=viewer_headers)
    assert resp.status_code == 403
