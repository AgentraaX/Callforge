"""Appointment booking -- offers concrete meeting slots and confirms via tool calling.

Slots are always real future dates (never weekends/Sundays).
Booking references are unique and spoken clearly to the caller.
"""
from __future__ import annotations
import logging
import random
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

log = logging.getLogger("callforge.sales.booking")

# Shared between the browser-JSON/Telnyx turn engine (conversation/turn.py)
# and the LiveKit voice agent (voice_agent/agent.py): wording alone
# ("call offer_booking_slots before naming a time") isn't reliably obeyed
# by the smaller/faster models this app supports -- observed live on both
# paths. Forcing a real tool call the moment the caller signals booking
# intent (while no slots have been offered yet) makes it deterministic
# instead of hoping the instruction gets followed.
#
# Multi-word commitment phrases, not bare single words -- confirmed live:
# a caller describing their OWN problem ("our team has to book calls and
# answer leads") incidentally contains "book", false-triggering an
# immediate slot-offer before the agent had even pitched anything. A
# phrase like "book me" or "book a demo" essentially never appears by
# accident.
BOOKING_INTENT_KEYWORDS = (
    "book me", "book a demo", "book a call", "book a meeting", "book it",
    "booking a demo", "booking a call", "booking that demo",
    "let's book", "let's schedule", "schedule a demo", "schedule a call",
    "schedule me", "schedule it", "scheduling a demo", "scheduling that",
    "set up a call", "set up a demo", "sign me up",
    "when are you free", "what times are you free",
)

_AFFIRMATIVE_WORDS = (
    "yes", "yeah", "yep", "sure", "sounds good", "that works",
    "works for me", "okay", "ok", "let's do it", "go ahead", "please",
)


def booking_confirmed_by_context(prev_agent_text: str, caller_text: str) -> bool:
    """Catches the far more common real-world pattern the caller-only
    keyword check above misses: the AGENT proposes booking ("Would you
    like to book a demo?"), and the caller just says "yes" / "sure" --
    never saying "book" themselves at all. Requires BOTH the agent having
    just proposed booking AND the caller affirming it, so a bare "yes" to
    an unrelated question doesn't false-trigger."""
    if not prev_agent_text:
        return False
    proposed = any(kw in prev_agent_text.lower() for kw in BOOKING_INTENT_KEYWORDS)
    return proposed and any(w in caller_text.lower() for w in _AFFIRMATIVE_WORDS)

# Same problem, one step later: once slots have been offered, the caller's
# NEXT substantive reply is almost always either picking one or handing
# over contact details -- exactly the turn that should call confirm_booking,
# and exactly where models were observed narrating a fake "Confirming your
# booking..." instead of actually calling it. A phone number, an email, or
# a slot-selection word are all strong signals this is that turn.
_CONFIRMATION_SIGNAL_WORDS = (
    "yes", "yeah", "sure", "sounds good", "that works", "works for me",
    "first", "second", "third", "option", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
)

# STT transcribes a spoken phone number/email as WORDS ("oh three one one",
# "at gmail dot com"), not literal digits/"@" -- verified live: a caller
# spelling out contact details produced text with zero raw digits and zero
# "@" characters, so a naive regex over the raw text finds nothing.
# Normalize word-forms to their symbols first, everywhere contact info is
# detected or extracted from.
_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}


def _normalize_spoken_contact(text: str) -> str:
    t = text.lower()
    # Word-boundary regex, not space-padded str.replace -- adjacent repeated
    # words ("six six seven seven") share a single space between them, which
    # a naive " word " replace consumes on the first match, leaving the
    # second occurrence with no leading space left to match against.
    for word, digit in _DIGIT_WORDS.items():
        t = re.sub(rf"\b{word}\b", digit, t)
    t = re.sub(r"\s+at\s+", "@", t)
    t = re.sub(r"\s+dot\s+", ".", t)
    if "@" not in t:
        # Groq Whisper sometimes renders spoken "at" as a literal hyphen
        # instead of the word "at" or "@" -- observed live:
        # "my email is X at gmail dot com" transcribed as "X-gmail.com",
        # no "@" or "at" anywhere to normalize the usual way. Only the
        # hyphen directly before a domain-shaped segment is a plausible
        # match for this, so it's safe to target narrowly.
        t = re.sub(r"-(?=[a-z0-9]+\.[a-z]{2,})", "@", t, count=1)
    t = t.replace(",", " ")  # spoken digit groups are comma-separated ("oh three one one, four...")
    return t


def looks_like_booking_response(text: str) -> bool:
    t = _normalize_spoken_contact(text)
    if "@" in t or re.search(r"\d[\d\-\s]{6,}\d", t):  # email or phone-number-shaped
        return True
    return any(w in t for w in _CONFIRMATION_SIGNAL_WORDS)


_PHONE_RE = re.compile(r"(\+?\d[\d\-\s]{6,}\d)")
_EMAIL_RE = re.compile(r"[\w.\-]+@[\w.\-]+\.\w+")
_ORDINAL_INDEX = {
    "first": 0, "1st": 0, "one": 0,
    "second": 1, "2nd": 1, "two": 1,
    "third": 2, "3rd": 2, "three": 2,
}


def extract_contact_info(text: str) -> tuple[str | None, str | None]:
    """Best-effort phone/email extraction from a caller utterance -- STT
    transcribes a spoken phone/email as words ("oh three one one", "at
    gmail dot com"), verified live, so normalize those to digits/symbols
    before matching."""
    t = _normalize_spoken_contact(text)
    phone_m = _PHONE_RE.search(t)
    email_m = _EMAIL_RE.search(t)
    phone = re.sub(r"\s+", "", phone_m.group(1)) if phone_m else None
    return (phone, email_m.group(0) if email_m else None)


def extract_slot_pick(text: str, booking_offer: list[dict]) -> dict | None:
    """Best-effort slot selection from a caller utterance -- ordinal word
    ("second"), "option N", or a weekday/date fragment matching one of the
    offered labels. Falls back to the only slot if just one was offered."""
    t = text.lower()
    for word, idx in _ORDINAL_INDEX.items():
        if word in t and idx < len(booking_offer):
            return booking_offer[idx]
    m = re.search(r"option\s*(\d+)", t)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(booking_offer):
            return booking_offer[idx]
    for slot in booking_offer:
        if any(w in t for w in slot["label"].lower().split() if len(w) > 3):
            return slot
    if len(booking_offer) == 1:
        return booking_offer[0]
    return None


# Last-resort safety net: the deterministic offer/confirm bypasses above
# only fire on specific trigger phrases -- every OTHER turn is still free
# text from the LLM, which (confirmed live, repeatedly, on the smaller
# open model this app can afford to run rate-limit-free) will confidently
# narrate an entire fake booking -- wrong dates, a fabricated phone number
# ("1-800-555-1234", never spoken by the caller) -- when the conversation
# calls for a confirmation and it has no real one to give. Catching the
# claim itself, not just the moment it should have called a tool, is the
# only thing that reliably stops a lie from being spoken aloud.
_FAKE_CONFIRMATION_PHRASES = (
    "confirmed", "i've booked", "i have booked", "booking is set",
    "is booked", "booked the demo", "booking for you now",
)


def sounds_like_unverified_confirmation(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in _FAKE_CONFIRMATION_PHRASES)


# Forcing tool_choice does sometimes make the model actually emit a
# confirm_booking call (unlike the earlier finding that Ollama ignores it
# outright) -- but confirmed live: it can fill the arguments with a
# textbook-example placeholder instead of the caller's real words --
# "John Doe" / "(555) 123-4567" / "johndoe@example.com", the exact values
# a developer would type into a function-call example. A forced call
# succeeding is not proof its arguments are real; reject anything that
# looks like a stock placeholder before it can create a fake booking.
_PLACEHOLDER_CONTACT_PATTERNS = (
    "john doe", "jane doe", "example.com", "example.org", "example.net",
    "555-123", "555)123", "555-0100", "5551234", "123-456-7890", "1234567890",
)


def is_placeholder_contact(name: str, phone: str | None, email: str | None) -> bool:
    combined = f"{name} {phone or ''} {email or ''}".lower()
    return any(p in combined for p in _PLACEHOLDER_CONTACT_PATTERNS)


def resolve_slot(booking_offer: list[dict], slot_id: str) -> dict | None:
    """offer_booking_slots's own tool result presents options as "Option 1/
    2/3" for natural speech (the real machine id only lives further away,
    in the system instructions) -- observed live: models calling
    confirm_booking with slot_id="Option 2" instead of the real id. Resolve
    either form rather than relying on the model always using the exact id
    string."""
    for s in booking_offer:
        if s["id"] == slot_id:
            return s
    match = re.search(r"\d+", slot_id or "")
    if match:
        idx = int(match.group()) - 1
        if 0 <= idx < len(booking_offer):
            return booking_offer[idx]
    return None

# Pakistan business hours (PKT), Monday-Saturday
SLOT_HOURS = (10, 11, 14, 15, 16)
_WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                  "Saturday", "Sunday")


def _fmt_hour(hour: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    h12 = hour if 1 <= hour <= 12 else (hour - 12 or 12)
    return f"{h12}:00 {suffix}"


def _next_business_days(n: int, start: datetime | None = None) -> list[datetime]:
    """Next n dates that aren't Sunday."""
    days: list[datetime] = []
    d = (start or datetime.now()) + timedelta(days=1)
    while len(days) < n:
        if d.weekday() != 6:  # Sunday
            days.append(d)
        d += timedelta(days=1)
    return days


def available_slots(n: int = 3) -> list[dict]:
    """Get n available booking slots -- always real future dates."""
    slots = []
    for day in _next_business_days(2):
        for hour in SLOT_HOURS:
            slots.append({
                "id": f"{day:%Y-%m-%d}-{hour:02d}",
                "label": (f"{_WEEKDAY_NAMES[day.weekday()]} {day:%d %b}, "
                          f"{_fmt_hour(hour)}"),
                "date": day.strftime("%Y-%m-%d"),
                "hour": hour,
            })
    # Shuffle by hour-of-day so repeated calls don't always show same 3
    random.Random(int(time.time()) // 3600).shuffle(slots)
    return slots[:n]


@dataclass
class Booking:
    booking_id: str = ""
    call_id: str = ""
    lead_id: str | None = None
    slot_id: str = ""
    slot_label: str = ""
    purpose: str = "consultation"   # "consultation" | "site_visit" | "demo"
    contact_name: str = ""
    contact_phone: str | None = None
    contact_email: str | None = None
    status: str = "confirmed"       # "confirmed" | "cancelled" | "completed"
    created_at: float = field(default_factory=time.time)


# In-memory store
BOOKINGS: dict[str, Booking] = {}
_MAX_BOOKINGS = 200
_seq = 4000


def confirm(call_id: str, slot_id: str, slot_label: str,
            purpose: str = "consultation", contact_name: str = "",
            contact_phone: str | None = None, contact_email: str | None = None,
            lead_id: str | None = None) -> Booking:
    """Confirm a booking and return the booking record."""
    global _seq
    _seq += 1
    booking = Booking(
        booking_id=f"BK-{_seq}",
        call_id=call_id,
        lead_id=lead_id,
        slot_id=slot_id,
        slot_label=slot_label,
        purpose=purpose,
        contact_name=contact_name,
        contact_phone=contact_phone,
        contact_email=contact_email,
    )
    BOOKINGS[booking.booking_id] = booking
    while len(BOOKINGS) > _MAX_BOOKINGS:
        BOOKINGS.pop(next(iter(BOOKINGS)))
    log.info("Booking confirmed: %s for %s (%s)", booking.booking_id,
             contact_name, slot_label)
    return booking


def cancel(booking_id: str) -> Booking | None:
    """Cancel a booking."""
    booking = BOOKINGS.get(booking_id)
    if booking:
        booking.status = "cancelled"
        log.info("Booking cancelled: %s", booking_id)
    return booking


def get(booking_id: str) -> Booking | None:
    return BOOKINGS.get(booking_id)


def all_bookings() -> list[dict]:
    """All bookings sorted by most recent."""
    return [asdict(b) for b in
            sorted(BOOKINGS.values(), key=lambda b: -b.created_at)]


# --- LLM Tool Definitions ---

BOOKING_TOOLS = [
    {
        "name": "offer_booking_slots",
        "description": "Get available meeting slots for the next 3 business days",
        "parameters": {
            "type": "object",
            "properties": {
                # Nullable: some providers (e.g. Groq) run strict JSON-schema
                # validation on tool calls and reject the model emitting a
                # literal `null` for an omitted optional field if the schema
                # only allows "integer" -- allowing null keeps this portable.
                "n": {"type": ["integer", "null"], "description": "Number of slots to offer", "default": 3}
            },
        },
    },
    {
        "name": "confirm_booking",
        "description": (
            "Confirm a booking after the caller picks a slot. Ask for the "
            "caller's best phone number and email BEFORE calling this -- a "
            "real rep always locks down contact details when booking a "
            "meeting, so the confirmation actually reaches them."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "slot_id": {"type": "string", "description": "The selected slot ID"},
                # Nullable for the same reason as "n" above -- it's optional
                # (not in "required") but strict validators still need null
                # declared as an allowed type, not just an absent key.
                "purpose": {"type": ["string", "null"], "description": "Meeting purpose"},
                "contact_name": {"type": "string", "description": "Caller's name"},
                "contact_phone": {"type": ["string", "null"], "description": "Caller's best phone number, if given"},
                "contact_email": {"type": ["string", "null"], "description": "Caller's email, if given"},
            },
            "required": ["slot_id", "contact_name"],
        },
    },
]


def format_slots_for_speech(slots: list[dict], language: str = "en") -> str:
    """Format slots as a natural spoken list, mirroring the caller's language.

    Slot labels/dates stay exactly as generated -- only the scaffolding
    around them is translated, so the caller and dashboard never disagree
    on what was actually offered.
    """
    if not slots:
        return ("Maazrat, abhi koi slot available nahi hai."
                if language == "ur" else
                "I'm sorry, there are no available slots right now.")

    if language == "ur":
        lines = ["Yeh slots available hain:"]
        for i, slot in enumerate(slots, 1):
            lines.append(f"Option {i}: {slot['label']}")
        lines.append("Kaunsa slot aapke liye theek rahega?")
        return " ".join(lines)

    lines = ["I have these slots available:"]
    for i, slot in enumerate(slots, 1):
        lines.append(f"Option {i}: {slot['label']}")
    lines.append("Which one works best for you?")
    return " ".join(lines)


def format_confirmation_for_speech(booking: Booking, language: str = "en") -> str:
    """Format booking confirmation as natural speech, mirroring the caller's
    language. The reference number is always read back verbatim -- never
    translated or approximated -- since it's the one fact the caller needs
    to get exactly right."""
    confirmation_note = ""
    if booking.contact_email:
        confirmation_note = " I'll send the confirmation to your email."
    elif booking.contact_phone:
        confirmation_note = " I'll text a confirmation to that number."

    if language == "ur":
        return (
            f"Perfect! Maine aapko {booking.slot_label} ke liye book kar "
            f"diya hai. Aapka reference number hai {booking.booking_id}. "
            f"Aur kuch madad chahiye?"
        )
    return (
        f"Perfect! I've booked you for {booking.slot_label}. "
        f"Your reference number is {booking.booking_id}.{confirmation_note} "
        f"Is there anything else I can help you with?"
    )
