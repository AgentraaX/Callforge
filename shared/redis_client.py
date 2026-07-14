"""Shared Redis client — schema contract documented in docs/REDIS_SCHEMA.md.

Written by agent (P3) and dialer service (P4). Any key-shape change
requires notifying the other backend dev before merge.
"""

import asyncio
import os

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Keyed by event loop, not a single global — an asyncio Redis connection is
# bound to the loop it was created on. LiveKit Agents runs each job in its
# own thread with its own loop (Day 10 surfaced this: a single cached
# client crashed with "Future attached to a different loop" as soon as two
# job threads both called get_redis()).
_clients: dict[int, redis.Redis] = {}


def get_redis() -> redis.Redis:
    loop_id = id(asyncio.get_running_loop())
    client = _clients.get(loop_id)
    if client is None:
        client = redis.from_url(REDIS_URL, decode_responses=True)
        _clients[loop_id] = client
    return client
