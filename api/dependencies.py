"""Shared FastAPI dependencies. Currently just the JWT auth guard used by
every router that requires a logged-in user (see each router's
`dependencies=[Depends(get_current_user)]`).
"""
import uuid

from fastapi import Depends, Header, HTTPException
from jose import JWTError
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.models import User
from api.services.auth import decode_access_token


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Validates the `Authorization: Bearer <jwt>` header and loads the
corresponding user. Raises 401 for any failure mode (missing header,
malformed scheme, invalid/expired/tampered token, or a token whose
`sub` no longer matches a user) - callers never need to distinguish
these, a 401 is a 401."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")

    return user


def user_filter(user: User, model):
    """Return a query filter that scopes `model` to the current user.

    Admin/manager roles are not implemented yet; every user sees only their
    own rows. Existing rows with user_id NULL are invisible to regular users.
    """
    return model.user_id == user.id
