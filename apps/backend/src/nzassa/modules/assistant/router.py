"""Endpoints de l'assistant intelligent.

Principe de sécurité : l'assistant PROPOSE, l'utilisateur CONFIRME.
Aucune opération financière n'est exécutée sans confirmation explicite
(`POST /assistant/proposals/{id}/confirm`).
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import or_

from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import BusinessRuleError, NotFoundError, ValidationAppError
from nzassa.core.responses import ok
from nzassa.core.tenancy import tenant_query
from nzassa.models.ai import AiActionProposal, AiConversation, AiMessage
from nzassa.models.catalog import Product, Service
from nzassa.modules.assistant.providers import get_ai_provider
from nzassa.modules.sales import service as sales_service
from nzassa.modules.sales.schemas import SaleCreate

router = APIRouter(prefix="/assistant", tags=["assistant"])


class CommandRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    branch_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


async def _resolve_item(
    db: Db, tenant_id: uuid.UUID, query: str
) -> tuple[str, uuid.UUID, Any] | None:
    """Résout un libellé libre vers un produit ou une prestation du tenant."""
    like = f"%{query}%"
    product = (
        (
            await db.execute(
                tenant_query(Product, tenant_id)
                .where(Product.archived.is_(False), Product.name.ilike(like))
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if product is not None:
        return ("product", product.id, product)
    # essaie mot par mot (ex. « parfums clarins » -> « Parfum Clarins 50ml »)
    for word in query.split():
        if len(word) < 3:
            continue
        product = (
            (
                await db.execute(
                    tenant_query(Product, tenant_id)
                    .where(Product.archived.is_(False), Product.name.ilike(f"%{word}%"))
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if product is not None:
            return ("product", product.id, product)
    service = (
        (
            await db.execute(
                tenant_query(Service, tenant_id)
                .where(
                    Service.archived.is_(False),
                    or_(
                        *[Service.name.ilike(f"%{w}%") for w in query.split() if len(w) >= 3]
                        or [Service.name.ilike(like)]
                    ),
                )
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if service is not None:
        return ("service", service.id, service)
    return None


@router.post("/command", dependencies=[require_permissions("assistant.use")])
async def interpret_command(payload: CommandRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    """Transforme une phrase libre en proposition de vente structurée."""
    tenant_id = ctx.require_tenant()
    provider = get_ai_provider()
    intent = await provider.parse_sale(payload.text)
    if not intent.items:
        raise ValidationAppError(
            "Je n'ai pas compris les articles de cette vente. "
            "Exemple : « J'ai vendu trois parfums Clarins à 25 000 FCFA chacun. »"
        )

    conversation: AiConversation | None = None
    if payload.conversation_id:
        conversation = (
            (
                await db.execute(
                    tenant_query(AiConversation, tenant_id).where(
                        AiConversation.id == payload.conversation_id
                    )
                )
            )
            .scalars()
            .first()
        )
    if conversation is None:
        conversation = AiConversation(
            tenant_id=tenant_id, user_id=ctx.user.id, title=payload.text[:80]
        )
        db.add(conversation)
        await db.flush()
    db.add(
        AiMessage(
            tenant_id=tenant_id, conversation_id=conversation.id, role="user", content=payload.text
        )
    )

    resolved_items: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for item in intent.items:
        match = await _resolve_item(db, tenant_id, item["query"])
        if match is None:
            unresolved.append(item["query"])
            continue
        kind, entity_id, entity = match
        unit_price = item["unit_price"]
        if unit_price is None:
            unit_price = entity.selling_price if kind == "product" else entity.price
        resolved_items.append(
            {
                "item_type": kind,
                "product_id": str(entity_id) if kind == "product" else None,
                "service_id": str(entity_id) if kind == "service" else None,
                "label": entity.name,
                "quantity": str(item["quantity"]),
                "unit_price": str(unit_price),
            }
        )
    if not resolved_items:
        raise ValidationAppError(
            "Aucun article de votre catalogue ne correspond",
            details={"unresolved": unresolved},
        )

    sale_payload: dict[str, Any] = {
        "branch_id": str(payload.branch_id),
        "customer_id": str(payload.customer_id) if payload.customer_id else None,
        "items": resolved_items,
        "payments": [{"method": p["method"], "amount": str(p["amount"])} for p in intent.payments],
        "status": "completed",
    }
    total = sum(
        __import__("decimal").Decimal(i["unit_price"])
        * __import__("decimal").Decimal(i["quantity"])
        for i in resolved_items
    )
    paid = sum(__import__("decimal").Decimal(p["amount"]) for p in intent.payments)

    proposal = AiActionProposal(
        tenant_id=tenant_id,
        conversation_id=conversation.id,
        user_id=ctx.user.id,
        action_type="create_sale",
        payload=sale_payload,
    )
    db.add(proposal)
    await db.flush()

    summary = (
        f"Proposition de vente : {len(resolved_items)} article(s), total estimé {total:,.0f}, "
        f"payé {paid:,.0f}, reste {max(total - paid, 0):,.0f}. "
        "Confirmez pour enregistrer la vente."
    )
    db.add(
        AiMessage(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            role="assistant",
            content=summary,
            metadata_={"proposal_id": str(proposal.id)},
        )
    )
    return ok(
        {
            "proposal_id": str(proposal.id),
            "conversation_id": str(conversation.id),
            "action_type": "create_sale",
            "summary": summary,
            "sale": sale_payload,
            "unresolved_items": unresolved,
            "requires_confirmation": True,
        },
        message="Proposition prête — confirmation requise",
    )


@router.post("/proposals/{proposal_id}/confirm", dependencies=[require_permissions("sales.create")])
async def confirm_proposal(proposal_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    """Exécute une proposition APRÈS confirmation explicite de l'utilisateur."""
    tenant_id = ctx.require_tenant()
    proposal = (
        (
            await db.execute(
                tenant_query(AiActionProposal, tenant_id).where(AiActionProposal.id == proposal_id)
            )
        )
        .scalars()
        .first()
    )
    if proposal is None:
        raise NotFoundError("Proposition introuvable")
    if proposal.status != "proposed":
        raise BusinessRuleError(f"Cette proposition est déjà {proposal.status}")
    if proposal.user_id != ctx.user.id:
        raise BusinessRuleError("Seul l'auteur de la demande peut confirmer cette proposition")

    proposal.status = "confirmed"
    proposal.confirmed_at = datetime.now(UTC)
    try:
        if proposal.action_type == "create_sale":
            sale = await sales_service.create_sale(
                db,
                tenant_id=tenant_id,
                user=ctx.user,
                payload=SaleCreate.model_validate(proposal.payload),
                require_cash_session=False,
            )
            proposal.status = "executed"
            proposal.executed_at = datetime.now(UTC)
            proposal.result_reference = str(sale.id)
            return ok(
                {"sale_id": str(sale.id), "number": sale.number, "total": str(sale.total)},
                message="Vente enregistrée",
            )
        raise BusinessRuleError("Type d'action non supporté")
    except Exception:
        proposal.status = "failed"
        raise


@router.post("/proposals/{proposal_id}/reject", dependencies=[require_permissions("assistant.use")])
async def reject_proposal(proposal_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    proposal = (
        (
            await db.execute(
                tenant_query(AiActionProposal, tenant_id).where(AiActionProposal.id == proposal_id)
            )
        )
        .scalars()
        .first()
    )
    if proposal is None:
        raise NotFoundError("Proposition introuvable")
    if proposal.status != "proposed":
        raise BusinessRuleError(f"Cette proposition est déjà {proposal.status}")
    proposal.status = "rejected"
    return ok(message="Proposition rejetée")


@router.post("/ask", dependencies=[require_permissions("assistant.use")])
async def ask_question(payload: QuestionRequest, db: Db, ctx: Ctx) -> dict[str, Any]:
    """Répond aux questions sur les données de l'entreprise (contexte tenant uniquement)."""
    from nzassa.modules.reports.router import dashboard as dashboard_endpoint
    from nzassa.modules.reports.router import top_products as top_products_endpoint

    dashboard_data = (await dashboard_endpoint(db, ctx))["data"]
    top = (await top_products_endpoint(db, ctx))["data"]
    provider = get_ai_provider()
    answer = await provider.answer(
        payload.question,
        {
            "dashboard": dashboard_data,
            "top_products": top,
            "low_stock_count": dashboard_data["low_stock_count"],
        },
    )
    return ok({"answer": answer})
