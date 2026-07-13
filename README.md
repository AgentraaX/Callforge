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
| 5 | vLLM/Qwen2.5-7B LLM + function-calling (`book_meeting`, `transfer_to_human`, `log_objection`) | next |

**Local dev note:** this machine has no NVIDIA GPU (Intel Iris Xe only), so local
LLM testing uses Ollama (`qwen2.5:7b`, CPU) instead of vLLM. Same OpenAI-compatible
API shape, so `pipeline/llm.py` will point at a real vLLM+Qwen2.5-7B-AWQ endpoint
on a rented cloud GPU once Week 2 latency work starts (Section 11 of the spec doc).

See `docs/API_CONTRACT.md` and `docs/REDIS_SCHEMA.md` for the P3/P4 shared
contracts, and `docs/LIVEKIT_SETUP.md` for local LiveKit setup steps.
