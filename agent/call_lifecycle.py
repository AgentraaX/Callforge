"""Day 7 (P4 side, built jointly): call row creation, status lifecycle, and
transcript persistence for a real call - closes the gap where `calls` and
`transcripts` were readable via the API but nothing ever wrote to them.

Mirrors enrichment.py/ab_testing.py's conventions: sync DB work wrapped in
asyncio.to_thread, lead_id resolved from the "outbound-{lead_id}" room-name
convention, and every function logs-and-swallows its own failures rather
than raising - a DB hiccup degrades bookkeeping, it must never take down a
live call.
"""

import asyncio
import json
import logging
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.db.session import SessionLocal
from api.models import Call, Transcript
from api.services.crm import push_call_outcome
from shared.constants import CALL_STATE_KEY
from shared.redis_client import get_redis

_TERMINAL_STATUSES = {"completed", "failed", "no-answer"}

logger = logging.getLogger("agent.call_lifecycle")

_OUTBOUND_ROOM_RE = re.compile(r"^outbound-(.+)$")


def _create_call_for_lead_sync(lead_id: str) -> str | None:
    try:
        lead_uuid = uuid.UUID(lead_id)
    except ValueError:
        return None

    with SessionLocal() as session:
        call = Call(lead_id=lead_uuid, direction="outbound", status="pending")
        session.add(call)
        session.commit()
        session.refresh(call)
        return str(call.id)


async def create_call_for_lead(lead_id: str) -> str | None:
    """Creates the Call row an outbound dial represents. Returns the new
    call_id, or None if the lead_id isn't a real DB lead or the write fails
    - dialer.py must still place the call either way (see its own docstring:
    bookkeeping failures don't block dialing)."""
    try:
        return await asyncio.to_thread(_create_call_for_lead_sync, lead_id)
    except Exception:
        logger.exception("Failed to create Call row for lead, continuing without one", extra={"lead_id": lead_id})
        return None


def _resolve_call_id_for_room_sync(lead_id: str) -> str | None:
    try:
        lead_uuid = uuid.UUID(lead_id)
    except ValueError:
        return None

    with SessionLocal() as session:
        call = (
            session.query(Call)
            .filter(Call.lead_id == lead_uuid)
            .order_by(Call.created_at.desc())
            .first()
        )
        return str(call.id) if call else None


async def resolve_call_id_for_room(room_name: str) -> str | None:
    """Returns the Call row id for an outbound room, or None (inbound test
    room - no room-name convention carries a lead_id for those yet - or a
    lookup failure). Callers must treat None as "no DB call to track",
    same as enrichment.get_enrichment_for_room."""
    match = _OUTBOUND_ROOM_RE.match(room_name)
    if not match:
        return None

    lead_id = match.group(1)
    try:
        return await asyncio.to_thread(_resolve_call_id_for_room_sync, lead_id)
    except Exception:
        logger.exception("Call lookup failed for room, continuing without one", extra={"lead_id": lead_id})
        return None


def _set_call_status_sync(call_id: str, status: str) -> None:
    with SessionLocal() as session:
        call = session.get(Call, uuid.UUID(call_id))
        if call is not None:
            call.status = status
            session.commit()


async def set_call_status(call_id: str | None, status: str) -> None:
    """Updates calls.status and mirrors a lightweight live-state snapshot
    into Redis (call:{call_id}:state, Section 5 contract) so a dashboard can
    poll GET /calls/{id}/live without hitting Postgres on every tick.

    Day 10: a terminal status also pushes the call's outcome to the CRM
    (api/services/crm.py) - this is the one place a real, live call reaches
    a final status today, unlike the LangGraph outcome field (booked/
    transferred/closed_lost), which isn't wired into the live pipeline yet
    (see agent/main.py's TODO). push_call_outcome still reports any Bookings
    that exist for the call, so Day 8's calendar work isn't wasted even
    though it's presently only reachable via the standalone graph test.
    """
    if call_id is None:
        return

    try:
        await asyncio.to_thread(_set_call_status_sync, call_id, status)
    except Exception:
        logger.exception("Failed to update call status", extra={"call_id": call_id, "status": status})
        return

    try:
        redis = get_redis()
        state = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
        await redis.set(CALL_STATE_KEY.format(call_id=call_id), json.dumps(state))
    except Exception:
        logger.exception("Failed to mirror call status to Redis", extra={"call_id": call_id})

    if status in _TERMINAL_STATUSES:
        await push_call_outcome(call_id, status)


def _persist_transcript_turn_sync(call_id: str, speaker: str, text: str) -> None:
    with SessionLocal() as session:
        session.add(Transcript(call_id=uuid.UUID(call_id), speaker=speaker, text=text))
        session.commit()


async def persist_transcript_turn(call_id: str | None, speaker: str, text: str) -> None:
    """Writes one turn (speaker in {"agent", "prospect"}) to the transcripts
    table. No-ops when call_id is None (inbound test room with no DB call)."""
    if call_id is None or not text:
        return

    try:
        await asyncio.to_thread(_persist_transcript_turn_sync, call_id, speaker, text)
    except Exception:
        logger.exception(
            "Failed to persist transcript turn", extra={"call_id": call_id, "speaker": speaker}
        )
