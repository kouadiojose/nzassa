"""Abstraction de fournisseur de paiement d'abonnement.

Permet de brancher ultérieurement CinetPay, Wave, Orange Money, MTN Money,
Flutterwave ou Paystack. AUCUN fournisseur ne simule un paiement réussi en
production : `ManualPaymentProvider` exige une activation manuelle par le
Super Admin.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from nzassa.core.config import get_settings


@dataclass
class PaymentIntent:
    reference: str
    checkout_url: str | None
    status: str  # pending | requires_manual_confirmation


class SubscriptionPaymentProvider(ABC):
    """Contrat commun à tous les fournisseurs de paiement d'abonnement."""

    name: str = "abstract"

    @abstractmethod
    async def create_payment(
        self, *, invoice_number: str, amount: Decimal, currency: str, customer_email: str
    ) -> PaymentIntent: ...

    @abstractmethod
    async def verify_payment(self, reference: str) -> bool:
        """Retourne True uniquement si le fournisseur confirme réellement le paiement."""


class ManualPaymentProvider(SubscriptionPaymentProvider):
    """Fournisseur par défaut : le règlement est confirmé manuellement
    (virement, Mobile Money hors ligne...) par le Super Admin."""

    name = "manual"

    async def create_payment(
        self, *, invoice_number: str, amount: Decimal, currency: str, customer_email: str
    ) -> PaymentIntent:
        return PaymentIntent(
            reference=f"manual:{invoice_number}",
            checkout_url=None,
            status="requires_manual_confirmation",
        )

    async def verify_payment(self, reference: str) -> bool:
        # Jamais de confirmation automatique : l'activation passe par le Super Admin.
        return False


def get_payment_provider() -> SubscriptionPaymentProvider:
    """Résolution du fournisseur selon la configuration.

    Les intégrations réelles (CinetPay, Wave, ...) seront ajoutées ici avec
    leurs identifiants ; voir docs/TECHNICAL_DEBT.md.
    """
    _ = get_settings()
    return ManualPaymentProvider()
