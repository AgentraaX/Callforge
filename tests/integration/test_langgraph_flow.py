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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from agent.graph.state_machine import compiled_graph
from api.services.call_state import get_call_state


def _create_fixture_call() -> str:
    """Scenario 2 reaches book_or_route, which inserts a real Booking row -
    bookings.call_id is a FK to calls.id, so it needs an actual Call row to
    point at, not the placeholder "test-123" used by Scenario 1 (which never
    reaches book_meeting).
    """
    from api.db.session import SessionLocal
    from api.models import Call, Campaign, Lead, User
    from api.services.auth import hash_password

    db = SessionLocal()
    try:
        user = db.query(User).first()
        if user is None:
            user = User(email="test-langgraph-flow@example.com", password_hash=hash_password("testpass123"))
            db.add(user)
            db.commit()
            db.refresh(user)

        campaign = db.query(Campaign).filter(Campaign.user_id == user.id).first()
        if campaign is None:
            campaign = Campaign(user_id=user.id, name="LangGraph test fixture")
            db.add(campaign)
            db.commit()
            db.refresh(campaign)

        lead = Lead(
            user_id=user.id,
            campaign_id=campaign.id,
            name="LangGraph test lead",
            phone="+15550001111",
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

        call = Call(user_id=user.id, lead_id=lead.id, direction="outbound", status="active")
        db.add(call)
        db.commit()
        db.refresh(call)
        return str(call.id)
    finally:
        db.close()


async def run_scenario(label: str, bant: bool, recursion_limit: int, call_id: str = "test-123") -> None:
    print(f"\n{'=' * 60}")
    print(label)
    print('=' * 60)

    initial_state = {
        "call_id": call_id,
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
    state_from_redis = await get_call_state(call_id)
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
        call_id=_create_fixture_call(),
    )


if __name__ == "__main__":
    asyncio.run(main())
