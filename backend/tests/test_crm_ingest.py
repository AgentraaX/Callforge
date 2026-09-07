"""persist_call() -- the voice-agent -> CRM bridge."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _clean_stores():
    from app.realtime.bus import bus
    from app.sales import booking, escalation, leads

    bus.calls.clear()
    leads.LEADS.clear()
    booking.BOOKINGS.clear()
    escalation.CASES.clear()
    yield
    bus.calls.clear()
    leads.LEADS.clear()
    booking.BOOKINGS.clear()
    escalation.CASES.clear()


async def _seed_call(call_id: str, *, phone: str, owner: str, transcript=None, escalated=False):
    from app.realtime.bus import bus

    call = bus.open_call(call_id, caller=phone, owner_email=owner)
    call["agent"] = {"id": "persona-1", "name": "Sam", "company": "Acme"}
    call["transcript"] = transcript or [{"who": "agent", "name": "Sam", "text": "Hi there"}]
    call["escalated"] = escalated
    return call


async def test_ingest_creates_contact_call_and_activity(app, client, alice_headers):
    # alice_headers forces her org to exist
    await client.get("/api/crm/contacts", headers=alice_headers)

    from app.crm.ingest import persist_call

    await _seed_call("callaaaa01", phone="+14155559001", owner="alice@acme.test")
    rec_id = await persist_call("callaaaa01")
    assert rec_id == "callaaaa01"

    calls = (await client.get("/api/crm/calls", headers=alice_headers)).json()
    assert calls["total"] == 1
    assert calls["items"][0]["to_number"] == "+14155559001"

    contacts = (await client.get("/api/crm/contacts", headers=alice_headers)).json()
    assert contacts["total"] == 1
    contact_id = contacts["items"][0]["id"]
    assert contacts["items"][0]["phone"] == "+14155559001"
    assert contacts["items"][0]["source"] == "cold_call"

    timeline = (await client.get(f"/api/crm/contacts/{contact_id}/timeline", headers=alice_headers)).json()
    kinds = [i["kind"] for i in timeline["items"]]
    assert "call" in kinds and "activity" in kinds


async def test_ingest_is_idempotent_and_matches_existing_contact(app, client, alice_headers):
    await client.get("/api/crm/contacts", headers=alice_headers)

    from app.crm.ingest import persist_call

    await _seed_call("callaaaa02", phone="+14155559002", owner="alice@acme.test")
    await persist_call("callaaaa02")
    await persist_call("callaaaa02")  # again -- must not duplicate

    assert (await client.get("/api/crm/calls", headers=alice_headers)).json()["total"] == 1
    assert (await client.get("/api/crm/contacts", headers=alice_headers)).json()["total"] == 1

    # A second call to the same number reuses the contact
    await _seed_call("callaaaa03", phone="+14155559002", owner="alice@acme.test")
    await persist_call("callaaaa03")
    assert (await client.get("/api/crm/calls", headers=alice_headers)).json()["total"] == 2
    assert (await client.get("/api/crm/contacts", headers=alice_headers)).json()["total"] == 1


async def test_ingest_booking_opens_a_deal(app, client, alice_headers):
    await client.get("/api/crm/contacts", headers=alice_headers)

    from app.crm.ingest import persist_call
    from app.sales import booking

    await _seed_call("callaaaa04", phone="+14155559004", owner="alice@acme.test")
    booking.confirm(call_id="callaaaa04", slot_id="s1", slot_label="Mon 10:00", contact_name="Pat")

    await persist_call("callaaaa04")

    calls = (await client.get("/api/crm/calls", headers=alice_headers)).json()
    assert calls["items"][0]["outcome"] == "booked"

    deals = (await client.get("/api/crm/deals", headers=alice_headers)).json()
    assert deals["total"] == 1
    assert deals["items"][0]["stage"] == "demo"


async def test_ingest_noop_without_owner(app):
    from app.crm.ingest import persist_call
    from app.realtime.bus import bus

    bus.open_call("callaaaa05", caller="+14155559005")  # no owner_email
    assert await persist_call("callaaaa05") is None
