"""init crm schema

Revision ID: 0001_init_crm
Revises:
Create Date: 2026-09-01

The initial migration builds every CRM table straight from the SQLAlchemy
models, so the schema is guaranteed to match ``app/db/models.py`` on any
dialect (JSONB on Postgres, JSON elsewhere). Later migrations use normal
``alembic revision --autogenerate``.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_init_crm"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "organizations",
    "org_memberships",
    "companies",
    "contacts",
    "deals",
    "call_records",
    "activities",
)


def upgrade() -> None:
    from app.db import Base
    from app.db import models  # noqa: F401 -- register tables on the metadata

    bind = op.get_bind()
    Base.metadata.create_all(bind, tables=[Base.metadata.tables[t] for t in _TABLES])


def downgrade() -> None:
    from app.db import Base
    from app.db import models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind, tables=[Base.metadata.tables[t] for t in reversed(_TABLES)])
