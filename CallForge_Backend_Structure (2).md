# CallForge — Backend Development Documentation

**Scope:** Detailed backend structure, ownership, build order, and quality process for the 2-week MVP
**Team:** Backend Lead (Person 3) + Backend Support (Person 4)
**Stack:** FastAPI · LiveKit · Whisper.cpp · vLLM + Qwen2.5-7B-AWQ · Kokoro · LangGraph · PostgreSQL · Redis

---

## 1. Backend Responsibilities Split

| Layer | Owner | Why |
|---|---|---|
| Real-time voice pipeline (LiveKit, STT, LLM, TTS) | Backend Lead (P3) | Needs deep audio/AI pipeline knowledge |
| Data layer, REST API, orchestration state | Backend Support (P4) | Needs DB/DevOps ownership, feeds P3's pipeline |

The two backends meet at two seams: **Redis** (call-state, written by both) and **LangGraph** (decision engine, called by P3's agent, defined jointly). Both seams must be treated as a contract, not a convenience — a silent change on either side breaks the other person's work without warning.

---

## 2. Repository / Folder Structure

```
callforge-backend/
├── agent/                     # LiveKit voice agent (Person 3)
│   ├── main.py                 # Agent entrypoint, joins LiveKit room
│   ├── pipeline/
│   │   ├── stt.py              # Whisper.cpp wrapper
│   │   ├── llm.py              # vLLM client (Qwen2.5-7B-AWQ)
│   │   ├── tts.py              # Kokoro wrapper
│   │   └── vad.py              # Barge-in / interruption detection
│   ├── graph/
│   │   ├── state_machine.py    # LangGraph state definitions
│   │   ├── nodes.py            # BANT qualification, objection handling nodes
│   │   └── tools.py            # Function-calling tools (book_meeting, transfer_call)
│   └── config.py
│
├── api/                        # FastAPI service (Person 4)
│   ├── main.py                 # App entrypoint
│   ├── routers/
│   │   ├── campaigns.py
│   │   ├── calls.py
│   │   ├── leads.py
│   │   ├── objections.py
│   │   ├── analytics.py
│   │   └── auth.py
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic request/response schemas
│   ├── services/                # Business logic (dialer, briefing generator)
│   └── db/
│       ├── session.py
│       └── migrations/          # Alembic
│
├── shared/
│   ├── redis_client.py
│   ├── postgres_client.py
│   └── constants.py
│
├── docker/
│   ├── Dockerfile.agent
│   ├── Dockerfile.api
│   └── docker-compose.yml
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── load/
│
├── .github/workflows/ci.yml    # Lint + test on every PR
└── docs/
    ├── API_CONTRACT.md
    └── REDIS_SCHEMA.md
```

---

## 3. Core Data Flow (Backend View)

```
Inbound/Outbound call
   → LiveKit room created (api/routers/calls.py triggers or SIP inbound)
   → agent/main.py joins room
   → stt.py transcribes prospect audio (Whisper.cpp)
   → graph/state_machine.py (LangGraph) decides next action
   → llm.py generates reply (vLLM + Qwen)
   → tts.py speaks reply (Kokoro)
   → Redis: call state updated every turn (shared/redis_client.py)
   → PostgreSQL: transcript + lead data persisted at call end (api/services)
```

---

## 4. Database Schema (PostgreSQL) — Owned by Person 4

| Table | Key Columns | Purpose |
|---|---|---|
| `campaigns` | id, **user_id**, name, status, pitch_variant_a, pitch_variant_b | Outbound campaign config (owned by a user) |
| `leads` | id, **user_id**, campaign_id, name, phone, company, status, enrichment_json | CSV-uploaded prospects (owned by a user) |
| `calls` | id, **user_id**, lead_id, direction, status, sentiment, duration, recording_url | Call metadata (owned by a user) |
| `transcripts` | id, call_id, speaker, text, timestamp | Turn-by-turn transcript (owned via call) |
| `objections` | id, text, response, category, success_rate | Objection playbook (global) |
| `bookings` | id, **user_id**, call_id, calendar_event_id, scheduled_at | Meetings booked (owned by a user) |
| `users` | id, email, password_hash, role | Sales team / managers |

Use **Alembic** for migrations from Day 2 onward so schema changes stay versioned as the two backend devs work in parallel. Every migration must be reviewed by the other backend dev before merge, since both sides query these tables.

---

## 5. Redis Usage — Shared Contract Between P3 and P4

| Key pattern | Written by | Read by | TTL |
|---|---|---|---|
| `call:{call_id}:state` | Agent (P3) | Dashboard API, Ghost Mode | Call duration |
| `call:{call_id}:transcript_buffer` | Agent (P3) | WebSocket broadcaster (P4) | Call duration |
| `call:{call_id}:sentiment` | Agent (P3) | Dashboard (P4) | Call duration |
| `dialer:queue:{campaign_id}` | Dialer service (P4) | Agent (P3, on pickup) | Until dialed |

Agree on this schema on **Day 1** and write it down in `docs/REDIS_SCHEMA.md`. Any change to a key's shape requires a message to the other dev before merging, not after.

---

## 6. API Endpoints (FastAPI) — Owned by Person 4

```
POST   /auth/login
GET    /campaigns
POST   /campaigns
GET    /campaigns/{id}
PATCH  /campaigns/{id}          # pause/resume
POST   /campaigns/{id}/leads    # CSV upload

GET    /calls
GET    /calls/{id}
GET    /calls/{id}/transcript
POST   /calls/{id}/takeover     # Ghost Mode trigger
WS     /calls/{id}/stream       # live audio/transcript feed

GET    /objections
POST   /objections
PATCH  /objections/{id}

GET    /analytics/conversion
GET    /analytics/objections
GET    /briefing/today
```

Document every endpoint's request/response shape in `docs/API_CONTRACT.md` before frontend needs it — this avoids the frontend team guessing at payload shapes and re-integrating twice.

---

## 7. Voice Pipeline Details — Owned by Person 3

**STT — Whisper.cpp**
- Run as a local C++ binary/service, streamed audio in, partial + final transcripts out.
- Target: ~200ms latency per utterance chunk.

**LLM — vLLM serving Qwen2.5-7B-AWQ**
- Serve via vLLM's OpenAI-compatible endpoint, function-calling enabled for `book_meeting`, `transfer_to_human`, `log_objection`.
- Constrain output with JSON mode / pre-approved response templates in Week 1 to avoid hallucination.

**TTS — Kokoro**
- CPU-based synthesis, stream audio back into the LiveKit room as it's generated (don't wait for full sentence when possible).

**LangGraph**
- Nodes: `greet → qualify_BANT → handle_objection → book_or_route → close`.
- Each node reads/writes call state to Redis so Ghost Mode and dashboard can reflect live progress.

---

## 8. Day-by-Day Build Plan (with Build Steps, Acceptance Criteria & Review)

Every day follows the same rhythm so nothing slips silently:

1. **Morning (15 min):** Standup — yesterday's result, today's target, blockers.
2. **Build:** Work the day's task against the acceptance criteria below.
3. **Self-test:** Run the checks listed for that day before calling it done.
4. **End-of-day review (30 min):** The other backend dev (or lead, for cross-cutting days) reviews the PR against the Definition of Done in Section 9. Nothing merges to `main` unmerged/unreviewed.
5. **Log:** One line in the shared build log — what shipped, what's still open, what's blocking.

### WEEK 1 — Inbound Foundation

#### Person 3 (Backend Lead) — Voice Pipeline

| Day | Build | Acceptance Criteria | Review Check |
|---|---|---|---|
| 1 | Scaffold `agent/` repo, config management, logging setup, CI skeleton | `python main.py` boots cleanly with no errors; structured logging in place | P4 confirms repo structure matches Section 2; CI pipeline runs (even if empty) |
| 2 | Self-hosted LiveKit server; room creation + token generation | A test client can join a room using a generated token | Token expiry and scoping tested — no room without a valid, short-lived token |
| 3 | LiveKit Agents framework wired; agent auto-joins on room creation | Agent appears in room within 2s of room creation, logged | Confirm agent handles room-join failure gracefully (retry/backoff, not crash) |
| 4 | Whisper.cpp STT streamed into agent | Spoken test phrase transcribes correctly ≥90% of test set; partial transcripts stream | Latency measured and logged (~200ms target); silence/noise doesn't produce garbage text |
| 5 | vLLM + Qwen2.5-7B-AWQ serving, connected to agent | Given a transcript, LLM returns a valid structured (JSON) response every time | Test with malformed/empty input — must not crash the agent; timeout handling verified |
| 6 | Kokoro TTS wired to agent output | LLM text reliably produces audible, correctly-timed speech in room | Verify streaming starts before full sentence is ready; audio doesn't clip or overlap |
| 7 | End-to-end test: phone → STT → LLM → TTS → phone | Full round trip works on 5 consecutive test calls without manual intervention | Joint review with P4: call state correctly appears in Redis at every turn |

#### Person 4 (Backend Support) — Data & API Layer

| Day | Build | Acceptance Criteria | Review Check |
|---|---|---|---|
| 1 | PostgreSQL + Redis running via Docker Compose | `docker compose up` starts both cleanly; connection verified from a script | P3 confirms Redis is reachable from agent's planned host/port |
| 2 | Schema design + Alembic migrations for core tables | `alembic upgrade head` runs clean on a fresh DB; all Section 4 tables exist | Peer review of schema — types, foreign keys, indexes on frequently-queried columns |
| 3 | Campaign CRUD endpoints | All 5 campaign endpoints pass manual Postman/curl tests, return correct status codes | Input validation checked (empty name, bad status value) — no silent 500s |
| 4 | Call logs + transcript endpoints | `/calls` and `/calls/{id}/transcript` return correctly shaped, paginated data | Confirm response shape matches `docs/API_CONTRACT.md` exactly |
| 5 | Redis session/state layer for live calls | Call state written/read correctly under the Section 5 key schema | P3 confirms key names/shapes match what the agent writes — dry run together |
| 6 | LangGraph state machine (basic BANT flow) drafted jointly | Given a sample transcript, state machine transitions through greet → qualify → close correctly | Walk through each node with P3; confirm no dead-end states |
| 7 | Full integration test: frontend + API + agent | Frontend dashboard shows a real, live call end to end | Joint review — Friday Week 1 checklist (Section 10) run in full |

### WEEK 2 — Outbound + Intelligence

#### Person 3

| Day | Build | Acceptance Criteria | Review Check |
|---|---|---|---|
| 8 | Outbound dialer logic, pulls from Redis queue | Agent picks up queued leads and initiates outbound calls correctly, in order | Confirm no double-dials; queue item removed only after confirmed pickup |
| 9 | LinkedIn enrichment data feeds into agent context | Agent references enrichment data correctly in a test call | Verify graceful fallback when enrichment data is missing |
| 10 | Ghost Mode: human joins room, whisper channel to agent | Manager can join silently, prospect hears no interruption, whisper audio is manager-only | Test the "prospect never knows" requirement explicitly — record and listen back |
| 11 | A/B testing engine routes calls to pitch variant A/B | Calls split ~50/50 across variants over a 20-call test run; result logged per call | Confirm variant assignment is logged and immutable per call (for accurate analytics) |
| 12 | Barge-in / interruption handling | Agent stops speaking within ~300ms of prospect starting to talk | Test with overlapping speech, background noise — no audio stutter/lockup |
| 13 | Voice cloning (Chatterbox-Turbo) for demo voice | Cloned voice produces intelligible, natural speech from sample text | Confirm consent/data handling for the voice sample used |
| 14 | Latency tuning across full pipeline | End-to-end turn latency consistently <500ms across 10 test calls | Joint load test with P4; log and report actual numbers, not estimates |

#### Person 4

| Day | Build | Acceptance Criteria | Review Check |
|---|---|---|---|
| 8 | Calendar integration (Cal.com API) | A booked call creates a real calendar event with correct time/attendee | Test timezone handling explicitly — this is a common silent bug |
| 9 | Morning briefing email service | Scheduled job sends a correctly formatted email at 8 AM with real data | Verify job runs even if triggered manually outside the schedule (idempotent) |
| 10 | CRM webhook integration | Call outcome correctly pushes to external CRM sandbox | Confirm retry/backoff on webhook failure — no silent data loss |
| 11 | Call recording storage | Recordings saved, linked to `calls.recording_url`, retrievable | Confirm storage access is permissioned, not publicly world-readable |
| 12 | Analytics aggregation pipeline | Conversion, objection-success, and campaign stats compute correctly against test data | Cross-check numbers by hand against raw DB rows before trusting the dashboard |
| 13 | Dockerize agent + API + all dependencies | `docker compose up` on a clean machine brings up the full stack | P3 verifies agent container has GPU access if applicable |
| 14 | Production deploy | Full system reachable and functional on the target cloud instance | Joint go/no-go review against Section 10 before calling it "demo ready" |

---

## 9. Definition of Done (applies to every task, every day)

A task is **not done** until all of the following are true:

- [ ] Code is committed to a feature branch and opened as a PR (never pushed straight to `main`)
- [ ] The acceptance criteria for that day's task (Section 8) are met and demonstrated, not assumed
- [ ] The other backend dev has reviewed and approved the PR
- [ ] Automated or manual test evidence exists (a passing test, a recorded call, a curl output) — not just "it worked on my machine"
- [ ] Errors are handled explicitly (no bare `except: pass`, no unhandled promise/async rejection)
- [ ] Logging is in place for the new code path (enough to debug a failure without reproducing it live)
- [ ] Any change to the Redis schema, DB schema, or API contract is reflected in `docs/` before merge
- [ ] Secrets (API keys, DB passwords) are in environment variables / `.env`, never hardcoded or committed

---

## 10. Review & QA Process

### Daily
- End-of-day PR review between P3 and P4 (Section 8 table).
- Build log entry: what shipped, what's open, what's blocking — visible to the whole team, not just backend.

### Twice-Weekly Cross-Check (Wed and Fri)
- Backend Lead + Backend Support + Product Lead sit together and run a live test call, not a code review — actually place a call and watch it work.
- Any bug found gets logged with severity (blocker / major / minor) before moving on.

### Friday Review — End of Week 1 (Must Pass Before Week 2 Starts)

| Check | Pass Criteria |
|---|---|
| Inbound call answered | AI picks up within 2 rings, consistently |
| Natural speech | Kokoro voice is clear, correctly paced, no audio artifacts |
| Live dashboard | Manager sees the call appear in real time |
| Live listen | Manager can hear the call as it happens |
| Transcript persistence | Full transcript saved to DB, retrievable after call ends |
| Error handling | A dropped call or bad input doesn't crash the agent or API |

If any of these fail, Week 2 scope is cut, not the review — do not carry unresolved Week 1 defects into Week 2 build time.

### Friday Demo — End of Week 2 (Pre-Demo Checklist)

- [ ] Full demo flow rehearsed at least twice end-to-end, not just in pieces
- [ ] A recorded backup demo exists in case of live failure (never demo live without a backup)
- [ ] Latency verified under load, not just on a single test call
- [ ] Ghost Mode tested with a real "prospect never notices" listen-back
- [ ] All secrets/credentials used in the demo are non-production/sandboxed unless explicitly approved otherwise
- [ ] Rollback plan exists if the production deploy breaks on demo day

### Code Review Standards (applies to every PR, not just end-of-week)

- Reviewer actually runs the code — review is not just reading a diff.
- Reviewer checks the acceptance criteria for that day's task, not just "does it look reasonable."
- No PR is self-approved. If the other backend dev is unavailable, the Backend/Product Lead reviews instead — never skip review to keep moving.
- Comments that block merge must be resolved, not just acknowledged.

---

## 11. Risk Notes Specific to Backend

- **Hallucination risk:** keep LLM on JSON-mode/function-calling only in MVP; no free-form generation until playbook is proven.
- **GPU setup:** have a pre-built Docker image ready; fallback to Qwen2.5-1.5B on CPU (~600ms) if GPU provisioning slips.
- **Latency budget:** STT ~200ms + LLM ~150ms + TTS streaming start ≈ keep total turn latency under 500ms by Week 2, Day 14.
- **Silent contract drift:** the single biggest risk to a 2-person backend team is Redis/DB/API shapes changing without the other person knowing — treat every shared schema as a reviewed artifact, not a private implementation detail.
- **Data handling:** call recordings and transcripts contain real prospect data — access-control storage from Day 1, don't retrofit security at the end.

---

## 12. Local Dev Setup Checklist

```bash
# 1. Infra
docker compose up postgres redis

# 2. LLM serving
vllm serve Qwen/Qwen2.5-7B-Instruct-AWQ --port 8001

# 3. API
cd api && uvicorn main:app --reload --port 8000

# 4. Agent
cd agent && python main.py dev

# 5. Migrations
alembic upgrade head
```

---

## 13. Daily Standup Questions (Backend)

- Is the LiveKit → STT → LLM → TTS loop still working end-to-end?
- Is turn latency under budget?
- Are DB schema changes migrated and communicated to the other backend dev?
- Any Redis key contract changes that affect the other side?
- Did yesterday's task actually pass its acceptance criteria, or is it "mostly done"?
- Is there anything currently unreviewed sitting in a PR overnight?
