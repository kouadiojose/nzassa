"""Utilitaires monétaires — Decimal partout, jamais de float."""

from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def money(value: Decimal | int | str) -> Decimal:
    """Normalise un montant à 2 décimales (arrondi commercial)."""
    if isinstance(value, float):  # pragma: no cover — refusé par le typage
        raise TypeError("Les montants ne doivent jamais être des float")
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


ZERO = money("0")
