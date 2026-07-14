"""Standalone test: invoke the LangGraph BANT flow on a fake CallState, then
confirm the nodes actually wrote to Redis.

Run from the project root:
    python scripts/test_langgraph_flow.py

Scenario 1 — all BANT False: graph loops qualify_bant <-> handle_objection
until recursion_limit. Verifies Redis writes by early nodes.

Scenario 2 — all BANT True: graph runs the full path to close. Verifies
stage=="close" and outcome is set.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.graph.state_machine import compiled_graph
from api.services.call_state import get_call_state


async def run_scenario(label: str, bant: bool, recursion_limit: int) -> None:
    print(f"\n{'=' * 60}")
    print(label)
    print('=' * 60)

    initial_state = {
        "call_id": "test-123",
        "stage": "",
        "transcript": [],
        "budget_confirmed": bant,
        "authority_confirmed": bant,
        "need_confirmed": bant,
        "timeline_confirmed": bant,
        "objection_text": None,
        "outcome": None,
    }

    print("Invoking compiled_graph ...")
    try:
        final_state = await compiled_graph.ainvoke(
            initial_state,
            config={"recursion_limit": recursion_limit},
        )
        print(f"  stage  : {final_state['stage']}")
        print(f"  outcome: {final_state['outcome']}")
    except Exception as e:
        print(f"  Graph halted: {type(e).__name__}: {e}")

    print("\nChecking Redis for call state ...")
    state_from_redis = await get_call_state("test-123")
    if state_from_redis:
        print(f"  Redis OK — stage in Redis: {state_from_redis.get('stage')}")
    else:
        print("  Redis EMPTY — nodes did not write (is Redis running?)")


async def main() -> None:
    await run_scenario(
        label="Scenario 1: incomplete BANT (expect loop)",
        bant=False,
        recursion_limit=6,
    )
    await run_scenario(
        label="Scenario 2: complete BANT (expect full path to close)",
        bant=True,
        recursion_limit=20,
    )


if __name__ == "__main__":
    asyncio.run(main())
