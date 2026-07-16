"""User model — sales team members / managers."""
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    # Nullable: an OAuth-only signup (Google/Microsoft/GitHub) never sets a
    # password - see api/models/oauth_account.py. Email/password signup
    # always sets this; api/services/auth.py enforces that at the point of
    # registration rather than here at the column level.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="rep")  # rep / manager / admin

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
