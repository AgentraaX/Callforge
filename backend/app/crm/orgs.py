"""Organisation resolution + membership.

Auth has no org table (it's an in-memory user store), so the CRM owns the
concept: the first time a signed-in user touches a CRM endpoint we find their
``OrgMembership`` by email or lazily create an org for them. Everything the
CRM reads or writes is then scoped by ``org_id``, so a user can never see
another org's records.
"""
from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import UserRecord
from ..auth.deps import current_user
from ..db import get_session
from ..db.models import Organization, OrgMembership


async def _get_membership(session: AsyncSession, email: str) -> OrgMembership | None:
    email = email.strip().lower()
    return await session.scalar(select(OrgMembership).where(OrgMembership.email == email))


async def get_or_create_org(session: AsyncSession, user: UserRecord) -> Organization:
    """Resolve the user's org, creating one on first contact.

    New org name: the user's company if they set one at signup, else
    ``"<name>'s team"``. The creator is the ``owner`` member.
    """
    email = user.email.strip().lower()
    membership = await _get_membership(session, email)
    if membership is not None:
        org = await session.get(Organization, membership.org_id)
        if org is not None:
            return org

    org = Organization(name=(user.company or "").strip() or f"{user.name or email}'s team")
    session.add(org)
    await session.flush()
    session.add(OrgMembership(org_id=org.id, email=email, role="owner"))
    await session.flush()
    return org


async def resolve_org_id(
    session: AsyncSession, email: str, *, company: str = "", name: str = ""
) -> str | None:
    """Standalone org lookup for non-request code (call ingest, websocket
    handlers) that has an email but no ``UserRecord``. Creates the org on
    first use, same as :func:`get_or_create_org`."""
    email = (email or "").strip().lower()
    if not email:
        return None
    membership = await _get_membership(session, email)
    if membership is not None:
        return membership.org_id
    org = Organization(name=(company or "").strip() or f"{name or email}'s team")
    session.add(org)
    await session.flush()
    session.add(OrgMembership(org_id=org.id, email=email, role="owner"))
    await session.flush()
    return org.id


class OrgContext:
    """What every CRM route depends on: the authed user, their org, and a
    session. Keeps route signatures to one parameter."""

    def __init__(self, user: UserRecord, org: Organization, session: AsyncSession):
        self.user = user
        self.org = org
        self.session = session

    @property
    def org_id(self) -> str:
        return self.org.id

    @property
    def email(self) -> str:
        return self.user.email.strip().lower()

    @property
    def role(self) -> str:
        return getattr(self, "_role", "member")


async def org_context(
    user: UserRecord = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> OrgContext:
    org = await get_or_create_org(session, user)
    ctx = OrgContext(user, org, session)
    membership = await _get_membership(session, user.email)
    ctx._role = membership.role if membership else "member"
    return ctx


async def list_members(session: AsyncSession, org_id: str) -> list[OrgMembership]:
    rows = await session.scalars(
        select(OrgMembership).where(OrgMembership.org_id == org_id).order_by(OrgMembership.created_at)
    )
    return list(rows)


async def add_member(session: AsyncSession, org_id: str, email: str, role: str = "member") -> OrgMembership:
    email = email.strip().lower()
    existing = await session.scalar(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id, OrgMembership.email == email
        )
    )
    if existing:
        return existing
    membership = OrgMembership(org_id=org_id, email=email, role=role if role in ("owner", "member") else "member")
    session.add(membership)
    await session.flush()
    return membership
