"""Function-calling tools exposed to the LLM: book_meeting, transfer_to_human, log_objection."""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from api.db.session import SessionLocal
from api.models import Booking, Call, Lead
from api.services.calendar import create_calendar_event

logger = logging.getLogger("agent.graph.tools")


def _lead_for_call_sync(call_id: str) -> Lead | None:
    with SessionLocal() as session:
        call = session.get(Call, uuid.UUID(call_id))
        if call is None:
            return None
        lead = session.get(Lead, call.lead_id)
        if lead is None:
            return None
        session.expunge(lead)
        return lead


def _create_booking_sync(call_id: str, scheduled_at: datetime) -> str | None:
    with SessionLocal() as session:
        call = session.get(Call, uuid.UUID(call_id))
        if call is None:
            logger.warning("Booking skipped: call %s not found", call_id)
            return None
        booking = Booking(
            user_id=call.user_id,
            call_id=call_id,
            scheduled_at=scheduled_at,
        )
        session.add(booking)
        session.commit()
        session.refresh(booking)
        return str(booking.id)


def _set_booking_calendar_event_sync(booking_id: str, calendar_event_id: str) -> None:
    with SessionLocal() as session:
        booking = session.get(Booking, uuid.UUID(booking_id))
        if booking is not None:
            booking.calendar_event_id = calendar_event_id
            session.commit()


async def book_meeting(*, call_id: str, scheduled_at: datetime | None = None, **_kwargs) -> None:
    """Create a Booking row for call_id, then try to create a real Cal.com
    calendar event for it (Day 8). The Booking always gets created even if
    the calendar side fails or the lead has no email on file - only
    calendar_event_id is affected, never the booking itself.

    nodes.py's book_or_route doesn't pass scheduled_at yet - CallState has no
    field for a negotiated meeting time (see agent/graph/state_machine.py).
    Defaults to +1 day as a visible placeholder rather than guessing; wire a
    real time through CallState once the graph captures the negotiated slot.
    """
    if scheduled_at is None:
        scheduled_at = datetime.now(timezone.utc) + timedelta(days=1)
        logger.warning(
            "book_meeting called without scheduled_at, defaulting to +1 day",
            extra={"call_id": call_id},
        )

    booking_id = await asyncio.to_thread(_create_booking_sync, call_id, scheduled_at)

    lead = await asyncio.to_thread(_lead_for_call_sync, call_id)
    if lead is None:
        logger.warning("No lead found for call, skipping calendar event", extra={"call_id": call_id})
        return

    event = await asyncio.to_thread(
        create_calendar_event, lead.name, lead.email, scheduled_at
    )
    if event is not None:
        await asyncio.to_thread(_set_booking_calendar_event_sync, booking_id, event["uid"])


async def transfer_to_human(*, call_id: str, **_kwargs) -> None:
    """Log a human-handoff request for call_id.

    No "transferred" value exists in _VALID_STATUSES (api/routers/calls.py:14)
    - setting status="completed" here would misrepresent an escalation as a
    successful AI-only resolution. Logging only until a real status value or
    dedicated handoff field is added to the calls schema (P4).
    """
    logger.info("transfer_to_human requested", extra={"call_id": call_id})


async def log_objection(*, call_id: str, text: str | None = None, **_kwargs) -> None:
    """Log a prospect objection raised during call_id.

    api/models/objection.py's `objections` table is a playbook (text/response/
    category/success_rate) with no call_id or timestamp column - it's a
    reference catalog, not a per-call event log, so writing one row per raised
    objection would corrupt its aggregate-stats semantics. Logging only until
    a per-call objection log surface exists (P4).
    """
    logger.info("log_objection", extra={"call_id": call_id, "objection_text": text})
