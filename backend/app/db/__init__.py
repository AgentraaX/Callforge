"""Async SQLAlchemy engine + session plumbing for the CRM store.

The CRM is an *additive* Postgres layer -- the voice agent, auth, personas,
and the live-call bus still run entirely in memory. Everything here is lazy:
if ``settings.database_url`` is empty the engine is never built and CRM
routes return 503, so the rest of the app is unaffected.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..config import settings

log = logging.getLogger("callforge.db")


class Base(DeclarativeBase):
    """Declarative base for every CRM model (see ``app/db/models.py``)."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _init_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None or not settings.db_configured:
        return
    _engine = create_async_engine(
        settings.db_async_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        future=True,
        connect_args=settings.db_connect_args,
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    log.info("CRM database engine ready")


def db_ready() -> bool:
    """True once the engine has been built (i.e. DATABASE_URL is set)."""
    return _sessionmaker is not None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency -- yields a session, commits on success, rolls back
    on error. CRM routes ``Depends(get_session)``."""
    if _sessionmaker is None:
        _init_engine()
    if _sessionmaker is None:
        from fastapi import HTTPException

        raise HTTPException(503, "CRM database is not configured (set DATABASE_URL)")
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def session_scope() -> AsyncSession:
    """Non-dependency accessor for background tasks (e.g. call ingest).

    Caller owns the lifecycle: ``async with await session_scope() as s: ...``
    then commit/rollback explicitly. Returns None-guarded via db_ready().
    """
    if _sessionmaker is None:
        _init_engine()
    if _sessionmaker is None:
        raise RuntimeError("CRM database is not configured")
    return _sessionmaker()


async def init_db() -> None:
    """Startup hook. Builds the engine and, when ``crm_auto_create_tables``
    is on, creates any missing tables straight from the models -- the
    zero-setup dev path. Production runs ``alembic upgrade head`` and leaves
    the flag off.
    """
    if not settings.db_configured:
        log.info("CRM database not configured -- CRM endpoints disabled")
        return
    _init_engine()
    if _engine is None:
        return
    if settings.crm_auto_create_tables:
        from . import models  # noqa: F401  -- register mappers on Base.metadata

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("CRM tables ensured (crm_auto_create_tables=true)")


async def ping() -> bool:
    """Cheap liveness check for /health."""
    if _sessionmaker is None:
        _init_engine()
    if _sessionmaker is None:
        return False
    from sqlalchemy import text

    try:
        async with _sessionmaker() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover -- surfaced in /health only
        log.warning("CRM database ping failed: %s", exc)
        return False


async def dispose() -> None:
    """Shutdown hook -- close the pool."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None


def _dialect_json() -> Any:
    """JSONB on Postgres, plain JSON elsewhere (keeps SQLite usable in tests)."""
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import JSONB

    return JSON().with_variant(JSONB(), "postgresql")
