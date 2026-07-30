"""Assistant intelligent : conversations, messages, propositions d'action."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from nzassa.models.base import Base, TenantMixin, TimestampMixin, UUIDPkMixin


class AiConversation(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "ai_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(default=None)


class AiMessage(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    __tablename__ = "ai_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column()  # user | assistant
    content: Mapped[str] = mapped_column()
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class AiActionProposal(Base, UUIDPkMixin, TenantMixin, TimestampMixin):
    """Proposition d'action structurée par l'assistant.

    JAMAIS exécutée sans confirmation explicite de l'utilisateur.
    """

    __tablename__ = "ai_action_proposals"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action_type: Mapped[str] = mapped_column()  # create_sale | create_expense | ...
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(default="proposed", index=True)
    # proposed | confirmed | rejected | executed | failed
    confirmed_at: Mapped[datetime | None] = mapped_column(default=None)
    executed_at: Mapped[datetime | None] = mapped_column(default=None)
    result_reference: Mapped[str | None] = mapped_column(default=None)
