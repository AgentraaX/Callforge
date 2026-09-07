# CallForge Sales Voice Agent -- Technical Specification

Status: implemented (Phase 1). This document specs the cold-calling sales
agent pivot described in the build plan, for evaluation by a company
testing this as a real sales tool, not just a demo.

## 1. What this is

A voice agent that places (or receives, in the browser test path) sales
calls under a user-defined persona -- a name, a company, a pitch, a
knowledge base of facts it's allowed to state, a personality, and a cloned
or selected voice -- and runs a genuine cold-calling conversation: rapport,
discovery, objection handling, and a close, grounded so it never invents
facts about the product being sold.

## 2. Architecture

```
                 ┌─────────────────────────┐
 Browser  ──────▶│   /ws/call (browser     │
 (test call)     │   WebSocket protocol)   │──┐
                 └─────────────────────────┘  │
                                               ▼
                                    ┌─────────────────────┐
                                    │  conversation/turn.py │
                                    │  run_turn() -- the    │
                                    │  ONE turn engine:      │
                                    │  lead capture,          │
                                    │  escalation check,       │
                                    │  grounded LLM reply       │
                                    │  (sales playbook +          │
                                    │  persona knowledge),          │
                                    │  emotion tag, booking tools,   │
                                    │  chunked TTS                    │
                                    └─────────────────────┘  ▲
                                               │              │
                 ┌─────────────────────────┐  │              │
 Telnyx   ──────▶│  /ws/telnyx-media       │──┘              │
 (real call)     │  (Telnyx Media Streaming│─────────────────┘
                 │  protocol, VAD-buffered)│
                 └─────────────────────────┘
```

Both transports call the same `run_turn()` so the sales technique,
grounding, and anti-hallucination logic exists in exactly one place. See
`packages/backend/app/conversation/turn.py`.

## 3. Persona data model

Defined in `packages/backend/app/conversation/personas.py`, owned per user,
CRUD via `/api/personas`:

| Field | Purpose |
|---|---|
| `name`, `company` | Who the agent is and who it's calling on behalf of |
| `product_pitch` | One-line description of what's being sold |
| `personality` | Tone/character instruction for the LLM |
| `knowledge_text` | The agent's ONLY source of facts -- pricing, features, FAQs |
| `opening_line` | Optional scripted opener; auto-generated if blank |
| `call_goal` | What a successful call ends with (book a demo, close, qualify) |
| `elevenlabs_voice_id` | Selected or instant-cloned ElevenLabs voice |
| `default_emotion` | Fallback delivery style if the model omits its emotion tag |

## 4. Sales technique

`packages/backend/app/llm/sales_playbook.py` injects a persona-independent
cold-calling methodology into every system prompt: a permission-based
opener, rapport/mirroring, needs discovery before pitching, a named
objection-handling playbook (not interested / no time / email me /
price / competitor), and a hard requirement to end every call with a
concrete outcome (booking, callback, or a clean decline) via
`sales/booking.py`'s existing slot-offer/confirm tools.

## 5. Anti-hallucination

The agent's system prompt states explicitly that `knowledge_text` is its
only source of facts, and instructs it to say "let me confirm and follow
up" rather than invent pricing, features, or claims -- see
`packages/backend/app/llm/prompts.py`. This mirrors the logistics-era
grounding pattern, simplified: since a persona's knowledge base is
user-authored and short, it's injected directly rather than
keyword-retrieved.

## 6. Emotion and voice

The LLM prefixes every reply with a hidden `[[emotion:tag]]` (neutral,
warm, confident, enthusiastic, empathetic, urgent), parsed and stripped by
`turn.py` before anything is spoken or shown, then mapped to ElevenLabs
stability/similarity/style settings in `tts/elevenlabs.py`. Voices can be
picked from an existing ElevenLabs voice ID or instant-cloned from a short
reference recording via `/api/voices/clone` in the persona builder.

## 7. Latency

- **TTS**: `eleven_flash_v2_5` -- ElevenLabs' lowest-latency model
  (~75-150ms to first byte), a deliberate trade of a sliver of quality for
  speed on a live call.
- **Chunk-ahead streaming**: `tts/splitter.py` splits replies into
  growing-budget chunks (small first chunk ~75 chars) so playback of
  earlier chunks masks synthesis time of later ones -- unchanged from the
  original build, still the right pattern.
- **No department-routing LLM call**: the old logistics receptionist ->
  specialist intent classification/routing step was removed entirely for
  the sales flow (single persona, no transfers) -- one fewer LLM round trip
  per turn.
- **Telnyx audio path**: ElevenLabs emits `ulaw_8000` directly, so outbound
  audio needs no resampling before reaching Telnyx (PCMU is the same
  encoding as mulaw).

**Deferred to Phase 2**: full token-level LLM streaming straight into TTS
(a bigger refactor requiring a streaming-capable LLM client) and real
barge-in/interruption handling (the current Telnyx bridge is simple
half-duplex -- caller audio is ignored while the agent is speaking).

## 8. Telephony (Telnyx)

`POST /api/calls/dial {to_number, persona_id}` places a real call via the
Telnyx Call Control API (`telephony/telnyx_client.py`). Unlike a
TwiML-style flow, Telnyx starts bidirectional media streaming as soon as
the call is dialed -- `stream_url`/`stream_track`/`stream_bidirectional_*`
are parameters on the same `POST /v2/calls` request, pointed straight at
`/ws/telnyx-media`, with no separate answer-webhook round trip. Inbound
audio (8kHz PCMU/mulaw, `track: "inbound"`) is buffered with a simple
RMS-threshold silence detector (~700ms) to find turn boundaries, wrapped in
a WAV container for the existing batch STT engines, and run through the
same `run_turn()` as the browser path. Call status comes back via
`/api/telephony/telnyx-status`, a per-call webhook (JSON, Telnyx's
`data.event_type`/`data.payload` envelope), and updates the live dashboard
feed on terminal events (`call.hangup`).

Requires `TELNYX_API_KEY` / `TELNYX_CONNECTION_ID` (the Voice API App your
number is assigned to) / `TELNYX_FROM_NUMBER` and a publicly reachable
`PUBLIC_BASE_URL` (ngrok in local dev), and `TTS_ENGINE=elevenlabs`.

## 9. GPU-hosted models

- **LLM**: any OpenAI-compatible endpoint (vLLM, TGI, Ollama, etc.) works
  by pointing `LLM_BASE_URL` at it -- no code change.
- **STT/TTS**: `STT_ENGINE=remote` / `TTS_ENGINE=remote` already proxy to a
  GPU pod via `VOICE_SPEECH_BASE_URL` -- see `stt/remote.py` /
  `tts/remote.py` for the expected request/response shape; adjust those two
  files if your actual GPU server's API differs.

## 10. LiveKit voice pipeline (browser test-call only)

The browser test-call page (`/dashboard/test-call`) runs on a second,
separate voice pipeline: real WebRTC via LiveKit, instead of the
base64-JSON-over-WebSocket transport `/ws/call` used to serve. Telnyx
phone calls (§8) are completely untouched by this -- two pipelines
temporarily, by deliberate choice (see below).

**Why a second pipeline**: the JSON/WebSocket browser transport never had
real mic capture (`STT_ENGINE=mock` was the only thing that ever ran
against it) and neither it nor the Telnyx bridge has real barge-in --
interrupting the agent mid-sentence doesn't stop it. LiveKit Agents
solves both: real WebRTC audio (echo cancellation, proper codec) and
Silero VAD-based turn detection with built-in interruption handling.

**Split infrastructure, and why**: LiveKit's own media server (SFU) needs
Linux host networking and a wide open UDP range for WebRTC -- Docker on
Windows/Mac can't do that reliably, and self-hosting SIP's RTP media is
worse still. So the **SFU is LiveKit Cloud** (managed, free tier), while
the **agent worker is entirely ours** -- a separate Python process
(`app/voice_agent/agent.py`, run via `python -m app.voice_agent.agent
start`, its own `livekit_agent` service in `docker-compose.yml`) that
connects OUT to LiveKit Cloud over a WebSocket. No inbound ports, so it
runs identically on a Windows dev box, a Linux GPU server, or in
production.

**Architecture**:
```
Browser --POST /api/livekit/token--> FastAPI --AccessToken w/ RoomAgentDispatch--> LiveKit Cloud
Browser --livekit-client, real WebRTC audio-------------------------------------> LiveKit Cloud
                                                                                        │
                                                          agent auto-dispatched into room
                                                                                        ▼
                                                                     app/voice_agent/agent.py
                                                                     AgentSession(
                                                                       stt=ExistingEngineSTT(...)  -- wraps stt/whisper.py or stt/remote.py, unchanged
                                                                       llm=openai.LLM(base_url=LLM_BASE_URL, ...)  -- same GPU/OpenAI-compatible config
                                                                       tts=elevenlabs.TTS(voice_id=persona.elevenlabs_voice_id, ...)
                                                                       vad=silero.VAD.load()
                                                                     )
                                                                          │
                                                        internal_client.py -- HTTP, see below
                                                                          ▼
                                                          FastAPI /internal/* endpoints
```

**Critical detail: the agent worker is a separate OS process, with no
shared memory with FastAPI.** `conversation.personas`, `realtime.bus`,
and `sales.*` are all in-memory stores living inside the FastAPI
process's own memory. The agent worker cannot import and call them
directly and expect to see the same data -- discovered live (persona
lookups returned nothing, transcript never reached the dashboard) and
fixed by routing everything cross-process through
`app/voice_agent/internal_client.py`, an HTTP client hitting a small set
of `/internal/*` endpoints on `main.py`, guarded by a shared
`INTERNAL_API_KEY` header (not a user's bearer token, since the worker
isn't acting as any particular logged-in user):
- `GET /internal/personas/{id}` -- persona lookup
- `POST /internal/calls/{id}/transcript`, `/state` -- mirrored into
  `realtime/bus.py`, which is what the dashboard's `/ws/dashboard`
  actually broadcasts from
- `POST /internal/calls/{id}/lead-extract`, `/escalate` -- run
  `sales/leads.py` / `sales/escalation.py` inside the FastAPI process, so
  writes land in the same `LEADS`/`CASES` stores `/api/leads` and
  `/api/escalations` read from
- `POST /internal/bookings/confirm` -- same reasoning for `BOOKINGS`

Pure/stateless functions (`sales/booking.py`'s `available_slots()` and
the `format_*_for_speech()` formatters, `sales/escalation.py`'s
`detect_escalation_trigger()`, `llm/prompts.py::build_system_prompt`)
stay directly imported in the agent worker -- they don't touch any
shared store, so there's nothing to bridge. `agent_state_changed` maps
directly onto the existing listening/thinking/speaking vocabulary used
by `CallAnimation` and the other two transports.

Verified live end-to-end (not just unit-level): a headless script created
a real persona over the REST API, requested a LiveKit token, joined the
room as a fake caller, and confirmed the agent worker joined, published a
real ElevenLabs-synthesized audio track for its greeting, and that
greeting appeared as a transcript line over `/ws/dashboard` -- the full
cross-process path, working.

**Known trade-off**: the `[[emotion:tag]]` mechanism (§6) does not carry
over here -- `build_system_prompt(..., include_emotion_tag=False)` omits
the instruction entirely, since there's no step in this pipeline to strip
the tag before ElevenLabs would otherwise speak it aloud verbatim. The
LiveKit path uses one fixed voice delivery per call instead of per-turn
emotion switching. Phase 2 item: a custom `Agent.llm_node()` override to
intercept streamed tokens and dynamically retune TTS `voice_settings`
mid-call.

**Config**: `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` from
a free LiveKit Cloud project (cloud.livekit.io).

## 11. Phase 2 (explicitly out of scope for this pass)

- Bring-your-own caller ID (Telnyx Verified Numbers) -- calls currently
  always originate from CallForge's own Telnyx number.
- Full token-level LLM streaming into TTS on the Telnyx/browser-JSON path.
- Unify the Telnyx phone path onto LiveKit SIP (LiveKit Cloud can
  terminate a Telnyx SIP trunk directly, routing real phone calls into
  the same Agent pipeline the browser uses -- would collapse two voice
  pipelines into one and gain real VAD/barge-in on phone calls too, plus
  real inbound calling) -- deliberately deferred this pass.
- Per-utterance emotion switching on the LiveKit path (see §10).
- Batch/campaign dialing (multiple numbers from one persona).
- Call recording and post-call analytics.
- Non-English language support for the sales flow (the underlying
  bilingual machinery still exists but isn't extended here).
