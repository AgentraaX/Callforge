# Redis Schema — Shared Contract Between P3 (Agent) and P4 (API)

Agreed Day 1. Any change to a key's shape requires notifying the other
backend dev before merge, not after.

| Key pattern | Written by | Read by | TTL |
|---|---|---|---|
| `call:{call_id}:state` | Agent (P3) | Dashboard API, Ghost Mode | Call duration |
| `call:{call_id}:transcript_buffer` | Agent (P3) | WebSocket broadcaster (P4) | Call duration |
| `call:{call_id}:sentiment` | Agent (P3) | Dashboard (P4) | Call duration |
| `dialer:queue:{campaign_id}` | Dialer service (P4) | Agent (P3, on pickup) | Until dialed |
| `dialer:processing:{campaign_id}` | Agent (P3) | Agent (P3), dashboard (P4, optional — shows "currently dialing") | Until confirmed or requeued |

Key templates live in `shared/constants.py` — import them, don't hardcode key strings.

## Day 8 addition — dialer queue item shape

Each item in `dialer:queue:{campaign_id}` is a JSON string:
```json
{"lead_id": "...", "phone": "+1...", "name": "...", "campaign_id": "..."}
```

`agent/dialer.py` pops items with `LMOVE queue -> processing` (atomic — no
two dialer instances can grab the same lead), creates the outbound
LiveKit room, and only then removes the item from `processing`. If room
creation fails, the item is pushed back onto `queue` for retry rather
than lost. Until P4's real campaign/CRM service populates `queue`,
`agent/enqueue_test_leads.py` pushes fake leads for testing.
