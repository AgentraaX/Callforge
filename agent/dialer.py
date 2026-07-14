"""Outbound dialer: pulls queued leads from Redis and initiates calls.

Redis contract (see docs/REDIS_SCHEMA.md):
  dialer:queue:{campaign_id}      - list of pending leads (JSON strings), written by
                                     the campaign/dialer service (P4)
  dialer:processing:{campaign_id} - leads picked up but not yet confirmed dialed

A lead moves queue -> processing atomically (LMOVE), so a crash between
pickup and confirmation leaves it recoverable in "processing" rather than
silently dropped. It's removed from "processing" only once its outbound
room has been created and the agent dispatched to it - that's what
"pickup confirmed" means here. LMOVE's atomicity is also what prevents
two dialer instances from ever grabbing the same lead (no double-dials).

This creates the LiveKit room and dispatches the agent into it; it does
not place a real PSTN call (no SIP trunk configured in local dev) - that
wiring is a production integration detail on top of this.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from livekit_utils import create_room
from shared.constants import DIALER_PROCESSING_KEY, DIALER_QUEUE_KEY
from shared.redis_client import get_redis

logger = logging.getLogger("agent.dialer")


async def _pop_next_lead(campaign_id: str) -> tuple[dict, str] | None:
    redis = get_redis()
    queue_key = DIALER_QUEUE_KEY.format(campaign_id=campaign_id)
    processing_key = DIALER_PROCESSING_KEY.format(campaign_id=campaign_id)

    raw = await redis.lmove(queue_key, processing_key, "LEFT", "RIGHT")
    if raw is None:
        return None
    return json.loads(raw), raw


async def _confirm_pickup(campaign_id: str, raw: str) -> None:
    redis = get_redis()
    processing_key = DIALER_PROCESSING_KEY.format(campaign_id=campaign_id)
    await redis.lrem(processing_key, 1, raw)


async def _requeue_failed(campaign_id: str, raw: str) -> None:
    redis = get_redis()
    queue_key = DIALER_QUEUE_KEY.format(campaign_id=campaign_id)
    processing_key = DIALER_PROCESSING_KEY.format(campaign_id=campaign_id)
    await redis.lrem(processing_key, 1, raw)
    await redis.rpush(queue_key, raw)


async def dial_next(campaign_id: str) -> bool:
    """Pop one lead and initiate its outbound call. Returns False if the queue was empty."""
    popped = await _pop_next_lead(campaign_id)
    if popped is None:
        return False
    lead, raw = popped

    room_name = f"outbound-{lead['lead_id']}"
    logger.info(
        "Dialing lead",
        extra={"lead_id": lead["lead_id"], "phone": lead.get("phone"), "room": room_name},
    )

    try:
        await create_room(room_name)
    except Exception:
        logger.exception("Failed to initiate outbound call, requeueing", extra={"lead_id": lead["lead_id"]})
        await _requeue_failed(campaign_id, raw)
        return True

    await _confirm_pickup(campaign_id, raw)
    logger.info("Outbound call initiated", extra={"lead_id": lead["lead_id"], "room": room_name})
    return True


async def run_dialer(campaign_id: str, poll_interval: float = 2.0) -> None:
    """Continuously drain a campaign's queue, one lead at a time, in order."""
    logger.info("Dialer started", extra={"campaign_id": campaign_id})
    while True:
        picked_up = await dial_next(campaign_id)
        if not picked_up:
            await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python dialer.py <campaign_id>")
        raise SystemExit(1)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    asyncio.run(run_dialer(sys.argv[1]))
