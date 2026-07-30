"""Assemblage du routeur API v1."""

from fastapi import APIRouter

from nzassa.modules.health.router import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)


def _include_module_routers() -> None:
    """Les modules sont ajoutés ici au fur et à mesure de leur développement."""
    from nzassa.modules.auth.router import router as auth_router

    api_router.include_router(auth_router)


_include_module_routers()
