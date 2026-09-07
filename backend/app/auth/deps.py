"""Shared FastAPI auth dependencies.

Extracted from ``app/main.py`` so the CRM router (``app/crm/routes.py``) can
resolve the current user without importing ``main`` (circular).
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from . import UserRecord, get_user_by_token


def current_user(authorization: str | None = Header(default=None)) -> UserRecord:
    """Resolve the ``Authorization: Bearer <token>`` header to a user, or 401.

    Sessions live in the in-memory store (``app/auth``), so a backend restart
    invalidates every token -- callers get a clean 401 and the frontend
    re-authenticates.
    """
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    user = get_user_by_token(token) if token else None
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user
