# CallForge

AI voice-calling backend (inbound/outbound sales calls) — LiveKit + Whisper + Qwen2.5 + Kokoro + LangGraph.
See `CallForge_Backend_Structure (2).md` for the full spec.

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
