"""CRM data model.

One org owns everything; every row carries ``org_id`` (scoping) and
``owner_email`` (the teammate responsible). Ids are uuid4 hex strings so
records can be referenced in URLs and logs without exposing sequence counts,
and so a live ``bus`` call id can be reused verbatim as a ``CallRecord`` pk.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base, _dialect_json


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


class OrgScopedMixin(TimestampMixin):
    """Every CRM entity except Organization/OrgMembership mixes this in."""

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner_email: Mapped[str] = mapped_column(String(320), index=True, nullable=False, default="")


# --------------------------------------------------------------------------- #
# Org + membership
# --------------------------------------------------------------------------- #


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    memberships: Mapped[list["OrgMembership"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class OrgMembership(Base, TimestampMixin):
    __tablename__ = "org_memberships"
    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_membership_org_email"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")  # owner | member

    organization: Mapped[Organization] = relationship(back_populates="memberships")


# --------------------------------------------------------------------------- #
# Companies + contacts
# --------------------------------------------------------------------------- #


class Company(Base, OrgScopedMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(120))
    size: Mapped[str | None] = mapped_column(String(40))  # "1-10", "11-50", ...
    website: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")
    deals: Mapped[list["Deal"]] = relationship(back_populates="company")


CONTACT_LIFECYCLE = ("lead", "mql", "sql", "customer", "churned")


class Contact(Base, OrgScopedMixin):
    __tablename__ = "contacts"
    __table_args__ = (Index("ix_contacts_org_phone", "org_id", "phone"),)

    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    full_name: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(40))  # E.164, matched on call ingest
    title: Mapped[str | None] = mapped_column(String(160))
    company_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    lifecycle_stage: Mapped[str] = mapped_column(String(20), nullable=False, default="lead")
    source: Mapped[str | None] = mapped_column(String(80))  # "cold_call", "manual", "import", ...
    do_not_call: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[list] = mapped_column(_dialect_json(), nullable=False, default=list)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company | None] = relationship(back_populates="contacts")
    deals: Mapped[list["Deal"]] = relationship(back_populates="contact", cascade="all, delete-orphan")
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )
    calls: Mapped[list["CallRecord"]] = relationship(back_populates="contact")


# --------------------------------------------------------------------------- #
# Deals (pipeline)
# --------------------------------------------------------------------------- #


DEAL_STAGES = ("new", "qualified", "demo", "proposal", "negotiation", "won", "lost")
DEAL_OPEN_STAGES = ("new", "qualified", "demo", "proposal", "negotiation")


class Deal(Base, OrgScopedMixin):
    __tablename__ = "deals"

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    contact_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    stage: Mapped[str] = mapped_column(String(20), nullable=False, default="new", index=True)
    amount: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    expected_close_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    probability: Mapped[int | None] = mapped_column()  # 0-100, optional manual override
    lost_reason: Mapped[str | None] = mapped_column(String(240))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    board_order: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    contact: Mapped[Contact | None] = relationship(back_populates="deals")
    company: Mapped[Company | None] = relationship(back_populates="deals")
    activities: Mapped[list["Activity"]] = relationship(back_populates="deal")


# --------------------------------------------------------------------------- #
# Activities (unified timeline: notes, tasks, logged calls/emails/meetings)
# --------------------------------------------------------------------------- #


ACTIVITY_TYPES = ("note", "task", "call", "email", "meeting")


class Activity(Base, OrgScopedMixin):
    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_org_due", "org_id", "due_at"),)

    type: Mapped[str] = mapped_column(String(20), nullable=False, default="note")
    subject: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    body: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    deal_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("deals.id", ondelete="SET NULL"), index=True
    )
    call_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("call_records.id", ondelete="SET NULL"), index=True
    )
    author_email: Mapped[str] = mapped_column(String(320), nullable=False, default="")

    contact: Mapped[Contact | None] = relationship(back_populates="activities")
    deal: Mapped[Deal | None] = relationship(back_populates="activities")
    call: Mapped["CallRecord | None"] = relationship(back_populates="activities")


# --------------------------------------------------------------------------- #
# Call history (persisted from the in-memory bus when a call ends)
# --------------------------------------------------------------------------- #


CALL_OUTCOMES = ("booked", "callback", "declined", "escalated", "none")


class CallRecord(Base, OrgScopedMixin):
    __tablename__ = "call_records"

    # id == the live bus call_id (10-hex). Overrides OrgScopedMixin default so
    # persist_call() can upsert idempotently on the same key.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    persona_id: Mapped[str | None] = mapped_column(String(32))
    persona_name: Mapped[str | None] = mapped_column(String(120))
    direction: Mapped[str] = mapped_column(String(12), nullable=False, default="outbound")
    from_number: Mapped[str | None] = mapped_column(String(40))
    to_number: Mapped[str | None] = mapped_column(String(40))
    contact_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("contacts.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    outcome: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    case_id: Mapped[str | None] = mapped_column(String(32))
    transcript: Mapped[list] = mapped_column(_dialect_json(), nullable=False, default=list)
    lead_snapshot: Mapped[dict | None] = mapped_column(_dialect_json())
    recording_url: Mapped[str | None] = mapped_column(String(500))

    contact: Mapped[Contact | None] = relationship(back_populates="calls")
    activities: Mapped[list[Activity]] = relationship(back_populates="call")
