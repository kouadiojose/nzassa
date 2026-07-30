"""Rendez-vous."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nzassa.models.base import Base, TenantEntity

APPOINTMENT_STATUSES = (
    "pending",
    "confirmed",
    "arrived",
    "in_progress",
    "completed",
    "cancelled",
    "no_show",
)


class Appointment(Base, TenantEntity):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("ix_appointments_branch_start", "branch_id", "starts_at"),
        Index("ix_appointments_employee_start", "employee_id", "starts_at"),
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id", ondelete="RESTRICT"))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True, default=None
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"), default=None
    )
    starts_at: Mapped[datetime] = mapped_column(index=True)
    ends_at: Mapped[datetime] = mapped_column()
    status: Mapped[str] = mapped_column(default="pending", index=True)
    notes: Mapped[str | None] = mapped_column(default=None)
    sale_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales.id", ondelete="SET NULL"), default=None
    )
    reminder_sent_at: Mapped[datetime | None] = mapped_column(default=None)
    cancelled_reason: Mapped[str | None] = mapped_column(default=None)

    services: Mapped[list["AppointmentService"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan", lazy="selectin"
    )


class AppointmentService(Base, TenantEntity):
    __tablename__ = "appointment_services"

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id", ondelete="RESTRICT"))
    duration_minutes: Mapped[int] = mapped_column(default=30)

    appointment: Mapped[Appointment] = relationship(back_populates="services")
