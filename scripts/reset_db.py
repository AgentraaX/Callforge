"""Truncate all application data while preserving schema/tables.

Usage:
    DATABASE_URL=postgresql://postgres:postgres@localhost:5433/callforge \
        .venv/bin/python scripts/reset_db.py

This empties every table tracked by SQLAlchemy Base.metadata and resets
sequences. It does NOT drop tables, migrations, or Alembic state.
"""

import os
import sys
from pathlib import Path

# Make imports from the project root work when running from scripts/
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text

from api.models import Base


def get_database_url() -> str:
    """Return DATABASE_URL from the environment, raising if missing."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Export it first, e.g.:\n"
            "  export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/callforge"
        )
    return url


def reset_database(database_url: str) -> None:
    """Truncate all tables defined by SQLAlchemy models."""
    engine = create_engine(database_url)

    # Dependency-friendly order (CASCADE makes the exact order forgiving).
    table_names = [
        "transcripts",
        "bookings",
        "calls",
        "leads",
        "campaigns",
        "oauth_accounts",
        "users",
        "objections",
    ]

    # Safety check: every table should exist in metadata.
    metadata_tables = {t.name for t in Base.metadata.sorted_tables}
    for name in table_names:
        if name not in metadata_tables:
            raise RuntimeError(f"Table '{name}' not found in SQLAlchemy metadata.")

    quoted = ", ".join(f'"{name}"' for name in table_names)
    truncate_sql = f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE;"

    with engine.begin() as connection:
        connection.execute(text(truncate_sql))

    print(f"Reset complete. {len(table_names)} tables truncated:")
    for name in table_names:
        print(f"  - {name}")


if __name__ == "__main__":
    url = get_database_url()
    reset_database(url)
