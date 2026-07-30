"""Règles métier des ventes — TOUS les calculs financiers vivent ici, en Decimal."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from nzassa.core.audit import record_audit
from nzassa.core.errors import (
    BusinessRuleError,
    CashSessionRequiredError,
    ConflictError,
    NotFoundError,
)
from nzassa.core.money import ZERO, money
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.auth import User
from nzassa.models.business import Branch, Employee
from nzassa.models.catalog import Product, Service, Tax
from nzassa.models.commissions import EmployeeCommission, EmployeeCommissionRule
from nzassa.models.customers import Customer, CustomerDebt, LoyaltyAccount, LoyaltyTransaction
from nzassa.models.inventory import StockMovement
from nzassa.models.sales import CashMovement, CashSession, Payment, Refund, Sale, SaleItem
from nzassa.modules.inventory import service as stock_service
from nzassa.modules.sales.schemas import PaymentIn, RefundRequest, SaleCreate

LOYALTY_POINTS_PER_UNIT = Decimal("1000")  # 1 point par 1000 (devise du tenant)


async def _next_sale_number(db: AsyncSession, tenant_id: uuid.UUID) -> str:
    """Numérotation séquentielle par tenant, protégée par un verrou advisory."""
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"sale_number:{tenant_id}"},
    )
    count = (
        await db.execute(select(func.count()).select_from(Sale).where(Sale.tenant_id == tenant_id))
    ).scalar_one()
    year = datetime.now(UTC).year
    return f"V-{year}-{count + 1:06d}"


async def _open_session_for_branch(
    db: AsyncSession, tenant_id: uuid.UUID, branch_id: uuid.UUID
) -> CashSession | None:
    return (
        (
            await db.execute(
                tenant_query(CashSession, tenant_id).where(
                    CashSession.branch_id == branch_id, CashSession.status == "open"
                )
            )
        )
        .scalars()
        .first()
    )


async def _find_commission_rule(
    db: AsyncSession, tenant_id: uuid.UUID, item: SaleItem
) -> EmployeeCommissionRule | None:
    """Règle la plus spécifique : produit/prestation > catégorie > générale."""
    rules = (
        (
            await db.execute(
                tenant_query(EmployeeCommissionRule, tenant_id).where(
                    EmployeeCommissionRule.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    candidates: list[tuple[int, EmployeeCommissionRule]] = []
    for rule in rules:
        if rule.employee_id is not None and rule.employee_id != item.employee_id:
            continue
        if (rule.scope == "product" and rule.product_id == item.product_id and item.product_id) or (
            rule.scope == "service" and rule.service_id == item.service_id and item.service_id
        ):
            candidates.append((3, rule))
        elif rule.scope == "all":
            candidates.append((1, rule))
    if not candidates:
        return None
    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return candidates[0][1]


async def _accrue_commission(
    db: AsyncSession, tenant_id: uuid.UUID, sale: Sale, item: SaleItem
) -> None:
    if item.employee_id is None:
        return
    employee = await db.get(Employee, item.employee_id)
    if employee is None or not employee.can_receive_commissions:
        return
    rule = await _find_commission_rule(db, tenant_id, item)
    if rule is None:
        return
    if rule.commission_type == "percent" and rule.rate is not None:
        amount = money(item.line_total * rule.rate)
    elif rule.commission_type == "fixed" and rule.fixed_amount is not None:
        amount = money(rule.fixed_amount * item.quantity)
    else:
        return
    if amount <= 0:
        return
    db.add(
        EmployeeCommission(
            tenant_id=tenant_id,
            employee_id=item.employee_id,
            sale_id=sale.id,
            sale_item_id=item.id,
            rule_id=rule.id,
            base_amount=item.line_total,
            amount=amount,
            period_date=date.today(),
        )
    )


async def _award_loyalty(db: AsyncSession, tenant_id: uuid.UUID, sale: Sale) -> None:
    if sale.customer_id is None or sale.total <= 0:
        return
    points = int(sale.total // LOYALTY_POINTS_PER_UNIT)
    if points <= 0:
        return
    account = (
        (
            await db.execute(
                tenant_query(LoyaltyAccount, tenant_id).where(
                    LoyaltyAccount.customer_id == sale.customer_id
                )
            )
        )
        .scalars()
        .first()
    )
    if account is None:
        account = LoyaltyAccount(tenant_id=tenant_id, customer_id=sale.customer_id)
        db.add(account)
        await db.flush()
    account.points_balance += points
    account.lifetime_points += points
    if account.lifetime_points >= 500:
        account.tier = "gold"
    elif account.lifetime_points >= 100:
        account.tier = "silver"
    db.add(
        LoyaltyTransaction(
            tenant_id=tenant_id,
            account_id=account.id,
            points=points,
            transaction_type="earn",
            reference_type="sale",
            reference_id=sale.id,
        )
    )


async def create_sale(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user: User,
    payload: SaleCreate,
    require_cash_session: bool = True,
) -> Sale:
    # Idempotence offline : même client_reference -> renvoie la vente existante
    if payload.client_reference:
        existing = (
            (
                await db.execute(
                    tenant_query(Sale, tenant_id).where(
                        Sale.client_reference == payload.client_reference
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            await db.refresh(existing, ["items", "payments"])
            return existing  # type: ignore[no-any-return]

    await get_tenant_entity(db, Branch, payload.branch_id, tenant_id)
    if payload.customer_id is not None:
        await get_tenant_entity(db, Customer, payload.customer_id, tenant_id)

    session = await _open_session_for_branch(db, tenant_id, payload.branch_id)
    has_cash_payment = any(p.method == "cash" for p in payload.payments)
    if (
        payload.status == "completed"
        and has_cash_payment
        and require_cash_session
        and session is None
    ):
        raise CashSessionRequiredError()

    sale = Sale(
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        customer_id=payload.customer_id,
        cash_session_id=session.id if session else None,
        seller_employee_id=payload.seller_employee_id,
        number=await _next_sale_number(db, tenant_id),
        client_reference=payload.client_reference,
        status="draft",
        sold_at=payload.sold_at or datetime.now(UTC),
        notes=payload.notes,
        created_by=user.id,
    )
    db.add(sale)
    await db.flush()

    subtotal = ZERO
    tax_total = ZERO
    for item_in in payload.items:
        label: str
        tax_rate = Decimal("0")
        if item_in.item_type == "product":
            if item_in.product_id is None:
                raise BusinessRuleError("product_id requis pour une ligne produit")
            product = await get_tenant_entity(db, Product, item_in.product_id, tenant_id)
            if not product.is_active or product.archived:
                raise BusinessRuleError(f"Produit indisponible : {product.name}")
            catalog_price = (
                product.promo_price if product.promo_price is not None else product.selling_price
            )
            label = product.name
            tax_obj = await db.get(Tax, product.tax_id) if product.tax_id else None
            if tax_obj is not None and tax_obj.is_active:
                tax_rate = Decimal(tax_obj.rate)
        else:
            if item_in.service_id is None:
                raise BusinessRuleError("service_id requis pour une ligne prestation")
            service = await get_tenant_entity(db, Service, item_in.service_id, tenant_id)
            if not service.is_active or service.archived:
                raise BusinessRuleError(f"Prestation indisponible : {service.name}")
            catalog_price = (
                service.promo_price if service.promo_price is not None else service.price
            )
            label = service.name
            tax_obj = await db.get(Tax, service.tax_id) if service.tax_id else None
            if tax_obj is not None and tax_obj.is_active:
                tax_rate = Decimal(tax_obj.rate)

        unit_price = money(item_in.unit_price if item_in.unit_price is not None else catalog_price)
        gross = money(unit_price * item_in.quantity)
        if item_in.discount_amount > gross:
            raise BusinessRuleError("La remise ligne dépasse le montant de la ligne")
        line_total = money(gross - item_in.discount_amount)
        # Taxes incluses dans le prix (norme locale) : montant informatif
        tax_amount = money(line_total * tax_rate / (1 + tax_rate)) if tax_rate > 0 else ZERO

        item = SaleItem(
            tenant_id=tenant_id,
            sale_id=sale.id,
            item_type=item_in.item_type,
            product_id=item_in.product_id,
            service_id=item_in.service_id,
            employee_id=item_in.employee_id,
            label=label,
            quantity=item_in.quantity,
            unit_price=unit_price,
            discount_amount=money(item_in.discount_amount),
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            line_total=line_total,
        )
        db.add(item)
        subtotal += line_total
        tax_total += tax_amount

    await db.flush()  # les lignes doivent exister avant la finalisation

    if payload.discount_amount > subtotal:
        raise BusinessRuleError("La remise globale dépasse le total")
    sale.subtotal = money(subtotal)
    sale.discount_amount = money(payload.discount_amount)
    sale.tax_amount = money(tax_total)
    sale.total = money(subtotal - payload.discount_amount)

    if payload.status == "draft":
        sale.amount_due = sale.total
        await db.flush()
        await db.refresh(sale, ["items", "payments"])
        return sale

    await finalize_sale(db, tenant_id=tenant_id, user=user, sale=sale, payments=payload.payments)
    await db.refresh(sale, ["items", "payments"])
    return sale


async def finalize_sale(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user: User,
    sale: Sale,
    payments: list[PaymentIn],
) -> None:
    """Valide une vente : paiements, stock, dette, fidélité, commissions."""
    await db.refresh(sale, ["items"])
    total_paid = ZERO
    now = datetime.now(UTC)
    for pay in payments:
        amount = money(pay.amount)
        total_paid += amount
        if pay.method == "credit":
            continue  # le crédit n'est pas un encaissement
        db.add(
            Payment(
                tenant_id=tenant_id,
                sale_id=sale.id,
                customer_id=sale.customer_id,
                method=pay.method,
                amount=amount,
                reference=pay.reference,
                paid_at=now,
                received_by=user.id,
            )
        )
        if pay.method == "cash" and sale.cash_session_id:
            db.add(
                CashMovement(
                    tenant_id=tenant_id,
                    session_id=sale.cash_session_id,
                    movement_type="sale",
                    amount=amount,
                    reference_type="sale",
                    reference_id=sale.id,
                )
            )

    cash_and_electronic = money(
        sum((money(p.amount) for p in payments if p.method != "credit"), ZERO)
    )
    if cash_and_electronic > sale.total:
        raise BusinessRuleError("Le montant payé dépasse le total de la vente")

    sale.amount_paid = cash_and_electronic
    sale.amount_due = money(sale.total - cash_and_electronic)

    if sale.amount_due > 0:
        if sale.customer_id is None:
            raise BusinessRuleError("Une vente à crédit nécessite un client identifié")
        customer = await db.get(Customer, sale.customer_id)
        if customer is not None and customer.credit_limit is not None:
            open_debt = (
                await db.execute(
                    select(func.coalesce(func.sum(CustomerDebt.balance), 0)).where(
                        CustomerDebt.tenant_id == tenant_id,
                        CustomerDebt.customer_id == sale.customer_id,
                        CustomerDebt.status.in_(["open", "partially_paid"]),
                    )
                )
            ).scalar_one()
            if Decimal(open_debt) + sale.amount_due > customer.credit_limit:
                raise BusinessRuleError(
                    "Limite de crédit du client dépassée",
                    details={"credit_limit": str(customer.credit_limit)},
                )
        db.add(
            CustomerDebt(
                tenant_id=tenant_id,
                customer_id=sale.customer_id,
                sale_id=sale.id,
                original_amount=sale.amount_due,
                balance=sale.amount_due,
                created_by=user.id,
            )
        )

    # Déduction de stock
    for item in sale.items:
        if item.item_type == "product" and item.product_id is not None:
            product = await db.get(Product, item.product_id)
            if product is not None:
                await stock_service.deduct_for_sale(
                    db,
                    tenant_id=tenant_id,
                    branch_id=sale.branch_id,
                    product=product,
                    quantity=item.quantity,
                    sale_id=sale.id,
                    performed_by=user.id,
                )
        await _accrue_commission(db, tenant_id, sale, item)

    sale.status = "completed"
    await _award_loyalty(db, tenant_id, sale)
    await record_audit(
        db,
        action="sales.complete",
        tenant_id=tenant_id,
        user_id=user.id,
        entity_type="sale",
        entity_id=sale.id,
        after={"number": sale.number, "total": str(sale.total)},
    )
    await db.flush()


async def add_payments(
    db: AsyncSession, *, tenant_id: uuid.UUID, user: User, sale: Sale, payments: list[PaymentIn]
) -> Sale:
    """Règlement (partiel) du solde d'une vente à crédit."""
    if sale.status != "completed":
        raise BusinessRuleError("Seule une vente validée peut recevoir un paiement")
    if sale.amount_due <= 0:
        raise BusinessRuleError("Cette vente est déjà soldée")
    incoming = money(sum((money(p.amount) for p in payments), ZERO))
    if incoming > sale.amount_due:
        raise BusinessRuleError(
            "Le paiement dépasse le solde dû", details={"amount_due": str(sale.amount_due)}
        )
    now = datetime.now(UTC)
    session = await _open_session_for_branch(db, tenant_id, sale.branch_id)
    for pay in payments:
        if pay.method == "credit":
            raise BusinessRuleError("Le crédit n'est pas un moyen de règlement")
        db.add(
            Payment(
                tenant_id=tenant_id,
                sale_id=sale.id,
                customer_id=sale.customer_id,
                method=pay.method,
                amount=money(pay.amount),
                reference=pay.reference,
                paid_at=now,
                received_by=user.id,
            )
        )
        if pay.method == "cash" and session is not None:
            db.add(
                CashMovement(
                    tenant_id=tenant_id,
                    session_id=session.id,
                    movement_type="sale",
                    amount=money(pay.amount),
                    reference_type="sale",
                    reference_id=sale.id,
                )
            )
    sale.amount_paid = money(sale.amount_paid + incoming)
    sale.amount_due = money(sale.amount_due - incoming)

    # Mise à jour de la dette liée
    debt = (
        (
            await db.execute(
                tenant_query(CustomerDebt, tenant_id).where(CustomerDebt.sale_id == sale.id)
            )
        )
        .scalars()
        .first()
    )
    if debt is not None:
        from nzassa.models.customers import DebtPayment

        debt.balance = money(debt.balance - incoming)
        for pay in payments:
            db.add(
                DebtPayment(
                    tenant_id=tenant_id,
                    debt_id=debt.id,
                    amount=money(pay.amount),
                    method=pay.method,
                    paid_at=now,
                    received_by=user.id,
                    reference=pay.reference,
                )
            )
        debt.status = "paid" if debt.balance <= 0 else "partially_paid"
    await record_audit(
        db,
        action="sales.payment",
        tenant_id=tenant_id,
        user_id=user.id,
        entity_type="sale",
        entity_id=sale.id,
        after={"amount": str(incoming)},
    )
    await db.flush()
    await db.refresh(sale, ["items", "payments"])
    return sale


async def cancel_sale(
    db: AsyncSession, *, tenant_id: uuid.UUID, user: User, sale: Sale, reason: str
) -> Sale:
    """Annulation avec état précédent, compensations de stock et de caisse."""
    if sale.status not in ("draft", "completed"):
        raise ConflictError("Cette vente ne peut plus être annulée")
    previous = {
        "status": sale.status,
        "total": str(sale.total),
        "amount_paid": str(sale.amount_paid),
        "amount_due": str(sale.amount_due),
    }
    now = datetime.now(UTC)
    if sale.status == "completed":
        await db.refresh(sale, ["items"])
        for item in sale.items:
            if item.item_type == "product" and item.product_id is not None:
                remaining = item.quantity - item.refunded_quantity
                if remaining > 0:
                    await stock_service.restock_for_reversal(
                        db,
                        tenant_id=tenant_id,
                        branch_id=sale.branch_id,
                        product_id=item.product_id,
                        quantity=remaining,
                        reference_type="sale_cancellation",
                        reference_id=sale.id,
                        performed_by=user.id,
                        reason=f"Annulation vente {sale.number}",
                    )
        # Contre-passation caisse pour les paiements espèces
        if sale.cash_session_id and sale.amount_paid > 0:
            cash_paid = money(
                sum(
                    (money(p.amount) for p in sale.payments if p.method == "cash"),
                    ZERO,
                )
            )
            if cash_paid > 0:
                db.add(
                    CashMovement(
                        tenant_id=tenant_id,
                        session_id=sale.cash_session_id,
                        movement_type="refund",
                        amount=-cash_paid,
                        reference_type="sale_cancellation",
                        reference_id=sale.id,
                    )
                )
        for payment in sale.payments:
            payment.status = "reversed"
        # Annule la dette éventuelle
        debt = (
            (
                await db.execute(
                    tenant_query(CustomerDebt, tenant_id).where(CustomerDebt.sale_id == sale.id)
                )
            )
            .scalars()
            .first()
        )
        if debt is not None and debt.status in ("open", "partially_paid"):
            debt.balance = ZERO
            debt.status = "paid"
        # Annule les commissions non validées
        commissions = (
            (
                await db.execute(
                    tenant_query(EmployeeCommission, tenant_id).where(
                        EmployeeCommission.sale_id == sale.id,
                        EmployeeCommission.status == "pending",
                    )
                )
            )
            .scalars()
            .all()
        )
        for commission in commissions:
            commission.status = "cancelled"

    sale.status = "cancelled"
    sale.cancelled_at = now
    sale.cancelled_by = user.id
    sale.cancellation_reason = reason
    sale.previous_state = previous
    await record_audit(
        db,
        action="sales.cancel",
        tenant_id=tenant_id,
        user_id=user.id,
        entity_type="sale",
        entity_id=sale.id,
        before=previous,
        after={"reason": reason},
    )
    await db.flush()
    return sale


async def refund_sale(
    db: AsyncSession, *, tenant_id: uuid.UUID, user: User, sale: Sale, payload: RefundRequest
) -> Refund:
    if sale.status not in ("completed", "partially_refunded"):
        raise BusinessRuleError("Seule une vente validée peut être remboursée")
    await db.refresh(sale, ["items"])
    items_by_id = {item.id: item for item in sale.items}
    refund_total = ZERO
    refund_items = []
    for entry in payload.items:
        item = items_by_id.get(entry.sale_item_id)
        if item is None:
            raise NotFoundError("Ligne de vente introuvable")
        refundable = item.quantity - item.refunded_quantity
        if entry.quantity > refundable:
            raise BusinessRuleError(
                "Quantité à rembourser supérieure à la quantité restante",
                details={"sale_item_id": str(item.id), "refundable": str(refundable)},
            )
        unit_net = money(item.line_total / item.quantity)
        refund_total += money(unit_net * entry.quantity)
        item.refunded_quantity = item.refunded_quantity + entry.quantity
        refund_items.append({"sale_item_id": str(item.id), "quantity": str(entry.quantity)})
        if payload.restock and item.item_type == "product" and item.product_id is not None:
            await stock_service.restock_for_reversal(
                db,
                tenant_id=tenant_id,
                branch_id=sale.branch_id,
                product_id=item.product_id,
                quantity=entry.quantity,
                reference_type="refund",
                reference_id=sale.id,
                performed_by=user.id,
                reason=f"Remboursement vente {sale.number}",
            )

    refund_total = money(min(refund_total, sale.amount_paid))
    refund = Refund(
        tenant_id=tenant_id,
        sale_id=sale.id,
        amount=refund_total,
        method=payload.method,
        reason=payload.reason,
        refunded_at=datetime.now(UTC),
        refunded_by=user.id,
        restock=payload.restock,
        items=refund_items,
        created_by=user.id,
    )
    db.add(refund)
    if payload.method == "cash" and sale.cash_session_id:
        db.add(
            CashMovement(
                tenant_id=tenant_id,
                session_id=sale.cash_session_id,
                movement_type="refund",
                amount=-refund_total,
                reference_type="refund",
                reference_id=sale.id,
            )
        )
    fully_refunded = all(item.refunded_quantity >= item.quantity for item in sale.items)
    sale.status = "refunded" if fully_refunded else "partially_refunded"
    await record_audit(
        db,
        action="sales.refund",
        tenant_id=tenant_id,
        user_id=user.id,
        entity_type="sale",
        entity_id=sale.id,
        after={"amount": str(refund_total), "reason": payload.reason},
    )
    await db.flush()
    return refund


__all__ = ["StockMovement"]
