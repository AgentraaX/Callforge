"""Pydantic request/response models for the CRM API.

``*In`` types are what routes accept (create/patch); ``*Out`` types are what
they return, built from ORM rows via ``model_validate`` (``from_attributes``).
Patch routes use ``*Patch`` with every field optional + ``exclude_unset`` so
a PATCH only touches the keys the client sent.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Common
# --------------------------------------------------------------------------- #


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(ORMModel):
    total: int
    limit: int
    offset: int


class ListParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    order_by: str = "-created_at"
    q: str | None = None


# --------------------------------------------------------------------------- #
# Company
# --------------------------------------------------------------------------- #


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    domain: str | None = None
    industry: str | None = None
    size: str | None = None
    website: str | None = None
    phone: str | None = None
    notes: str | None = None
    owner_email: str | None = None


class CompanyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    domain: str | None = None
    industry: str | None = None
    size: str | None = None
    website: str | None = None
    phone: str | None = None
    notes: str | None = None
    owner_email: str | None = None


class CompanyOut(ORMModel):
    id: str
    name: str
    domain: str | None
    industry: str | None
    size: str | None
    website: str | None
    phone: str | None
    notes: str | None
    owner_email: str
    created_at: datetime
    updated_at: datetime


class CompanyList(Page):
    items: list[CompanyOut]


# --------------------------------------------------------------------------- #
# Contact
# --------------------------------------------------------------------------- #

Lifecycle = Literal["lead", "mql", "sql", "customer", "churned"]


class ContactIn(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    company_id: str | None = None
    lifecycle_stage: Lifecycle = "lead"
    source: str | None = "manual"
    do_not_call: bool = False
    tags: list[str] = Field(default_factory=list)
    owner_email: str | None = None


class ContactPatch(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    company_id: str | None = None
    lifecycle_stage: Lifecycle | None = None
    source: str | None = None
    do_not_call: bool | None = None
    tags: list[str] | None = None
    owner_email: str | None = None


class ContactOut(ORMModel):
    id: str
    first_name: str | None
    last_name: str | None
    full_name: str
    email: str | None
    phone: str | None
    title: str | None
    company_id: str | None
    lifecycle_stage: str
    source: str | None
    do_not_call: bool
    tags: list[str]
    last_contacted_at: datetime | None
    owner_email: str
    created_at: datetime
    updated_at: datetime


class ContactOutWithCompany(ContactOut):
    company: CompanyOut | None = None


class ContactList(Page):
    items: list[ContactOut]


# --------------------------------------------------------------------------- #
# Deal
# --------------------------------------------------------------------------- #

Stage = Literal["new", "qualified", "demo", "proposal", "negotiation", "won", "lost"]


class DealIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    contact_id: str | None = None
    company_id: str | None = None
    stage: Stage = "new"
    amount: float | None = None
    currency: str = "USD"
    expected_close_date: datetime | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    owner_email: str | None = None


class DealPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    contact_id: str | None = None
    company_id: str | None = None
    stage: Stage | None = None
    amount: float | None = None
    currency: str | None = None
    expected_close_date: datetime | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    lost_reason: str | None = None
    owner_email: str | None = None


class DealMove(BaseModel):
    stage: Stage
    board_order: float = 0.0
    lost_reason: str | None = None


class DealOut(ORMModel):
    id: str
    title: str
    contact_id: str | None
    company_id: str | None
    stage: str
    amount: float | None
    currency: str
    expected_close_date: datetime | None
    probability: int | None
    lost_reason: str | None
    closed_at: datetime | None
    board_order: float
    owner_email: str
    created_at: datetime
    updated_at: datetime


class DealList(Page):
    items: list[DealOut]


class BoardColumn(BaseModel):
    stage: str
    count: int
    total_amount: float
    deals: list[DealOut]


class DealBoard(BaseModel):
    columns: list[BoardColumn]


# --------------------------------------------------------------------------- #
# Activity
# --------------------------------------------------------------------------- #

ActivityType = Literal["note", "task", "call", "email", "meeting"]


class ActivityIn(BaseModel):
    type: ActivityType = "note"
    subject: str = ""
    body: str | None = None
    due_at: datetime | None = None
    contact_id: str | None = None
    deal_id: str | None = None
    author_email: str | None = None


class ActivityPatch(BaseModel):
    type: ActivityType | None = None
    subject: str | None = None
    body: str | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None
    contact_id: str | None = None
    deal_id: str | None = None


class ActivityOut(ORMModel):
    id: str
    type: str
    subject: str
    body: str | None
    due_at: datetime | None
    completed_at: datetime | None
    contact_id: str | None
    deal_id: str | None
    call_id: str | None
    author_email: str
    owner_email: str
    created_at: datetime
    updated_at: datetime


class ActivityList(Page):
    items: list[ActivityOut]


# --------------------------------------------------------------------------- #
# Call records
# --------------------------------------------------------------------------- #


class TranscriptLine(BaseModel):
    who: str
    name: str
    text: str


class CallOut(ORMModel):
    id: str
    persona_id: str | None
    persona_name: str | None
    direction: str
    from_number: str | None
    to_number: str | None
    contact_id: str | None
    status: str
    outcome: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_s: float
    language: str
    escalated: bool
    case_id: str | None
    recording_url: str | None
    owner_email: str
    created_at: datetime


class CallDetail(CallOut):
    transcript: list[TranscriptLine]
    lead_snapshot: dict | None


class CallList(Page):
    items: list[CallOut]


class LinkContactIn(BaseModel):
    contact_id: str


# --------------------------------------------------------------------------- #
# Timeline (merged view for a contact)
# --------------------------------------------------------------------------- #


class TimelineItem(BaseModel):
    kind: Literal["call", "activity", "deal"]
    id: str
    at: datetime
    title: str
    subtitle: str | None = None
    meta: dict = Field(default_factory=dict)


class Timeline(BaseModel):
    items: list[TimelineItem]


# --------------------------------------------------------------------------- #
# Org
# --------------------------------------------------------------------------- #


class OrgOut(ORMModel):
    id: str
    name: str
    created_at: datetime


class MemberOut(ORMModel):
    email: str
    role: str
    created_at: datetime


class MemberIn(BaseModel):
    email: str
    role: Literal["owner", "member"] = "member"


class OrgPatch(BaseModel):
    name: str = Field(min_length=1, max_length=200)


# --------------------------------------------------------------------------- #
# Analytics + search
# --------------------------------------------------------------------------- #


class StageCount(BaseModel):
    stage: str
    count: int
    total_amount: float


class DayCount(BaseModel):
    date: str
    count: int


class AnalyticsOverview(BaseModel):
    contacts: int
    open_deals: int
    pipeline_value: float
    won_this_month: int
    win_rate: float
    calls_this_week: int
    bookings_this_week: int
    open_tasks: int
    overdue_tasks: int
    deals_by_stage: list[StageCount]
    calls_per_day: list[DayCount]


class SearchHit(BaseModel):
    kind: Literal["contact", "company", "deal"]
    id: str
    label: str
    sublabel: str | None = None


class SearchResults(BaseModel):
    hits: list[SearchHit]
