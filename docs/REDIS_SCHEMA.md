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
| `briefing:sent:{date}` | API (P4, `api/services/briefing.py`) | API (P4) — idempotency lock, not meant to be read elsewhere | 2 days |
| `crm:webhook:failed` | Agent (P3, via `agent/call_lifecycle.py` → `api/services/crm.py`) | API/agent (P4/P3) — drained by `retry_failed_webhooks()` | Until delivered |
| `oauth:state:{state}` | API (P4, `api/services/auth.py`, on `GET /auth/{provider}/login`) | API (P4) — single-use CSRF check on `GET /auth/{provider}/callback`, deleted on read via `GETDEL` | 10 min |
| `auth:refresh:{token}` | API (P4, `api/services/auth.py`, on `/auth/login`, `/{provider}/callback`, `/auth/refresh`) | API (P4) — `/auth/refresh` (rotates via `GETDEL` + reissue), `/auth/logout` (deletes) | 30 days, reset on each rotation |

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

## Day 10 addition — CRM webhook failure queue

`crm:webhook:failed` is a plain list (RPUSH/LPOP, FIFO), each item a JSON
string of the same outcome payload `api/services/crm.py::push_call_outcome`
tried to deliver. A payload only lands here after exhausting 3 delivery
attempts (1s/2s/4s backoff) — `retry_failed_webhooks()` drains it FIFO,
re-attempting each; a still-failing payload gets pushed back and drains
stop for that call (no busy-loop against a CRM that's still down). No TTL —
an undelivered outcome must not silently expire and vanish.

## Auth addition — refresh tokens (hybrid access/refresh model)

`auth:refresh:{token}` is the source of truth for a login session; the
value is the owning user's id, plain string. Rotated on every
`/auth/refresh` call: the old key is consumed via `GETDEL` (same
single-use pattern as `oauth:state:{state}`) and a new key/token pair
issued in its place, TTL reset to the full 30 days. `/auth/logout`
deletes the key outright.

Deliberately asymmetric with access tokens: a JWT access token (15 min
default, `JWT_EXPIRE_MINUTES`) is verified locally in
`api/dependencies.py::get_current_user` and never touches Redis - only
`/auth/login`, `/{provider}/callback`, `/auth/refresh`, and
`/auth/logout` read or write this key. This means a revoked refresh
token stops new access tokens from being minted, but any access token
already issued remains valid until its own expiry - by design, not a
gap to close.
