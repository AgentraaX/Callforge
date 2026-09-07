# CallForge

CallForge is an AI voice agent that runs real sales calls for a business, in English and Urdu. Give it a persona, a name, a company, a one line pitch, a personality, a cloned or chosen voice, and a knowledge base of facts it is allowed to state, and it places or receives calls and runs a genuine cold calling conversation: a permission based opener, rapport building, discovery before pitching, objection handling, and a close that ends in a booked meeting, a callback, or a clean decline. A live supervisor dashboard shows every call as it happens so a human can step in on a hot lead at any moment.

Built by [AgentraaX](https://github.com/AgentraaX) for the Alibaba Cloud AI Hackathon Pakistan 2026.

## What it does

- Places outbound calls and answers inbound calls through Twilio, or runs a browser test call for building and testing personas
- Runs a real cold calling playbook: rapport, discovery, objection handling, and a hard requirement to end every call with a concrete outcome
- Speaks and listens in English and Urdu, including code switching between the two mid call
- Grounds every answer in a persona's own knowledge base; if it does not know something it says so and offers to follow up instead of inventing an answer
- Clones or reuses a voice per persona and adjusts delivery (warm, confident, urgent, and so on) per reply
- Scores leads hot, warm, or cold, books appointments, and escalates anything it cannot confidently handle with an AI written case summary
- Streams every call, lead, and booking to a live dashboard over WebSocket, with a full CRM (contacts, companies, deals, activities) behind it

## Architecture

```
Browser (test call) ──▶ /ws/call ─────────┐
                                           ▼
                                run_turn()  (conversation/turn.py)
                                one engine: lead capture, escalation
                                check, grounded LLM reply, emotion
                                tag, booking tools, chunked TTS
                                           ▲
Twilio (real call)  ──▶ /ws/twilio-media ──┘
```

Both call paths run through the same turn engine, so the sales technique, the grounding, and the anti hallucination logic live in exactly one place. See [`docs/SALES_AGENT_SPEC.md`](docs/SALES_AGENT_SPEC.md) for the full technical specification.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI + WebSocket | one conversation engine shared by the browser test path and the real Twilio path |
| LLM | Qwen Plus, any OpenAI compatible endpoint | swap providers or point at a self hosted model with no code change |
| STT | Whisper / VibeVoice | handles accented and noisy audio |
| TTS | ElevenLabs Flash, with Edge and Uplift fallback for Urdu | lowest latency option, first byte in well under 200ms |
| Telephony | Twilio Media Streams | real inbound and outbound calling |
| Frontend | Next.js 15, React 19, Tailwind v4 | persona builder, live call dashboard, and CRM |
| CRM storage | PostgreSQL + SQLAlchemy + Alembic | contacts, companies, deals, activities behind the dashboard |

## Repository layout

```
backend/    FastAPI app: voice pipeline, sales playbook, telephony, CRM, tests
frontend/   Next.js app: persona builder, live call dashboard, CRM, marketing site
shared/     Data contracts shared between backend and frontend
docs/       Technical specification and CRM dashboard plan
```

## Running it locally

```bash
cp .env.example .env
# fill in the keys you plan to use, see the comments in .env.example

# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend, in a second terminal
cd frontend
npm install
npm run dev
```

Or with Docker:

```bash
docker compose up
```

The backend runs with mock speech and text to speech engines out of the box, so the full conversation flow works with no API keys at all. Set `STT_ENGINE` / `TTS_ENGINE` in `.env` to a real engine, and add `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_FROM_NUMBER` plus a public `PUBLIC_BASE_URL`, once you want a real phone call.

## Status

Working end to end: the full voice loop, real inbound and outbound calling through Twilio, four cloned voice personas, a live supervisor dashboard, and a CRM behind it. See [`docs/SALES_AGENT_SPEC.md`](docs/SALES_AGENT_SPEC.md) for what is deferred to a later phase, including full token level LLM streaming into speech and real barge in handling on live calls.
