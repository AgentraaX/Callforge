"""End-to-end CRM API tests over the router (SQLite-backed)."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


async def test_contact_crud_and_org_scoping(client, alice_headers, carol_headers):
    # Alice creates a contact
    r = await client.post(
        "/api/crm/contacts",
        headers=alice_headers,
        json={"first_name": "Dana", "last_name": "Lee", "phone": "+14155550100", "email": "dana@lead.test"},
    )
    assert r.status_code == 201, r.text
    contact = r.json()
    assert contact["full_name"] == "Dana Lee"
    cid = contact["id"]

    # Alice lists -> sees it
    r = await client.get("/api/crm/contacts", headers=alice_headers)
    assert r.json()["total"] == 1

    # Carol (different org) cannot see or fetch it
    assert (await client.get("/api/crm/contacts", headers=carol_headers)).json()["total"] == 0
    assert (await client.get(f"/api/crm/contacts/{cid}", headers=carol_headers)).status_code == 404

    # Patch merges full_name from parts
    r = await client.patch(f"/api/crm/contacts/{cid}", headers=alice_headers, json={"last_name": "Park"})
    assert r.json()["full_name"] == "Dana Park"

    # Delete
    assert (await client.delete(f"/api/crm/contacts/{cid}", headers=alice_headers)).status_code == 204
    assert (await client.get("/api/crm/contacts", headers=alice_headers)).json()["total"] == 0


async def test_org_sharing_via_invite(client, alice_headers, bob_headers):
    # Alice (owner) invites Bob
    r = await client.post("/api/crm/org/members", headers=alice_headers, json={"email": "bob@acme.test"})
    assert r.status_code == 201, r.text

    # Alice adds a company
    r = await client.post("/api/crm/companies", headers=alice_headers, json={"name": "Globex"})
    assert r.status_code == 201

    # Bob sees the shared company
    r = await client.get("/api/crm/companies", headers=bob_headers)
    assert r.status_code == 200
    assert [c["name"] for c in r.json()["items"]] == ["Globex"]

    # Bob is a member, not an owner -> cannot invite
    r = await client.post("/api/crm/org/members", headers=bob_headers, json={"email": "x@acme.test"})
    assert r.status_code == 403


async def test_deal_board_and_move(client, alice_headers):
    r = await client.post("/api/crm/contacts", headers=alice_headers, json={"full_name": "Eve"})
    contact_id = r.json()["id"]

    r = await client.post(
        "/api/crm/deals",
        headers=alice_headers,
        json={"title": "Eve — annual plan", "contact_id": contact_id, "amount": 12000, "stage": "new"},
    )
    assert r.status_code == 201, r.text
    deal_id = r.json()["id"]

    board = (await client.get("/api/crm/deals/board", headers=alice_headers)).json()
    new_col = next(c for c in board["columns"] if c["stage"] == "new")
    assert new_col["count"] == 1
    assert new_col["total_amount"] == 12000

    # Move to won -> closed_at set, leaves the open buckets
    r = await client.patch(
        f"/api/crm/deals/{deal_id}/move", headers=alice_headers, json={"stage": "won", "board_order": 1.0}
    )
    assert r.status_code == 200, r.text
    assert r.json()["stage"] == "won"
    assert r.json()["closed_at"] is not None

    board = (await client.get("/api/crm/deals/board", headers=alice_headers)).json()
    assert next(c for c in board["columns"] if c["stage"] == "new")["count"] == 0
    assert next(c for c in board["columns"] if c["stage"] == "won")["count"] == 1


async def test_activity_complete_and_overdue_filter(client, alice_headers):
    r = await client.post("/api/crm/contacts", headers=alice_headers, json={"full_name": "Frank"})
    contact_id = r.json()["id"]

    r = await client.post(
        "/api/crm/activities",
        headers=alice_headers,
        json={"type": "task", "subject": "Follow up", "contact_id": contact_id,
              "due_at": "2020-01-01T00:00:00Z"},
    )
    assert r.status_code == 201
    task_id = r.json()["id"]

    overdue = (await client.get("/api/crm/activities?type=task&status=overdue", headers=alice_headers)).json()
    assert overdue["total"] == 1

    r = await client.post(f"/api/crm/activities/{task_id}/complete", headers=alice_headers)
    assert r.json()["completed_at"] is not None

    overdue = (await client.get("/api/crm/activities?type=task&status=overdue", headers=alice_headers)).json()
    assert overdue["total"] == 0


async def test_analytics_and_search(client, alice_headers):
    await client.post("/api/crm/companies", headers=alice_headers, json={"name": "Initech"})
    r = await client.post("/api/crm/contacts", headers=alice_headers,
                          json={"full_name": "Grace Hopper", "email": "grace@initech.test"})
    contact_id = r.json()["id"]
    await client.post("/api/crm/deals", headers=alice_headers,
                      json={"title": "Initech expansion", "contact_id": contact_id, "amount": 5000})

    overview = (await client.get("/api/crm/analytics/overview", headers=alice_headers)).json()
    assert overview["contacts"] == 1
    assert overview["open_deals"] == 1
    assert overview["pipeline_value"] == 5000
    assert len(overview["calls_per_day"]) == 14

    hits = (await client.get("/api/crm/search?q=initech", headers=alice_headers)).json()["hits"]
    kinds = {h["kind"] for h in hits}
    assert {"company", "deal"} <= kinds


async def test_requires_auth(client):
    assert (await client.get("/api/crm/contacts")).status_code == 401
