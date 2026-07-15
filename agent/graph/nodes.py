"""BANT qualification and objection-handling node implementations. Built Day 6.

Each node receives the full CallState, updates it, writes the new stage to Redis,
and returns the updated state. P3 wires these nodes to the voice pipeline.
"""
import json
import logging

from agent.graph.tools import book_meeting, log_objection, transfer_to_human
from shared.constants import CALL_STATE_KEY
from shared.redis_client import get_redis

logger = logging.getLogger("agent.graph.nodes")


async def _persist_state(state: dict) -> None:
    """Write full call state to Redis under the Section 5 key contract."""
    redis = get_redis()
    key = CALL_STATE_KEY.format(call_id=state["call_id"])
    await redis.set(key, json.dumps(state))


async def greet(state: dict) -> dict:
    state = {**state, "stage": "greet"}
    await _persist_state(state)
    logger.info("greet node", extra={"call_id": state["call_id"]})
    return state


async def qualify_bant(state: dict) -> dict:
    state = {**state, "stage": "qualify_bant"}
    await _persist_state(state)
    logger.info(
        "qualify_bant node",
        extra={
            "call_id": state["call_id"],
            "budget": state["budget_confirmed"],
            "authority": state["authority_confirmed"],
            "need": state["need_confirmed"],
            "timeline": state["timeline_confirmed"],
        },
    )
    return state


async def handle_objection(state: dict) -> dict:
    state = {**state, "stage": "handle_objection"}
    await _persist_state(state)
    logger.info(
        "handle_objection node",
        extra={"call_id": state["call_id"], "objection": state.get("objection_text")},
    )
    if state.get("objection_text"):
        await log_objection(call_id=state["call_id"], text=state["objection_text"])
    return state


async def book_or_route(state: dict) -> dict:
    state = {**state, "stage": "book_or_route"}
    await _persist_state(state)

    if state["need_confirmed"] and state["budget_confirmed"]:
        await book_meeting(call_id=state["call_id"])
        state = {**state, "outcome": "booked"}
        logger.info("book_or_route: booked", extra={"call_id": state["call_id"]})
    else:
        await transfer_to_human(call_id=state["call_id"])
        state = {**state, "outcome": "transferred"}
        logger.info("book_or_route: transferred", extra={"call_id": state["call_id"]})

    await _persist_state(state)
    return state


async def close(state: dict) -> dict:
    state = {**state, "stage": "close"}
    if not state.get("outcome"):
        state = {**state, "outcome": "closed_lost"}
    await _persist_state(state)
    logger.info(
        "close node",
        extra={"call_id": state["call_id"], "outcome": state["outcome"]},
    )
    return state
