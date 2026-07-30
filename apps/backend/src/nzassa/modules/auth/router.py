"""Endpoints d'authentification."""

import uuid
from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from nzassa.core.deps import Ctx, Db
from nzassa.core.responses import ok
from nzassa.models.auth import DeviceSession
from nzassa.modules.auth import service
from nzassa.modules.auth.schemas import (
    AuthResult,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SessionOut,
    TokenPair,
    UserOut,
    VerifyOtpRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_info(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    return ip, request.headers.get("User-Agent")


@router.post("/register", status_code=201)
async def register(payload: RegisterRequest, request: Request, db: Db) -> dict[str, Any]:
    tenant, user = await service.register_tenant(db, payload)
    ip, ua = _client_info(request)
    _, _, tokens = await service.login(
        db,
        LoginRequest(email=payload.email, password=payload.password),
        ip_address=ip,
        user_agent=ua,
    )
    return ok(
        {
            "tenant_id": str(tenant.id),
            "user": UserOut.model_validate(user).model_dump(mode="json"),
            "tokens": tokens.model_dump(),
        },
        message="Compte créé avec succès",
    )


@router.post("/login")
async def login(payload: LoginRequest, request: Request, db: Db) -> dict[str, Any]:
    ip, ua = _client_info(request)
    user, _session, tokens = await service.login(db, payload, ip_address=ip, user_agent=ua)
    from nzassa.core.deps import _load_permissions

    permissions = sorted(await _load_permissions(db, user.id))
    result = AuthResult(user=UserOut.model_validate(user), tokens=tokens, permissions=permissions)
    return ok(result.model_dump(mode="json"), message="Connexion réussie")


@router.post("/refresh")
async def refresh(payload: RefreshRequest, db: Db) -> dict[str, Any]:
    _user, tokens = await service.refresh_tokens(db, payload.refresh_token)
    return ok(TokenPair.model_validate(tokens).model_dump())


@router.post("/logout")
async def logout(payload: LogoutRequest, ctx: Ctx, db: Db) -> dict[str, Any]:
    await service.logout(db, ctx.user, ctx.session_id, payload.refresh_token)
    return ok(message="Déconnexion réussie")


@router.get("/me")
async def me(ctx: Ctx) -> dict[str, Any]:
    return ok(
        {
            "user": UserOut.model_validate(ctx.user).model_dump(mode="json"),
            "permissions": sorted(ctx.permissions),
            "tenant_id": str(ctx.tenant_id) if ctx.tenant_id else None,
        }
    )


@router.get("/sessions")
async def list_sessions(ctx: Ctx, db: Db) -> dict[str, Any]:
    sessions = (
        (
            await db.execute(
                select(DeviceSession)
                .where(DeviceSession.user_id == ctx.user.id)
                .order_by(DeviceSession.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return ok([SessionOut.model_validate(s).model_dump(mode="json") for s in sessions])


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: uuid.UUID, ctx: Ctx, db: Db) -> dict[str, Any]:
    await service.revoke_session(db, ctx.user, session_id)
    return ok(message="Session révoquée")


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, db: Db) -> dict[str, Any]:
    await service.forgot_password(db, payload.email)
    return ok(message="Si un compte existe, un email de réinitialisation a été envoyé")


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, db: Db) -> dict[str, Any]:
    await service.reset_password(db, payload.token, payload.new_password)
    return ok(message="Mot de passe réinitialisé")


@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, ctx: Ctx, db: Db) -> dict[str, Any]:
    await service.change_password(db, ctx.user, payload.current_password, payload.new_password)
    return ok(message="Mot de passe modifié")


@router.post("/verify-email")
async def verify_email(payload: VerifyOtpRequest, ctx: Ctx, db: Db) -> dict[str, Any]:
    await service.verify_email(db, ctx.user, payload.code)
    return ok(message="Email vérifié")


@router.post("/verify-email/resend")
async def resend_verification(ctx: Ctx, db: Db) -> dict[str, Any]:
    await service.send_verification_email(db, ctx.user)
    return ok(message="Code de vérification renvoyé")


@router.post("/verify-phone/send")
async def send_phone_otp(ctx: Ctx) -> dict[str, Any]:
    await service.send_phone_otp(ctx.user)
    return ok(message="Code OTP envoyé")


@router.post("/verify-phone")
async def verify_phone(payload: VerifyOtpRequest, ctx: Ctx, db: Db) -> dict[str, Any]:
    await service.verify_phone(ctx.user, payload.code)
    return ok(message="Téléphone vérifié")
