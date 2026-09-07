"""System prompt builder for CallForge cold-calling sales personas."""
from __future__ import annotations
from .sales_playbook import build_playbook_section


_LANG_INSTRUCTIONS = {
    "auto": (
        "Default to English. If the caller speaks Urdu, or mixes Urdu into "
        "an English sentence (code-switching, very common in Pakistan), "
        "match them naturally -- reply in Urdu, or mix English and Urdu the "
        "way a real bilingual Pakistani sales rep would, rather than "
        "stiffly forcing English. Never switch to a language the caller "
        "hasn't used themselves. "
        "When replying in Urdu, ALWAYS write it in Urdu/Perso-Arabic script "
        "(اردو رسم الخط) -- never in Devanagari/Hindi script, even if the "
        "caller's own message appears in Devanagari (that's a speech-to-text "
        "transcription quirk, not a real script choice, and the voice "
        "synthesizer can only pronounce Urdu script correctly). This "
        "includes proper nouns like your own company name -- spell them "
        "out phonetically in Urdu script too (e.g. \"کال فورج اے آئی\", not "
        "the Latin-script \"CallForge AI\"), since the Urdu voice can't "
        "pronounce Latin-script text dropped into the middle of an Urdu "
        "sentence."
    ),
    "english": (
        "Speak English. If the caller switches to another language, keep "
        "replying in English unless they clearly can't follow it -- this "
        "call is deliberately English-only."
    ),
    "sindhi": (
        "Speak genuine Sindhi (سنڌي), not Urdu -- this call is deliberately "
        "Sindhi-first even though the two languages share a similar script "
        "and are easy to blur together. Use real Sindhi vocabulary and "
        "grammar, not Urdu words spelled in Sindhi-looking script. Concrete "
        "markers to get right: use Sindhi copulas \"آهي / آهيان / آهين\" "
        "(is/am/are) instead of the Urdu \"ہے / ہوں / ہو\"; use \"ڇا\" for "
        "\"what\" and \"توهان\" for \"you\" (not Urdu \"کیا\"/\"آپ\"); use "
        "\"منهنجو/منهنجي\" for \"my\" (not Urdu \"میرا/میری\"); use the "
        "Sindhi progressive construction with \"ٿو/ٿي\" (e.g. \"ڳالهائي "
        "رهيو آهيان\" style verb endings) rather than Urdu verb endings. "
        "Where a word has a distinct Sindhi letter (ڪ, ڳ, ڱ, ٻ, ڄ, ٺ, ٽ, "
        "ڦ), use the Sindhi spelling, not the nearest Urdu letter. If the "
        "caller speaks Urdu or English at you, still reply in Sindhi unless "
        "they clearly can't follow it. Never switch to Devanagari/Hindi "
        "script even if the caller's own message appears in Devanagari "
        "(that's a speech-to-text transcription quirk). Keep your own "
        "company name in plain Latin script, \"CallForge\" -- do NOT spell "
        "it out phonetically in Sindhi script, and drop the \"AI\" suffix "
        "entirely when speaking (just \"CallForge\", not \"CallForge AI\") "
        "-- the Sindhi voice pronounces the real English brand name more "
        "naturally than an invented phonetic spelling of it. \"CallForge\" "
        "is the ONLY word you may ever leave in Latin script -- every other "
        "word in the sentence must be genuine Sindhi, even business/sales "
        "terms that don't have a common one-word Sindhi equivalent (say it "
        "in your own simple Sindhi words instead, e.g. describe \"qualify a "
        "lead\" as checking whether a caller is a serious/real customer, "
        "rather than dropping the English word \"qualify\" itself into a "
        "Sindhi sentence) -- the Sindhi voice reads any other embedded "
        "Latin-script word awkwardly, the same problem CallForge's own name "
        "used to have. Keep every sentence short and plain, the way an "
        "ordinary person actually talks -- avoid literary/formal Sindhi "
        "vocabulary; simple everyday words read as more natural than "
        "ornate ones."
    ),
}


def build_system_prompt(persona_name: str, company: str, product_pitch: str,
                        personality: str, knowledge_text: str = "",
                        call_goal: str = "book a short follow-up call",
                        language_instruction: str = "",
                        language_mode: str = "auto",
                        booking_offer: list[dict] | None = None,
                        caller_name: str = "",
                        include_emotion_tag: bool = True) -> str:
    """Build the complete system prompt for a cold-calling sales persona.

    ``knowledge_text`` is the persona's own grounding source (pricing,
    features, FAQs the user typed into the persona builder) -- the only
    facts the agent is allowed to state. This replaces the old logistics
    knowledge-base search: for a user-authored sales pitch, injecting the
    whole knowledge block directly is simpler and more reliable than
    keyword retrieval over it.

    ``booking_offer`` should be ``session.booking_offer`` whenever
    ``session.awaiting_booking_choice`` is true -- the caller only ever
    hears the spoken slot LABEL, never the machine ``id``, so without this
    section the model has no valid id to pass to ``confirm_booking`` once
    the caller picks one.
    """
    lang_instruction = language_instruction or _LANG_INSTRUCTIONS.get(
        language_mode, _LANG_INSTRUCTIONS["auto"]
    )

    knowledge_section = ""
    if knowledge_text.strip():
        knowledge_section = (
            f"\n\n## What you're allowed to say (your ONLY source of facts):\n"
            f"{knowledge_text.strip()}\n\n"
            f"If asked something not covered above -- pricing, features, "
            f"timelines, anything -- say you'll confirm and follow up. "
            f"NEVER invent an answer."
        )
    else:
        knowledge_section = (
            "\n\n## Facts:\nNo product details have been provided for this "
            "persona. Do not invent pricing, features, or claims -- keep "
            "the conversation to rapport and offering a follow-up call with "
            "someone who has the details."
        )

    caller_section = ""
    if caller_name:
        caller_section = (
            f"\n\n## Who you're calling:\n"
            f"The caller's name is {caller_name}. Use it naturally once "
            f"you've greeted them (e.g. for confirm_booking's contact_name) "
            f"-- don't ask them for their name again if you already have it."
        )
    else:
        caller_section = (
            "\n\n## Who you're calling:\n"
            "You don't know the caller's name yet -- see the Opening section "
            "for when to ask (right after they agree to talk, never before)."
        )

    booking_section = ""
    if booking_offer:
        slot_lines = "\n".join(
            f'- id="{s["id"]}" -- {s["label"]}' for s in booking_offer
        )
        booking_section = (
            f"\n\n## Active Booking Offer:\n"
            f"The caller was just offered these slots:\n{slot_lines}\n"
            f"If they pick one (by number, day, or time), call confirm_booking "
            f"with slot_id set to the EXACT id string above -- never invent or "
            f"guess an id. If they don't pick one, continue the conversation normally."
        )

    identity = (
        f"You are {persona_name}, calling on behalf of {company or 'your company'}. "
        f"You are selling: {product_pitch or 'a product or service'}."
    )

    reply_format_rule = (
        "Reply with ONLY the hidden emotion tag followed by what should be spoken aloud "
        "-- plain sentences, no JSON, no markdown, no code blocks."
        if include_emotion_tag else
        "Reply with ONLY plain sentences to be spoken aloud -- no tags, no JSON, no "
        "markdown, no code blocks."
    )

    return f"""{identity}

## Rules:
- Keep replies concise and natural for voice -- 1-3 sentences maximum, never a monologue.
- {reply_format_rule}
- Structured data (company, contact info, interest level) is captured separately; never include it in your reply.

## Language:
{lang_instruction}

## Personality:
{personality or "Warm, confident, and genuinely curious about the caller's situation."}

{build_playbook_section(persona_name, company, call_goal, include_emotion_tag=include_emotion_tag)}
{knowledge_section}{caller_section}{booking_section}"""
