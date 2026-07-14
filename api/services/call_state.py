"""Redis session/state layer for live calls. Built Day 5. Owned by Person 4.

Implements the Section 5 key contract from docs/REDIS_SCHEMA.md.
P4 reads: call:{call_id}:state and call:{call_id}:sentiment (written by P3's agent).
P4 writes: dialer:queue:{campaign_id} (consumed by P3's agent on pickup).
"""
import json

from shared.constants import CALL_SENTIMENT_KEY, CALL_STATE_KEY, DIALER_QUEUE_KEY
from shared.redis_client import get_redis


async def get_call_state(call_id: str) -> dict | None:
    """Return the live call state dict for call_id, or None if the call is not active."""
    redis = get_redis()
    key = CALL_STATE_KEY.format(call_id=call_id)
    value = await redis.get(key)
    if value is None:
        return None
    return json.loads(value)


async def get_call_sentiment(call_id: str) -> str | None:
    """Return the current sentiment string for call_id, or None if not yet set."""
    redis = get_redis()
    key = CALL_SENTIMENT_KEY.format(call_id=call_id)
    return await redis.get(key)


async def push_to_dialer_queue(campaign_id: str, lead_id: str) -> None:
    """Enqueue a lead for outbound dialling under the given campaign (FIFO)."""
    redis = get_redis()
    key = DIALER_QUEUE_KEY.format(campaign_id=campaign_id)
    await redis.rpush(key, lead_id)


async def pop_from_dialer_queue(campaign_id: str) -> str | None:
    """Dequeue the next lead_id for dialling, or None if the queue is empty."""
    redis = get_redis()
    key = DIALER_QUEUE_KEY.format(campaign_id=campaign_id)
    return await redis.lpop(key)
