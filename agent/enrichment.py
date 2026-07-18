"""Day 9: loads a lead's enrichment data for outbound calls.

The dialer (agent/dialer.py) names outbound rooms "outbound-{lead_id}".
If a room name matches that pattern, look up the lead's `enrichment_json`
(plus name/company) from Postgres so the LLM can reference it. Returns
None for inbound calls (room name doesn't match) or when the lead/data
is missing - callers must treat None as "no enrichment, proceed normally."
"""

import asyncio
import logging
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.db.session import SessionLocal
from api.models import Lead

logger = logging.getLogger("agent.enrichment")

_OUTBOUND_ROOM_RE = re.compile(r"^outbound-(.+)$")


def _fetch_lead_sync(lead_id: str) -> dict | None:
    try:
        lead_uuid = uuid.UUID(lead_id)
    except ValueError:
        logger.info("Room's lead_id isn't a DB UUID, skipping enrichment", extra={"lead_id": lead_id})
        return None

    with SessionLocal() as session:
        lead = session.get(Lead, lead_uuid)
        if lead is None:
            logger.info("No lead found for enrichment lookup", extra={"lead_id": lead_id})
            return None

        data = {"name": lead.name, "company": lead.company}
        data.update(lead.enrichment_json or {})
        return data


async def get_enrichment_for_room(room_name: str) -> dict | None:
    """Returns enrichment data for an outbound room, or None (inbound call,
    unknown lead, or a lookup failure — never raises)."""
    match = _OUTBOUND_ROOM_RE.match(room_name)
    if not match:
        return None

    lead_id = match.group(1)
    try:
        return await asyncio.to_thread(_fetch_lead_sync, lead_id)
    except Exception:
        logger.exception("Enrichment lookup failed, continuing without it", extra={"lead_id": lead_id})
        return None
