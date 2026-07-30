"""Schémas utilisateurs / employés / rôles."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class InviteUserRequest(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str | None = None
    role_code: str = Field(pattern="^(admin|manager|cashier|seller|employee|accountant|viewer)$")
    branch_id: uuid.UUID | None = None
    job_title: str | None = None
    # En développement le mot de passe initial est généré et renvoyé ;
    # en production un email d'invitation est envoyé.
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UpdateMemberRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    role_code: str | None = Field(
        default=None, pattern="^(admin|manager|cashier|seller|employee|accountant|viewer)$"
    )
    branch_id: uuid.UUID | None = None
    job_title: str | None = None
    is_active: bool | None = None


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    phone: str | None
    first_name: str
    last_name: str
    is_active: bool
    last_login_at: datetime | None
    roles: list[str] = []
    employee_id: uuid.UUID | None = None
    job_title: str | None = None
    branch_id: uuid.UUID | None = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    business_id: uuid.UUID
    branch_id: uuid.UUID | None
    user_id: uuid.UUID | None
    first_name: str
    last_name: str
    phone: str | None
    email: str | None
    job_title: str | None
    hired_on: date | None
    status: str
    can_receive_commissions: bool


class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str | None = None
    email: EmailStr | None = None
    branch_id: uuid.UUID | None = None
    job_title: str | None = None
    hired_on: date | None = None
    can_receive_commissions: bool = True


class EmployeeUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    branch_id: uuid.UUID | None = None
    job_title: str | None = None
    hired_on: date | None = None
    status: str | None = Field(default=None, pattern="^(active|suspended|left)$")
    can_receive_commissions: bool | None = None
