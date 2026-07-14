"""Day 9 test helper: seeds one campaign + one lead with enrichment_json,
so get_enrichment_for_room() has real data to look up. Prints the lead's
UUID so you can create a room named "outbound-<that-uuid>" to test with.

Usage: python seed_test_lead.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.db.session import SessionLocal
from api.models import Campaign, Lead

if __name__ == "__main__":
    with SessionLocal() as session:
        campaign = Campaign(name="Day 9 test campaign", status="active")
        session.add(campaign)
        session.flush()

        lead = Lead(
            campaign_id=campaign.id,
            name="Jordan Lee",
            phone="+15550001234",
            company="Acme Robotics",
            enrichment_json={
                "title": "VP of Engineering",
                "linkedin_summary": "Leads a 40-person engineering org, posted last month about scaling CI/CD.",
            },
        )
        session.add(lead)
        session.commit()

        print(f"lead_id={lead.id}")
        print(f"Test room name: outbound-{lead.id}")
