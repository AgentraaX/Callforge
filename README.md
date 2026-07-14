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
| 7 | Manual end-to-end verification: STT → LLM → TTS round trip, real mic input | (verified across Days 1–6 branches) |
| 8 | Outbound dialer — pulls leads from Redis queue, in order, no double-dials | `day8-outbound-dialer` |
| 9 | LinkedIn/lead enrichment data fed into the LLM's context for outbound calls | `day9-lead-enrichment` |
| 10 | Ghost Mode — manager whisper channel via an isolated room, agent applies guidance silently | `day10-ghost-mode` |
| 11 | A/B pitch variant testing — assigned once per call, immutable, ~50/50 split | `day11-ab-pitch-testing` |
| 12 | Barge-in / interruption handling | next |

**Local dev note:** this machine has no NVIDIA GPU (Intel Iris Xe only), so local
LLM testing uses Ollama (`qwen2.5:7b`, CPU) instead of vLLM. Same OpenAI-compatible
API shape, so `pipeline/llm.py` will point at a real vLLM+Qwen2.5-7B-AWQ endpoint
on a rented cloud GPU once Week 2 latency work starts (Section 11 of the spec doc).

See `docs/API_CONTRACT.md` and `docs/REDIS_SCHEMA.md` for the P3/P4 shared
contracts, and `docs/LIVEKIT_SETUP.md` for local LiveKit setup steps.

**P4's Day 1–2 work** (`verify_infra.py`, SQLAlchemy models + Alembic
migration for all 7 core tables) is merged into the P3 branches from Day 8
onward — `alembic upgrade head` runs clean against a fresh Postgres.
