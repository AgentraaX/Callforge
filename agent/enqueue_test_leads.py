"""Day 8 test helper.

The real enqueue side (P4's campaign/CRM service pushing real leads onto
dialer:queue:{campaign_id}) doesn't exist yet, so this pushes fake leads
onto the same queue for testing the dialer's pickup/ordering logic.

Usage: python enqueue_test_leads.py <campaign_id> <count>
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.constants import DIALER_QUEUE_KEY
from shared.redis_client import get_redis


async def main(campaign_id: str, count: int) -> None:
    redis = get_redis()
    key = DIALER_QUEUE_KEY.format(campaign_id=campaign_id)
    for i in range(1, count + 1):
        lead = {
            "lead_id": f"test-lead-{i}",
            "phone": f"+15550000{i:03d}",
            "name": f"Test Lead {i}",
            "campaign_id": campaign_id,
        }
        await redis.rpush(key, json.dumps(lead))
        print(f"Enqueued {lead['lead_id']}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python enqueue_test_leads.py <campaign_id> <count>")
        raise SystemExit(1)

    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
