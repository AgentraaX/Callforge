"""CRM HTTP API -- everything under ``/api/crm``.

Every route depends on :func:`org_context`, which resolves the bearer token
to a user and their org and hands back a session. Nothing here can read or
write outside ``ctx.org_id``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select

from ..db.models import (
    DEAL_STAGES,
    Activity,
    CallRecord,
    Company,
    Contact,
    Deal,
)
from . import analytics as analytics_mod
from . import repository as repo
from . import search as search_mod
from .orgs import OrgContext, add_member, list_members, org_context
from .schemas import (
    ActivityIn,
    ActivityList,
    ActivityOut,
    ActivityPatch,
    AnalyticsOverview,
    BoardColumn,
    CallDetail,
    CallList,
    CallOut,
    CompanyIn,
    CompanyList,
    CompanyOut,
    CompanyPatch,
    ContactIn,
    ContactList,
    ContactOut,
    ContactPatch,
    DealBoard,
    DealIn,
    DealList,
    DealMove,
    DealOut,
    DealPatch,
    LinkContactIn,
    MemberIn,
    MemberOut,
    OrgOut,
    OrgPatch,
    SearchResults,
    Timeline,
    TimelineItem,
)

router = APIRouter(prefix="/api/crm", tags=["crm"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _full_name(first: str | None, last: str | None, explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    return " ".join(p for p in [(first or "").strip(), (last or "").strip()] if p).strip()


# --------------------------------------------------------------------------- #
# Contacts
# --------------------------------------------------------------------------- #


@router.get("/contacts", response_model=ContactList)
async def list_contacts(
    ctx: OrgContext = Depends(org_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order_by: str = "-created_at",
    lifecycle_stage: str | None = None,
    company_id: str | None = None,
    owner_email: str | None = None,
    q: str | None = None,
):
    extra = []
    if q and len(q) >= 2:
        like = f"%{q.strip()}%"
        extra.append(or_(Contact.full_name.ilike(like), Contact.email.ilike(like), Contact.phone.ilike(like)))
    rows, total = await repo.list_(
        ctx.session, Contact, ctx.org_id,
        filters={"lifecycle_stage": lifecycle_stage, "company_id": company_id, "owner_email": owner_email},
        order_by=order_by, limit=limit, offset=offset, extra_where=extra,
    )
    return ContactList(items=[ContactOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("/contacts", response_model=ContactOut, status_code=201)
async def create_contact(body: ContactIn, ctx: OrgContext = Depends(org_context)):
    data = body.model_dump()
    data["full_name"] = _full_name(data.get("first_name"), data.get("last_name"), data.get("full_name"))
    if not data["full_name"] and not data.get("email") and not data.get("phone"):
        raise HTTPException(400, "A contact needs at least a name, email, or phone")
    if data.get("company_id"):
        await repo.get_or_404(ctx.session, Company, ctx.org_id, data["company_id"])
    row = await repo.create(ctx.session, Contact, ctx.org_id, ctx.email, data)
    return ContactOut.model_validate(row)


@router.get("/contacts/{contact_id}", response_model=ContactOut)
async def get_contact(contact_id: str, ctx: OrgContext = Depends(org_context)):
    return ContactOut.model_validate(await repo.get_or_404(ctx.session, Contact, ctx.org_id, contact_id))


@router.patch("/contacts/{contact_id}", response_model=ContactOut)
async def patch_contact(contact_id: str, body: ContactPatch, ctx: OrgContext = Depends(org_context)):
    data = body.model_dump(exclude_unset=True)
    if data.get("company_id"):
        await repo.get_or_404(ctx.session, Company, ctx.org_id, data["company_id"])
    if any(k in data for k in ("first_name", "last_name", "full_name")):
        current = await repo.get_or_404(ctx.session, Contact, ctx.org_id, contact_id)
        data["full_name"] = _full_name(
            data.get("first_name", current.first_name),
            data.get("last_name", current.last_name),
            data.get("full_name"),
        ) or current.full_name
    row = await repo.update(ctx.session, Contact, ctx.org_id, contact_id, data)
    return ContactOut.model_validate(row)


@router.delete("/contacts/{contact_id}", status_code=204)
async def delete_contact(contact_id: str, ctx: OrgContext = Depends(org_context)):
    await repo.delete(ctx.session, Contact, ctx.org_id, contact_id)


@router.get("/contacts/{contact_id}/timeline", response_model=Timeline)
async def contact_timeline(contact_id: str, ctx: OrgContext = Depends(org_context)):
    await repo.get_or_404(ctx.session, Contact, ctx.org_id, contact_id)
    items: list[TimelineItem] = []

    calls = await ctx.session.scalars(
        select(CallRecord).where(CallRecord.org_id == ctx.org_id, CallRecord.contact_id == contact_id)
    )
    for c in calls:
        items.append(TimelineItem(
            kind="call", id=c.id, at=c.started_at or c.created_at,
            title=f"Call — {c.outcome}", subtitle=c.persona_name,
            meta={"duration_s": c.duration_s, "escalated": c.escalated, "direction": c.direction},
        ))

    acts = await ctx.session.scalars(
        select(Activity).where(Activity.org_id == ctx.org_id, Activity.contact_id == contact_id)
    )
    for a in acts:
        items.append(TimelineItem(
            kind="activity", id=a.id, at=a.completed_at or a.due_at or a.created_at,
            title=a.subject or a.type.title(), subtitle=a.type,
            meta={"body": a.body, "completed": a.completed_at is not None, "activity_type": a.type},
        ))

    deals = await ctx.session.scalars(
        select(Deal).where(Deal.org_id == ctx.org_id, Deal.contact_id == contact_id)
    )
    for d in deals:
        items.append(TimelineItem(
            kind="deal", id=d.id, at=d.updated_at,
            title=d.title, subtitle=f"{d.stage} · {d.currency} {d.amount or 0:g}",
            meta={"stage": d.stage, "amount": float(d.amount or 0)},
        ))

    items.sort(key=lambda i: i.at, reverse=True)
    return Timeline(items=items)


# --------------------------------------------------------------------------- #
# Companies
# --------------------------------------------------------------------------- #


@router.get("/companies", response_model=CompanyList)
async def list_companies(
    ctx: OrgContext = Depends(org_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order_by: str = "-created_at",
    q: str | None = None,
):
    extra = []
    if q and len(q) >= 2:
        extra.append(Company.name.ilike(f"%{q.strip()}%"))
    rows, total = await repo.list_(
        ctx.session, Company, ctx.org_id, order_by=order_by, limit=limit, offset=offset, extra_where=extra
    )
    return CompanyList(items=[CompanyOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("/companies", response_model=CompanyOut, status_code=201)
async def create_company(body: CompanyIn, ctx: OrgContext = Depends(org_context)):
    row = await repo.create(ctx.session, Company, ctx.org_id, ctx.email, body.model_dump())
    return CompanyOut.model_validate(row)


@router.get("/companies/{company_id}", response_model=CompanyOut)
async def get_company(company_id: str, ctx: OrgContext = Depends(org_context)):
    return CompanyOut.model_validate(await repo.get_or_404(ctx.session, Company, ctx.org_id, company_id))


@router.patch("/companies/{company_id}", response_model=CompanyOut)
async def patch_company(company_id: str, body: CompanyPatch, ctx: OrgContext = Depends(org_context)):
    row = await repo.update(ctx.session, Company, ctx.org_id, company_id, body.model_dump(exclude_unset=True))
    return CompanyOut.model_validate(row)


@router.delete("/companies/{company_id}", status_code=204)
async def delete_company(company_id: str, ctx: OrgContext = Depends(org_context)):
    await repo.delete(ctx.session, Company, ctx.org_id, company_id)


# --------------------------------------------------------------------------- #
# Deals
# --------------------------------------------------------------------------- #


@router.get("/deals", response_model=DealList)
async def list_deals(
    ctx: OrgContext = Depends(org_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order_by: str = "-created_at",
    stage: str | None = None,
    contact_id: str | None = None,
    owner_email: str | None = None,
):
    rows, total = await repo.list_(
        ctx.session, Deal, ctx.org_id,
        filters={"stage": stage, "contact_id": contact_id, "owner_email": owner_email},
        order_by=order_by, limit=limit, offset=offset,
    )
    return DealList(items=[DealOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/deals/board", response_model=DealBoard)
async def deal_board(ctx: OrgContext = Depends(org_context)):
    rows = await ctx.session.scalars(
        select(Deal).where(Deal.org_id == ctx.org_id).order_by(Deal.board_order.asc(), Deal.created_at.desc())
    )
    buckets: dict[str, list[Deal]] = {s: [] for s in DEAL_STAGES}
    for d in rows:
        buckets.setdefault(d.stage, []).append(d)
    columns = [
        BoardColumn(
            stage=s,
            count=len(buckets[s]),
            total_amount=float(sum(d.amount or 0 for d in buckets[s])),
            deals=[DealOut.model_validate(d) for d in buckets[s]],
        )
        for s in DEAL_STAGES
    ]
    return DealBoard(columns=columns)


@router.post("/deals", response_model=DealOut, status_code=201)
async def create_deal(body: DealIn, ctx: OrgContext = Depends(org_context)):
    data = body.model_dump()
    if data.get("contact_id"):
        await repo.get_or_404(ctx.session, Contact, ctx.org_id, data["contact_id"])
    if data.get("company_id"):
        await repo.get_or_404(ctx.session, Company, ctx.org_id, data["company_id"])
    row = await repo.create(ctx.session, Deal, ctx.org_id, ctx.email, data)
    return DealOut.model_validate(row)


@router.get("/deals/{deal_id}", response_model=DealOut)
async def get_deal(deal_id: str, ctx: OrgContext = Depends(org_context)):
    return DealOut.model_validate(await repo.get_or_404(ctx.session, Deal, ctx.org_id, deal_id))


@router.patch("/deals/{deal_id}", response_model=DealOut)
async def patch_deal(deal_id: str, body: DealPatch, ctx: OrgContext = Depends(org_context)):
    data = body.model_dump(exclude_unset=True)
    if "stage" in data:
        data = _apply_stage_side_effects(data, data["stage"])
    row = await repo.update(ctx.session, Deal, ctx.org_id, deal_id, data)
    return DealOut.model_validate(row)


@router.patch("/deals/{deal_id}/move", response_model=DealOut)
async def move_deal(deal_id: str, body: DealMove, ctx: OrgContext = Depends(org_context)):
    data: dict = {"stage": body.stage, "board_order": body.board_order}
    if body.lost_reason is not None:
        data["lost_reason"] = body.lost_reason
    data = _apply_stage_side_effects(data, body.stage)
    row = await repo.update(ctx.session, Deal, ctx.org_id, deal_id, data)
    return DealOut.model_validate(row)


def _apply_stage_side_effects(data: dict, stage: str) -> dict:
    """``closed_at`` is set on entering won/lost, cleared on leaving them."""
    if stage in ("won", "lost"):
        data.setdefault("closed_at", _now())
    else:
        data["closed_at"] = None
        data["lost_reason"] = None
    return data


@router.delete("/deals/{deal_id}", status_code=204)
async def delete_deal(deal_id: str, ctx: OrgContext = Depends(org_context)):
    await repo.delete(ctx.session, Deal, ctx.org_id, deal_id)


# --------------------------------------------------------------------------- #
# Activities / tasks
# --------------------------------------------------------------------------- #


@router.get("/activities", response_model=ActivityList)
async def list_activities(
    ctx: OrgContext = Depends(org_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order_by: str = "-created_at",
    type: str | None = None,
    contact_id: str | None = None,
    deal_id: str | None = None,
    status: str | None = Query(None, description="open | completed | overdue"),
):
    extra = []
    if status == "open":
        extra.append(Activity.completed_at.is_(None))
    elif status == "completed":
        extra.append(Activity.completed_at.is_not(None))
    elif status == "overdue":
        extra.append(Activity.completed_at.is_(None))
        extra.append(Activity.due_at.is_not(None))
        extra.append(Activity.due_at < _now())
    rows, total = await repo.list_(
        ctx.session, Activity, ctx.org_id,
        filters={"type": type, "contact_id": contact_id, "deal_id": deal_id},
        order_by=order_by, limit=limit, offset=offset, extra_where=extra,
    )
    return ActivityList(items=[ActivityOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.post("/activities", response_model=ActivityOut, status_code=201)
async def create_activity(body: ActivityIn, ctx: OrgContext = Depends(org_context)):
    data = body.model_dump()
    if not data.get("author_email"):
        data["author_email"] = ctx.email
    if data.get("contact_id"):
        await repo.get_or_404(ctx.session, Contact, ctx.org_id, data["contact_id"])
    if data.get("deal_id"):
        await repo.get_or_404(ctx.session, Deal, ctx.org_id, data["deal_id"])
    row = await repo.create(ctx.session, Activity, ctx.org_id, ctx.email, data)
    return ActivityOut.model_validate(row)


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
async def patch_activity(activity_id: str, body: ActivityPatch, ctx: OrgContext = Depends(org_context)):
    row = await repo.update(ctx.session, Activity, ctx.org_id, activity_id, body.model_dump(exclude_unset=True))
    return ActivityOut.model_validate(row)


@router.post("/activities/{activity_id}/complete", response_model=ActivityOut)
async def complete_activity(activity_id: str, ctx: OrgContext = Depends(org_context)):
    row = await repo.update(
        ctx.session, Activity, ctx.org_id, activity_id, {"completed_at": _now()}
    )
    return ActivityOut.model_validate(row)


@router.delete("/activities/{activity_id}", status_code=204)
async def delete_activity(activity_id: str, ctx: OrgContext = Depends(org_context)):
    await repo.delete(ctx.session, Activity, ctx.org_id, activity_id)


# --------------------------------------------------------------------------- #
# Calls
# --------------------------------------------------------------------------- #


@router.get("/calls", response_model=CallList)
async def list_calls(
    ctx: OrgContext = Depends(org_context),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    order_by: str = "-created_at",
    outcome: str | None = None,
    contact_id: str | None = None,
    persona_id: str | None = None,
):
    rows, total = await repo.list_(
        ctx.session, CallRecord, ctx.org_id,
        filters={"outcome": outcome, "contact_id": contact_id, "persona_id": persona_id},
        order_by=order_by, limit=limit, offset=offset,
    )
    return CallList(items=[CallOut.model_validate(r) for r in rows], total=total, limit=limit, offset=offset)


@router.get("/calls/{call_id}", response_model=CallDetail)
async def get_call(call_id: str, ctx: OrgContext = Depends(org_context)):
    return CallDetail.model_validate(await repo.get_or_404(ctx.session, CallRecord, ctx.org_id, call_id))


@router.post("/calls/{call_id}/link-contact", response_model=CallDetail)
async def link_call_contact(call_id: str, body: LinkContactIn, ctx: OrgContext = Depends(org_context)):
    await repo.get_or_404(ctx.session, Contact, ctx.org_id, body.contact_id)
    row = await repo.update(ctx.session, CallRecord, ctx.org_id, call_id, {"contact_id": body.contact_id})
    return CallDetail.model_validate(row)


# --------------------------------------------------------------------------- #
# Analytics + search
# --------------------------------------------------------------------------- #


@router.get("/analytics/overview", response_model=AnalyticsOverview)
async def analytics_overview(ctx: OrgContext = Depends(org_context)):
    return await analytics_mod.overview(ctx.session, ctx.org_id)


@router.get("/search", response_model=SearchResults)
async def crm_search(q: str = Query(..., min_length=1), ctx: OrgContext = Depends(org_context)):
    return await search_mod.search(ctx.session, ctx.org_id, q)


# --------------------------------------------------------------------------- #
# Org + members
# --------------------------------------------------------------------------- #


@router.get("/org", response_model=OrgOut)
async def get_org(ctx: OrgContext = Depends(org_context)):
    return OrgOut.model_validate(ctx.org)


@router.patch("/org", response_model=OrgOut)
async def patch_org(body: OrgPatch, ctx: OrgContext = Depends(org_context)):
    if ctx.role != "owner":
        raise HTTPException(403, "Only an org owner can rename the org")
    ctx.org.name = body.name
    await ctx.session.flush()
    return OrgOut.model_validate(ctx.org)


@router.get("/org/members", response_model=list[MemberOut])
async def get_members(ctx: OrgContext = Depends(org_context)):
    return [MemberOut.model_validate(m) for m in await list_members(ctx.session, ctx.org_id)]


@router.post("/org/members", response_model=MemberOut, status_code=201)
async def invite_member(body: MemberIn, ctx: OrgContext = Depends(org_context)):
    if ctx.role != "owner":
        raise HTTPException(403, "Only an org owner can add members")
    member = await add_member(ctx.session, ctx.org_id, body.email, body.role)
    return MemberOut.model_validate(member)
