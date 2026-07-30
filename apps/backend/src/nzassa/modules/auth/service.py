"""Logique métier de l'authentification."""

import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nzassa.core.audit import record_audit
from nzassa.core.config import get_settings
from nzassa.core.errors import (
    AccountDisabledError,
    AccountLockedError,
    ConflictError,
    InvalidCredentialsError,
    TokenError,
    ValidationAppError,
)
from nzassa.core.logging import get_logger
from nzassa.core.rbac import get_system_role, sync_rbac
from nzassa.core.redis import get_redis
from nzassa.core.security import (
    create_access_token,
    generate_opaque_token,
    generate_otp,
    hash_password,
    hash_token,
    verify_password,
)
from nzassa.core.tasks import send_email_task
from nzassa.models.auth import DeviceSession, LoginAttempt, RefreshToken, User, UserRole
from nzassa.models.business import Branch, Business, Employee
from nzassa.models.sales import CashRegister, PaymentMethod
from nzassa.models.subscriptions import Subscription, SubscriptionPlan
from nzassa.models.tenant import Tenant
from nzassa.modules.auth.schemas import LoginRequest, RegisterRequest, TokenPair

logger = get_logger(__name__)

DEFAULT_PAYMENT_METHODS = [
    ("cash", "Espèces", False),
    ("wave", "Wave", True),
    ("orange_money", "Orange Money", True),
    ("mtn_money", "MTN Money", True),
    ("moov_money", "Moov Money", True),
    ("card", "Carte bancaire", True),
    ("bank_transfer", "Virement", True),
    ("credit", "Crédit client", False),
]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "entreprise"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    slug = _slugify(base)
    candidate = slug
    n = 1
    while (
        await db.execute(select(Tenant.id).where(Tenant.slug == candidate))
    ).scalar_one_or_none() is not None:
        n += 1
        candidate = f"{slug}-{n}"
    return candidate


async def register_tenant(db: AsyncSession, payload: RegisterRequest) -> tuple[Tenant, User]:
    """Crée tenant + entreprise + point de vente + caisse + propriétaire + essai gratuit."""
    email = payload.email.lower()
    existing = (
        await db.execute(select(User.id).where(User.email == email, User.deleted_at.is_(None)))
    ).first()
    if existing:
        raise ConflictError("Un compte existe déjà avec cet email")

    await sync_rbac(db)

    tenant = Tenant(name=payload.business_name, slug=await _unique_slug(db, payload.business_name))
    db.add(tenant)
    await db.flush()

    user = User(
        tenant_id=tenant.id,
        email=email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
    )
    db.add(user)
    await db.flush()
    tenant.owner_user_id = user.id

    owner_role = await get_system_role(db, "owner")
    db.add(UserRole(user_id=user.id, role_id=owner_role.id, tenant_id=tenant.id))

    business = Business(
        tenant_id=tenant.id,
        legal_name=payload.business_name,
        trade_name=payload.business_name,
        industry=payload.industry,
        currency=payload.currency,
        country=payload.country,
        created_by=user.id,
    )
    db.add(business)
    await db.flush()

    branch = Branch(
        tenant_id=tenant.id,
        business_id=business.id,
        code="MAIN",
        name="Point de vente principal",
        created_by=user.id,
    )
    db.add(branch)
    await db.flush()

    db.add(
        Employee(
            tenant_id=tenant.id,
            business_id=business.id,
            branch_id=branch.id,
            user_id=user.id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=email,
            job_title="Propriétaire",
        )
    )
    db.add(CashRegister(tenant_id=tenant.id, branch_id=branch.id, name="Caisse principale"))
    for code, name, requires_ref in DEFAULT_PAYMENT_METHODS:
        db.add(
            PaymentMethod(
                tenant_id=tenant.id, code=code, name=name, requires_reference=requires_ref
            )
        )

    # Essai gratuit sur le plan Essentiel
    plan = (
        await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == "essential"))
    ).scalar_one_or_none()
    if plan is not None:
        now = datetime.now(UTC)
        db.add(
            Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="trialing",
                trial_ends_at=now + timedelta(days=plan.trial_days),
                current_period_start=now,
                current_period_end=now + timedelta(days=plan.trial_days),
            )
        )

    await record_audit(
        db,
        action="auth.register",
        tenant_id=tenant.id,
        user_id=user.id,
        entity_type="tenant",
        entity_id=tenant.id,
    )
    await send_verification_email(db, user)
    return tenant, user


async def send_verification_email(db: AsyncSession, user: User) -> None:
    token = generate_otp()
    await get_redis().setex(f"email_verify:{user.id}", 3600, token)
    send_email_task.send(
        user.email, "Vérifiez votre email N'Zassa Business", f"Votre code de vérification : {token}"
    )


async def verify_email(db: AsyncSession, user: User, code: str) -> None:
    stored = await get_redis().get(f"email_verify:{user.id}")
    if stored is None or stored != code:
        raise ValidationAppError("Code de vérification invalide ou expiré")
    user.email_verified_at = datetime.now(UTC)
    await get_redis().delete(f"email_verify:{user.id}")


async def send_phone_otp(user: User) -> None:
    """OTP téléphone — simulé en développement (loggé), SMS réel via connecteur ultérieur."""
    code = generate_otp()
    await get_redis().setex(f"phone_otp:{user.id}", get_settings().otp_expire_minutes * 60, code)
    logger.info("phone_otp_simulated", user_id=str(user.id), code=code)


async def verify_phone(user: User, code: str) -> None:
    stored = await get_redis().get(f"phone_otp:{user.id}")
    if stored is None or stored != code:
        raise ValidationAppError("Code OTP invalide ou expiré")
    user.phone_verified_at = datetime.now(UTC)
    await get_redis().delete(f"phone_otp:{user.id}")


async def _issue_tokens(
    db: AsyncSession, user: User, session: DeviceSession
) -> tuple[TokenPair, RefreshToken]:
    settings = get_settings()
    access = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        session_id=session.id,
        is_superadmin=user.is_superadmin,
    )
    raw_refresh = generate_opaque_token()
    refresh = RefreshToken(
        user_id=user.id,
        session_id=session.id,
        token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(refresh)
    await db.flush()
    pair = TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        expires_in=settings.access_token_expire_minutes * 60,
    )
    return pair, refresh


async def login(
    db: AsyncSession,
    payload: LoginRequest,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, DeviceSession, TokenPair]:
    settings = get_settings()
    email = payload.email.lower()
    now = datetime.now(UTC)
    attempt = LoginAttempt(
        email=email,
        ip_address=ip_address,
        user_agent=user_agent,
        success=False,
        attempted_at=now,
    )
    db.add(attempt)
    user = (
        await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if user is None:
        await db.commit()  # trace de la tentative conservée malgré l'erreur levée
        raise InvalidCredentialsError()
    if user.locked_until is not None and user.locked_until > now:
        await db.commit()
        raise AccountLockedError(details={"locked_until": user.locked_until.isoformat()})
    if not verify_password(payload.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.max_login_attempts:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            await record_audit(
                db, action="auth.account_locked", tenant_id=user.tenant_id, user_id=user.id
            )
        # Commit indispensable : le gestionnaire de session ferait un rollback
        # sur l'exception et perdrait le compteur de tentatives.
        await db.commit()
        raise InvalidCredentialsError()
    if not user.is_active:
        await db.commit()
        raise AccountDisabledError()

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    attempt.success = True

    session = DeviceSession(
        user_id=user.id,
        tenant_id=user.tenant_id,
        device_name=payload.device_name,
        device_type=payload.device_type,
        ip_address=ip_address,
        user_agent=user_agent,
        last_seen_at=now,
    )
    db.add(session)
    await db.flush()
    tokens, _ = await _issue_tokens(db, user, session)
    await record_audit(
        db, action="auth.login", tenant_id=user.tenant_id, user_id=user.id, ip_address=ip_address
    )
    return user, session, tokens


async def refresh_tokens(db: AsyncSession, raw_token: str) -> tuple[User, TokenPair]:
    """Rotation du refresh token. La réutilisation d'un token consommé révoque la session."""
    now = datetime.now(UTC)
    token = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
        )
    ).scalar_one_or_none()
    if token is None:
        raise TokenError()
    if token.revoked_at is not None or token.used_at is not None:
        # Réutilisation détectée -> révocation de toute la session (vol probable)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.session_id == token.session_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await db.execute(
            update(DeviceSession).where(DeviceSession.id == token.session_id).values(revoked_at=now)
        )
        await record_audit(db, action="auth.refresh_reuse_detected", user_id=token.user_id)
        await db.commit()  # la révocation doit survivre à l'erreur 401
        raise TokenError("Session révoquée")
    if token.expires_at < now:
        raise TokenError("Refresh token expiré")

    session = await db.get(DeviceSession, token.session_id)
    if session is None or session.revoked_at is not None:
        raise TokenError("Session révoquée")
    user = await db.get(User, token.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise TokenError()

    token.used_at = now
    session.last_seen_at = now
    pair, new_token = await _issue_tokens(db, user, session)
    token.replaced_by_id = new_token.id
    return user, pair


async def logout(
    db: AsyncSession, user: User, session_id: uuid.UUID, raw_refresh: str | None
) -> None:
    now = datetime.now(UTC)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.session_id == session_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.execute(
        update(DeviceSession).where(DeviceSession.id == session_id).values(revoked_at=now)
    )
    await record_audit(db, action="auth.logout", tenant_id=user.tenant_id, user_id=user.id)


async def revoke_session(db: AsyncSession, user: User, session_id: uuid.UUID) -> None:
    session = await db.get(DeviceSession, session_id)
    if session is None or session.user_id != user.id:
        raise TokenError("Session introuvable")
    now = datetime.now(UTC)
    session.revoked_at = now
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.session_id == session_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await record_audit(
        db,
        action="auth.session_revoked",
        tenant_id=user.tenant_id,
        user_id=user.id,
        entity_type="device_session",
        entity_id=session_id,
    )


async def forgot_password(db: AsyncSession, email: str) -> None:
    """Toujours silencieux : ne révèle pas l'existence d'un compte."""
    user = (
        await db.execute(select(User).where(User.email == email.lower(), User.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if user is None:
        return
    raw = generate_opaque_token()
    await get_redis().setex(
        f"pwd_reset:{hash_token(raw)}",
        get_settings().password_reset_expire_minutes * 60,
        str(user.id),
    )
    send_email_task.send(
        user.email,
        "Réinitialisation de votre mot de passe",
        f"Utilisez ce token pour réinitialiser votre mot de passe : {raw}",
    )


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    key = f"pwd_reset:{hash_token(token)}"
    user_id = await get_redis().get(key)
    if user_id is None:
        raise ValidationAppError("Token de réinitialisation invalide ou expiré")
    user = await db.get(User, uuid.UUID(str(user_id)))
    if user is None:
        raise ValidationAppError("Token de réinitialisation invalide ou expiré")
    user.password_hash = hash_password(new_password)
    await get_redis().delete(key)
    # Révoque toutes les sessions existantes
    now = datetime.now(UTC)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.execute(
        update(DeviceSession)
        .where(DeviceSession.user_id == user.id, DeviceSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await record_audit(db, action="auth.password_reset", tenant_id=user.tenant_id, user_id=user.id)


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise InvalidCredentialsError("Mot de passe actuel incorrect")
    user.password_hash = hash_password(new_password)
    await record_audit(
        db, action="auth.password_changed", tenant_id=user.tenant_id, user_id=user.id
    )
