"""Shared Redis client — schema contract documented in docs/REDIS_SCHEMA.md.

Written by agent (P3) and dialer service (P4). Any key-shape change
requires notifying the other backend dev before merge.
"""

import os

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
    return _client
