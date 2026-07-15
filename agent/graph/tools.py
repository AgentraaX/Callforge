"""Function-calling tools exposed to the LLM: book_meeting, transfer_to_human, log_objection."""

import logging
from datetime import datetime, timedelta, timezone

from api.db.session import SessionLocal
from api.models import Booking

logger = logging.getLogger("agent.graph.tools")


async def book_meeting(*, call_id: str, scheduled_at: datetime | None = None, **_kwargs) -> None:
    """Create a Booking row for call_id.

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

    db = SessionLocal()
    try:
        db.add(Booking(call_id=call_id, scheduled_at=scheduled_at))
        db.commit()
    finally:
        db.close()


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
