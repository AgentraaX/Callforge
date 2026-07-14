"""Day 11: A/B pitch variant testing.

Assignment happens once per outbound call and is immutable: stored in
Redis under call:{room_name}:pitch_variant with a check-then-SETNX
pattern, so a job restart (or a concurrent duplicate call) never
re-randomizes a call that's already been assigned - the same room name
always gets back the same variant once one has been picked.

Persisting the assignment into calls.pitch_variant at call-end (for
permanent cross-session analytics) is P4's job, since `calls` is their
table - see docs/REDIS_SCHEMA.md for the key they should read.
"""

import asyncio
import logging
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.db.session import SessionLocal
from api.models import Campaign, Lead
from shared.constants import CALL_PITCH_VARIANT_KEY
from shared.redis_client import get_redis

logger = logging.getLogger("agent.ab_testing")


def _fetch_campaign_pitches_sync(lead_id: str) -> tuple[str | None, str | None, str | None]:
    """Returns (campaign_id, pitch_variant_a, pitch_variant_b), any of
    which may be None if the lead/campaign is missing or unconfigured."""
    try:
        lead_uuid = uuid.UUID(lead_id)
    except ValueError:
        return None, None, None

    with SessionLocal() as session:
        lead = session.get(Lead, lead_uuid)
        if lead is None:
            return None, None, None
        campaign = session.get(Campaign, lead.campaign_id)
        if campaign is None:
            return None, None, None
        return str(campaign.id), campaign.pitch_variant_a, campaign.pitch_variant_b


async def assign_variant_for_room(room_name: str) -> dict | None:
    """Returns {"variant": "A"|"B", "pitch": <text>} for an outbound call's
    room, or None (inbound call, unknown lead/campaign, or neither pitch
    variant configured — callers must proceed with no pitch script)."""
    if not room_name.startswith("outbound-"):
        return None
    lead_id = room_name.removeprefix("outbound-")

    redis = get_redis()
    key = CALL_PITCH_VARIANT_KEY.format(room_name=room_name)

    existing = await redis.get(key)
    if existing:
        variant, pitch = existing.split("|", 1)
        return {"variant": variant, "pitch": pitch}

    try:
        campaign_id, pitch_a, pitch_b = await asyncio.to_thread(_fetch_campaign_pitches_sync, lead_id)
    except Exception:
        logger.exception("Pitch variant lookup failed, continuing without one", extra={"lead_id": lead_id})
        return None

    if campaign_id is None or not (pitch_a or pitch_b):
        return None

    variant = random.choice(["A", "B"])
    pitch = pitch_a if variant == "A" else pitch_b
    if not pitch:  # the coin-flip landed on the unconfigured variant - use whichever exists
        variant, pitch = ("B", pitch_b) if pitch_b else ("A", pitch_a)

    was_set = await redis.set(key, f"{variant}|{pitch}", nx=True, ex=3600)
    if not was_set:
        # a concurrent job (or retry) beat us to it - defer to whatever it assigned
        existing = await redis.get(key)
        variant, pitch = existing.split("|", 1)

    logger.info(
        "Pitch variant assigned",
        extra={"room": room_name, "variant": variant, "campaign_id": campaign_id},
    )
    return {"variant": variant, "pitch": pitch}
