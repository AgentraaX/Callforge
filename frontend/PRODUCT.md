# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js 15 + React 19 + Tailwind v4. No UI library. Self-hosted fonts via next/font.

## Users

1. **Sales founders and revenue leaders** evaluating AI-powered cold calling and lead qualification for their own outbound or inbound sales motion, across any industry.
2. **Hackathon judges** assessing technical innovation, demo polish, and market viability.
3. **Sales supervisors** monitoring live AI agent calls, leads, bookings, and escalations in real time.

## Product Purpose

CallForge is an AI voice agent that runs sales calls on behalf of any business — qualifying leads, handling objections, booking appointments, answering grounded questions from that business's own knowledge base, and escalating complex issues — in English and Urdu. It replaces the inconsistency of a human cold calling team with an always-on AI agent that never misses a lead and never goes off script.

Success means: a business can define a persona for CallForge in minutes and have it handle a real share of its sales calls autonomously, capturing qualified leads and booking meetings without human intervention.

## Positioning

CallForge is an AI voice agent for cold calling and inbound sales, built around user-defined personas rather than a one-size-fits-all script — a name, a pitch, a personality, a knowledge base, and a voice, configurable per business. It combines bilingual Urdu and English support, strict grounding so it never invents facts about what it is selling, and a real-time supervisor dashboard. Generic AI call tools cannot match its cold-calling technique, its anti-hallucination guarantees, or the dashboard that lets a human team intervene on a hot lead instantly.

## Operating Context

- Deployed as a cloud service; any business connects its phone number via Twilio or tests personas directly in the browser
- Supervisor dashboard is always-on for sales teams monitoring call quality and lead flow
- STT must handle ambient noise, accented speech, and code switching between English and Urdu mid call
- A full CRM (contacts, companies, deals, activities) sits behind the dashboard for lead handoff

## Capabilities and Constraints

- Real-time voice loop: STT (VibeVoice/Whisper) → LLM (Qwen-Plus) → TTS (CosyVoice/Edge)
- Intent classification across 11 intents with entity extraction
- Anti-hallucination: 4-layer grounding defense ensures answers come only from verified knowledge base
- Bilingual code-switching detection (English ↔ Urdu)
- Lead scoring (hot/warm/cold) with fire-and-forget extraction
- Appointment booking with slot management
- Escalation detection with AI-generated case summaries
- WebSocket-based real-time dashboard for supervisors
- No fabricated metrics or customer claims in marketing — the demo speaks for itself

## Brand Commitments

- **Company:** AgentraX
- **Product:** CallForge
- **Voice:** Professional, technically credible, direct. Not startup-hype; the product is serious infrastructure for a serious sales operation.
- **Visual identity:** Dark, operational, premium. Evokes a command center — not a consumer chatbot.

## Evidence on Hand

- Working demo with full voice loop, 4 AI personas (Ahmed, Bilal, Mahnoor, Shahzaib)
- Real voice samples cloned via CosyVoice
- Complete backend with 36 Python modules across 8 packages
- Live WebSocket dashboard with real-time call monitoring
- No real customer testimonials yet — do not fabricate

## Product Principles

1. **Grounded truth over hallucinated confidence** — every answer traces to verified knowledge; "I don't have that information" is always preferred over invention.
2. **Human oversight, not replacement** — supervisors see everything live and can intervene; AI handles volume, humans handle judgment.
3. **Persona-native, not generic** — every deployment runs on that business's own pitch, knowledge, and voice from day one, not a shared script.
4. **Latency is trust** — sub-second voice response; any delay erodes caller confidence.
5. **Bilingual by design** — Urdu and English are first-class, not afterthoughts.
