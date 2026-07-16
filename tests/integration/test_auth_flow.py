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
from api.models import User  # noqa: E402
from api.services.auth import _jwt_algorithm, _jwt_secret  # noqa: E402

TEST_EMAIL = f"test-auth-flow-{uuid.uuid4().hex[:8]}@example.com"
TEST_PASSWORD = "correcthorsebatterystaple123"

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

    print("\n6. Cleanup: deleting test user from DB")
    db = SessionLocal()
    try:
        deleted = db.query(User).filter(User.email == TEST_EMAIL).delete()
        db.commit()
        _check("test user deleted, test is repeatable", deleted == 1)
    finally:
        db.close()

    print(f"\n{'=' * 60}\n{_passed} passed, {_failed} failed\n{'=' * 60}")
    if _failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
