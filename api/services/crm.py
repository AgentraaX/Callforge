"""Day 10: CRM webhook integration - pushes a call's final outcome to an
external CRM. webhook.site is the sandbox stand-in for local dev/testing;
CRM_WEBHOOK_URL swaps to a real CRM's incoming-webhook URL in production -
the payload is generic JSON, nothing webhook.site-specific.

"No silent data loss" per the acceptance criteria: a payload that exhausts
its retries is pushed onto a durable Redis queue (crm:webhook:failed)
instead of being dropped. retry_failed_webhooks() drains that queue
whenever called (manually, or wired to a schedule later).
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv

from api.db.session import SessionLocal
from api.models import Booking, Call
from shared.constants import CRM_WEBHOOK_FAILED_KEY
from shared.redis_client import get_redis

# Mirrors calendar.py/briefing.py's own load_dotenv() - no guarantee
# agent/config.py has already run first in this process.
load_dotenv()

logger = logging.getLogger("api.services.crm")

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = [1, 2, 4]  # delay before retry attempts 2 and 3


def _build_outcome_payload_sync(call_id: str, status: str) -> dict | None:
    with SessionLocal() as session:
        call = session.get(Call, uuid.UUID(call_id))
        if call is None:
            return None
        bookings = session.query(Booking).filter(Booking.call_id == call.id).all()
        return {
            "call_id": str(call.id),
            "lead_id": str(call.lead_id),
            "direction": call.direction,
            "status": status,
            "sentiment": call.sentiment,
            "duration": call.duration,
            "bookings": [
                {"scheduled_at": b.scheduled_at.isoformat(), "calendar_event_id": b.calendar_event_id}
                for b in bookings
            ],
            "pushed_at": datetime.now(timezone.utc).isoformat(),
        }


def _post_sync(url: str, payload: dict) -> None:
    response = httpx.post(url, json=payload, timeout=10.0)
    response.raise_for_status()


async def _attempt_delivery(payload: dict) -> bool:
    url = os.getenv("CRM_WEBHOOK_URL")
    if not url:
        logger.warning("CRM_WEBHOOK_URL not configured, skipping CRM push", extra={"call_id": payload.get("call_id")})
        return False

    for attempt in range(_MAX_ATTEMPTS):
        try:
            await asyncio.to_thread(_post_sync, url, payload)
            logger.info("CRM push delivered", extra={"call_id": payload.get("call_id"), "attempt": attempt + 1})
            return True
        except Exception as e:
            logger.warning(
                "CRM push attempt failed",
                extra={"call_id": payload.get("call_id"), "attempt": attempt + 1, "error": str(e)},
            )
            if attempt < _MAX_ATTEMPTS - 1:
                await asyncio.sleep(_BACKOFF_SECONDS[attempt])

    return False


async def push_call_outcome(call_id: str | None, status: str) -> None:
    """Pushes a terminal call outcome to the CRM. On exhausting retries,
    queues the payload in Redis instead of dropping it - never raises,
    mirroring every other cross-service call in this codebase."""
    if call_id is None:
        return

    try:
        payload = await asyncio.to_thread(_build_outcome_payload_sync, call_id, status)
    except Exception:
        logger.exception("Failed to build CRM outcome payload", extra={"call_id": call_id})
        return

    if payload is None:
        return

    if await _attempt_delivery(payload):
        return

    try:
        redis = get_redis()
        await redis.rpush(CRM_WEBHOOK_FAILED_KEY, json.dumps(payload))
        logger.error(
            "CRM push exhausted retries, queued for later delivery",
            extra={"call_id": call_id, "queue_key": CRM_WEBHOOK_FAILED_KEY},
        )
    except Exception:
        logger.exception("Failed to queue undelivered CRM push - data loss", extra={"call_id": call_id})


async def retry_failed_webhooks() -> int:
    """Drains the failure queue FIFO, re-attempting each payload (with its
    own internal retry/backoff). Returns the count successfully redelivered.
    Stops at the first payload that still fails and pushes it back, rather
    than busy-looping through a queue while the CRM is still down."""
    redis = get_redis()
    delivered_count = 0

    while True:
        raw = await redis.lpop(CRM_WEBHOOK_FAILED_KEY)
        if raw is None:
            break

        payload = json.loads(raw)
        if await _attempt_delivery(payload):
            delivered_count += 1
        else:
            await redis.rpush(CRM_WEBHOOK_FAILED_KEY, raw)
            break

    return delivered_count
