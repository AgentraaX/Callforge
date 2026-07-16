"""Standalone integration test: creates a real campaign + lead directly in
Postgres (same fixture pattern as test_langgraph_flow.py's
_create_fixture_call), then exercises the /leads endpoints in-process
(httpx against the actual FastAPI app via ASGI transport) and confirms
both the HTTP responses and what Postgres actually holds afterward.

Run from the project root:
    python tests/integration/test_leads_flow.py

Requires local Postgres reachable via DATABASE_URL (see .env.example).
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dotenv import load_dotenv

load_dotenv()

import httpx  # noqa: E402

from api.db.session import SessionLocal  # noqa: E402
from api.main import app  # noqa: E402
from api.models import Campaign, Lead  # noqa: E402

TEST_CAMPAIGN_NAME = f"test-leads-flow-{uuid.uuid4().hex[:8]}"
TEST_LEAD_NAME = "Leads Flow Test Lead"
TEST_LEAD_PHONE = "+15550009999"

_passed = 0
_failed = 0


def _check(label: str, condition: bool, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS - {label}")
    else:
        _failed += 1
        print(f"  FAIL - {label} {detail}")


def _create_fixture() -> tuple[uuid.UUID, uuid.UUID]:
    db = SessionLocal()
    try:
        campaign = Campaign(name=TEST_CAMPAIGN_NAME)
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        lead = Lead(campaign_id=campaign.id, name=TEST_LEAD_NAME, phone=TEST_LEAD_PHONE, status="new")
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return campaign.id, lead.id
    finally:
        db.close()


def _cleanup(campaign_id: uuid.UUID, lead_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        db.query(Lead).filter(Lead.id == lead_id).delete()
        db.query(Campaign).filter(Campaign.id == campaign_id).delete()
        db.commit()
    finally:
        db.close()


async def main() -> None:
    print("\n0. Setup: creating test campaign + lead directly in Postgres")
    campaign_id, lead_id = _create_fixture()
    print(f"  campaign_id={campaign_id} lead_id={lead_id}")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:

        print("\n1. GET /leads")
        r = await client.get("/leads", params={"campaign_id": str(campaign_id)})
        _check("returns 200", r.status_code == 200, f"got {r.status_code}: {r.text}")
        body = r.json()
        _check(
            "response has pagination shape (items/total/page/page_size)",
            all(k in body for k in ("items", "total", "page", "page_size")),
            f"got keys: {list(body.keys())}",
        )
        ids_in_response = [item["id"] for item in body.get("items", [])]
        _check("test lead appears in results", str(lead_id) in ids_in_response)

        print("\n2. GET /leads/{id}")
        r2 = await client.get(f"/leads/{lead_id}")
        _check("returns 200", r2.status_code == 200, f"got {r2.status_code}: {r2.text}")
        body2 = r2.json()
        _check("correct id returned", body2.get("id") == str(lead_id))
        _check("correct name returned", body2.get("name") == TEST_LEAD_NAME)
        _check("correct phone returned", body2.get("phone") == TEST_LEAD_PHONE)
        _check("correct campaign_id returned", body2.get("campaign_id") == str(campaign_id))

        print("\n3. GET /leads/{random-uuid} (should not exist)")
        random_id = uuid.uuid4()
        r3 = await client.get(f"/leads/{random_id}")
        _check("returns 404", r3.status_code == 404, f"got {r3.status_code}: {r3.text}")

        print("\n4. PATCH /leads/{id} with a valid status")
        r4 = await client.patch(f"/leads/{lead_id}", json={"status": "contacted"})
        _check("returns 200", r4.status_code == 200, f"got {r4.status_code}: {r4.text}")
        _check("response reflects the new status", r4.json().get("status") == "contacted")

        db = SessionLocal()
        try:
            refreshed = db.get(Lead, lead_id)
            _check(
                "DB actually reflects the change",
                refreshed is not None and refreshed.status == "contacted",
                f"got status={getattr(refreshed, 'status', None)!r}",
            )
        finally:
            db.close()

        print("\n5. PATCH /leads/{id} with an invalid status")
        r5 = await client.patch(f"/leads/{lead_id}", json={"status": "banana"})
        _check("rejected (400), not silently accepted", r5.status_code == 400, f"got {r5.status_code}: {r5.text}")

        db = SessionLocal()
        try:
            unchanged = db.get(Lead, lead_id)
            _check(
                "DB status unchanged after the rejected update",
                unchanged is not None and unchanged.status == "contacted",
                f"got status={getattr(unchanged, 'status', None)!r}",
            )
        finally:
            db.close()

    print("\n6. Cleanup: deleting test lead + campaign")
    _cleanup(campaign_id, lead_id)
    db = SessionLocal()
    try:
        _check("test lead deleted, test is repeatable", db.get(Lead, lead_id) is None)
        _check("test campaign deleted, test is repeatable", db.get(Campaign, campaign_id) is None)
    finally:
        db.close()

    print(f"\n{'=' * 60}\n{_passed} passed, {_failed} failed\n{'=' * 60}")
    if _failed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
