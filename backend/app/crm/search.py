"""Cross-entity quick search for the dashboard ⌘K box."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Company, Contact, Deal
from .schemas import SearchHit, SearchResults

_PER_KIND = 6


async def search(session: AsyncSession, org_id: str, q: str) -> SearchResults:
    q = (q or "").strip()
    if len(q) < 2:
        return SearchResults(hits=[])
    like = f"%{q}%"
    hits: list[SearchHit] = []

    contacts = await session.scalars(
        select(Contact)
        .where(
            Contact.org_id == org_id,
            or_(
                Contact.full_name.ilike(like),
                Contact.email.ilike(like),
                Contact.phone.ilike(like),
            ),
        )
        .order_by(Contact.updated_at.desc())
        .limit(_PER_KIND)
    )
    for c in contacts:
        hits.append(
            SearchHit(kind="contact", id=c.id, label=c.full_name or c.email or c.phone or "Contact",
                      sublabel=c.title or c.email)
        )

    companies = await session.scalars(
        select(Company)
        .where(Company.org_id == org_id, Company.name.ilike(like))
        .order_by(Company.updated_at.desc())
        .limit(_PER_KIND)
    )
    for co in companies:
        hits.append(SearchHit(kind="company", id=co.id, label=co.name, sublabel=co.domain or co.industry))

    deals = await session.scalars(
        select(Deal)
        .where(Deal.org_id == org_id, Deal.title.ilike(like))
        .order_by(Deal.updated_at.desc())
        .limit(_PER_KIND)
    )
    for d in deals:
        hits.append(SearchHit(kind="deal", id=d.id, label=d.title, sublabel=d.stage))

    return SearchResults(hits=hits)
