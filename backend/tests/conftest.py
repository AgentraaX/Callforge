"""Test harness for the CRM layer.

Runs against a throwaway SQLite file (via aiosqlite) so it needs no
Postgres. The models are written to stay dialect-portable -- JSONB degrades
to JSON, and ids are plain strings -- specifically so this works.

The full ``app.main`` pulls in the voice stack (torch, livekit, ...), so
these tests mount just the CRM router on a bare FastAPI app.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

_TMP_DB = Path(tempfile.gettempdir()) / "callforge_crm_test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP_DB}"
os.environ["CRM_AUTO_CREATE_TABLES"] = "true"


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture()
async def app():
    if _TMP_DB.exists():
        _TMP_DB.unlink()

    from fastapi import FastAPI

    from app import db as crm_db
    from app.crm.routes import router

    # Fresh engine per test session pointed at the temp file.
    await crm_db.dispose()
    application = FastAPI()
    application.include_router(router)
    await crm_db.init_db()
    try:
        yield application
    finally:
        await crm_db.dispose()
        if _TMP_DB.exists():
            _TMP_DB.unlink()


@pytest_asyncio.fixture()
async def client(app):
    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_user(email: str, company: str) -> str:
    """Create an in-memory user + session, return a bearer token."""
    from app import auth

    auth.USERS.pop(email.strip().lower(), None)
    user = auth.create_user(email, "pw-12345", email.split("@")[0], company)
    return auth.create_session(user.email)


@pytest.fixture()
def alice_headers() -> dict:
    return {"Authorization": f"Bearer {_make_user('alice@acme.test', 'Acme')}"}


@pytest.fixture()
def bob_headers() -> dict:
    """Same company as Alice -> same org."""
    return {"Authorization": f"Bearer {_make_user('bob@acme.test', 'Acme')}"}


@pytest.fixture()
def carol_headers() -> dict:
    """Different company -> isolated org."""
    return {"Authorization": f"Bearer {_make_user('carol@other.test', 'Other Inc')}"}
