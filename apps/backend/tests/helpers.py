"""Aides de test partagées."""

from typing import Any

from httpx import AsyncClient


async def get_main_branch(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    resp = await client.get("/business/branches", headers=headers)
    assert resp.status_code == 200, resp.text
    return next(b for b in resp.json()["data"] if b["code"] == "MAIN")


async def create_product(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str = "Parfum Clarins 50ml",
    selling_price: str = "25000",
    purchase_price: str = "15000",
    **kwargs: Any,
) -> dict[str, Any]:
    resp = await client.post(
        "/catalog/products",
        json={
            "name": name,
            "selling_price": selling_price,
            "purchase_price": purchase_price,
            **kwargs,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def stock_in(
    client: AsyncClient,
    headers: dict[str, str],
    branch_id: str,
    product_id: str,
    quantity: str = "10",
) -> dict[str, Any]:
    resp = await client.post(
        "/stock/entries",
        json={"branch_id": branch_id, "product_id": product_id, "quantity": quantity},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def create_customer(
    client: AsyncClient, headers: dict[str, str], *, phone: str = "+2250709080706"
) -> dict[str, Any]:
    resp = await client.post(
        "/customers",
        json={"first_name": "Mariam", "last_name": "Diabaté", "phone": phone},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def open_cash_session(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    registers = (await client.get("/cash/registers", headers=headers)).json()["data"]
    resp = await client.post(
        "/cash/sessions/open",
        json={"register_id": registers[0]["id"], "opening_float": "10000"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]
