"""OAuthAccount model — links a user to a Google/GitHub identity.

One row per (user, provider) link. A user can link multiple providers
(one row each); a given provider identity can only ever link to one user.
"""
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base


class OAuthAccount(Base):
    __tablename__ = "oauth_accounts"
    __table_args__ = (
        # One provider identity links to exactly one user.
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_identity"),
        # A user can't link the same provider twice.
        UniqueConstraint("user_id", "provider", name="uq_oauth_user_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # google | github
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
