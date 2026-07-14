"""Shared Postgres connection helper (used outside the API's own session.py, e.g. by the agent)."""

import os

from sqlalchemy import create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/callforge")

engine = create_engine(DATABASE_URL)
