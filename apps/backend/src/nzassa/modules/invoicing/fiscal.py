"""Abstraction de connecteur fiscal (Facture Normalisée Électronique — Côte d'Ivoire).

IMPORTANT : la solution N'EST PAS intégrée officiellement à la DGI.
`SimulatedFiscalConnector` n'est actif qu'en environnement de développement,
pour préparer l'architecture. L'intégration réelle nécessitera l'API officielle,
la documentation et l'agrément (voir docs/TECHNICAL_DEBT.md).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from nzassa.core.config import get_settings
from nzassa.models.invoicing import Invoice


@dataclass
class FiscalSubmissionResult:
    accepted: bool
    reference: str | None
    message: str


class FiscalConnector(ABC):
    name: str = "abstract"

    @abstractmethod
    async def submit_invoice(self, invoice: Invoice) -> FiscalSubmissionResult: ...


class NullFiscalConnector(FiscalConnector):
    """Production par défaut : aucune soumission tant qu'un connecteur agréé n'existe pas."""

    name = "none"

    async def submit_invoice(self, invoice: Invoice) -> FiscalSubmissionResult:
        return FiscalSubmissionResult(
            accepted=False,
            reference=None,
            message="Aucun connecteur fiscal agréé configuré — facture non soumise à la DGI",
        )


class SimulatedFiscalConnector(FiscalConnector):
    """Développement uniquement : simule une acceptation pour tester le flux."""

    name = "simulated-dev"

    async def submit_invoice(self, invoice: Invoice) -> FiscalSubmissionResult:
        return FiscalSubmissionResult(
            accepted=True,
            reference=f"SIM-FNE-{invoice.number}",
            message="Soumission SIMULÉE (environnement de développement uniquement)",
        )


def get_fiscal_connector() -> FiscalConnector:
    settings = get_settings()
    if settings.nzassa_env in ("development", "test"):
        return SimulatedFiscalConnector()
    return NullFiscalConnector()
