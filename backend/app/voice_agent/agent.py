"""LiveKit Agent worker entrypoint -- the browser test-call voice pipeline.

Run with: python -m app.voice_agent.agent dev   (or `start` in production)

Connects OUT to LiveKit Cloud (settings.livekit_url) -- no inbound ports.
Reuses the exact same sales playbook and grounding as the browser-JSON and
Telnyx paths (conversation/turn.py); only the STT->LLM->TTS
*orchestration* is handed off to LiveKit's AgentSession, which gets us
real VAD-based turn detection and barge-in for free. See
SALES_AGENT_SPEC.md.

This worker is a SEPARATE OS PROCESS from the FastAPI backend, so it
cannot import conversation.personas / realtime.bus / sales.* and expect
to see the same in-memory data -- see internal_client.py, which is how
persona lookups, transcript/state updates, lead capture, escalation, and
booking confirmation actually reach the backend's shared stores.
"""
from __future__ import annotations
import asyncio
import json
import logging

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool
from livekit.agents.llm import ChatContext
from livekit.agents.voice.agent import ModelSettings
from livekit.plugins import openai, silero

from ..config import settings
from ..conversation.bilingual import detect_language, ensure_urdu_script
from ..conversation.session import CallSession
from ..conversation.turn import _generate_varied_opener, _template_opener
from ..llm import Message, create_client, create_urdu_fallback_client
from ..llm.prompts import build_system_prompt
from ..sales.booking import (
    available_slots, format_slots_for_speech, BOOKING_INTENT_KEYWORDS,
    looks_like_booking_response, resolve_slot as _resolve_slot,
    extract_contact_info, extract_slot_pick, sounds_like_unverified_confirmation,
    booking_confirmed_by_context, is_placeholder_contact,
)
from ..sales.escalation import detect_escalation_trigger
from ..stt import create_engine as create_stt_engine
from . import internal_client as backend
from .constants import AGENT_NAME
from .stt_adapter import ExistingEngineSTT
from .tts_adapter import EdgeTTS, ElevenLabsHybridTTS, UpliftTTS

log = logging.getLogger("callforge.voice_agent")


class SalesAgent(Agent):
    """One LiveKit Agent instance per call -- holds the booking tools,
    which reach the backend's shared BOOKINGS store over HTTP (see
    internal_client.py) rather than a direct import, since this process
    doesn't share memory with the FastAPI backend."""

    def __init__(self, persona, call_id: str, call_session: CallSession):
        super().__init__(instructions=self._build_instructions(persona, call_session))
        self._persona = persona
        self._call_id = call_id
        self._session_state = call_session
        # Per-turn language detection is fragile against garbled STT --
        # confirmed live: a mis-transcribed Roman-Urdu utterance ("kya bat
        # ke?") didn't hit the word-ratio threshold, so it silently fell
        # through to the local GPU model (bad at Urdu) instead of the
        # Urdu-capable Groq model, even on this Urdu-first persona. Since
        # the persona itself is unambiguous, always use the Urdu-capable
        # LLM for it rather than re-deciding per turn.
        self._is_urdu_persona = detect_language(persona.opening_line or "").primary == "ur"

    def _build_instructions(self, persona, call_session: CallSession) -> str:
        return build_system_prompt(
            persona.name, persona.company, persona.product_pitch,
            persona.personality, knowledge_text=persona.knowledge_text,
            call_goal=persona.call_goal,
            language_mode=getattr(persona, "language_mode", "auto"),
            booking_offer=call_session.booking_offer if call_session.awaiting_booking_choice else None,
            include_emotion_tag=False,  # no strip-and-map step in this pipeline
        )

    async def llm_node(self, chat_ctx: ChatContext, tools, model_settings: ModelSettings):
        last_user_text = ""
        prev_agent_text = ""
        for msg in reversed(chat_ctx.messages()):
            if msg.role == "user" and not last_user_text:
                last_user_text = (msg.text_content or "").lower()
            elif msg.role == "assistant" and last_user_text and not prev_agent_text:
                prev_agent_text = msg.text_content or ""
                break

        # Cache a phone/email the moment the caller states it in ANY turn,
        # not just the booking turn -- same fix as conversation/turn.py --
        # so booking can complete immediately later without re-asking for
        # something already given.
        _cached_phone, _cached_email = extract_contact_info(last_user_text)
        if _cached_phone and not self._session_state.caller_phone:
            self._session_state.caller_phone = _cached_phone
        if _cached_email and not self._session_state.caller_email:
            self._session_state.caller_email = _cached_email

        # tool_choice is sent to the LLM but confirmed NOT honored by this
        # backend (Ollama silently free-styles text instead of calling the
        # tool, even forced with only one tool registered) -- deterministically
        # complete the booking ourselves the moment we can extract everything
        # needed from the caller's own words, same fix as conversation/turn.py.
        # Also fires when the AGENT just proposed booking and the caller
        # simply said "yes" -- confirmed live, the far more common real
        # pattern: the caller virtually never says "book" themselves.
        if not self._session_state.booking_offer and (
            any(kw in last_user_text for kw in BOOKING_INTENT_KEYWORDS)
            or booking_confirmed_by_context(prev_agent_text, last_user_text)
        ):
            # Same principle, one step earlier: trusting the LLM to call
            # offer_booking_slots itself is what let it ad-lib a time as
            # its own suggestion and run an entire booking through to a
            # fabricated reference number without ever touching a real
            # slot -- awaiting_booking_choice never became true, so the
            # confirm-step bypass below never even got a chance to engage.
            slots = available_slots(3)
            self._session_state.booking_offer = slots
            self._session_state.awaiting_booking_choice = True
            await self.update_instructions(self._build_instructions(self._persona, self._session_state))
            log.warning("Deterministically offered slots (bypassed LLM) on: %r", last_user_text)
            yield format_slots_for_speech(slots, "en")
            return

        if self._session_state.awaiting_booking_choice and looks_like_booking_response(last_user_text):
            phone, email = extract_contact_info(last_user_text)
            slot = extract_slot_pick(last_user_text, self._session_state.booking_offer)
            # Reuse a phone/email already given earlier in the call instead
            # of forcing an extra round-trip to re-ask for it -- see the
            # opportunistic capture above.
            phone = phone or self._session_state.caller_phone or None
            email = email or self._session_state.caller_email or None
            if slot and (phone or email):
                caller_name = (
                    self._session_state.caller_name
                    if self._session_state.caller_name and self._session_state.caller_name != "Guest"
                    else "the caller"
                )
                confirmation = await backend.confirm_booking(
                    self._call_id, slot["id"], slot["label"],
                    caller_name, "consultation",
                    contact_phone=phone, contact_email=email,
                )
                self._session_state.awaiting_booking_choice = False
                self._session_state.real_booking_confirmed = True
                await self.update_instructions(self._build_instructions(self._persona, self._session_state))
                log.warning("Deterministically confirmed booking (bypassed LLM) on: %r", last_user_text)
                yield confirmation
                return

        if not self._session_state.booking_offer:
            matched = [kw for kw in BOOKING_INTENT_KEYWORDS if kw in last_user_text]
            if matched:
                model_settings = ModelSettings(tool_choice="required")
                log.warning("FORCING tool_choice=required (offer step, matched %s) on: %r",
                            matched, last_user_text)
        elif self._session_state.awaiting_booking_choice and looks_like_booking_response(last_user_text):
            # Forcing generic "required" here is ambiguous between the two
            # registered tools -- name the specific one so a forced call
            # can't itself go wrong by re-offering slots instead of
            # confirming. Same fix as conversation/turn.py.
            model_settings = ModelSettings(
                tool_choice={"type": "function", "function": {"name": "confirm_booking"}}
            )
            log.warning("FORCING confirm_booking tool_choice on: %r", last_user_text)

        # The local-GPU model (qwen2.5:7b / qwen3:8b) produces broken,
        # hallucinated Urdu -- confirmed live (garbled mid-word tokens,
        # invented product facts). Route Urdu turns to a larger cloud model
        # directly, bypassing self.llm (and tool-calling) entirely for this
        # turn -- booking is already handled by the deterministic bypasses
        # above regardless of language, so the only thing lost here is
        # tool-calling on a turn that wasn't a booking trigger anyway.
        if (self._is_urdu_persona or detect_language(last_user_text).primary == "ur") and (urdu_client := create_urdu_fallback_client()):
            sys_prompt = self._build_instructions(self._persona, self._session_state)
            history = [
                Message(role=m.role, content=m.text_content or "")
                for m in chat_ctx.messages() if m.role in ("user", "assistant")
            ]
            response = await urdu_client.chat([Message(role="system", content=sys_prompt)] + history, max_tokens=350)
            full_text = (response.content or "").replace("�", "")
            if not full_text:
                return
            full_text = await ensure_urdu_script(full_text)
            if not self._session_state.real_booking_confirmed and sounds_like_unverified_confirmation(full_text):
                log.warning("BLOCKED fake confirmation claim (Urdu path, no real booking exists): %r", full_text)
                self._session_state.awaiting_booking_choice = False
                self._session_state.booking_offer = []
                yield "Let me pull up our real availability for you, one moment -- what day and time works best?"
            else:
                yield full_text
            return

        # Buffer the model's plain-text output fully before speaking any of
        # it -- confirmed live, repeatedly: this model will confidently
        # narrate an entire fake booking (wrong dates, a fabricated phone
        # number never spoken by the caller) when the conversation calls
        # for a confirmation and it has none real to give. The deterministic
        # bypasses above catch the specific trigger turns; this is the
        # last-resort net for every other turn, where it's still free text.
        # Real tool-call chunks are forwarded immediately, unaffected.
        buffered: list[str] = []
        async for chunk in Agent.default.llm_node(self, chat_ctx, tools, model_settings):
            if isinstance(chunk, str):
                buffered.append(chunk)
                continue
            tc = getattr(chunk.delta, "tool_calls", None) if getattr(chunk, "delta", None) else None
            if tc:
                log.warning("LLM tool_calls this chunk: %s", [t.name for t in tc])
                yield chunk
                continue
            content = getattr(chunk.delta, "content", None) if getattr(chunk, "delta", None) else None
            if content:
                buffered.append(content)
                continue
            yield chunk  # metadata-only chunk (e.g. usage) -- forward as-is

        full_text = "".join(buffered)
        if not full_text:
            return
        if not self._session_state.real_booking_confirmed and sounds_like_unverified_confirmation(full_text):
            log.warning("BLOCKED fake confirmation claim (no real booking exists): %r", full_text)
            self._session_state.awaiting_booking_choice = False
            self._session_state.booking_offer = []
            yield "Let me pull up our real availability for you, one moment -- what day and time works best?"
        else:
            yield full_text

    @function_tool(
        description=(
            "Get available meeting slots for the next 3 business days. Relay the "
            "returned slot list to the caller exactly as given -- do not paraphrase "
            "the dates/times or invent additional ones."
        )
    )
    async def offer_booking_slots(self, context: RunContext, n: int = 3) -> str:
        slots = available_slots(n)  # pure/deterministic -- no shared state, safe locally
        log.warning("offer_booking_slots called -> %s", [s["label"] for s in slots])
        self._session_state.booking_offer = slots
        self._session_state.awaiting_booking_choice = True
        # The Agent's instructions are a static string set once at call
        # start (unlike conversation/turn.py, which rebuilds the system
        # prompt fresh every turn) -- without this refresh, the model has
        # no valid slot_id to pass to confirm_booking once the caller picks
        # one, and silently gives up instead of calling it.
        await self.update_instructions(self._build_instructions(self._persona, self._session_state))
        return format_slots_for_speech(slots, "en")

    @function_tool(
        description=(
            "Confirm a booking after the caller picks a slot. Ask for the "
            "caller's best phone number and email BEFORE calling this -- a "
            "real rep always locks down contact details when booking. Read "
            "the returned confirmation -- especially the reference number -- "
            "back to the caller digit-for-digit, never approximated or reworded."
        )
    )
    async def confirm_booking(self, context: RunContext, slot_id: str,
                              contact_name: str, purpose: str = "consultation",
                              contact_phone: str | None = None,
                              contact_email: str | None = None) -> str:
        log.warning("confirm_booking called: slot_id=%r contact_name=%r phone=%r email=%r",
                    slot_id, contact_name, contact_phone, contact_email)
        if is_placeholder_contact(contact_name, contact_phone, contact_email):
            log.warning("confirm_booking: REJECTED placeholder-looking contact info")
            return "Sorry, I didn't quite catch your phone number and email correctly -- could you repeat them?"
        slot = _resolve_slot(self._session_state.booking_offer, slot_id)
        if not slot:
            log.warning("confirm_booking: slot_id %r not found in offered slots %s",
                        slot_id, [s["id"] for s in self._session_state.booking_offer])
            return "Sorry, that slot isn't available anymore. Would you like to pick another option?"

        if not contact_name.strip() or "[" in contact_name or "]" in contact_name:
            log.warning("confirm_booking: placeholder/empty contact_name %r -- using fallback", contact_name)
            contact_name = "the caller"

        self._session_state.awaiting_booking_choice = False
        self._session_state.real_booking_confirmed = True
        await self.update_instructions(self._build_instructions(self._persona, self._session_state))
        return await backend.confirm_booking(
            self._call_id, slot["id"], slot["label"], contact_name, purpose,
            contact_phone=contact_phone, contact_email=contact_email,
        )


server = AgentServer(
    ws_url=settings.livekit_url or None,
    api_key=settings.livekit_api_key or None,
    api_secret=settings.livekit_api_secret or None,
)


async def _on_session_end(ctx: agents.JobContext) -> None:
    metadata = json.loads(ctx.job.metadata or "{}")
    call_id = metadata.get("call_id", "")
    if call_id:
        await backend.update_state(call_id, "ended")
        await backend.finalize_call(call_id)
    log.info("LiveKit call %s ended", call_id)


@server.rtc_session(agent_name=AGENT_NAME, on_session_end=_on_session_end)
async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()

    metadata = json.loads(ctx.job.metadata or "{}")
    call_id = metadata.get("call_id", "")
    persona_id = metadata.get("persona_id", "")
    persona = await backend.get_persona(persona_id) if persona_id else None

    if not call_id or persona is None:
        log.warning("LiveKit job missing call_id/persona_id, or persona lookup failed -- closing")
        return

    call_session = CallSession()
    call_session.call_id = call_id
    call_session.persona_id = persona.id
    call_session.caller_name = "Guest"

    llm_kwargs: dict = {
        "model": settings.llm_model,
        "api_key": settings.effective_llm_api_key,
        "max_completion_tokens": 350,
    }
    if settings.effective_llm_base_url:
        llm_kwargs["base_url"] = settings.effective_llm_base_url
    # Groq's gpt-oss/qwen3 models are reasoning models -- uncapped reasoning
    # effort can burn the whole completion-token budget before any visible
    # reply is produced, returning empty content on a real-time voice turn.
    # See app/llm/qwen.py for the same fix on the other two transports.
    if "groq.com" in settings.effective_llm_base_url:
        llm_kwargs["reasoning_effort"] = "low"

    # Persona's opening_line signals whether this is an Urdu-first persona
    # (e.g. "Saad (Urdu)") -- pin STT's language for the whole call rather
    # than leaving Whisper to auto-detect per clip (confirmed live: garbles/
    # misrecognizes short Urdu utterances), and pin TTS to the Urdu voice
    # for the whole call too rather than re-deciding per chunk (confirmed
    # live: causes the voice to audibly flip mid-reply whenever a short
    # fragment gets classified as English).
    is_urdu_persona = detect_language(persona.opening_line or "").primary == "ur"
    # Whisper has a dedicated "sd" Sindhi language code -- forcing Sindhi
    # audio through "ur" instead biases the model toward Urdu phonetic/
    # orthographic priors on a genuinely different language, confirmed
    # live to hurt accuracy (a tester reported only ~60% of Sindhi/Urdu
    # speech understood correctly).
    stt_language = (
        "sd" if getattr(persona, "language_mode", "auto") == "sindhi"
        else "ur" if is_urdu_persona else None
    )

    # settings.tts_engine picks the engine for the browser-JSON/Telnyx
    # paths too (see tts/__init__.py); mirror that choice here so both
    # transports agree on which engine is actually configured right now.
    if settings.tts_engine == "elevenlabs":
        tts_engine = ElevenLabsHybridTTS(elevenlabs_voice_id=persona.elevenlabs_voice_id, force_urdu=is_urdu_persona)
    elif settings.tts_engine == "uplift":
        tts_engine = UpliftTTS(
            urdu_voice_id=getattr(persona, "uplift_voice_id", "") or "podcast-host",
            elevenlabs_voice_id=persona.elevenlabs_voice_id,
            force_urdu=is_urdu_persona,
            roman_script=getattr(persona, "uplift_roman_script", False),
            native_tts_provider=getattr(persona, "native_tts_provider", "uplift"),
            native_language_code="sd" if getattr(persona, "language_mode", "auto") == "sindhi" else "ur",
        )
    else:
        tts_engine = EdgeTTS()

    session = AgentSession(
        stt=ExistingEngineSTT(create_stt_engine(settings.stt_engine), default_language=stt_language),
        llm=openai.LLM(**llm_kwargs),
        tts=tts_engine,
        vad=silero.VAD.load(),
        # Defaults (min_interruption_words=0) let ANY 0.5s of VAD-detected
        # voice activity -- a breath, a cough, background noise -- count as
        # a real interruption even when STT never recognizes an actual
        # word, so the agent just stops and never resumes. Requiring a
        # few real words routes silent/noise-only "interruptions" through
        # resume_false_interruption instead (already enabled by default)
        # so the agent picks its sentence back up. Also helps (though
        # doesn't fully solve -- see stt_adapter's silence/hallucination
        # filtering, and use headphones when testing) against acoustic
        # echo: the agent's own TTS output leaking back through a
        # caller's speakers into their mic, which a few short leaked
        # words could otherwise register as a real caller turn.
        min_interruption_duration=0.6,
        min_interruption_words=3,
    )

    def _on_item_added(event) -> None:
        item = event.item
        text = getattr(item, "text_content", "") or ""
        if not text or getattr(item, "type", "") != "message":
            return
        who = "caller" if item.role == "user" else "agent"
        name = call_session.caller_name if who == "caller" else persona.name
        asyncio.create_task(backend.append_transcript(call_id, who, name, text))

        if who != "caller":
            return
        # Skip on short fillers ("yeah", "sure") -- never carry lead signal,
        # and this is a real LLM call on the backend side (see
        # sales/leads.py::maybe_extract's matching guard), a meaningful
        # token cost against Groq's free-tier per-minute limit.
        if len(text.split()) >= 4:
            asyncio.create_task(backend.extract_lead(call_id, text, call_session.caller_name))
        trigger = detect_escalation_trigger(text, call_session)
        if trigger and not call_session.escalated:
            call_session.escalated = True
            asyncio.create_task(_speak_escalation(session, call_session, call_id, trigger))

    def _on_state_changed(event) -> None:
        call_session.transition(event.new_state)
        asyncio.create_task(backend.update_state(call_id, event.new_state))

    session.on("conversation_item_added", _on_item_added)
    session.on("agent_state_changed", _on_state_changed)

    await session.start(agent=SalesAgent(persona, call_id, call_session), room=ctx.room)

    # Freshly worded every call, same as the browser-JSON/Telnyx paths --
    # a real rep never opens with the exact same sentence twice.
    # _generate_varied_opener already falls back to a fixed template if the
    # LLM call itself errors, but a "successful" response can still come
    # back with a corrupted character (observed live: a stray U+FFFD "�"
    # from a request that got interrupted mid-stream by a Groq 429 retry) --
    # ElevenLabs hard-fails synthesis on that with no audio produced at
    # all, which left the call stuck forever on "Waiting for the
    # greeting...". Strip it defensively; if the WHOLE greeting somehow
    # comes back empty/invalid, fall back to the plain-ASCII template
    # rather than risk another silent stall on the very first thing said.
    greeting = (await _generate_varied_opener(persona, "", create_client())).replace("�", "")
    if not greeting.strip():
        greeting = _template_opener(persona, "")
    session.say(greeting, add_to_chat_ctx=True)


async def _speak_escalation(session: AgentSession, call_session: CallSession,
                            call_id: str, trigger: str) -> None:
    """Verbatim escalation speech, bypassing the LLM -- same deterministic-
    template approach conversation/turn.py uses, so the case number is
    always read back exactly rather than paraphrased."""
    speech = await backend.escalate(call_id, trigger, call_session.caller_name)
    session.say(speech, add_to_chat_ctx=True)


if __name__ == "__main__":
    agents.cli.run_app(server)
