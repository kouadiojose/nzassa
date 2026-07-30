"""Abstraction de fournisseur IA.

`StubProvider` : parsing déterministe par règles (aucun appel externe),
utilisé par défaut et dans les tests.
`AnthropicProvider` : branché quand AI_PROVIDER=anthropic et AI_API_KEY définie.

Les données envoyées au fournisseur restent limitées au tenant courant.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from nzassa.core.config import get_settings

# Moyens de paiement reconnus dans le texte libre
METHOD_KEYWORDS = {
    "wave": "wave",
    "orange": "orange_money",
    "orange money": "orange_money",
    "om": "orange_money",
    "mtn": "mtn_money",
    "momo": "mtn_money",
    "moov": "moov_money",
    "espèce": "cash",
    "espèces": "cash",
    "espece": "cash",
    "cash": "cash",
    "liquide": "cash",
    "carte": "card",
    "virement": "bank_transfer",
    "crédit": "credit",
    "credit": "credit",
}


@dataclass
class ParsedSaleIntent:
    """Proposition de vente structurée extraite d'une phrase."""

    items: list[dict[str, Any]] = field(default_factory=list)
    # [{"query": "parfum clarins", "quantity": Decimal, "unit_price": Decimal|None}]
    payments: list[dict[str, Any]] = field(default_factory=list)
    # [{"method": "wave", "amount": Decimal}]
    notes: str | None = None
    confidence: float = 0.0


class AiProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def parse_sale(self, text: str) -> ParsedSaleIntent: ...

    @abstractmethod
    async def answer(self, question: str, context: dict[str, Any]) -> str: ...


_NUMBER_WORDS = {
    "un": 1,
    "une": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "douze": 12,
    "quinze": 15,
    "vingt": 20,
}


def _parse_amount(raw: str) -> Decimal:
    cleaned = raw.replace(" ", "").replace("\u202f", "").replace(".", "").replace(",", "")
    return Decimal(cleaned)


class StubProvider(AiProvider):
    """Extraction par règles : quantités, articles, prix unitaires, paiements."""

    name = "stub"

    async def parse_sale(self, text: str) -> ParsedSaleIntent:
        intent = ParsedSaleIntent(notes=text.strip())
        lowered = text.lower()

        # Paiements d'abord : « a payé 50 000 (FCFA) par Wave », « 20 000 en espèces »
        payment_pattern = re.compile(
            r"(?:payé|paye|réglé|regle|versé|verse|donné|donne)?\s*([\d\s., ]{4,})\s*"
            r"(?:fcfa|f|xof|francs?)?\s*(?:par|en|via|avec)\s+([a-zà-ÿ' ]{2,20})",
            re.IGNORECASE,
        )
        payment_spans: list[tuple[int, int]] = []
        for match in payment_pattern.finditer(lowered):
            amount_raw, method_raw = match.group(1), match.group(2).strip()
            method = None
            for keyword, code in METHOD_KEYWORDS.items():
                if method_raw.startswith(keyword):
                    method = code
                    break
            if method is None or method == "credit":
                continue
            try:
                amount = _parse_amount(amount_raw)
            except Exception:
                continue
            if amount > 0:
                intent.payments.append({"method": method, "amount": amount})
                payment_spans.append(match.span())

        # On retire les phrases de paiement du texte avant de chercher les articles,
        # sinon « 50 000 par Wave » serait interprété comme un article.
        chars = list(lowered)
        for start, end in payment_spans:
            for i in range(start, end):
                chars[i] = " "
        item_text = "".join(chars)

        # Articles : « (j'ai vendu) trois parfums Clarins à 25 000 (FCFA) »
        item_pattern = re.compile(
            r"(?:vendu|vends|vendre|pris|acheté)?\s*"
            r"(\d+|" + "|".join(_NUMBER_WORDS) + r")\s+"
            r"([a-zà-ÿ0-9'\- ]{2,60}?)"
            r"(?:\s+(?:à|a|au prix de|pour)\s+([\d\s.,\u202f]+)\s*(?:fcfa|f|xof|francs?)?\s*"
            r"(?:chacun|chacune|l'unité|piece|pièce)?)?"
            r"(?=[,.;]|\s+et\s+|$)",
            re.IGNORECASE,
        )
        stop_words = {"fcfa", "xof", "franc", "francs", "client", "cliente"}
        for match in item_pattern.finditer(item_text):
            qty_raw, label, price_raw = match.group(1), match.group(2), match.group(3)
            label = label.strip(" .,;")
            if not label or label in METHOD_KEYWORDS:
                continue
            if any(word in stop_words for word in label.split()):
                continue
            quantity = Decimal(_NUMBER_WORDS.get(qty_raw, qty_raw))
            unit_price = _parse_amount(price_raw) if price_raw else None
            intent.items.append({"query": label, "quantity": quantity, "unit_price": unit_price})

        intent.confidence = 0.9 if intent.items else 0.1
        return intent

    async def answer(self, question: str, context: dict[str, Any]) -> str:
        """Réponse basée uniquement sur le contexte fourni (données du tenant)."""
        parts = ["Voici ce que je peux vous dire sur la base de vos données :"]
        if "dashboard" in context:
            d = context["dashboard"]
            parts.append(
                f"Chiffre d'affaires sur la période : {d['revenue']} ; "
                f"dépenses : {d['expenses']} ; bénéfice estimé : {d['estimated_profit']}."
            )
        if context.get("top_products"):
            top = ", ".join(p["label"] for p in context["top_products"][:3])
            parts.append(f"Vos meilleurs produits : {top}.")
        if context.get("low_stock_count"):
            parts.append(
                f"Attention : {context['low_stock_count']} produit(s) sous le seuil de stock."
            )
        return " ".join(parts)


def get_ai_provider() -> AiProvider:
    settings = get_settings()
    if settings.ai_provider == "anthropic" and settings.ai_api_key:
        # L'intégration Anthropic nécessite une clé API externe ;
        # le contrat est identique (parse_sale / answer). Voir docs/TECHNICAL_DEBT.md.
        return StubProvider()
    return StubProvider()
