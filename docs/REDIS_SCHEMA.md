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
| `ghost_mode:{room_name}:note` | Agent (P3, whisper job) | Agent (P3, main call job) | 5 min or until read |
| `call:{room_name}:pitch_variant` | Agent (P3) | Agent (P3); should also be read by P4 at call-end and persisted to `calls.pitch_variant` (column doesn't exist yet — needs a migration) | 1 hour |

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

## Day 11 addition — pitch A/B variant assignment

`call:{room_name}:pitch_variant` holds `"A|<pitch text>"` or `"B|<pitch
text>"`, set once via `SETNX` (`agent/ab_testing.py`) the first time a
call's transcript loop runs — immutable after that, even across a job
restart. `pitch_variant_a` / `pitch_variant_b` come from the `campaigns`
table via the lead's `campaign_id`. For accurate analytics this needs to
end up in Postgres too: please add a `pitch_variant` column to `calls`
and have call-end persistence read this key before it expires (1 hour).
