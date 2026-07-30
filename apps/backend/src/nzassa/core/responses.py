"""Enveloppes de réponse API standardisées."""

from typing import Any

from pydantic import BaseModel


class ApiResponse[T](BaseModel):
    success: bool = True
    message: str = "Opération réalisée avec succès"
    data: T | None = None
    meta: dict[str, Any] = {}


class ErrorBody(BaseModel):
    code: str
    details: dict[str, Any] = {}


class ApiErrorResponse(BaseModel):
    success: bool = False
    message: str
    error: ErrorBody


def ok(
    data: Any = None, message: str = "Opération réalisée avec succès", **meta: Any
) -> dict[str, Any]:
    """Construit une réponse de succès standard."""
    return {"success": True, "message": message, "data": data, "meta": meta}
