"""Assemblage du routeur API v1."""

from fastapi import APIRouter

from nzassa.modules.health.router import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)


def _include_module_routers() -> None:
    """Les modules sont ajoutés ici au fur et à mesure de leur développement."""
    from nzassa.modules.appointments.router import router as appointments_router
    from nzassa.modules.assistant.router import router as assistant_router
    from nzassa.modules.auth.router import router as auth_router
    from nzassa.modules.businesses.router import router as businesses_router
    from nzassa.modules.catalog.router import router as catalog_router
    from nzassa.modules.commissions.router import router as commissions_router
    from nzassa.modules.customers.router import router as customers_router
    from nzassa.modules.debts.router import router as debts_router
    from nzassa.modules.expenses.router import router as expenses_router
    from nzassa.modules.inventory.router import router as inventory_router
    from nzassa.modules.invoicing.router import router as invoicing_router
    from nzassa.modules.notifications.router import router as notifications_router
    from nzassa.modules.reports.router import router as reports_router
    from nzassa.modules.sales.router import router as sales_router
    from nzassa.modules.subscriptions.router import router as subscriptions_router
    from nzassa.modules.superadmin.router import router as superadmin_router
    from nzassa.modules.suppliers.router import router as suppliers_router
    from nzassa.modules.sync.router import router as sync_router
    from nzassa.modules.users.router import router as users_router

    api_router.include_router(auth_router)
    api_router.include_router(businesses_router)
    api_router.include_router(users_router)
    api_router.include_router(catalog_router)
    api_router.include_router(inventory_router)
    api_router.include_router(customers_router)
    api_router.include_router(sales_router)
    api_router.include_router(expenses_router)
    api_router.include_router(debts_router)
    api_router.include_router(appointments_router)
    api_router.include_router(commissions_router)
    api_router.include_router(suppliers_router)
    api_router.include_router(subscriptions_router)
    api_router.include_router(notifications_router)
    api_router.include_router(reports_router)
    api_router.include_router(sync_router)
    api_router.include_router(assistant_router)
    api_router.include_router(invoicing_router)
    api_router.include_router(superadmin_router)


_include_module_routers()
