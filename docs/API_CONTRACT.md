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
Multipart file upload, field name `file`. Must be `.csv` with `name` and `phone` columns (`company` optional). Max file size 5MB.
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
### GET /briefing/today
_Not yet built._