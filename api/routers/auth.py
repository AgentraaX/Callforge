"""Auth endpoints: email/password (register, login) and OAuth2 (Google,
GitHub) authorization-code flow.

The OAuth endpoints below are complete, spec-correct implementations of
each provider's authorization-code flow (not stubs) - but are untestable
end-to-end until real GOOGLE_CLIENT_ID/SECRET and GITHUB_CLIENT_ID/SECRET
are obtained and set in .env. Until then, /auth/{provider}/login and
/callback correctly raise a 503 for whichever provider(s) aren't
configured, rather than silently no-op.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.dependencies import get_current_user
from api.models import User
from api.schemas.auth import (
    LoginRequest,
    SendVerificationCodeRequest,
    TokenResponse,
    UserCreate,
    UserOut,
    VerifyCodeRequest,
)
from api.services.auth import (
    build_authorization_url,
    create_access_token,
    exchange_code_for_user,
    hash_password,
    validate_password_strength,
    verify_password,
)
from api.services.email_verification import (
    consume_pending_registration,
    generate_verification_code,
    get_pending_registration,
    send_verification_email,
    store_pending_registration,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_VALID_PROVIDERS = {"google", "github"}


def _validate_provider(provider: str) -> None:
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid provider. Valid values: {', '.join(sorted(_VALID_PROVIDERS))}",
        )


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/register/send-code", status_code=200)
async def send_registration_code(payload: SendVerificationCodeRequest, db: Session = Depends(get_db)):
    """Step 1 of email-verified signup: validate email/password up front (same
    checks /register applies) and email a 6-digit code, without creating a
    User yet - the account is only created once verify-code confirms it."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_error = validate_password_strength(payload.password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    code = generate_verification_code()
    await store_pending_registration(payload.email, hash_password(payload.password), code)

    try:
        await send_verification_email(payload.email, code)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {"detail": "Verification code sent"}


@router.post("/register/verify-code", response_model=TokenResponse, status_code=201)
async def verify_registration_code(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Step 2: confirm the code, create the User (finally persisting the
    password hash that's been sitting in Redis since send-code), and log
    them straight in - same behavior /register's callers already expect."""
    pending = await get_pending_registration(payload.email)
    if pending is None:
        raise HTTPException(status_code=400, detail="Code expired or not requested. Please request a new code.")
    if pending["code"] != payload.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    consumed = await consume_pending_registration(payload.email)
    if consumed is None:
        # Consumed by a concurrent request between the check above and here.
        raise HTTPException(status_code=400, detail="Code expired or not requested. Please request a new code.")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=payload.email, password_hash=consumed["password_hash"])
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    # Timing-safe: verify_password always runs a real bcrypt check, even
    # when user is None or has no password_hash (OAuth-only account) - see
    # api/services/auth.py. The 401 detail is identical either way so a
    # response can't be used to enumerate which emails are registered.
    password_hash = user.password_hash if user is not None else None
    if user is None or not verify_password(payload.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    return user


@router.get("/{provider}/login")
async def oauth_login(provider: str):
    _validate_provider(provider)
    try:
        url = await build_authorization_url(provider)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return RedirectResponse(url)


@router.get("/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    code: str | None = Query(None),
    state: str = Query(...),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    db: Session = Depends(get_db),
):
    _validate_provider(provider)

    # The user can decline consent on the provider's own screen - it redirects
    # back with `error`/`error_description` instead of `code`, which isn't a
    # validation failure on our end and shouldn't 422 as if `code` were
    # malformed; report it as a clean 400 instead.
    if error is not None:
        raise HTTPException(
            status_code=400,
            detail=f"{provider} authorization was not completed: {error_description or error}",
        )
    if code is None:
        raise HTTPException(status_code=400, detail="Missing 'code' query parameter")

    try:
        user = await exchange_code_for_user(db, provider, code, state)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token)
