"""Transport-agnostic turn engine.

Both the browser test-call WebSocket (/ws/call) and the real Telnyx phone
call bridge (/ws/telnyx-media) funnel caller utterances through
``run_turn`` so the sales technique, grounding, anti-hallucination, lead
capture, escalation, and booking logic exists in exactly one place. Each
transport only owns getting caller *text* in and playable *audio* out.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime
from typing import Awaitable, Callable

from ..llm import Message, Tool, create_urdu_fallback_client
from ..llm.prompts import build_system_prompt
from ..tts.splitter import split_for_speech
from ..tts import voice_from_persona
from ..sales import (
    maybe_extract as extract_lead, get as get_lead,
    detect_escalation_trigger, create_case, format_escalation_speech,
    available_slots, confirm as confirm_booking,
    format_slots_for_speech, format_confirmation_for_speech, BOOKING_TOOLS,
    BOOKING_INTENT_KEYWORDS, looks_like_booking_response, resolve_slot as _resolve_slot,
    extract_contact_info, extract_slot_pick, sounds_like_unverified_confirmation,
    booking_confirmed_by_context, is_placeholder_contact,
)
from .bilingual import detect_language, ensure_urdu_script
from .personas import persona_payload
from .session import CallSession
from ..realtime.bus import bus

log = logging.getLogger("callforge.conversation.turn")

_BOOKING_TOOLS_TYPED = [
    Tool(name=t["name"], description=t["description"], parameters=t["parameters"])
    for t in BOOKING_TOOLS
]

_EMOTION_TAGS = {"neutral", "warm", "confident", "enthusiastic", "empathetic", "urgent"}
# Accepts both the instructed [[emotion:tag]] form and a bare [[tag]] --
# smaller/weaker models sometimes drop the "emotion:" literal even when
# told not to; matching both keeps the tag from leaking into speech either way.
_EMOTION_TAG_RE = re.compile(r'^\s*\[\[(?:emotion:)?(\w+)\]\]\s*', re.IGNORECASE)

# (text_chunk, audio_bytes, mime, chunk_index) -> None
EmitFn = Callable[[str, bytes, str, int], Awaitable[None]]


def _strip_emotion_tag(text: str, default: str) -> tuple[str, str]:
    """Parse and remove the leading [[emotion:tag]] (or bare [[tag]]) the
    LLM was instructed to prefix every reply with. Strips the bracket
    wrapper whenever the structural pattern matches, even if the tag word
    itself isn't one of the allowed ones (falls back to the persona's
    default emotion in that case) -- a model that invents an unlisted tag
    name (e.g. "understanding" instead of "empathetic") should never leak
    the raw [[...]] markup into what's actually spoken."""
    m = _EMOTION_TAG_RE.match(text)
    if not m:
        return text.strip(), default
    tag = m.group(1).lower()
    if tag not in _EMOTION_TAGS:
        tag = default
    remainder = text[m.end():].strip()
    return remainder or text.strip(), tag


async def generate_greeting(session: CallSession, persona, tts_engine, llm_client, *,
                            telephony: bool = False) -> tuple[str, bytes, str]:
    """Pre-generate the opening line -- freshly worded every call, the way
    a real rep never says the exact same sentence twice even with a
    consistent pitch. ``persona.opening_line`` (if set) is used as a style
    reference for the LLM to riff on, not spoken verbatim."""
    name = session.caller_name if session.caller_name and session.caller_name != "Guest" else ""
    greeting = await _generate_varied_opener(persona, name, llm_client)

    voice = voice_from_persona(persona, telephony=telephony)
    result = await tts_engine.synthesize(greeting, voice, persona.default_emotion)
    return greeting, result.audio, result.mime


def _time_of_day() -> str:
    """Server-local time of day for a natural "good morning/afternoon/
    evening" -- an approximation (no caller timezone info available), but
    a real time-appropriate greeting reads far more human than a flat
    "Hi" on every single call regardless of when it happens."""
    hour = datetime.now().hour
    if hour < 12:
        return "morning"
    if hour < 17:
        return "afternoon"
    return "evening"


def _template_opener(persona, name: str) -> str:
    # The persona's own opening_line, verbatim, is the safest fallback --
    # it's already in whatever language/register the persona was written
    # for (e.g. an Urdu-first persona's Urdu greeting). Reconstructing an
    # English "Good morning, this is..." template here would silently
    # discard that, which is exactly what happened before this fix: an
    # Urdu persona's opening_line was only ever used as a "style reference"
    # for an LLM prompt that hardcoded English greeting words, so the LLM
    # produced an English opener regardless of the persona's language.
    reference = (persona.opening_line or "").strip()
    if reference:
        return reference
    greeting_word = f"Good {_time_of_day()}"
    if name:
        return f"{greeting_word}, {name}, this is {persona.name} calling from {persona.company or 'our team'} -- got a quick minute?"
    return f"{greeting_word}, this is {persona.name} calling from {persona.company or 'our team'} -- got a quick minute?"


async def _generate_varied_opener(persona, name: str, llm_client) -> str:
    """Ask the LLM for a fresh, natural cold-call opener. Falls back to a
    fixed template if the LLM is unavailable or errors -- a call should
    never stall on this."""
    reference = (persona.opening_line or "").strip()
    is_urdu = detect_language(reference).primary == "ur" if reference else False
    if is_urdu:
        return await _generate_varied_urdu_opener(persona, name, reference)

    language_instruction = (
        "Open with a natural time-of-day greeting (\"Good morning\"/"
        "\"Good afternoon\"/\"Good evening\", matching the time above -- "
        "vary how you phrase it call to call, don't always use the exact "
        "words \"Good afternoon\")."
    )

    prompt = (
        f"You are {persona.name}, calling on behalf of "
        f"{persona.company or 'your company'} to pitch: "
        f"{persona.product_pitch or 'a product or service'}.\n"
        f"Personality: {persona.personality or 'warm and confident'}.\n"
        f"It's currently {_time_of_day()} where the call is happening.\n"
        + (f'Style reference for the opener (vary the wording -- never repeat it verbatim): "{reference}"\n' if reference else "")
        + (f"The caller's name is {name} -- use it naturally.\n" if name else "")
        + f"Write ONE natural, permission-based cold-call opening line. {language_instruction} "
          "State your name and company plainly, then a brief hook or ask for "
          "a moment of their time. Under 20 words. Sound like a real person "
          "on the phone, not a script -- no two calls should open with the "
          "exact same wording. Reply with ONLY the line to be spoken, "
          "nothing else -- no quotes, no explanation."
    )
    try:
        response = await llm_client.chat(
            [Message(role="user", content=prompt)],
            max_tokens=120, temperature=0.95,
        )
        text = (response.content or "").strip().strip('"')
        if text:
            return text
    except Exception as exc:
        log.warning("Varied greeting generation failed, using fallback: %s", exc)
    return _template_opener(persona, name)


async def _generate_varied_urdu_opener(persona, name: str, reference: str) -> str:
    """Urdu/Sindhi opener variation. Every real cold-call rep opens each
    call a little differently -- an Urdu/Sindhi persona repeating the
    exact same sentence verbatim on every single call (the previous
    behavior here) reads as scripted the moment anyone tests more than
    one call back to back.

    Uses the Urdu-capable cloud LLM (the local GPU model produces broken
    Urdu/Sindhi, see run_turn), then validates the result before trusting
    it -- even the larger cloud model has been caught getting basic Urdu
    greeting etiquette wrong (confirmed live: opened with "وعلیکم السلام",
    the REPLY-only form, instead of a correct initiating greeting). The
    very first thing said on a call is too high-stakes to risk an
    unvalidated rewrite, so anything that fails the checks below falls
    back to the persona's own opening_line verbatim rather than risk a
    wrong-sounding first line.
    """
    urdu_client = create_urdu_fallback_client()
    if not urdu_client:
        return reference or _template_opener(persona, name)

    language_mode = getattr(persona, "language_mode", "auto")
    if language_mode == "sindhi":
        lang_label = "Sindhi (سنڌي)"
        brand_instruction = (
            'Keep the company name in plain Latin script, "CallForge" '
            '(never spelled out phonetically in Sindhi script, and drop '
            'any "AI" suffix when spoken -- just "CallForge").'
        )
        # Confirmed live: a longer opener (greeting + name + company +
        # permission-ask clause) came out unclear/hard to understand
        # through this TTS voice -- every extra clause is another chance
        # to garble. Keep it to the absolute minimum: greeting, name,
        # company, nothing else. Length constraint only for Sindhi.
        length_instruction = (
            "Keep it EXTREMELY short -- ONLY a greeting, your name, and "
            "the company name, nothing else added. No permission-ask, no "
            "question, no extra clause. Under 8 words total. Example "
            'shape (vary the greeting word only): "هيلو، آئون سعد آهيان، '
            'CallForge مان."'
        )
    else:
        lang_label = "Urdu (اردو)"
        brand_instruction = (
            'Spell the company name out phonetically in Urdu script '
            '(e.g. "کال فورج"), never in Latin script.'
        )
        length_instruction = (
            "State your name and company, then a brief permission-based "
            "hook or question. Under 20 words."
        )

    prompt = (
        f"You are {persona.name}, calling on behalf of "
        f"{persona.company or 'your company'} to pitch: "
        f"{persona.product_pitch or 'a product or service'}.\n"
        f"Personality: {persona.personality or 'warm and confident'}.\n"
        f'Style/language reference (vary the wording -- never repeat this '
        f'exact sentence verbatim): "{reference}"\n'
        + (f"The caller's name is {name} -- use it naturally.\n" if name else "")
        + f"Write ONE natural, permission-based cold-call opening line in "
          f"{lang_label}, in the same script as the reference line. "
          f"{brand_instruction} You are INITIATING the call, not replying "
          f'to a greeting -- if you use a greeting word at all, use a '
          f'plain/initiating one; never use a reply-only greeting form '
          f'like "وعلیکم السلام" (that is only ever correct as a REPLY). '
          f"{length_instruction} Sound like a real person on the phone, "
          f"not a script -- vary the wording call to call. Reply with "
          f"ONLY the line to be spoken, nothing else -- no quotes, no "
          f"explanation, no transliteration, no English translation "
          f"alongside it."
    )
    try:
        # A short max_tokens budget starves this -- gpt-oss/qwen3 reasoning
        # models spend a chunk of it on hidden reasoning before the visible
        # reply even with reasoning_effort capped low (confirmed live: 120
        # tokens burned entirely on reasoning, empty content, finish_reason
        # "length"). Match run_turn's real-reply budget instead of a
        # tighter one that only fits a plain non-reasoning model.
        response = await urdu_client.chat(
            [Message(role="user", content=prompt)],
            max_tokens=350, temperature=0.9,
        )
        text = (response.content or "").strip().strip('"')
        text = await ensure_urdu_script(text) if text else text
    except Exception as exc:
        log.warning("Varied Urdu/Sindhi greeting generation failed, using fallback: %s", exc)
        return reference or _template_opener(persona, name)

    if not text or detect_language(text).primary != "ur":
        log.warning("Varied Urdu/Sindhi greeting failed script validation, using fallback: %r", text)
        return reference or _template_opener(persona, name)
    if text.strip().startswith("وعلیکم"):
        log.warning("Varied opener used reply-only greeting etiquette, using fallback: %r", text)
        return reference or _template_opener(persona, name)

    return text


async def run_turn(session: CallSession, call: dict, text: str, persona,
                   llm_client, tts_engine, emit_chunk: EmitFn, *,
                   telephony: bool = False) -> None:
    """Process one caller utterance end-to-end and emit the agent's reply.

    ``emit_chunk`` is called once per TTS chunk as it's ready (small first
    chunk, growing budget -- see tts/splitter.py) so the transport can start
    playback before the whole reply is synthesized.
    """
    session.transition("thinking")
    session.turn_count += 1

    call["transcript"].append({"who": "caller", "name": session.caller_name, "text": text})
    await bus.update(call)

    # --- Business automation: lead capture (fire-and-forget) ---
    extract_lead(session, call, text)

    # Cache a phone/email the moment the caller states it in ANY turn, not
    # just the booking turn -- lets booking complete immediately later
    # without re-asking for something already given (see the deterministic
    # confirm branch below).
    _cached_phone, _cached_email = extract_contact_info(text)
    if _cached_phone and not session.caller_phone:
        session.caller_phone = _cached_phone
    if _cached_email and not session.caller_email:
        session.caller_email = _cached_email

    # --- Escalation: check before spending an LLM turn on it ---
    trigger = detect_escalation_trigger(text, session)
    if trigger and not session.escalated:
        session.transition("speaking")
        case = await create_case(
            call["id"], trigger,
            caller_name=session.caller_name,
            caller_intent=session.intent_log[-1] if session.intent_log else "unknown",
            transcript=call.get("transcript", []),
            lead_data=call.get("lead"),
            history=session.history,
        )
        session.escalated = True
        session.case_id = case.case_id
        speech = format_escalation_speech(case, session.language)

        session.add_to_history("assistant", speech)
        session.last_spoken = speech
        voice = voice_from_persona(persona, telephony=telephony)

        call["transcript"].append({"who": "agent", "name": persona.name, "text": speech})
        call["agent"] = persona_payload(persona)
        await bus.update(call)

        for i, chunk in enumerate(split_for_speech(speech)):
            result = await tts_engine.synthesize(chunk, voice, "empathetic")
            await emit_chunk(chunk, result.audio, result.mime, i)

        session.transition("listening")
        return

    # --- LLM reply, grounded in the persona's own knowledge + sales playbook ---
    session.add_to_history("user", text)

    system_prompt = build_system_prompt(
        persona.name, persona.company, persona.product_pitch,
        persona.personality, knowledge_text=persona.knowledge_text,
        call_goal=persona.call_goal,
        language_mode=getattr(persona, "language_mode", "auto"),
        booking_offer=session.booking_offer if session.awaiting_booking_choice else None,
        caller_name=session.caller_name if session.caller_name != "Guest" else "",
    )

    messages = [Message(role="system", content=system_prompt)]
    messages.extend(
        Message(role=m["role"], content=m["content"]) for m in session.history[-6:]
    )

    # tool_choice is sent to the LLM but NOT reliably honored by every
    # backend -- confirmed live: Ollama (qwen2.5:7b) silently ignores
    # tool_choice="required" and free-styles plain text instead of calling
    # the tool, even with only one tool registered. Rather than trust it,
    # deterministically complete the booking ourselves the moment we can
    # extract everything needed from the caller's own words -- the same
    # principle already used for escalation's template speech, now applied
    # to the single highest-stakes tool call in the whole conversation.
    prev_agent_text = ""
    if len(session.history) >= 2 and session.history[-2].get("role") == "assistant":
        prev_agent_text = session.history[-2].get("content", "")

    reply_text: str | None = None
    if not session.booking_offer and (
        any(kw in text.lower() for kw in BOOKING_INTENT_KEYWORDS)
        or booking_confirmed_by_context(prev_agent_text, text)
    ):
        # Same principle, one step earlier: trusting the LLM to call
        # offer_booking_slots itself is what let it ad-lib "Thursday at
        # 10 AM" as its own suggestion and run an entire booking through
        # to a fabricated reference number without ever touching a real
        # slot -- awaiting_booking_choice never became true, so the
        # confirm-step bypass below never even got a chance to engage.
        slots = available_slots(3)
        session.booking_offer = slots
        session.awaiting_booking_choice = True
        reply_text = format_slots_for_speech(slots, session.language)
        log.warning("Deterministically offered slots (bypassed LLM) on: %r", text)
    elif session.awaiting_booking_choice and looks_like_booking_response(text):
        phone, email = extract_contact_info(text)
        slot = extract_slot_pick(text, session.booking_offer)
        lead = get_lead(call["id"])
        # If the caller just names a slot ("Tuesday works") without contact
        # details in that same breath, don't force a whole extra round-trip
        # to re-ask for something already known -- reuse the phone lead
        # capture already picked up earlier in the call, or (browser test
        # calls only) the logged-in tester's own account email, exactly
        # like a real rep wouldn't re-ask for a number the caller already
        # gave. Still asks fresh if genuinely nothing is known yet.
        phone = phone or session.caller_phone or (lead.contact_phone if lead else None)
        email = email or session.caller_email or None
        if slot and (phone or email):
            new_booking = confirm_booking(
                call_id=call["id"], slot_id=slot["id"], slot_label=slot["label"],
                purpose="consultation",
                contact_name=session.caller_name if session.caller_name != "Guest" else "the caller",
                contact_phone=phone, contact_email=email,
                lead_id=lead.id if lead else None,
            )
            session.awaiting_booking_choice = False
            session.real_booking_confirmed = True
            reply_text = format_confirmation_for_speech(new_booking, session.language)
            log.warning("Deterministically confirmed booking (bypassed LLM) on: %r", text)

    tool_choice = None
    if reply_text is None:
        if not session.booking_offer and any(kw in text.lower() for kw in BOOKING_INTENT_KEYWORDS):
            tool_choice = "required"
            log.warning("FORCING tool_choice=required (offer step) on: %r", text)
        elif session.awaiting_booking_choice and looks_like_booking_response(text):
            # Forcing generic "required" here is ambiguous between the two
            # registered tools -- name the specific one so a forced call
            # can't itself go wrong by re-offering slots instead of
            # confirming. Best-effort backstop for backends that DO honor
            # tool_choice, since the deterministic path above only fires
            # when extraction succeeds.
            tool_choice = {"type": "function", "function": {"name": "confirm_booking"}}
            log.warning("FORCING confirm_booking tool_choice on: %r", text)

        # The local-GPU model produces broken/hallucinated Urdu (confirmed
        # live) -- route turns the caller spoke in Urdu to a larger cloud
        # model instead. English stays on the free/fast local GPU.
        # Per-turn detection alone is fragile against garbled STT (see
        # voice_agent/agent.py for the same fix) -- an Urdu-first persona
        # (opening_line in Urdu) always uses the Urdu-capable LLM, not just
        # when this specific turn's text happens to detect as Urdu.
        is_urdu_persona = detect_language(persona.opening_line or "").primary == "ur"
        if is_urdu_persona or detect_language(text).primary == "ur":
            urdu_client = create_urdu_fallback_client()
            if urdu_client:
                llm_client = urdu_client

        response = await llm_client.chat(messages, max_tokens=350, tools=_BOOKING_TOOLS_TYPED,
                                          tool_choice=tool_choice)

        if response.tool_calls:
            reply_text = await _handle_booking_tools(response.tool_calls, session, call["id"]) or response.content
        else:
            reply_text = response.content

    if reply_text:
        reply_text = await ensure_urdu_script(reply_text)

    if reply_text and not session.real_booking_confirmed and sounds_like_unverified_confirmation(reply_text):
        log.warning("BLOCKED fake confirmation claim (no real booking exists): %r", reply_text)
        reply_text = ("[[emotion:warm]] Let me pull up our real availability for you one moment -- "
                       "what day and time works best?")
        session.awaiting_booking_choice = False
        session.booking_offer = []

    reply_text = reply_text or "[[emotion:warm]] Sorry, could you say that one more time?"

    spoken, emotion = _strip_emotion_tag(reply_text, persona.default_emotion)
    if not spoken:
        spoken = "Sorry, could you say that one more time?"

    session.add_to_history("assistant", spoken)
    session.last_spoken = spoken

    # --- TTS (streamed, chunk-ahead) ---
    session.transition("speaking")
    voice = voice_from_persona(persona, telephony=telephony)
    chunks = split_for_speech(spoken)

    call["transcript"].append({"who": "agent", "name": persona.name, "text": spoken})
    call["agent"] = persona_payload(persona)
    await bus.update(call)

    for i, chunk in enumerate(chunks):
        result = await tts_engine.synthesize(chunk, voice, emotion)
        await emit_chunk(chunk, result.audio, result.mime, i)

    session.transition("listening")


async def _handle_booking_tools(tool_calls, session: CallSession, call_id: str) -> str:
    """Execute booking tool calls and return deterministic spoken text.

    The reply comes from the template formatters, not the LLM's own prose,
    so a slot time or booking reference is read back exactly -- never
    paraphrased or hallucinated.
    """
    reply = ""
    for tc in tool_calls:
        if tc.name == "offer_booking_slots":
            n = int(tc.arguments.get("n") or 3)
            slots = available_slots(n)
            session.booking_offer = slots
            session.awaiting_booking_choice = True
            reply = format_slots_for_speech(slots, session.language)

        elif tc.name == "confirm_booking":
            slot_id = str(tc.arguments.get("slot_id", ""))
            if is_placeholder_contact(
                str(tc.arguments.get("contact_name") or ""),
                tc.arguments.get("contact_phone"),
                tc.arguments.get("contact_email"),
            ):
                reply = "Sorry, I didn't quite catch your phone number and email correctly -- could you repeat them?"
                continue
            slot = _resolve_slot(session.booking_offer, slot_id)
            if not slot:
                reply = "Sorry, that slot isn't available anymore. Would you like to pick another option?"
                continue

            contact_name = str(tc.arguments.get("contact_name") or "").strip()
            if not contact_name or "[" in contact_name or "]" in contact_name:
                contact_name = session.caller_name if session.caller_name != "Guest" else "the caller"

            lead = get_lead(call_id)
            new_booking = confirm_booking(
                call_id=call_id,
                slot_id=slot["id"],
                slot_label=slot["label"],
                purpose=str(tc.arguments.get("purpose") or "consultation"),
                contact_name=contact_name,
                contact_phone=tc.arguments.get("contact_phone") or None,
                contact_email=tc.arguments.get("contact_email") or None,
                lead_id=lead.id if lead else None,
            )
            session.awaiting_booking_choice = False
            session.real_booking_confirmed = True
            reply = format_confirmation_for_speech(new_booking, session.language)

    return reply
