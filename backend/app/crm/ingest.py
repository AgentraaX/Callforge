"""Persist a finished call into the CRM.

Called once when a call ends (from ``realtime/ws.py`` teardown, and from the
LiveKit worker via ``/internal/calls/{id}/finalize``). Reads the in-memory
``bus`` call doc plus the live ``LEADS`` / ``BOOKINGS`` / ``CASES`` stores and
mirrors them into Postgres:

  * upsert a :class:`Contact` matched on phone number,
  * write a :class:`CallRecord` (idempotent on the bus call id),
  * drop a ``call`` :class:`Activity` on the contact's timeline,
  * if the agent confirmed a booking, open (or advance) a :class:`Deal`.

Fully guarded -- a misconfigured DB or a call with no org attached is a
logged no-op, never an exception into the websocket teardown path.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select

from ..db import db_ready, session_scope
from ..db.models import Activity, CallRecord, Contact, Deal
from ..realtime.bus import bus
from ..sales import booking as booking_mod
from ..sales import escalation as escalation_mod
from ..sales import leads as leads_mod

log = logging.getLogger("callforge.crm.ingest")

_E164 = re.compile(r"^\+[1-9]\d{6,14}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(epoch: float | None) -> datetime | None:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _derive_outcome(call: dict, lead: dict | None, booked: bool) -> str:
    if booked:
        return "booked"
    if call.get("escalated"):
        return "escalated"
    next_step = (lead or {}).get("next_step")
    if next_step == "callback":
        return "callback"
    if next_step == "not_interested":
        return "declined"
    return "none"


def _bookings_for_call(call_id: str) -> list:
    return [b for b in booking_mod.BOOKINGS.values() if b.call_id == call_id]


def _case_for_call(call_id: str):
    return next((c for c in escalation_mod.CASES.values() if c.call_id == call_id), None)


async def persist_call(call_id: str) -> str | None:
    """Mirror one finished call into the CRM. Returns the CallRecord id, or
    None if nothing was written. Safe to call more than once per call."""
    if not db_ready():
        return None

    call = bus.calls.get(call_id)
    if not call:
        return None
    org_id = call.get("org_id")
    owner_email = call.get("owner_email") or ""
    if not org_id and not owner_email:
        log.debug("persist_call %s skipped -- no org/owner on the call doc", call_id)
        return None

    lead_obj = leads_mod.get(call_id)
    lead = None
    if lead_obj is not None:
        from dataclasses import asdict

        lead = asdict(lead_obj)
    elif isinstance(call.get("lead"), dict):
        lead = call["lead"]

    bookings = _bookings_for_call(call_id)
    booked = len(bookings) > 0
    case = _case_for_call(call_id)

    agent = call.get("agent") or {}
    to_number = call.get("caller") or (lead or {}).get("contact_phone")
    phone = to_number if to_number and _E164.match(str(to_number)) else (lead or {}).get("contact_phone")

    started = _ts(call.get("started_at"))
    ended = _now()
    duration = (ended - started).total_seconds() if started else 0.0

    try:
        session = await session_scope()
    except RuntimeError:
        return None

    async with session:
        try:
            if not org_id:
                from .orgs import resolve_org_id

                org_id = await resolve_org_id(session, owner_email)
                if not org_id:
                    await session.rollback()
                    return None

            contact = None
            if phone and _E164.match(str(phone)):
                contact = await session.scalar(
                    select(Contact).where(Contact.org_id == org_id, Contact.phone == str(phone))
                )
                if contact is None:
                    contact = Contact(
                        org_id=org_id,
                        owner_email=owner_email,
                        phone=str(phone),
                        full_name=(lead or {}).get("contact_name") or "",
                        company_id=None,
                        email=None,
                        lifecycle_stage="lead",
                        source="cold_call",
                        last_contacted_at=ended,
                    )
                    session.add(contact)
                    await session.flush()
                else:
                    contact.last_contacted_at = ended
                    if not contact.full_name and (lead or {}).get("contact_name"):
                        contact.full_name = lead["contact_name"]

            record = await session.get(CallRecord, call_id)
            first_write = record is None
            if record is None:
                record = CallRecord(id=call_id, org_id=org_id, owner_email=owner_email)
                session.add(record)

            record.persona_id = agent.get("id")
            record.persona_name = agent.get("name")
            record.direction = "outbound"
            record.from_number = None
            record.to_number = str(to_number) if to_number else None
            record.contact_id = contact.id if contact else record.contact_id
            record.status = "completed"
            record.outcome = _derive_outcome(call, lead, booked)
            record.started_at = started
            record.ended_at = ended
            record.duration_s = round(duration, 1)
            record.language = call.get("language") or "en"
            record.escalated = bool(call.get("escalated"))
            record.case_id = call.get("case_id") or (case.case_id if case else None)
            record.transcript = list(call.get("transcript") or [])
            record.lead_snapshot = lead
            await session.flush()

            if contact is not None:
                existing_activity = await session.scalar(
                    select(Activity).where(Activity.org_id == org_id, Activity.call_id == call_id)
                )
                if existing_activity is None:
                    session.add(Activity(
                        org_id=org_id,
                        owner_email=owner_email,
                        author_email=owner_email,
                        type="call",
                        subject=f"Call — {record.outcome}",
                        body=_transcript_preview(record.transcript),
                        completed_at=ended,
                        contact_id=contact.id,
                        call_id=call_id,
                    ))

                if booked:
                    await _ensure_deal(session, org_id, owner_email, contact, agent, bookings[0])

                if record.outcome == "booked" and contact.lifecycle_stage == "lead":
                    contact.lifecycle_stage = "sql"

            await session.commit()
            log.info("persist_call %s -> CallRecord (%s, outcome=%s, new=%s)",
                     call_id, org_id, record.outcome, first_write)
            return call_id
        except Exception as exc:  # never break call teardown
            await session.rollback()
            log.warning("persist_call %s failed: %s", call_id, exc)
            return None


def _transcript_preview(transcript: list, limit: int = 400) -> str:
    text = " ".join(f"{t.get('name', t.get('who', ''))}: {t.get('text', '')}" for t in transcript)
    return text[:limit]


async def _ensure_deal(session, org_id, owner_email, contact, agent, booking) -> None:
    """One open deal per contact -- advance it to 'demo', or create it."""
    open_deal = await session.scalar(
        select(Deal).where(
            Deal.org_id == org_id,
            Deal.contact_id == contact.id,
            Deal.stage.in_(("new", "qualified", "demo", "proposal", "negotiation")),
        )
    )
    if open_deal is not None:
        if open_deal.stage in ("new", "qualified"):
            open_deal.stage = "demo"
        return
    company = agent.get("company") or ""
    session.add(Deal(
        org_id=org_id,
        owner_email=owner_email,
        title=f"{contact.full_name or contact.phone or 'New lead'}"
              + (f" · {company}" if company else "") + " — demo booked",
        contact_id=contact.id,
        company_id=contact.company_id,
        stage="demo",
        currency="USD",
    ))
