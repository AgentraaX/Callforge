"""Email-verification-code flow for registration: a 6-digit code plus the
prospective account's password hash are held in Redis (keyed by email,
single-use, short TTL) until the code is confirmed - the User row is only
ever created once that happens, so there's no "unverified user" state to
track on the User model itself.
"""
import asyncio
import json
import logging
import os
import secrets
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from shared.constants import ACCOUNT_DELETE_CODE_KEY, EMAIL_VERIFICATION_KEY
from shared.redis_client import get_redis

logger = logging.getLogger("api.services.email_verification")

_CODE_TTL_SECONDS = 600  # 10 minutes, matches OAuth state TTL


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def store_pending_registration(email: str, password_hash: str, code: str) -> None:
    redis = get_redis()
    payload = json.dumps({"code": code, "password_hash": password_hash})
    await redis.set(EMAIL_VERIFICATION_KEY.format(email=email), payload, ex=_CODE_TTL_SECONDS)


async def get_pending_registration(email: str) -> dict | None:
    """Non-destructive read - a wrong code shouldn't burn the user's one
    attempt, so this doesn't delete the key. Only consume_pending_registration
    (called once the code is confirmed correct) does."""
    redis = get_redis()
    raw = await redis.get(EMAIL_VERIFICATION_KEY.format(email=email))
    if raw is None:
        return None
    return json.loads(raw)


async def consume_pending_registration(email: str) -> dict | None:
    redis = get_redis()
    raw = await redis.getdel(EMAIL_VERIFICATION_KEY.format(email=email))
    if raw is None:
        return None
    return json.loads(raw)


def _send_verification_email_sync(email: str, code: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL")

    if not all([host, username, password, from_email]):
        raise RuntimeError("SMTP not fully configured - see .env's SMTP_* vars")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your CallForge verification code: {code}"
    msg["From"] = from_email
    msg["To"] = email

    text_body = f"Your CallForge verification code is: {code}\n\nThis code expires in 10 minutes."
    html_body = (
        f"<p>Your CallForge verification code is:</p>"
        f"<p style='font-size:24px;font-weight:bold;letter-spacing:4px'>{code}</p>"
        f"<p>This code expires in 10 minutes.</p>"
    )
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(from_email, [email], msg.as_string())


async def send_verification_email(email: str, code: str) -> None:
    await asyncio.to_thread(_send_verification_email_sync, email, code)


# ---------------------------------------------------------------------------
# Account-deletion verification code flow
# ---------------------------------------------------------------------------


async def store_pending_account_delete(email: str, code: str) -> None:
    redis = get_redis()
    payload = json.dumps({"code": code})
    await redis.set(ACCOUNT_DELETE_CODE_KEY.format(email=email), payload, ex=_CODE_TTL_SECONDS)


async def get_pending_account_delete(email: str) -> dict | None:
    redis = get_redis()
    raw = await redis.get(ACCOUNT_DELETE_CODE_KEY.format(email=email))
    if raw is None:
        return None
    return json.loads(raw)


async def consume_pending_account_delete(email: str) -> dict | None:
    redis = get_redis()
    raw = await redis.getdel(ACCOUNT_DELETE_CODE_KEY.format(email=email))
    if raw is None:
        return None
    return json.loads(raw)


def _send_delete_verification_email_sync(email: str, code: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL")

    if not all([host, username, password, from_email]):
        raise RuntimeError("SMTP not fully configured - see .env's SMTP_* vars")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your CallForge account deletion code: {code}"
    msg["From"] = from_email
    msg["To"] = email

    text_body = (
        f"Your CallForge account deletion code is: {code}\n\n"
        f"This code expires in 10 minutes.\n\n"
        f"If you did not request account deletion, ignore this email."
    )
    html_body = (
        f"<p>Your CallForge account deletion code is:</p>"
        f"<p style='font-size:24px;font-weight:bold;letter-spacing:4px'>{code}</p>"
        f"<p>This code expires in 10 minutes.</p>"
        f"<p>If you did not request account deletion, ignore this email.</p>"
    )
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(from_email, [email], msg.as_string())


async def send_delete_verification_email(email: str, code: str) -> None:
    await asyncio.to_thread(_send_delete_verification_email_sync, email, code)


async def send_account_delete_code(email: str) -> str:
    """Generate, store, and email a one-time account-deletion code.

    Returns the generated code so callers can log it in test environments if
    needed. In production the code is delivered only via email.
    """
    code = generate_verification_code()
    await store_pending_account_delete(email, code)
    await send_delete_verification_email(email, code)
    return code
