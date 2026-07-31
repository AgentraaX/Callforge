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
from api.models import OAuthAccount, User
from api.schemas.auth import (
    AccountDeletePasswordRequest,
    AccountDeleteVerifyRequest,
    BooleanResponse,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetRequest,
    PasswordVerifyCodeRequest,
    PasswordVerifyRequest,
    SendVerificationCodeRequest,
    TokenResponse,
    UserCreate,
    UserOAuthProvidersResponse,
    UserOut,
    VerifyCodeRequest,
)
from api.services.auth import (
    build_authorization_url,
    create_access_token,
    delete_redirect_uri,
    exchange_code_for_user,
    hash_password,
    validate_password_strength,
    verify_password,
)
from api.services.email_verification import (
    consume_pending_account_delete,
    consume_pending_password_change,
    consume_pending_registration,
    generate_verification_code,
    get_pending_password_change,
    get_pending_registration,
    send_account_delete_code,
    send_password_change_code,
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


@router.get("/me/oauth", response_model=UserOAuthProvidersResponse)
def get_me_oauth(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the OAuth providers linked to the current user."""
    providers = [
        row.provider
        for row in db.query(OAuthAccount.provider)
        .filter(OAuthAccount.user_id == user.id)
        .all()
    ]
    return UserOAuthProvidersResponse(has_oauth=bool(providers), providers=providers)


@router.delete("/me-password", status_code=204)
async def delete_me_password(
    payload: AccountDeletePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a password-based account after verifying the current password."""
    if user.password_hash is None:
        raise HTTPException(
            status_code=400,
            detail="Password-based deletion is not available for OAuth accounts",
        )
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=403, detail="Invalid password")
    db.delete(user)
    db.commit()
    return None


# ---------------------------------------------------------------------------
# Password change flow (all require a valid JWT via get_current_user):
#   1. POST /auth/me-password/verify      - re-check the current password
#   2. POST /auth/me-password/send-code    - email a 6-digit code
#   3. POST /auth/me-password/verify-code  - boolean pre-check of the code
#   4. POST /auth/me-password/reset        - actually set a new password
# Reset consumes the code server-side, so a stolen token alone can't change
# the password - the email-inbox code is a hard requirement, not a UX hint.
# ---------------------------------------------------------------------------


@router.post("/me-password/verify", response_model=BooleanResponse)
def verify_current_password(
    payload: PasswordVerifyRequest,
    user: User = Depends(get_current_user),
):
    """API 1: confirm the user knows their current password. Returns a
    boolean rather than raising on a wrong password so the client can show a
    "wrong password" message and stay on the same form. An OAuth-only
    account (password_hash is None) has no password to verify, so it's a
    clean 400."""
    if user.password_hash is None:
        raise HTTPException(
            status_code=400,
            detail="No password set on this account",
        )
    return BooleanResponse(valid=verify_password(payload.password, user.password_hash))


@router.post("/me-password/change", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the password for a user who knows their current one - the classic
    "old + new" flow. The old password is the proof of identity here (no email
    code); /me-password/reset is the email-code flow for when the user can't or
    won't type the old password. Strength is validated before the same-password
    check so a weak value reports the strength error first, and the same-password
    check uses verify_password (timing-safe) rather than a plaintext ==."""
    if user.password_hash is None:
        raise HTTPException(
            status_code=400,
            detail="No password set on this account",
        )
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Invalid password")

    password_error = validate_password_strength(payload.new_password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status_code=400,
            detail="New password must differ from the current password",
        )

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return None


@router.post("/me-password/send-code", status_code=200)
async def send_password_change_verification_code(
    user: User = Depends(get_current_user),
):
    """API 3: looks up the authenticated user's email and sends a one-time
    6-digit code to it. The code is stored in Redis (keyed by email, 10-min
    TTL) and consumed by /me-password/reset once correct."""
    try:
        await send_password_change_code(user.email)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"detail": "Verification code sent"}


@router.post("/me-password/verify-code", response_model=BooleanResponse)
async def verify_password_change_code(
    payload: PasswordVerifyCodeRequest,
    user: User = Depends(get_current_user),
):
    """API 4: boolean pre-check of the emailed code so the frontend can
    enable/disable the "Change password" button before submit. Non-
    destructive (a wrong code doesn't burn the attempt); the code is only
    consumed by /me-password/reset. Returns valid=false for a wrong,
    expired, or never-requested code so the response can't leak which."""
    pending = await get_pending_password_change(user.email)
    if pending is None:
        return BooleanResponse(valid=False)
    return BooleanResponse(valid=pending.get("code") == payload.code)


@router.post("/me-password/reset", status_code=204)
async def reset_password(
    payload: PasswordResetRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """API 2: sets a new password. Requires a valid code (from /me-password/
    send-code and pre-checked via /me-password/verify-code) - server-side
    enforced, not just a UX gate, so a stolen token alone can't change the
    password. The new password is strength-validated (same rules as signup)
    up front so a weak-password attempt doesn't burn the code; the code is
    then consumed atomically only once both checks pass."""
    password_error = validate_password_strength(payload.new_password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    pending = await get_pending_password_change(user.email)
    if pending is None or pending.get("code") != payload.code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    consumed = await consume_pending_password_change(user.email)
    if consumed is None:
        # Consumed by a concurrent request between the check above and here.
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    return None


@router.post("/me-provider", status_code=200)
async def delete_me_provider(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start deletion for an OAuth account.

    Google-linked accounts receive an email verification code.
    Non-Google OAuth accounts (e.g., GitHub) are redirected to the provider's
    consent screen for re-authentication; deletion completes at the callback.
    """
    if user.password_hash is not None:
        raise HTTPException(
            status_code=400,
            detail="Provider-based deletion is not available for password-based accounts",
        )

    linked_providers = {
        row.provider
        for row in db.query(OAuthAccount.provider).filter(OAuthAccount.user_id == user.id).all()
    }

    if "google" in linked_providers:
        try:
            await send_account_delete_code(user.email)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        return {"detail": "Verification code sent"}

    if "github" in linked_providers:
        try:
            url = await build_authorization_url("github", redirect_uri=delete_redirect_uri())
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        return RedirectResponse(url)

    raise HTTPException(
        status_code=400,
        detail="No supported OAuth provider linked to this account",
    )


@router.post("/me-verify", status_code=204)
async def verify_delete_me_provider(
    payload: AccountDeleteVerifyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm the Google OAuth account-deletion code and delete the account."""
    if user.password_hash is not None:
        raise HTTPException(
            status_code=400,
            detail="Provider-based deletion is not available for password-based accounts",
        )

    pending = await consume_pending_account_delete(user.email)
    if pending is None or pending.get("code") != payload.code:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    db.delete(user)
    db.commit()
    return None


@router.get("/me-provider/callback", status_code=204)
async def delete_me_provider_callback(
    code: str | None = Query(None),
    state: str = Query(...),
    error: str | None = Query(None),
    error_description: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """GitHub redirects here after re-authentication; complete account deletion."""
    if error is not None:
        raise HTTPException(
            status_code=400,
            detail=f"github authorization was not completed: {error_description or error}",
        )
    if code is None:
        raise HTTPException(status_code=400, detail="Missing 'code' query parameter")

    try:
        user = await exchange_code_for_user(
            db, "github", code, state, redirect_uri=delete_redirect_uri()
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if user.password_hash is not None:
        raise HTTPException(
            status_code=400,
            detail="Provider-based deletion is not available for password-based accounts",
        )

    db.delete(user)
    db.commit()
    return None


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
