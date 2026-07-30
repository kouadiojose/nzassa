"""Endpoints rendez-vous : calendrier, statuts, conflits, conversion en vente."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select

from nzassa.core.audit import record_audit
from nzassa.core.deps import Ctx, Db, require_permissions
from nzassa.core.errors import BusinessRuleError, ConflictError
from nzassa.core.pagination import PageParams, page_params, paginate
from nzassa.core.responses import ok
from nzassa.core.tenancy import get_tenant_entity, tenant_query
from nzassa.models.appointments import APPOINTMENT_STATUSES, Appointment, AppointmentService
from nzassa.models.business import Branch, Employee
from nzassa.models.catalog import Service
from nzassa.models.customers import Customer
from nzassa.modules.sales import service as sales_service
from nzassa.modules.sales.schemas import SaleCreate, SaleItemIn

router = APIRouter(prefix="/appointments", tags=["appointments"])

Page = Annotated[PageParams, Depends(page_params)]

# Transitions autorisées entre statuts
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"confirmed", "cancelled", "no_show"},
    "confirmed": {"arrived", "cancelled", "no_show", "pending"},
    "arrived": {"in_progress", "cancelled"},
    "in_progress": {"completed"},
    "completed": set(),
    "cancelled": set(),
    "no_show": set(),
}


class AppointmentCreate(BaseModel):
    branch_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    employee_id: uuid.UUID | None = None
    starts_at: datetime
    service_ids: list[uuid.UUID] = Field(min_length=1)
    notes: str | None = None


class AppointmentReschedule(BaseModel):
    starts_at: datetime


class AppointmentStatusUpdate(BaseModel):
    status: str = Field(pattern=f"^({'|'.join(APPOINTMENT_STATUSES)})$")
    reason: str | None = None


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    branch_id: uuid.UUID
    customer_id: uuid.UUID | None
    employee_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    status: str
    notes: str | None
    sale_id: uuid.UUID | None


async def _check_conflict(
    db: Db,
    tenant_id: uuid.UUID,
    employee_id: uuid.UUID | None,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if employee_id is None:
        return
    query = tenant_query(Appointment, tenant_id).where(
        Appointment.employee_id == employee_id,
        Appointment.status.in_(["pending", "confirmed", "arrived", "in_progress"]),
        and_(Appointment.starts_at < ends_at, Appointment.ends_at > starts_at),
    )
    if exclude_id:
        query = query.where(Appointment.id != exclude_id)
    if (await db.execute(query.limit(1))).first():
        raise ConflictError("Conflit d'horaires : l'employé a déjà un rendez-vous sur ce créneau")


@router.get("", dependencies=[require_permissions("appointments.read")])
async def list_appointments(
    db: Db,
    ctx: Ctx,
    params: Page,
    branch_id: uuid.UUID | None = None,
    employee_id: uuid.UUID | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    query = tenant_query(Appointment, ctx.require_tenant())
    if branch_id:
        query = query.where(Appointment.branch_id == branch_id)
    if employee_id:
        query = query.where(Appointment.employee_id == employee_id)
    if status:
        query = query.where(Appointment.status == status)
    if date_from:
        query = query.where(Appointment.starts_at >= date_from)
    if date_to:
        query = query.where(Appointment.starts_at < date_to)
    items, meta = await paginate(db, query, params, default_sort=Appointment.starts_at)
    return ok([AppointmentOut.model_validate(a).model_dump(mode="json") for a in items], **meta)


@router.post("", status_code=201, dependencies=[require_permissions("appointments.create")])
async def create_appointment(payload: AppointmentCreate, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    await get_tenant_entity(db, Branch, payload.branch_id, tenant_id)
    if payload.customer_id:
        await get_tenant_entity(db, Customer, payload.customer_id, tenant_id)
    if payload.employee_id:
        await get_tenant_entity(db, Employee, payload.employee_id, tenant_id)

    total_minutes = 0
    services: list[Service] = []
    for service_id in payload.service_ids:
        service = await get_tenant_entity(db, Service, service_id, tenant_id)
        services.append(service)
        total_minutes += service.duration_minutes
    ends_at = payload.starts_at + timedelta(minutes=max(total_minutes, 5))

    await _check_conflict(db, tenant_id, payload.employee_id, payload.starts_at, ends_at)

    appointment = Appointment(
        tenant_id=tenant_id,
        branch_id=payload.branch_id,
        customer_id=payload.customer_id,
        employee_id=payload.employee_id,
        starts_at=payload.starts_at,
        ends_at=ends_at,
        notes=payload.notes,
        created_by=ctx.user.id,
    )
    db.add(appointment)
    await db.flush()
    for service in services:
        db.add(
            AppointmentService(
                tenant_id=tenant_id,
                appointment_id=appointment.id,
                service_id=service.id,
                duration_minutes=service.duration_minutes,
            )
        )
    await record_audit(
        db,
        action="appointments.create",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        entity_type="appointment",
        entity_id=appointment.id,
    )
    return ok(
        AppointmentOut.model_validate(appointment).model_dump(mode="json"),
        message="Rendez-vous créé",
    )


@router.post("/{appointment_id}/status", dependencies=[require_permissions("appointments.update")])
async def update_status(
    appointment_id: uuid.UUID, payload: AppointmentStatusUpdate, db: Db, ctx: Ctx
) -> dict[str, Any]:
    appointment = await get_tenant_entity(db, Appointment, appointment_id, ctx.require_tenant())
    allowed = ALLOWED_TRANSITIONS.get(appointment.status, set())
    if payload.status not in allowed:
        raise BusinessRuleError(
            f"Transition invalide : {appointment.status} -> {payload.status}",
            details={"allowed": sorted(allowed)},
        )
    appointment.status = payload.status
    if payload.status == "cancelled":
        appointment.cancelled_reason = payload.reason
    appointment.updated_by = ctx.user.id
    return ok(AppointmentOut.model_validate(appointment).model_dump(mode="json"))


@router.post(
    "/{appointment_id}/reschedule", dependencies=[require_permissions("appointments.update")]
)
async def reschedule(
    appointment_id: uuid.UUID, payload: AppointmentReschedule, db: Db, ctx: Ctx
) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    appointment = await get_tenant_entity(db, Appointment, appointment_id, tenant_id)
    if appointment.status in ("completed", "cancelled", "no_show"):
        raise BusinessRuleError("Ce rendez-vous ne peut plus être reporté")
    duration = appointment.ends_at - appointment.starts_at
    new_end = payload.starts_at + duration
    await _check_conflict(
        db,
        tenant_id,
        appointment.employee_id,
        payload.starts_at,
        new_end,
        exclude_id=appointment.id,
    )
    appointment.starts_at = payload.starts_at
    appointment.ends_at = new_end
    appointment.status = "pending"
    appointment.updated_by = ctx.user.id
    return ok(
        AppointmentOut.model_validate(appointment).model_dump(mode="json"),
        message="Rendez-vous reporté",
    )


@router.post(
    "/{appointment_id}/convert-to-sale", dependencies=[require_permissions("sales.create")]
)
async def convert_to_sale(appointment_id: uuid.UUID, db: Db, ctx: Ctx) -> dict[str, Any]:
    tenant_id = ctx.require_tenant()
    appointment = await get_tenant_entity(db, Appointment, appointment_id, tenant_id)
    if appointment.sale_id is not None:
        raise ConflictError("Ce rendez-vous a déjà été converti en vente")
    if appointment.status not in ("arrived", "in_progress", "completed"):
        raise BusinessRuleError("Le client doit être présent pour convertir en vente")

    services = (
        (
            await db.execute(
                select(AppointmentService).where(
                    AppointmentService.appointment_id == appointment.id
                )
            )
        )
        .scalars()
        .all()
    )
    sale = await sales_service.create_sale(
        db,
        tenant_id=tenant_id,
        user=ctx.user,
        payload=SaleCreate(
            branch_id=appointment.branch_id,
            customer_id=appointment.customer_id,
            seller_employee_id=appointment.employee_id,
            items=[
                SaleItemIn(
                    item_type="service",
                    service_id=s.service_id,
                    employee_id=appointment.employee_id,
                )
                for s in services
            ],
            payments=[],
            status="draft",
        ),
    )
    appointment.sale_id = sale.id
    if appointment.status != "completed":
        appointment.status = "in_progress"
    return ok(
        {"sale_id": str(sale.id), "sale_number": sale.number, "total": str(sale.total)},
        message="Brouillon de vente créé depuis le rendez-vous",
    )


_ = datetime.now(UTC)
