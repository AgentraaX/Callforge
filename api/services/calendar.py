"""Day 8: Cal.com calendar integration.

book_meeting (agent/graph/tools.py) calls create_calendar_event() after
writing the Booking row, so a booked call produces a real calendar event,
not just a DB row. Never raises - a Cal.com outage or a lead with no email
on file must not break the booking flow; the Booking still exists locally
with calendar_event_id left None, same graceful-degrade pattern as every
other cross-service call in this codebase (enrichment, ab_testing).

Timezone handling (the acceptance criteria explicitly calls this out as a
common silent bug): `start` MUST be sent in UTC. `scheduled_at` is stored as
a tz-aware UTC datetime end to end (see call_lifecycle.py's book_meeting
default) - _to_utc_z() converts to UTC before formatting instead of trusting
the caller, so a naive or non-UTC datetime can't silently get sent as if it
were UTC.
"""

import logging
import os
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

# api/ has no shared config module that loads .env (unlike agent/config.py) -
# this module is reached via agent/graph/tools.py today, where config.py's
# own load_dotenv() happens to run first, but that's import-order luck, not
# a guarantee if api/ is ever driven standalone. Load here so this module
# doesn't silently depend on another package's side effect.
load_dotenv()

logger = logging.getLogger("api.services.calendar")

CAL_API_BASE = "https://api.cal.com/v2"
CAL_API_VERSION = "2026-02-25"  # bookings endpoint - see cal.com/docs/api-reference/v2/bookings


def _to_utc_z(dt: datetime) -> str:
    """Formats dt as Cal.com's expected UTC string (e.g. "2024-08-13T09:00:00Z").
    Converts to UTC first rather than assuming the caller already did -
    a naive datetime is assumed UTC (matches how it's produced upstream),
    never silently reinterpreted as local time."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_calendar_event(
    attendee_name: str,
    attendee_email: str,
    start_time: datetime,
    duration_minutes: int = 30,
) -> dict | None:
    """Creates a real Cal.com booking. Returns {"id": int, "uid": str} on
    success, or None (missing config, missing email, or API failure - all
    logged, never raised)."""
    api_key = os.getenv("CAL_API_KEY")
    event_type_id = os.getenv("CAL_EVENT_TYPE_ID")
    if not api_key or not event_type_id:
        logger.warning("Cal.com not configured (CAL_API_KEY/CAL_EVENT_TYPE_ID missing), skipping calendar event")
        return None

    if not attendee_email:
        logger.warning("No email on file for lead, skipping calendar event", extra={"attendee_name": attendee_name})
        return None

    body = {
        "eventTypeId": int(event_type_id),
        "start": _to_utc_z(start_time),
        "attendee": {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": "UTC",  # not collected per-lead yet; start above is authoritative UTC regardless
        },
    }

    try:
        response = httpx.post(
            f"{CAL_API_BASE}/bookings",
            json=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "cal-api-version": CAL_API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Cal.com booking creation failed",
            extra={"status_code": e.response.status_code, "body": e.response.text[:500]},
        )
        return None
    except Exception:
        logger.exception("Cal.com request failed")
        return None

    data = response.json().get("data", {})
    booking_id, uid = data.get("id"), data.get("uid")
    if uid is None:
        logger.error("Cal.com response missing booking uid", extra={"response": data})
        return None

    logger.info("Calendar event created", extra={"booking_id": booking_id, "uid": uid})
    return {"id": booking_id, "uid": uid}
