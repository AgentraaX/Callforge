# Redis Schema — Shared Contract Between P3 (Agent) and P4 (API)

Agreed Day 1. Any change to a key's shape requires notifying the other
backend dev before merge, not after.

| Key pattern | Written by | Read by | TTL |
|---|---|---|---|
| `call:{call_id}:state` | Agent (P3) | Dashboard API, Ghost Mode | Call duration |
| `call:{call_id}:transcript_buffer` | Agent (P3) | WebSocket broadcaster (P4) | Call duration |
| `call:{call_id}:sentiment` | Agent (P3) | Dashboard (P4) | Call duration |
| `dialer:queue:{campaign_id}` | Dialer service (P4) | Agent (P3, on pickup) | Until dialed |

Key templates live in `shared/constants.py` — import them, don't hardcode key strings.
