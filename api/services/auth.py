"""Auth service: password hashing/verification, JWT issue/verify, and
OAuth2 authorization-code exchange + user-linking for Google/GitHub.

OAuth endpoints are real, spec-correct implementations against each
provider's actual OAuth2/OIDC endpoints - not stubs. They are untestable
end-to-end until real GOOGLE_CLIENT_ID/SECRET and GITHUB_CLIENT_ID/SECRET
are obtained and set in .env (see .env.example) - each provider's /login
and /callback will raise a clear 503 until its own credentials are
configured, rather than silently no-op.
"""
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from authlib.integrations.requests_client import OAuth2Session
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from api.models import OAuthAccount, User
from shared.constants import OAUTH_STATE_KEY
from shared.redis_client import get_redis

logger = logging.getLogger("api.services.auth")

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# A valid bcrypt hash of a fixed, unused placeholder - verified against on
# every login attempt for an email that doesn't exist (or an OAuth-only
# user with no password), so failure takes the same time either way and
# an attacker can't use response latency to enumerate registered emails.
_DUMMY_HASH = _pwd_context.hash("callforge-timing-safe-dummy-password")

_OAUTH_STATE_TTL_SECONDS = 600


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Timing-safe: always runs a real bcrypt verify, even when password_hash
    is None (OAuth-only account) or the caller already knows the user
    doesn't exist - verifying against _DUMMY_HASH keeps the cost identical."""
    return _pwd_context.verify(password, password_hash or _DUMMY_HASH)


def validate_password_strength(password: str) -> str | None:
    """Mirrors the frontend's own check (components/signup/signup-form.tsx) -
    the frontend blocks weak passwords before this is ever hit, but the
    email-verification-code flow shouldn't trust the client alone since a
    valid session doesn't exist yet at this point in registration."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number."
    if not re.search(r"[^A-Za-z0-9]", password):
        return "Password must contain at least one special character."
    return None


# --------------------------------------------------------------------------
# JWT
# --------------------------------------------------------------------------

def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is not set - cannot issue or verify tokens")
    return secret


def _jwt_algorithm() -> str:
    return os.getenv("JWT_ALGORITHM", "HS256")


def _jwt_expire_minutes() -> int:
    return int(os.getenv("JWT_EXPIRE_MINUTES", "60"))


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=_jwt_expire_minutes())
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())


def decode_access_token(token: str) -> dict:
    """Raises jose.JWTError on an invalid/expired/tampered token - callers
    translate that into a 401, not caught here."""
    return jwt.decode(token, _jwt_secret(), algorithms=[_jwt_algorithm()])


# --------------------------------------------------------------------------
# OAuth provider config
# --------------------------------------------------------------------------

def _provider_config(provider: str) -> dict:
    """Raises RuntimeError if the provider's client id/secret aren't
    configured yet - real credentials are required, there is no fallback
    or stub mode."""
    if provider == "google":
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError("Google OAuth is not configured (GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET missing)")
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
            "scope": "openid email profile",
        }

    if provider == "github":
        client_id = os.getenv("GITHUB_CLIENT_ID")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError("GitHub OAuth is not configured (GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET missing)")
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "authorize_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "userinfo_url": "https://api.github.com/user",
            "scope": "read:user user:email",
        }

    raise ValueError(f"Unknown provider: {provider}")


def _redirect_uri(provider: str) -> str:
    base = os.getenv("OAUTH_REDIRECT_BASE_URL")
    if not base:
        raise RuntimeError("OAUTH_REDIRECT_BASE_URL is not set - cannot build an OAuth redirect_uri")
    return f"{base.rstrip('/')}/auth/{provider}/callback"


def delete_redirect_uri() -> str:
    """Redirect URI used for OAuth re-authentication during account deletion."""
    base = os.getenv("OAUTH_REDIRECT_BASE_URL")
    if not base:
        raise RuntimeError("OAUTH_REDIRECT_BASE_URL is not set - cannot build an OAuth redirect_uri")
    return f"{base.rstrip('/')}/auth/me-provider/callback"


async def build_authorization_url(provider: str, redirect_uri: str | None = None) -> str:
    """Generates the provider's consent-screen URL and stashes a
    short-lived, single-use CSRF state token in Redis (validated by
    exchange_code_for_user on callback) - a stateless flow (no server
    session/cookie) needs somewhere to hold that state server-side."""
    config = _provider_config(provider)
    session = OAuth2Session(
        config["client_id"], config["client_secret"], scope=config["scope"],
        redirect_uri=redirect_uri or _redirect_uri(provider),
    )
    uri, state = session.create_authorization_url(config["authorize_url"])

    redis = get_redis()
    await redis.set(OAUTH_STATE_KEY.format(state=state), provider, ex=_OAUTH_STATE_TTL_SECONDS)
    return uri


async def _consume_state(provider: str, state: str) -> None:
    redis = get_redis()
    key = OAUTH_STATE_KEY.format(state=state)
    stored_provider = await redis.getdel(key)
    if stored_provider is None:
        raise ValueError("OAuth state is invalid, expired, or already used")
    if stored_provider != provider:
        raise ValueError("OAuth state does not match the callback provider")


def _fetch_provider_identity(
    provider: str, config: dict, code: str, redirect_uri: str | None = None,
) -> tuple[str, str | None]:
    """Exchanges the authorization code for a token, then fetches the
    provider's userinfo endpoint. Returns (provider_user_id, email) -
    email may be None (GitHub users can keep their email private, in
    which case the caller falls back to a synthetic placeholder)."""
    session = OAuth2Session(
        config["client_id"], config["client_secret"],
        redirect_uri=redirect_uri or _redirect_uri(provider),
    )
    session.fetch_token(config["token_url"], code=code, grant_type="authorization_code")

    userinfo = session.get(config["userinfo_url"]).json()

    if provider == "google":
        return str(userinfo["sub"]), userinfo.get("email")

    if provider == "github":
        email = userinfo.get("email")
        if not email:
            # Private-email GitHub accounts don't return one from /user -
            # a real deployment should call GET /user/emails (requires
            # user:email scope, already requested above) and pick the
            # primary verified address; left as a follow-up rather than
            # guessing at a synthetic value here.
            logger.warning(
                "GitHub OAuth: no public email on account, provider_user_id-only linking",
                extra={"provider_user_id": userinfo.get("id")},
            )
        return str(userinfo["id"]), email

    raise ValueError(f"Unknown provider: {provider}")


async def exchange_code_for_user(
    db: Session, provider: str, code: str, state: str, redirect_uri: str | None = None,
) -> User:
    """Full callback flow: validate state, exchange code, fetch identity,
    then get-or-create the linked User. Raises ValueError on a bad/expired
    state (caller maps that to 400) or RuntimeError if the provider isn't
    configured (caller maps that to 503)."""
    await _consume_state(provider, state)
    config = _provider_config(provider)
    provider_user_id, email = _fetch_provider_identity(provider, config, code, redirect_uri)
    return _get_or_create_oauth_user(db, provider, provider_user_id, email)


def _get_or_create_oauth_user(db: Session, provider: str, provider_user_id: str, email: str | None) -> User:
    existing_link = (
        db.query(OAuthAccount)
        .filter(OAuthAccount.provider == provider, OAuthAccount.provider_user_id == provider_user_id)
        .first()
    )
    if existing_link is not None:
        return db.get(User, existing_link.user_id)

    # No existing link for this provider identity - link to a matching
    # email/password user if one exists, so someone who already registered
    # with email/password can also sign in with OAuth afterward, rather
    # than silently getting a second duplicate account.
    user = db.query(User).filter(User.email == email).first() if email else None
    if user is None:
        if not email:
            # No email from the provider and no way to deduplicate by it -
            # a synthetic placeholder keeps `email` NOT NULL/unique without
            # colliding with a real address.
            email = f"{provider}-{provider_user_id}@users.noreply.callforge.local"
        user = User(email=email, password_hash=None)
        db.add(user)
        db.flush()

    link = OAuthAccount(user_id=user.id, provider=provider, provider_user_id=provider_user_id)
    db.add(link)
    db.commit()
    db.refresh(user)
    return user
