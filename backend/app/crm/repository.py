"""Generic org-scoped CRUD over the CRM models.

One place enforces ``org_id`` filtering, patch semantics, sorting and
pagination -- routes stay thin. Every function takes ``(session, org_id, ...)``
and a not-found / wrong-org lookup raises 404, never leaks across orgs.
"""
from __future__ import annotations

from typing import Any, TypeVar

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import Base

ModelT = TypeVar("ModelT", bound=Base)

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


async def get_or_404(session: AsyncSession, model: type[ModelT], org_id: str, obj_id: str) -> ModelT:
    obj = await session.get(model, obj_id)
    if obj is None or getattr(obj, "org_id", None) != org_id:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


async def list_(
    session: AsyncSession,
    model: type[ModelT],
    org_id: str,
    *,
    filters: dict[str, Any] | None = None,
    order_by: str = "-created_at",
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    extra_where: list | None = None,
) -> tuple[list[ModelT], int]:
    """Return ``(rows, total)``. ``filters`` is exact-match on columns;
    ``order_by`` is a column name, ``-`` prefix for descending."""
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)

    stmt = select(model).where(model.org_id == org_id)
    count_stmt = select(func.count()).select_from(model).where(model.org_id == org_id)

    for key, value in (filters or {}).items():
        if value is None or not hasattr(model, key):
            continue
        col = getattr(model, key)
        stmt = stmt.where(col == value)
        count_stmt = count_stmt.where(col == value)

    for clause in extra_where or []:
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)

    desc = order_by.startswith("-")
    col_name = order_by[1:] if desc else order_by
    sort_col = getattr(model, col_name, None) or getattr(model, "created_at")
    stmt = stmt.order_by(sort_col.desc() if desc else sort_col.asc())

    total = int(await session.scalar(count_stmt) or 0)
    rows = list(await session.scalars(stmt.limit(limit).offset(offset)))
    return rows, total


async def create(
    session: AsyncSession, model: type[ModelT], org_id: str, owner_email: str, data: dict[str, Any]
) -> ModelT:
    payload = {k: v for k, v in data.items() if hasattr(model, k)}
    payload.pop("id", None)
    payload.pop("org_id", None)
    obj = model(**payload, org_id=org_id)
    if hasattr(obj, "owner_email") and not payload.get("owner_email"):
        obj.owner_email = owner_email
    session.add(obj)
    await session.flush()
    await session.refresh(obj)
    return obj


async def update(
    session: AsyncSession, model: type[ModelT], org_id: str, obj_id: str, data: dict[str, Any]
) -> ModelT:
    obj = await get_or_404(session, model, org_id, obj_id)
    for key, value in data.items():
        if key in ("id", "org_id", "created_at") or not hasattr(model, key):
            continue
        setattr(obj, key, value)
    await session.flush()
    await session.refresh(obj)
    return obj


async def delete(session: AsyncSession, model: type[ModelT], org_id: str, obj_id: str) -> None:
    obj = await get_or_404(session, model, org_id, obj_id)
    await session.delete(obj)
    await session.flush()
