# API Contract
Owner: Person 4. Update this file in the same PR as any endpoint change — frontend
and the agent both rely on this being current, not the code being "self-documenting."

## Auth
### POST /auth/login
_Request/response shape TBD — not yet built._

## Campaigns

### GET /campaigns
Returns list of all campaigns, newest first.
**Response 200:**
```json
[
  {
    "id": "uuid",
    "name": "string",
    "status": "draft | active | paused | completed",
    "pitch_variant_a": "string | null",
    "pitch_variant_b": "string | null",
    "created_at": "iso8601",
    "updated_at": "iso8601"
  }
]
```

### POST /campaigns
**Request:**
```json
{
  "name": "string (required)",
  "pitch_variant_a": "string | null",
  "pitch_variant_b": "string | null"
}
```
**Response 201:** same shape as GET item above. `status` defaults to `"draft"`.

### GET /campaigns/{id}
**Response 200:** same shape as GET item above.
**Response 404:** `{"detail": "Campaign not found"}`

### PATCH /campaigns/{id}
**Request:** any subset of `name`, `status`, `pitch_variant_a`, `pitch_variant_b`. Only provided fields are updated.
**Response 200:** updated campaign object.
**Response 404:** `{"detail": "Campaign not found"}`

### POST /campaigns/{id}/leads
Multipart file upload, field name `file`. Must be `.csv` with `name` and `phone` columns (`company`, `email` optional). Max file size 5MB.
`email` is required for Day 8's Cal.com calendar integration to create a
real attendee-linked event on `book_meeting` (see `api/services/calendar.py`)
— without it, the booking is still recorded in the `bookings` table, just
with `calendar_event_id` left `null`. There's no REST surface over
`bookings` yet (not in Section 6 of the spec doc); it's written internally
by `agent/graph/tools.py::book_meeting`.
**Response 201:**
```json
{
  "created": 2,
  "skipped": 0,
  "errors": []
}
```
**Response 400:** missing required columns or wrong file type.
**Response 404:** campaign not found.
**Response 413:** file exceeds 5MB.

## Calls

> **Room creation must go through `agent/livekit_utils.py:create_room()`**, not a raw
> LiveKit `CreateRoomRequest`. LiveKit does not auto-dispatch any agent to a new
> room by default (Day 3 finding) — `create_room()` attaches the
> `RoomAgentDispatch` for `callforge-voice-agent` so the voice agent actually
> joins. A room created any other way will sit empty.

### GET /calls
**Query params:**
- `page` (int, default 1, min 1)
- `page_size` (int, default 20, min 1, max 100)
- `status` (string, optional) — one of: `pending`, `active`, `completed`, `failed`, `no-answer`

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "lead_id": "uuid",
      "direction": "inbound | outbound",
      "status": "pending | active | completed | failed | no-answer",
      "sentiment": "string | null",
      "duration": 120,
      "recording_url": "string | null",
      "created_at": "iso8601"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```
**Response 400:** invalid status value.

### GET /calls/{id}
**Response 200:** single call object (same shape as items above).
**Response 404:** `{"detail": "Call not found"}`

### GET /calls/{id}/live
Day 7: Redis-backed live state for a dashboard to poll during an active call
(Section 5 contract: `call:{call_id}:state` / `:sentiment`, written by the
agent — see `agent/call_lifecycle.py`).
**Response 200:**
```json
{
  "call_id": "uuid",
  "status": "pending | active | completed | failed | no-answer",
  "live_status": "string | null",
  "live_updated_at": "iso8601 | null",
  "sentiment": "string | null"
}
```
`status` is the durable Postgres value. `live_status`/`live_updated_at`
reflect the last Redis write from the agent and are `null` if the call
never ran through the agent, or the key expired.
**Response 404:** `{"detail": "Call not found"}`

### GET /calls/{id}/transcript
**Query params:** `page` (default 1), `page_size` (default 50, max 100). Ordered oldest → newest.
**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "call_id": "uuid",
      "speaker": "agent | prospect",
      "text": "string",
      "timestamp": "iso8601"
    }
  ],
  "total": 38,
  "page": 1,
  "page_size": 50
}
```
**Response 404:** `{"detail": "Call not found"}`

### POST /calls/{id}/takeover
_Not yet built — Day 5._

### WS /calls/{id}/stream
_Not yet built — Day 5._

## Objections
### GET /objections
### POST /objections
### PATCH /objections/{id}
_Not yet built._

## Analytics
### GET /analytics/conversion
### GET /analytics/objections
_Not yet built._

### GET /briefing/today
Day 9. Covers the day that just ended (an 8 AM briefing summarizes
yesterday, not the still-in-progress today) - same data structure the
scheduled email is built from (`api/services/briefing.py`), so the in-app
view and the emailed version can never show different numbers.
**Response 200:**
```json
{
  "date": "2026-07-14",
  "total_calls": 8,
  "calls_by_status": {"completed": 1, "active": 7},
  "bookings_made": 7,
  "booking_times": ["iso8601", "..."],
  "active_campaigns": 2
}
```

**Scheduled job:** `send_daily_briefing()` runs daily at 8 AM (APScheduler,
`api/main.py`'s lifespan) via generic SMTP - `SMTP_HOST`/`SMTP_PORT`/
`SMTP_USERNAME`/`SMTP_PASSWORD`/`SMTP_FROM_EMAIL`/`BRIEFING_RECIPIENT_EMAIL`
in `.env`, works with any provider (Gmail, Outlook, a company mail server).
Idempotent per date via a Redis lock (`briefing:sent:{date}`) - a manual
trigger outside the schedule, or the job firing twice, never double-sends;
a failed send releases the lock so a genuine retry still goes through.