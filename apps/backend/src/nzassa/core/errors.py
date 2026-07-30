"""Erreurs applicatives avec codes stables.

Chaque erreur porte un code stable documenté dans
packages/shared-contracts/error-codes.md et un statut HTTP.
"""

from typing import Any


class AppError(Exception):
    """Erreur applicative de base — sérialisée au format d'erreur standard."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "Une erreur est survenue"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Ressource introuvable"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "Conflit avec l'état actuel de la ressource"


class ValidationAppError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Données invalides"


class BusinessRuleError(AppError):
    status_code = 422
    code = "BUSINESS_RULE_VIOLATION"
    message = "Règle métier violée"


class InsufficientStockError(BusinessRuleError):
    code = "INSUFFICIENT_STOCK"
    message = "Stock insuffisant"


class CashSessionRequiredError(BusinessRuleError):
    code = "CASH_SESSION_REQUIRED"
    message = "Aucune session de caisse ouverte"


class InvalidCredentialsError(AppError):
    status_code = 401
    code = "AUTH_INVALID_CREDENTIALS"
    message = "Email ou mot de passe incorrect"


class TokenError(AppError):
    status_code = 401
    code = "AUTH_TOKEN_INVALID"
    message = "Token invalide ou révoqué"


class TokenExpiredError(TokenError):
    code = "AUTH_TOKEN_EXPIRED"
    message = "Token expiré"


class AccountLockedError(AppError):
    status_code = 423
    code = "AUTH_ACCOUNT_LOCKED"
    message = "Compte temporairement verrouillé suite à trop de tentatives"


class AccountDisabledError(AppError):
    status_code = 403
    code = "AUTH_ACCOUNT_DISABLED"
    message = "Compte désactivé"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "PERMISSION_DENIED"
    message = "Permission insuffisante pour cette opération"


class SubscriptionLimitError(AppError):
    status_code = 402
    code = "SUBSCRIPTION_LIMIT_REACHED"
    message = "Limite du plan d'abonnement atteinte"


class SubscriptionExpiredError(AppError):
    status_code = 402
    code = "SUBSCRIPTION_EXPIRED"
    message = "Abonnement expiré"


class RateLimitedError(AppError):
    status_code = 429
    code = "RATE_LIMITED"
    message = "Trop de requêtes, veuillez réessayer plus tard"


class IdempotencyConflictError(ConflictError):
    code = "IDEMPOTENCY_CONFLICT"
    message = "Clé d'idempotence déjà utilisée avec une requête différente"
