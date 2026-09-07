"""Google / GitHub OAuth2 -- Authorization Code flow.

Flow: browser hits /api/auth/oauth/{provider}/start (full page redirect,
not fetch) -> we redirect to the provider's consent screen -> provider
redirects back to /api/auth/oauth/{provider}/callback with a code -> we
exchange it server-side for an access token, fetch the account's email,
find-or-create a CallForge user, and redirect the browser back to the
frontend with a session token.

Needs real credentials from the provider's own developer console --
GOOGLE_CLIENT_ID/SECRET and GITHUB_CLIENT_ID/SECRET in .env. Until those
are set, oauth_start() returns None from is_configured() and the caller
should redirect to the frontend with an error instead of Google/GitHub's
actual consent screen.
"""
from __future__ import annotations
import logging
import secrets
import time
from urllib.parse import urlencode

import httpx

from . import UserRecord, USERS

log = logging.getLogger("callforge.auth.oauth")

_STATE_TTL_S = 600
_STATES: dict[str, float] = {}  # state token -> expiry epoch

_PROVIDERS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "read:user user:email",
    },
}

PROVIDERS = tuple(_PROVIDERS.keys())


def _client_creds(provider: str) -> tuple[str, str]:
    from ..config import settings
    if provider == "google":
        return settings.google_client_id, settings.google_client_secret
    return settings.github_client_id, settings.github_client_secret


def is_configured(provider: str) -> bool:
    client_id, client_secret = _client_creds(provider)
    return bool(client_id and client_secret)


def redirect_uri(provider: str) -> str:
    from ..config import settings
    return f"{settings.oauth_redirect_base_url.rstrip('/')}/api/auth/oauth/{provider}/callback"


def new_state() -> str:
    """CSRF token for the OAuth round trip -- opaque, single-use, short-lived."""
    now = time.time()
    for s, exp in list(_STATES.items()):
        if exp < now:
            _STATES.pop(s, None)
    state = secrets.token_urlsafe(24)
    _STATES[state] = now + _STATE_TTL_S
    return state


def consume_state(state: str) -> bool:
    expiry = _STATES.pop(state, None)
    return expiry is not None and expiry >= time.time()


def build_authorize_url(provider: str, state: str) -> str:
    meta = _PROVIDERS[provider]
    client_id, _ = _client_creds(provider)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri(provider),
        "scope": meta["scope"],
        "state": state,
        "response_type": "code",
    }
    if provider == "google":
        params["access_type"] = "online"
        params["prompt"] = "select_account"
    return f"{meta['auth_url']}?{urlencode(params)}"


async def exchange_code(provider: str, code: str) -> str:
    """Exchange the authorization code for an access token. Returns the token."""
    meta = _PROVIDERS[provider]
    client_id, client_secret = _client_creds(provider)
    body = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri(provider),
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            meta["token_url"], data=body, headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    access_token = data.get("access_token", "")
    if not access_token:
        raise ValueError(f"{provider} token exchange returned no access_token")
    return access_token


async def fetch_profile(provider: str, access_token: str) -> dict:
    """Returns {"email": str, "name": str} from the provider's account."""
    meta = _PROVIDERS[provider]
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(meta["userinfo_url"], headers=headers)
        resp.raise_for_status()
        data = resp.json()

    if provider == "google":
        return {"email": data.get("email", ""), "name": data.get("name", "")}

    # GitHub: the profile omits email when the account has it set to private.
    email = data.get("email") or ""
    name = data.get("name") or data.get("login") or ""
    if not email:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://api.github.com/user/emails", headers=headers)
        if resp.status_code == 200:
            emails = resp.json()
            primary = next((e["email"] for e in emails if e.get("primary")), None)
            email = primary or (emails[0]["email"] if emails else "")

    return {"email": email, "name": name}


def find_or_create_oauth_user(email: str, name: str) -> UserRecord:
    """OAuth accounts get an unusable random password hash -- they can only
    ever sign in via the same provider again, never via email+password."""
    key = email.strip().lower()
    if not key:
        raise ValueError("Provider did not return an email address")

    existing = USERS.get(key)
    if existing:
        return existing

    user = UserRecord(
        email=key,
        name=name.strip() or key.split("@")[0],
        company="",
        password_hash=secrets.token_bytes(32),
        salt=secrets.token_bytes(16),
    )
    USERS[key] = user
    log.info("New OAuth account created: %s", key)
    return user
