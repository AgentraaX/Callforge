# API Contract
Owner: Person 4. Update this file in the same PR as any endpoint change — frontend
and the agent both rely on this being current, not the code being "self-documenting."

## Auth

### POST /auth/register
**Request:**
```json
{"email": "string", "password": "string"}
```
**Response 201:**
```json
{"id": "uuid", "email": "string", "role": "rep | manager | admin", "created_at": "iso8601"}
```
**Response 409:** `{"detail": "Email already registered"}`

### POST /auth/login
**Request:**
```json
{"email": "string", "password": "string"}
```
**Response 200:**
```json
{"access_token": "string (JWT)", "token_type": "bearer"}
```
**Response 401:** `{"detail": "Invalid email or password"}` — returned identically for a
wrong password and a nonexistent email (see `api/services/auth.py`'s timing-safe
`verify_password` — a real bcrypt check always runs against a dummy hash even when
no matching user exists, so response time can't be used to enumerate registered
emails either).

### GET /auth/{provider}/login
`{provider}` must be exactly one of `google`, `github`.
Redirects (302) to the provider's consent screen. A short-lived, single-use
CSRF `state` token is generated and stored in Redis (`oauth:state:{state}`,
10 min TTL — see `docs/REDIS_SCHEMA.md`), validated on the matching callback.
**Response 400:** `{"detail": "Invalid provider. Valid values: github, google"}`
**Response 503:** `{"detail": "<Provider> OAuth is not configured (...)"}` — real
Google/GitHub app credentials have not been obtained yet; each
provider independently 503s until its own `.env` vars are set (see `.env.example`).
This endpoint is a complete, spec-correct implementation per provider, not a
stub — it is untestable end-to-end only because live credentials don't exist yet.

### GET /auth/{provider}/callback
**Query params:** `code` (string, required on a successful provider redirect —
absent if the user declined consent), `state` (string, required — must match
the value issued by `/login`), `error`/`error_description` (string, present
instead of `code` if the user declined consent on the provider's screen).
**Response 200:** same shape as `POST /auth/login`.
**Response 400:** `{"detail": "Invalid provider. ..."}` (bad `{provider}`),
`{"detail": "OAuth state is invalid, expired, or already used"}` (state's
10 min TTL elapsed, or it was already consumed — see `/login` above),
`{"detail": "OAuth state does not match the callback provider"}`,
`{"detail": "Missing 'code' query parameter"}`, or
`{"detail": "<provider> authorization was not completed: <reason>"}`
(user declined consent on the provider's own screen).
**Response 503:** provider not configured (same as `/login`).

First sign-in via a given provider creates a new `users` row
(`password_hash` left `null` — see `api/models/user.py`) and links it via a new
`oauth_accounts` row; a later sign-in with the same provider identity reuses that
same linked user. If a `users` row with a matching email already exists (e.g. they
registered via email/password first), the new OAuth link attaches to that existing
user instead of creating a duplicate account.

### GET /auth/me
Requires `Authorization: Bearer <token>`.
**Response 200:** same shape as `POST /auth/register`'s response.
**Response 401:** `{"detail": "Missing or invalid Authorization header" | "Invalid or expired token" | "Invalid token subject" | "User no longer exists"}`

### GET /auth/me/oauth
Requires `Authorization: Bearer <token>`.
Returns whether the authenticated user has any linked OAuth accounts and, if so, which providers are linked.
**Response 200:**
```json
{"has_oauth": true, "providers": ["google", "github"]}
```
For a password-only account:
```json
{"has_oauth": false, "providers": []}
```
**Response 401:** same 401 shapes as `GET /auth/me`.

### DELETE /auth/me-password
Requires `Authorization: Bearer <token>`.
Deletes a **password-based** account immediately after verifying the current password.
**Request:**
```json
{"password": "string"}
```
**Response 204:** no body — account deleted.
**Response 400:** `{"detail": "Password-based deletion is not available for OAuth accounts"}`
**Response 403:** `{"detail": "Invalid password"}`
**Response 401:** same 401 shapes as `GET /auth/me`.

### POST /auth/me-provider
Requires `Authorization: Bearer <token>`.
Starts deletion for an **OAuth-only** account. Behavior depends on the linked provider:

- **Google-linked accounts:** a 6-digit verification code is emailed to the user's registered address. The account is only deleted after that code is confirmed via `POST /auth/me-verify`.
- **GitHub-linked accounts:** returns a redirect (307) to the GitHub consent screen so the user can re-authenticate with their GitHub password; deletion completes at `GET /auth/me-provider/callback`.

If a user has both Google and GitHub linked, the Google (email-code) path takes precedence.

**Request:** empty body.
**Response 200 (Google):** `{"detail": "Verification code sent"}`
**Response 307 (GitHub):** redirects to `https://github.com/login/oauth/authorize?...`
**Response 400:** `{"detail": "Provider-based deletion is not available for password-based accounts"}` or `{"detail": "No supported OAuth provider linked to this account"}`
**Response 503:** provider not configured (Google OAuth or GitHub OAuth credentials missing from `.env`).
**Response 401:** same 401 shapes as `GET /auth/me`.

### POST /auth/me-verify
Requires `Authorization: Bearer <token>`.
Confirms the Google account-deletion verification code and permanently deletes the account.
**Request:**
```json
{"code": "string (6 digits)"}
```
**Response 204:** no body — account deleted.
**Response 400:** `{"detail": "Invalid or expired code"}` or `{"detail": "Provider-based deletion is not available for password-based accounts"}`
**Response 401:** same 401 shapes as `GET /auth/me`.

### GET /auth/me-provider/callback
GitHub redirects here after the user re-authenticates on the consent screen started by `POST /auth/me-provider`.
**Query params:** same as `GET /auth/{provider}/callback`: `code` (string, required on success), `state` (string, required), `error`/`error_description` (present if the user declined consent).
**Response 204:** no body — account deleted.
**Response 400:** invalid/missing `code`, invalid/expired `state`, or user declined consent.
**Response 503:** GitHub OAuth not configured.

### Data consequences of deletion
Deleting a user removes the `users` row and cascades to any linked `oauth_accounts` rows. `campaigns`, `leads`, `calls`, `transcripts`, `bookings`, and `objections` are currently not user-scoped and remain in the database.

## Auth on every other endpoint below
`/campaigns`, `/leads`, `/calls`, `/analytics`, `/briefing` all now require
`Authorization: Bearer <token>` on every route (see `api/dependencies.py`'s
`get_current_user`, applied at the router level) — a request without a valid
token gets the same 401 shapes as `GET /auth/me` above. This was a breaking
change applied once the frontend was confirmed ready to send tokens on every
request (see `CallForge_Work.docx` section 2.3).

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

### GET /calls/{id}/recording
Day 11: streams the call's recording audio (`audio/wav`) through our own
API — the storage directory (`api/services/recording_storage.py`) is never
mounted as a static path, so this endpoint is the only way to reach a
recording, not a raw public URL. **No authentication exists on this
endpoint yet**, because no auth system exists anywhere in this API (see
`## Auth` above) — this is the one place a real deployment must add an
authorization check before going live; recordings and transcripts contain
real prospect data (Section 11 of the spec doc).

Note: no live-call audio capture is wired in yet either (that's a separate,
unbuilt piece — LiveKit Egress or a custom capture during the call). This
endpoint and `save_recording()` are storage-only, verified with a real
synthesized test clip, not live-call audio.
**Response 200:** the WAV file bytes.
**Response 404:** `{"detail": "Recording not found"}` — no recording_url set, or the file is missing.

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

### POST /calls/{id}/monitor
Listen-only join for a manager: mints a **subscribe-only** LiveKit token
(`can_publish`/`can_publish_data` explicitly `False`) for the call's actual
room, so a manager can hear a live call without ever being able to speak
into it. Room name is derived via the `outbound-{lead_id}` convention
(`agent/call_lifecycle.py`), not a stored column.

This is deliberately **not** Day 10 Ghost Mode
(`enable_ghost_mode`/`create_manager_whisper_token` in
`agent/livekit_utils.py`) — that joins a separate `{room}-whisper` room used
for a one-way voice-to-text hint channel to the AI (`agent/whisper_channel.py`),
with no main-call audio piped into it, so it cannot be used to listen to a
live call. See `api/services/livekit_rooms.py`'s module docstring.
**Response 200:**
```json
{
  "room_name": "outbound-<lead_id>",
  "token": "string (JWT, LiveKit access token)",
  "livekit_url": "ws://..."
}
```
**Response 404:** `{"detail": "Call not found"}`
**Response 409:** `{"detail": "Call is not active"}`
**Response 503:** LiveKit not configured or unreachable.

### POST /calls/{id}/takeover
_Not yet built — full "take over" (listen + speak, replacing the AI) is a
separate, unscoped decision (see `CallForge_Work.docx` section 2.1: is
hangup in scope? does this need auth immediately given it can hijack a live
call?). Only the listen-only half shipped, as `POST /calls/{id}/monitor` above._

### WS /calls/{id}/stream
_Not yet built — Day 5._

## Leads

### GET /leads
Paginated list, newest first. Was a dead stub router (never imported into
`api/main.py`) until now — lead creation itself still happens only via
`POST /campaigns/{id}/leads` (CSV upload, see above); this section covers
listing/viewing/updating leads afterward, for the frontend's kanban
pipeline view.

**Query params:**
- `page` (int, default 1, min 1)
- `page_size` (int, default 20, min 1, max 100)
- `campaign_id` (uuid, optional) — filter to one campaign
- `status` (string, optional) — one of: `new`, `contacted`, `qualified`, `booked`, `disqualified`

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "campaign_id": "uuid",
      "name": "string",
      "phone": "string",
      "email": "string | null",
      "company": "string | null",
      "status": "new | contacted | qualified | booked | disqualified",
      "created_at": "iso8601"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```
**Response 400:** invalid status value.

### GET /leads/{id}
**Response 200:** single lead object (same shape as items above).
**Response 404:** `{"detail": "Lead not found"}`

### PATCH /leads/{id}
Status-only update, for the kanban pipeline view (drag a lead card
between columns).
**Request:**
```json
{"status": "new | contacted | qualified | booked | disqualified"}
```
**Response 200:** updated lead object.
**Response 400:** `{"detail": "Invalid status. Valid values: booked, contacted, disqualified, new, qualified"}`
**Response 404:** `{"detail": "Lead not found"}`

## Contact

### POST /contact
**No authentication** — public landing-page contact form. Sends an email via
the same generic SMTP setup as the daily briefing (`api/services/contact.py`),
to `CONTACT_RECIPIENT_EMAIL` (falls back to `BRIEFING_RECIPIENT_EMAIL`).
**Request:**
```json
{"name": "string", "email": "string (valid email)", "message": "string"}
```
**Response 200:** `{"ok": true}`
**Response 422:** invalid email/empty fields.
**Response 503:** SMTP not configured.
**Response 502:** send failed (provider error, network issue, etc).

## Demo

### POST /demo/call/start
**No authentication** — public landing-page "Talk to the AI" widget. Creates
a real LiveKit room (`demo-{uuid4()}`) with the voice agent dispatched into
it, and mints a full-duplex token (`can_publish`/`can_subscribe` both
`True`) for a synthetic visitor identity.

**Not rate-limited.** Every call here spins up the real voice-AI pipeline
(LLM + TTS) and costs real money/compute. Acceptable for an internal/dev
pass; needs a per-IP or similar throttle before this is public on the open
internet — flagged, not solved, in this pass.
**Response 200:**
```json
{
  "room_name": "demo-<uuid>",
  "token": "string (JWT, LiveKit access token)",
  "livekit_url": "ws://..."
}
```
**Response 503:** LiveKit not configured or unreachable.

## Objections
### GET /objections
### POST /objections
### PATCH /objections/{id}
_Not yet built._

## Analytics
### GET /analytics/conversion
Day 12. `conversion_rate` = `bookings / total_calls`, per campaign and
overall — **not** `bookings / completed_calls`: real test data had 11
bookings against only 4 calls independently marked `completed` out of 15
total (calls can pick up a booking without every status transition being
tracked yet, see Day 7), which would give a >100% rate against that
denominator. `total_calls` is always the sane one.
**Response 200:**
```json
{
  "overall": {"total_calls": 15, "completed_calls": 4, "bookings": 11, "conversion_rate": 0.7333},
  "by_campaign": [
    {"campaign_id": "uuid", "campaign_name": "string", "total_calls": 15, "completed_calls": 4, "bookings": 11, "conversion_rate": 0.7333}
  ]
}
```

### GET /analytics/objections
Day 12. Returns the `objections` playbook (`text`, `response`, `category`,
`success_rate`) sorted by `success_rate` descending, nulls last — **not**
an aggregation over real per-call objections. No per-call objection log
exists yet (`agent/graph/tools.py::log_objection` only logs, deliberately —
the playbook table has no `call_id`/timestamp column, so writing one row
per raised objection would corrupt its aggregate-stats semantics). This is
a static reference snapshot; empty until the playbook is seeded.
**Response 200:**
```json
[
  {"id": "uuid", "text": "string", "response": "string", "category": "string | null", "success_rate": "number | null"}
]
```

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