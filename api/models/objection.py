"""Objection model — playbook of objections and responses."""
import uuid

from sqlalchemy import String, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.models.base import Base


class Objection(Base):
    __tablename__ = "objections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    success_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
