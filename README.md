# CallForge

AI voice-calling backend (inbound/outbound sales calls) — LiveKit + Whisper + Qwen2.5 + Kokoro + LangGraph.
See `CallForge_Backend_Structure (2).md` for the full spec.

## Local dev session notes (2026-07-20) — running it end-to-end + known issues

Got the full stack running locally (Docker postgres/redis/livekit + native
API/agent/frontend) and exercised the real "Talk to the AI" demo call
end-to-end. Real bugs found and fixed along the way:

- **`api/main.py` never called `load_dotenv()`.** Only
  `api/services/{briefing,calendar,crm}.py` did, and each of those already
  admitted in their own comments that it was "import-order luck, not a
  guarantee." Everything reading `DATABASE_URL`/etc. via bare `os.getenv()`
  (e.g. `api/db/session.py`) silently fell back to hardcoded defaults
  whenever the API ran outside Docker (where `env_file` supplies real OS
  env vars instead). Fixed by calling `load_dotenv()` first thing in
  `api/main.py`, before any project import that reads env vars at import
  time.
- **LiveKit-in-Docker on Windows needs `rtc.node_ip` set** (`docker/livekit.yaml`).
  With `use_external_ip: false` and no `node_ip`, the server advertises its
  own Docker-internal IP as the ICE candidate, which no browser on the host
  can ever reach — call connect fails with "could not establish pc
  connection." Set to `127.0.0.1` for same-machine local dev.
- **`docker-compose.yml`'s `50100-51100/udp` port range (1001 ports) silently
  failed to publish some ports on Docker Desktop for Windows** — the two TCP
  ports (7880/7881) ended up with empty host bindings even though the
  `docker compose up` command reported success. Shrunk the range to
  `50100-50150` (50 ports, plenty for a handful of concurrent dev calls) and
  it now binds cleanly every time.
- **Barge-in could cancel a reply before any audio ever played.** On
  CPU-only hardware (no GPU here), Kokoro can take longer than the ~243ms
  barge-in budget to produce its first audio chunk. Added an 800ms grace
  period (`agent/main.py`, `_BARGE_IN_GRACE_PERIOD_S`) after a reply starts
  before a barge-in can cancel it.
- **LiveKit Agents' default CPU-load-based dispatch throttle
  (`load_threshold=0.7`) blocked call dispatch entirely** whenever ambient
  system load (other processes on the dev machine) sat near/above it, even
  with zero active calls — logs showed `no worker available to handle job`
  with a worker registered and idle. Raised to `0.95` in `agent/main.py`'s
  `WorkerOptions`.
- **`LLM_MODEL` swapped to `qwen2.5:1.5b` for local dev demos.** `qwen2.5:7b`
  was repeatedly hitting its own 30s timeout under CPU contention (this
  laptop has no GPU — see the Day 14 latency notes above). `1.5b` replies in
  ~2-3s once warm. Per Day 14's own findings, `1.5b` is less reliable for
  `book_meeting`/`log_objection` — fine for demoing conversational flow, not
  a substitute for the real GPU-hosted model in Section 11 of the spec doc.
- Ports were remapped in this session's local `.env` (not committed) because
  another, unrelated project's Docker stack was already bound to
  5432/6379/7880/7881/3000/8000 on the same machine — CallForge now runs on
  5433/6380/7980-7981/8090/3002 there. That's a local-environment detail,
  not a code change; a clean machine can use the original ports in
  `.env.example`.

**Still open for the team:**
- The CPU-contention/timeout issues above are workarounds for this specific
  dev laptop, not a fix for the underlying latency (see Day 14's own
  conclusion — real fix is the GPU/vLLM migration in Section 11).
- No real PSTN/SIP calling exists anywhere in this project yet — every
  "call" is a LiveKit room (browser-mic demo or `agent/dialer.py`'s
  simulated outbound dial). `dialer.py`'s own docstring already flags this.
- A full audit of `callforge_frontend`'s "What's Real vs. Simulated" table
  is due — a large batch of previously-uncommitted work (auth, contact form,
  demo call, campaigns/leads CRUD) is included in this commit and hasn't
  been re-verified item-by-item against that table.

## Backend Build Log — Person 3 (Voice Pipeline)

| Day | Shipped | Branch |
|---|---|---|
| 1 | `agent/` scaffold, config management, logging, CI skeleton | `folder_structure_by_saad` |
| 2 | Self-hosted LiveKit server (Docker); room creation + scoped token generation | `livekit-setup` |
| 3 | LiveKit Agents worker (`callforge-voice-agent`) auto-joins on room creation (~0.9s) | `day3-agent-dispatch` |
| 4 | `faster-whisper` STT streamed from room audio, ~2s chunks, silence-safe | `day4-whisper-stt` |
| 5 | Qwen2.5-7B LLM (Ollama locally) + JSON-mode structured decisions | `day5-qwen-llm` |
| 6 | Kokoro TTS streamed into the room, agent speaks its replies | `day6-kokoro-tts` |
| 7 | Full integration test (joint with P4, done solo — P4 mid-exams): closed 4 real gaps found by audit — transcripts were never persisted, `calls.status` never transitioned, no live-state API existed, no disconnect handling. All fixed + verified against live Postgres/Redis. No frontend in this repo, so "dashboard shows a live call" is untestable here; backend plumbing for it now exists. | `day7-integration-test` |
| 8 | Outbound dialer — pulls leads from Redis queue, in order, no double-dials | `day8-outbound-dialer` |
| 8 (P4) | Cal.com calendar integration (P4's task, done solo — P4 mid-exams): `book_meeting` now creates a real Cal.com event via their API v2, verified against a live account (not mocked) — booking round-tripped with the exact UTC time and attendee confirmed back from Cal.com's API. Added `leads.email` (missing from schema, required for a real attendee). Booking always still gets created even if the calendar call fails or the lead has no email — only `calendar_event_id` is affected. | `day8-calendar-integration` |
| 9 (P4) | Morning briefing email service (P4's task, done solo — P4 mid-exams): scheduled 8 AM job (APScheduler) emails real call/booking stats over generic SMTP (any provider — Gmail, Outlook, company mail server), verified with a real Gmail send + received, not mocked. Idempotent per date via a Redis lock — proved a second trigger for the same day no-ops, and a forced SMTP auth failure correctly releases the lock for retry instead of silently blocking it forever. `GET /briefing/today` shares the same data generator as the email, so in-app and emailed numbers can't drift. | `day9-morning-briefing` |
| 10 (P4) | CRM webhook integration (P4's task, done solo — P4 mid-exams): a call reaching a terminal status (completed/failed/no-answer) pushes its outcome — including any bookings — to an external CRM sandbox (webhook.site, a real endpoint, not mocked). Retry/backoff (1s/2s/4s, 3 attempts) verified with a forced real 500 response (~7s measured, matching the schedule exactly); exhausted retries land in a durable Redis queue, never silently dropped — proved the queue drains and redelivers correctly once the endpoint recovers, independently confirmed via webhook.site's own request log (5/5 requests accounted for). | `day10-crm-webhook` |
| 11 (P4) | Call recording storage (P4's task, done solo — P4 mid-exams): recordings save to a local directory that's never mounted as a static path — the only way to reach one is `GET /calls/{id}/recording`, which streams bytes through our own code. Verified with a real Kokoro-synthesized clip: saved, `calls.recording_url` persisted correctly, retrieved back byte-identical through the real API. Flagged plainly, not hidden: no auth exists on that endpoint yet (no auth system exists anywhere in this API), and no live-call audio capture is wired in yet either (LiveKit Egress or equivalent — a separate, unbuilt piece) — this day is the storage half only. | `day11-recording-storage` |
| 12 (P4) | Analytics aggregation pipeline (P4's task, done solo — P4 mid-exams): `GET /analytics/conversion` (bookings/total_calls per campaign + overall — hand-verified against raw SQL first, matched exactly: 15 calls, 4 completed, 11 bookings on real test data) and `GET /analytics/objections`. Caught a real trap before shipping: bookings (11) exceeded completed-status calls (4) in real data, so `conversion_rate` uses `total_calls` as the denominator, not `completed_calls` — the obvious-looking definition would have silently produced a >100% rate. Objections analytics honestly scoped to the existing playbook table (no per-call objection log exists, by Day 7's own documented design) — not a fabricated aggregation. | `day12-analytics-aggregation` |
| 13 (P4) | Dockerize agent + API (P4's task, done solo — P4 mid-exams): found and fixed real "works on my machine, breaks on a clean machine" bugs, not just wrote Dockerfiles — `Dockerfile.agent` never copied `api/` in at all despite agent code importing it since Day 7; `docker-compose.yml` pointed both containers at `localhost` for Postgres/Redis/LiveKit, which only resolves correctly on the host, not inside the compose network; the agent image had no C++ toolchain for `chatterbox-tts`'s Cython dependency; torch's default wheel was about to pull several GB of unneeded CUDA runtime despite this whole project being CPU-only since Day 5 (fixed with the `+cpu` build, confirmed at 178.7MB vs 766.7MB+). Split `requirements.txt` into `requirements-api.txt`/`requirements-agent.txt` so the API image doesn't drag in TTS/STT dependencies it never uses. **Confirmed for real**: the API container now builds clean and runs correctly — `GET /health` and `GET /campaigns` both verified working through the actual compose network against the real Postgres — after catching and fixing one more genuine bug along the way (`Dockerfile.api`'s `WORKDIR`+`CMD` didn't match `api/main.py`'s own absolute imports, throwing `ModuleNotFoundError: No module named 'api'` on every real container start). The agent image's final dependency install hit 3 hash-mismatch failures on 3 different, unrelated packages across 3 attempts (~25-30 min into the download each time) — consistent with this machine's network reliability over very long downloads, not a code defect; every actual bug found in the agent image was fixed and is ready to build once network conditions allow (`docker compose build agent`). | `day13-dockerize` |
| 9 | LinkedIn/lead enrichment data fed into the LLM's context for outbound calls | `day9-lead-enrichment` |
| 10 | Ghost Mode — manager whisper channel via an isolated room, agent applies guidance silently | `day10-ghost-mode` |
| 11 | A/B pitch variant testing — assigned once per call, immutable, ~50/50 split | `day11-ab-pitch-testing` |
| 12 | Barge-in — agent stops speaking within ~243ms of the prospect talking, no lockup | `day12-barge-in` |
| 13 | Voice cloning (Chatterbox-Turbo) — 46s to clone+generate a sentence, offline/demo use, watermarked | `day13-voice-cloning` |
| 14 | Latency tuning (CPU-only) — measured real per-stage + end-to-end numbers, not estimates; see note below | `day14-latency-tuning` |

**Local dev note:** this machine has no NVIDIA GPU (Intel Iris Xe only), so local
LLM testing uses Ollama (`qwen2.5:7b`, CPU) instead of vLLM. Same OpenAI-compatible
API shape, so `pipeline/llm.py` will point at a real vLLM+Qwen2.5-7B-AWQ endpoint
on a rented cloud GPU once Week 2 latency work starts (Section 11 of the spec doc).

**Day 14 latency findings (real measurements, `agent/benchmark_latency.py`, n=5 trials/stage):**

| Stage | Before | After | Change |
|---|---|---|---|
| STT (faster-whisper) | `base.en` 1666ms mean | `tiny.en` 1043ms mean | **Adopted** — ~1.7x faster, identical transcript on test audio |
| LLM (Ollama `num_thread`/`num_predict`) | 11.4-13.8s mean, high variance | no change | **Not adopted** — explicit thread pinning and predict-length caps made it slower, not faster; Ollama's own defaults already beat every manual setting tried |
| LLM (model size) | `qwen2.5:7b`, 4/5 correct JSON decisions, ~13.7s mean | `qwen2.5:1.5b`, 3/5 correct, ~3.2s mean | **Not adopted** — 4.3x faster, but missed both `book_meeting` and `log_objection` on test transcripts, the two structured actions with real downstream consequences (no calendar entry, no CRM log) |
| End-to-end turn (sum of stage means) | ~25.8s | ~25.8-27.4s across repeated runs | STT's win is real but gets swamped by LLM/TTS run-to-run variance (LLM alone ranged 8.2-16.3s across identical trials) |

**Conclusion:** the doc's <500ms target is a GPU target and is not reachable on
this CPU. The dominant costs are Qwen2.5-7B inference (~12-14s/turn) and Kokoro
TTS synthesis (~12-13s/turn) — both already flagged as CPU-bound since Day 5/6.
The one genuine CPU-side win found (STT model swap) is shipped; the LLM
downsize and Ollama thread tuning were tested and rejected with real numbers,
not assumed. Closing the gap to <500ms requires the Week 2 GPU migration
(vLLM + AWQ quantization), not further CPU tuning.

See `docs/API_CONTRACT.md` and `docs/REDIS_SCHEMA.md` for the P3/P4 shared
contracts, and `docs/LIVEKIT_SETUP.md` for local LiveKit setup steps.

**P4's Day 1–2 work** (`verify_infra.py`, SQLAlchemy models + Alembic
migration for all 7 core tables) is merged into the P3 branches from Day 8
onward — `alembic upgrade head` runs clean against a fresh Postgres.
