"""Données de démonstration.

Usage : `python -m nzassa.seeds.demo` (ou `make seed`).
Identifiants documentés dans docs/deployment/installation.md — développement
uniquement, ne JAMAIS réutiliser en production.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from nzassa.core.database import get_session_factory
from nzassa.core.logging import configure_logging, get_logger
from nzassa.core.rbac import get_system_role, sync_rbac
from nzassa.core.security import hash_password
from nzassa.models.auth import User, UserRole
from nzassa.models.business import Branch, Employee
from nzassa.models.catalog import Product, ProductCategory, Service
from nzassa.models.customers import Customer
from nzassa.models.sales import CashRegister
from nzassa.modules.auth.schemas import RegisterRequest
from nzassa.modules.auth.service import register_tenant
from nzassa.modules.subscriptions.service import seed_plans

logger = get_logger(__name__)

DEMO_OWNER_EMAIL = "demo@nzassa.app"
DEMO_PASSWORD = "Demo#Nzassa2026"
SUPERADMIN_EMAIL = "admin@nzassa.app"


async def seed() -> None:
    configure_logging()
    async with get_session_factory()() as db:
        await sync_rbac(db)
        await seed_plans(db)

        existing = (
            await db.execute(select(User).where(User.email == DEMO_OWNER_EMAIL))
        ).scalar_one_or_none()
        if existing is not None:
            logger.info("seed_skip", reason="démo déjà présente")
            await db.commit()
            return

        # --- Super admin (compte plateforme, sans tenant) ---
        superadmin = User(
            email=SUPERADMIN_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            first_name="Super",
            last_name="Admin",
            is_superadmin=True,
        )
        db.add(superadmin)

        # --- Entreprise de démonstration ---
        tenant, owner = await register_tenant(
            db,
            RegisterRequest(
                business_name="Institut Nzassa Beauté",
                industry="beauty",
                first_name="Awa",
                last_name="Koné",
                email=DEMO_OWNER_EMAIL,
                phone="+2250701020304",
                password=DEMO_PASSWORD,
            ),
        )
        tenant_id = tenant.id
        branch_main = (
            (await db.execute(select(Branch).where(Branch.tenant_id == tenant_id)))
            .scalars()
            .first()
        )
        assert branch_main is not None

        # Deuxième point de vente + caisse
        branch2 = Branch(
            tenant_id=tenant_id,
            business_id=branch_main.business_id,
            code="COCODY",
            name="Boutique Cocody",
            address="Cocody, Abidjan",
        )
        db.add(branch2)
        await db.flush()
        db.add(CashRegister(tenant_id=tenant_id, branch_id=branch2.id, name="Caisse Cocody"))

        # --- Équipe ---
        team = [
            ("Gérant", "manager", "gerant@nzassa.app", "Ibrahim", "Traoré"),
            ("Caissier", "cashier", "caisse@nzassa.app", "Aminata", "Ouattara"),
            ("Vendeur", "seller", "vente@nzassa.app", "Moussa", "Koffi"),
        ]
        for job_title, role_code, email, first, last in team:
            member = User(
                tenant_id=tenant_id,
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                first_name=first,
                last_name=last,
            )
            db.add(member)
            await db.flush()
            role = await get_system_role(db, role_code)
            db.add(UserRole(user_id=member.id, role_id=role.id, tenant_id=tenant_id))
            db.add(
                Employee(
                    tenant_id=tenant_id,
                    business_id=branch_main.business_id,
                    branch_id=branch_main.id,
                    user_id=member.id,
                    first_name=first,
                    last_name=last,
                    email=email,
                    job_title=job_title,
                )
            )

        # --- Catalogue ---
        category = ProductCategory(tenant_id=tenant_id, name="Parfums", kind="product")
        db.add(category)
        await db.flush()
        products = [
            ("Parfum Clarins 50ml", "25000", "15000", "10"),
            ("Crème hydratante Nivea", "4500", "2800", "20"),
            ("Huile d'argan pure 100ml", "12000", "7000", "8"),
            ("Savon noir traditionnel", "1500", "700", "50"),
            ("Beurre de karité 250g", "3000", "1500", "30"),
        ]
        product_rows: list[Product] = []
        for name, sell, buy, threshold in products:
            product = Product(
                tenant_id=tenant_id,
                business_id=branch_main.business_id,
                category_id=category.id,
                name=name,
                sku=f"P-{uuid.uuid4().hex[:6].upper()}",
                selling_price=Decimal(sell),
                purchase_price=Decimal(buy),
                low_stock_threshold=Decimal(threshold),
            )
            db.add(product)
            product_rows.append(product)

        services = [
            ("Coiffure tresses", "10000", 90),
            ("Soin du visage complet", "15000", 60),
            ("Manucure + pose vernis", "5000", 45),
        ]
        for name, price, duration in services:
            db.add(
                Service(
                    tenant_id=tenant_id,
                    business_id=branch_main.business_id,
                    name=name,
                    price=Decimal(price),
                    duration_minutes=duration,
                )
            )

        # --- Clients ---
        customers = [
            ("Mariam", "Diabaté", "+2250709080706"),
            ("Fatou", "Bamba", "+2250102030405"),
            ("Adjoua", "Kouassi", "+2250506070809"),
        ]
        for first, last, phone in customers:
            db.add(
                Customer(
                    tenant_id=tenant_id,
                    business_id=branch_main.business_id,
                    first_name=first,
                    last_name=last,
                    phone=phone,
                    marketing_consent=True,
                )
            )
        await db.flush()

        # --- Stock initial (mouvements traçables) ---
        from nzassa.modules.inventory.service import apply_movement

        for product in product_rows:
            await apply_movement(
                db,
                tenant_id=tenant_id,
                branch_id=branch_main.id,
                product_id=product.id,
                movement_type="purchase_in",
                quantity=Decimal("50"),
                unit_cost=product.purchase_price,
                reason="Stock initial de démonstration",
                performed_by=owner.id,
            )

        await db.commit()
        logger.info(
            "seed_done",
            tenant=str(tenant_id),
            owner=DEMO_OWNER_EMAIL,
            superadmin=SUPERADMIN_EMAIL,
        )
        _ = datetime.now(UTC) + timedelta(days=1)


if __name__ == "__main__":
    asyncio.run(seed())
