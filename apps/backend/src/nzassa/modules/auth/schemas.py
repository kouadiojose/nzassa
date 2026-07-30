"""Schémas Pydantic du module auth."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Inscription : crée tenant, entreprise, point de vente principal et propriétaire."""

    business_name: str = Field(min_length=2, max_length=120)
    industry: str = "other"
    country: str = "CI"
    currency: str = "XOF"
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_name: str | None = None
    device_type: str = Field(default="web", pattern="^(web|android|ios)$")


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyOtpRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    email: str
    phone: str | None
    first_name: str
    last_name: str
    avatar_url: str | None
    language: str
    is_active: bool
    is_superadmin: bool
    email_verified_at: datetime | None
    phone_verified_at: datetime | None
    last_login_at: datetime | None


class AuthResult(BaseModel):
    user: UserOut
    tokens: TokenPair
    permissions: list[str]


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    device_name: str | None
    device_type: str
    ip_address: str | None
    last_seen_at: datetime | None
    created_at: datetime
    revoked_at: datetime | None
