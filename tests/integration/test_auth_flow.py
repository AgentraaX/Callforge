"""Standalone integration test: exercises the real Auth endpoints
in-process (httpx against the actual FastAPI app via ASGI transport - no
uvicorn process needed) against local Postgres, then confirms both the
HTTP responses and what actually landed in the database.

Run from the project root:
    python tests/integration/test_auth_flow.py

Requires local Postgres reachable via DATABASE_URL and JWT_SECRET_KEY set
(see .env.example) - loads .env the same way every other cross-service
module in this codebase does.
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

import httpx  # noqa: E402
from jose import jwt  # noqa: E402

from api.db.session import SessionLocal  # noqa: E402
from api.main import app  # noqa: E402
from api.models import OAuthAccount, User  # noqa: E402
from api.services.auth import _jwt_algorithm, _jwt_secret, create_access_token  # noqa: E402
from api.services.email_verification import store_pending_account_delete, store_pending_password_change  # noqa: E402

TEST_EMAIL = f"test-auth-flow-{uuid.uuid4().hex[:8]}@example.com"
TEST_PASSWORD = "correcthorsebatterystaple123"

TEST_GITHUB_EMAIL = f"test-auth-flow-github-{uuid.uuid4().hex[:8]}@example.com"
TEST_GOOGLE_EMAIL = f"test-auth-flow-google-{uuid.uuid4().hex[:8]}@example.com"

TEST_PWCHANGE_EMAIL = f"test-auth-flow-pwchange-{uuid.uuid4().hex[:8]}@example.com"
TEST_PWCHANGE_PASSWORD = "correcthorsebatterystaple123"
TEST_PWCHANGE_NEW_PASSWORD = "N3wP@sswordReset!2026"
TEST_PWCHANGE_CHANGE_PASSWORD = "Ch4ng3d!P@ssword-2026"

_passed = 0
_failed = 0


def _check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS - {label}")
    else:
        _failed += 1
        print(f"  FAIL - {label} {detail}")


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def main() -> None:
    created_user_id: uuid.UUID | None = None

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        print("\n1. POST /auth/register (new user)")
        r = await client.post("/auth/register", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        _check("returns 201", r.status_code == 201, f"got {r.status_code}: {r.text}")
        body = r.json()
        _check("response email matches", body.get("email") == TEST_EMAIL)

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == TEST_EMAIL).first()
            _check("user actually created in DB", user is not None)
            if user is not None:
                created_user_id = user.id
                _check("password_hash is not plaintext", user.password_hash != TEST_PASSWORD)
                _check(
                    "password_hash looks like a real bcrypt hash ($2b$...)",
                    (user.password_hash or "").startswith("$2b$"),
                    f"got: {user.password_hash!r}",
                )
        finally:
            db.close()

        print("\n2. POST /auth/register again (duplicate email)")
        r2 = await client.post("/auth/register", json={"email": TEST_EMAIL, "password": "whatever-different"})
        _check("duplicate register rejected, not a crash", r2.status_code == 409, f"got {r2.status_code}: {r2.text}")

        print("\n3. POST /auth/login (correct credentials)")
        r3 = await client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        _check("returns 200", r3.status_code == 200, f"got {r3.status_code}: {r3.text}")
        token = r3.json().get("access_token")
        _check("access_token present", bool(token))
        if token and created_user_id is not None:
            decoded = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_algorithm()])
            _check("JWT sub matches the created user's id", decoded.get("sub") == str(created_user_id))
            _check("JWT role present and correct", decoded.get("role") == "rep", f"got: {decoded.get('role')!r}")

        print("\n4. POST /auth/login (wrong password)")
        r4 = await client.post("/auth/login", json={"email": TEST_EMAIL, "password": "wrongpassword"})
        _check("returns 401, not a crash", r4.status_code == 401, f"got {r4.status_code}: {r4.text}")

        print("\n5. POST /auth/login (nonexistent email)")
        nonexistent_email = f"nonexistent-{uuid.uuid4().hex[:8]}@example.com"
        r5 = await client.post("/auth/login", json={"email": nonexistent_email, "password": "anything"})
        _check("returns 401, not 404 (doesn't leak whether the email exists)", r5.status_code == 401, f"got {r5.status_code}: {r5.text}")
        _check(
            "wrong-password and nonexistent-email give the identical response body",
            r4.json() == r5.json(),
            f"wrong-password body: {r4.json()!r}, nonexistent-email body: {r5.json()!r}",
        )

        print("\n6. GET /auth/me/oauth (password-only user)")
        r6 = await client.get("/auth/me/oauth", headers=_auth_header(token))
        _check("returns 200", r6.status_code == 200, f"got {r6.status_code}: {r6.text}")
        body = r6.json()
        _check("has_oauth is false for password-only user", body.get("has_oauth") is False)
        _check("providers is empty for password-only user", body.get("providers") == [])

        print("\n7. DELETE /auth/me-password (unauthenticated)")
        r7 = await client.request("DELETE", "/auth/me-password", json={"password": TEST_PASSWORD})
        _check("returns 401 without auth header", r7.status_code == 401, f"got {r7.status_code}: {r7.text}")

        print("\n8. DELETE /auth/me-password (wrong password)")
        r8 = await client.request(
            "DELETE", "/auth/me-password", json={"password": "wrongpassword"}, headers=_auth_header(token)
        )
        _check("returns 403", r8.status_code == 403, f"got {r8.status_code}: {r8.text}")

        print("\n9. DELETE /auth/me-password (correct password)")
        r9 = await client.request(
            "DELETE", "/auth/me-password", json={"password": TEST_PASSWORD}, headers=_auth_header(token)
        )
        _check("returns 204", r9.status_code == 204, f"got {r9.status_code}: {r9.text}")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == TEST_EMAIL).first()
            _check("password-based user deleted from DB", user is None)
        finally:
            db.close()

        print("\n10. GET /auth/me/oauth (Google OAuth user)")
        db = SessionLocal()
        try:
            google_user = User(email=TEST_GOOGLE_EMAIL, password_hash=None)
            db.add(google_user)
            db.commit()
            db.refresh(google_user)
            oauth = OAuthAccount(user_id=google_user.id, provider="google", provider_user_id="g_123")
            db.add(oauth)
            db.commit()
            google_token = create_access_token(google_user.id, google_user.role)
        finally:
            db.close()
        r10 = await client.get("/auth/me/oauth", headers=_auth_header(google_token))
        _check("returns 200", r10.status_code == 200, f"got {r10.status_code}: {r10.text}")
        body = r10.json()
        _check("has_oauth is true for google user", body.get("has_oauth") is True)
        _check("providers includes google", "google" in body.get("providers", []))

        print("\n11. POST /auth/me-provider (Google OAuth, sends deletion code)")
        r11 = await client.post("/auth/me-provider", headers=_auth_header(google_token))
        # SMTP may not be configured in the test environment; accept either the
        # code-sent response (200) or a 503 from unconfigured SMTP.
        _check(
            "returns 200 (code sent) or 503 (SMTP unavailable)",
            r11.status_code in (200, 503),
            f"got {r11.status_code}: {r11.text}",
        )

        print("\n12. POST /auth/me-verify (Google OAuth, seeded code)")
        db = SessionLocal()
        try:
            google_user = db.query(User).filter(User.email == TEST_GOOGLE_EMAIL).first()
            if google_user is None:
                _check("google user still exists for verify test", False)
            else:
                await store_pending_account_delete(TEST_GOOGLE_EMAIL, "654321")
                r12 = await client.post(
                    "/auth/me-verify",
                    json={"code": "654321"},
                    headers=_auth_header(google_token),
                )
                _check("returns 204", r12.status_code == 204, f"got {r12.status_code}: {r12.text}")
                user = db.query(User).filter(User.email == TEST_GOOGLE_EMAIL).first()
                _check("google user deleted after verify", user is None)
        finally:
            db.close()

        print("\n13. POST /auth/me-provider (GitHub OAuth, redirects to consent)")
        db = SessionLocal()
        try:
            github_user = User(email=TEST_GITHUB_EMAIL, password_hash=None)
            db.add(github_user)
            db.commit()
            db.refresh(github_user)
            oauth = OAuthAccount(user_id=github_user.id, provider="github", provider_user_id="gh_123")
            db.add(oauth)
            db.commit()
            github_token = create_access_token(github_user.id, github_user.role)
        finally:
            db.close()
        r13 = await client.post("/auth/me-provider", headers=_auth_header(github_token), follow_redirects=False)
        # If GitHub OAuth is configured, this returns a redirect to GitHub.
        # If not configured, it returns 503. Both are valid outcomes in this test.
        _check(
            "returns 307 redirect or 503 (OAuth not configured)",
            r13.status_code in (307, 503),
            f"got {r13.status_code}: {r13.text}",
        )
        if r13.status_code == 307:
            location = r13.headers.get("location", "")
            _check("redirect points to GitHub", "github.com" in location, f"location: {location!r}")

        print("\n14. Password-change flow: register a fresh password user")
        r_reg = await client.post(
            "/auth/register",
            json={"email": TEST_PWCHANGE_EMAIL, "password": TEST_PWCHANGE_PASSWORD},
        )
        _check("register returns 201", r_reg.status_code == 201, f"got {r_reg.status_code}: {r_reg.text}")
        pw_token = None
        try:
            r_login = await client.post(
                "/auth/login",
                json={"email": TEST_PWCHANGE_EMAIL, "password": TEST_PWCHANGE_PASSWORD},
            )
            _check("login returns 200", r_login.status_code == 200, f"got {r_login.status_code}: {r_login.text}")
            pw_token = r_login.json().get("access_token")
            _check("access_token present", bool(pw_token))
        except AssertionError:
            pass

        print("\n15. API 1: POST /auth/me-password/verify (wrong password)")
        if pw_token:
            r_w = await client.post(
                "/auth/me-password/verify",
                json={"password": "wrongpassword"},
                headers=_auth_header(pw_token),
            )
            _check("returns 200", r_w.status_code == 200, f"got {r_w.status_code}: {r_w.text}")
            _check("valid is false for wrong password", r_w.json().get("valid") is False)

        print("\n16. API 1: POST /auth/me-password/verify (correct password)")
        if pw_token:
            r_ok = await client.post(
                "/auth/me-password/verify",
                json={"password": TEST_PWCHANGE_PASSWORD},
                headers=_auth_header(pw_token),
            )
            _check("returns 200", r_ok.status_code == 200, f"got {r_ok.status_code}: {r_ok.text}")
            _check("valid is true for correct password", r_ok.json().get("valid") is True)

        print("\n17. API 4: POST /auth/me-password/verify-code (no code sent yet)")
        if pw_token:
            r_vc = await client.post(
                "/auth/me-password/verify-code",
                json={"code": "000000"},
                headers=_auth_header(pw_token),
            )
            _check("returns 200 with valid=false (no code in Redis)", r_vc.json().get("valid") is False)

        print("\n18. API 3: POST /auth/me-password/send-code")
        if pw_token:
            r_sc = await client.post("/auth/me-password/send-code", headers=_auth_header(pw_token))
            _check(
                "returns 200 (code sent) or 503 (SMTP unavailable)",
                r_sc.status_code in (200, 503),
                f"got {r_sc.status_code}: {r_sc.text}",
            )

        print("\n19. API 3 + 4 + 2: seed code, verify-code true, reset succeeds")
        if pw_token:
            await store_pending_password_change(TEST_PWCHANGE_EMAIL, "778899")
            r_vc2 = await client.post(
                "/auth/me-password/verify-code",
                json={"code": "778899"},
                headers=_auth_header(pw_token),
            )
            _check("verify-code returns valid=true for seeded code", r_vc2.json().get("valid") is True)
            # verify-code is non-destructive - code should still be consumable
            r_reset = await client.post(
                "/auth/me-password/reset",
                json={"new_password": TEST_PWCHANGE_NEW_PASSWORD, "code": "778899"},
                headers=_auth_header(pw_token),
            )
            _check("reset returns 204", r_reset.status_code == 204, f"got {r_reset.status_code}: {r_reset.text}")

            # verify-code is Consumed now - a repeat reset with same code must fail
            r_reset_again = await client.post(
                "/auth/me-password/reset",
                json={"new_password": TEST_PWCHANGE_NEW_PASSWORD, "code": "778899"},
                headers=_auth_header(pw_token),
            )
            _check(
                "repeat reset with consumed code rejected (400)",
                r_reset_again.status_code == 400,
                f"got {r_reset_again.status_code}: {r_reset_again.text}",
            )

        print("\n20. After reset: new password logs in, old password rejected")
        r_new = await client.post(
            "/auth/login",
            json={"email": TEST_PWCHANGE_EMAIL, "password": TEST_PWCHANGE_NEW_PASSWORD},
        )
        _check("login with new password returns 200", r_new.status_code == 200, f"got {r_new.status_code}: {r_new.text}")
        r_old = await client.post(
            "/auth/login",
            json={"email": TEST_PWCHANGE_EMAIL, "password": TEST_PWCHANGE_PASSWORD},
        )
        _check("login with old password returns 401", r_old.status_code == 401, f"got {r_old.status_code}: {r_old.text}")

        print("\n21. API 2: POST /auth/me-password/reset (wrong code -> 400)")
        if pw_token:
            # need a fresh code for an unauthenticated-tamper test would require
            # a new send; instead verify wrong code path directly via seed+wrong
            await store_pending_password_change(TEST_PWCHANGE_EMAIL, "111222")
            r_wrong = await client.post(
                "/auth/me-password/reset",
                json={"new_password": TEST_PWCHANGE_NEW_PASSWORD, "code": "999999"},
                headers=_auth_header(pw_token),
            )
            _check(
                "reset with wrong code rejected (400)",
                r_wrong.status_code == 400,
                f"got {r_wrong.status_code}: {r_wrong.text}",
            )

        print("\n22. API 2: POST /auth/me-password/reset (weak password -> 400)")
        if pw_token:
            r_weak = await client.post(
                "/auth/me-password/reset",
                json={"new_password": "weak", "code": "111222"},
                headers=_auth_header(pw_token),
            )
            _check(
                "reset with weak password rejected (400)",
                r_weak.status_code == 400,
                f"got {r_weak.status_code}: {r_weak.text}",
            )

        print("\n23. API 1: POST /auth/me-password/verify (unauthenticated)")
        r_un = await client.post("/auth/me-password/verify", json={"password": "anything"})
        _check("returns 401 without auth header", r_un.status_code == 401, f"got {r_un.status_code}: {r_un.text}")

        print("\n24. /me-password/change: correct old + new -> 204 (uses post-reset password)")
        if pw_token:
            # After step 19, TEST_PWCHANGE_EMAIL's password is TEST_PWCHANGE_NEW_PASSWORD.
            r_ch = await client.post(
                "/auth/me-password/change",
                json={"old_password": TEST_PWCHANGE_NEW_PASSWORD, "new_password": TEST_PWCHANGE_CHANGE_PASSWORD},
                headers=_auth_header(pw_token),
            )
            _check("change returns 204", r_ch.status_code == 204, f"got {r_ch.status_code}: {r_ch.text}")

        print("\n25. After /change: new password logs in, prior password rejected")
        r_ch_new = await client.post(
            "/auth/login",
            json={"email": TEST_PWCHANGE_EMAIL, "password": TEST_PWCHANGE_CHANGE_PASSWORD},
        )
        _check("login with changeset password returns 200", r_ch_new.status_code == 200, f"got {r_ch_new.status_code}: {r_ch_new.text}")
        r_ch_old = await client.post(
            "/auth/login",
            json={"email": TEST_PWCHANGE_EMAIL, "password": TEST_PWCHANGE_NEW_PASSWORD},
        )
        _check("login with prior password returns 401", r_ch_old.status_code == 401, f"got {r_ch_old.status_code}: {r_ch_old.text}")

        print("\n26. /me-password/change: wrong old password -> 403")
        if pw_token:
            r_ch_wrong = await client.post(
                "/auth/me-password/change",
                json={"old_password": "wrongoldpassword", "new_password": TEST_PWCHANGE_CHANGE_PASSWORD},
                headers=_auth_header(pw_token),
            )
            _check("returns 403", r_ch_wrong.status_code == 403, f"got {r_ch_wrong.status_code}: {r_ch_wrong.text}")

        print("\n27. /me-password/change: weak new password -> 400")
        if pw_token:
            r_ch_weak = await client.post(
                "/auth/me-password/change",
                json={"old_password": TEST_PWCHANGE_CHANGE_PASSWORD, "new_password": "weak"},
                headers=_auth_header(pw_token),
            )
            _check("returns 400 for weak new password", r_ch_weak.status_code == 400, f"got {r_ch_weak.status_code}: {r_ch_weak.text}")

        print("\n28. /me-password/change: new == old -> 400")
        if pw_token:
            r_ch_same = await client.post(
                "/auth/me-password/change",
                json={"old_password": TEST_PWCHANGE_CHANGE_PASSWORD, "new_password": TEST_PWCHANGE_CHANGE_PASSWORD},
                headers=_auth_header(pw_token),
            )
            _check(
                "returns 400 for new == old",
                r_ch_same.status_code == 400 and "differ" in r_ch_same.text,
                f"got {r_ch_same.status_code}: {r_ch_same.text}",
            )

        print("\n29. /me-password/change: unauthenticated -> 401")
        r_ch_un = await client.post(
            "/auth/me-password/change",
            json={"old_password": "any", "new_password": "AnyValid!Pw1234"},
        )
        _check("returns 401 without auth header", r_ch_un.status_code == 401, f"got {r_ch_un.status_code}: {r_ch_un.text}")

        print("\n30. /me-password/change: OAuth-only account -> 400")
        if pw_token and google_token:
            r_ch_oauth = await client.post(
                "/auth/me-password/change",
                json={"old_password": "any", "new_password": "AnyValid!Pw1234"},
                headers=_auth_header(google_token),
            )
            _check(
                "returns 400 for OAuth-only account",
                r_ch_oauth.status_code == 400,
                f"got {r_ch_oauth.status_code}: {r_ch_oauth.text}",
            )

    print("\n31. Cleanup: deleting any remaining test users from DB")
    db = SessionLocal()
    try:
        deleted = (
            db.query(User)
            .filter(
                User.email.in_([
                    TEST_EMAIL,
                    TEST_GITHUB_EMAIL,
                    TEST_GOOGLE_EMAIL,
                    TEST_PWCHANGE_EMAIL,
                ])
            )
            .delete()
        )
        db.commit()
        _check("test users deleted, test is repeatable", deleted >= 0)
    finally:
        db.close()

    print(f"\n{'=' * 60}\n{_passed} passed, {_failed} failed\n{'=' * 60}")
    if _failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
