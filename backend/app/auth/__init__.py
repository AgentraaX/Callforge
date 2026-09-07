"""Authentication -- real password hashing and session tokens.

In-memory store, same pattern as sales/leads.py and sales/booking.py
("production would use PostgreSQL"). Passwords are PBKDF2-SHA256 hashed
with a per-user random salt -- never stored or logged in plaintext.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import os
import secrets
import time
from dataclasses import dataclass, field

log = logging.getLogger("callforge.auth")

_PBKDF2_ITERATIONS = 200_000


@dataclass
class UserRecord:
    email: str
    name: str
    company: str
    password_hash: bytes
    salt: bytes
    created_at: float = field(default_factory=time.time)


# In-memory stores
USERS: dict[str, UserRecord] = {}       # email (lowercased) -> UserRecord
SESSIONS: dict[str, str] = {}           # token -> email


def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)


class EmailTaken(Exception):
    pass


class InvalidCredentials(Exception):
    pass


def create_user(email: str, password: str, name: str, company: str) -> UserRecord:
    """Register a new user. Raises EmailTaken if the email is already registered."""
    key = email.strip().lower()
    if not key or not password:
        raise InvalidCredentials("Email and password are required")
    if key in USERS:
        raise EmailTaken(f"An account already exists for {email}")

    salt = os.urandom(16)
    user = UserRecord(
        email=key,
        name=name.strip() or key.split("@")[0],
        company=company.strip(),
        password_hash=_hash_password(password, salt),
        salt=salt,
    )
    USERS[key] = user
    log.info("New account created: %s", key)
    return user


def verify_user(email: str, password: str) -> UserRecord:
    """Verify credentials. Raises InvalidCredentials on any mismatch.

    Uses hmac.compare_digest for constant-time comparison -- avoids leaking
    whether the email exists via response-timing.
    """
    key = email.strip().lower()
    user = USERS.get(key)
    if not user:
        # Still hash something to keep timing similar to the found-user path.
        _hash_password(password, os.urandom(16))
        raise InvalidCredentials("Incorrect email or password")

    candidate = _hash_password(password, user.salt)
    if not hmac.compare_digest(candidate, user.password_hash):
        raise InvalidCredentials("Incorrect email or password")

    return user


def create_session(email: str) -> str:
    """Issue a new session token for a verified user."""
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = email.strip().lower()
    return token


def get_user_by_token(token: str) -> UserRecord | None:
    email = SESSIONS.get(token)
    if not email:
        return None
    return USERS.get(email)


def revoke_session(token: str) -> None:
    SESSIONS.pop(token, None)


def user_payload(user: UserRecord) -> dict:
    """Serializable user info for the frontend -- never includes the hash/salt."""
    return {"email": user.email, "name": user.name, "company": user.company}
