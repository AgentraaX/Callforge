"""Escalation & handoff -- detects when human intervention is needed.

Triggers:
1. Caller explicitly asks for a human/supervisor
2. Reference number not found after 2 attempts
3. Charge dispute or refund request
4. Policy exception request (demurrage waiver)
5. Agent confidence below threshold for 3 consecutive turns
6. Caller frustration detected (repeated questions)
"""
from __future__ import annotations
import logging
import random
import time
from dataclasses import asdict, dataclass, field

log = logging.getLogger("callforge.sales.escalation")


@dataclass
class EscalationCase:
    case_id: str = ""
    call_id: str = ""
    reason: str = ""
    summary: str = ""
    caller_name: str = ""
    caller_intent: str = ""
    transcript_excerpt: list[str] = field(default_factory=list)
    lead_data: dict | None = None
    priority: str = "normal"    # "high" | "normal"
    created_at: float = field(default_factory=time.time)
    status: str = "pending"     # "pending" | "assigned" | "resolved"

    def __post_init__(self):
        if not self.case_id:
            self.case_id = f"CS-{random.randint(2000, 9899)}"


# In-memory store
CASES: dict[str, EscalationCase] = {}
_MAX_CASES = 100


# --- Trigger Detection ---

_ESCALATION_KEYWORDS = [
    # Phrase-based, not bare nouns -- a caller mentioning THEIR OWN manager
    # ("I'd need to check with my manager") or joking ("are you even a
    # real person?") must never trigger this. Only match when the caller
    # is actually asking to be connected to someone on OUR side.
    "speak to a human", "talk to a human", "speak with a human",
    "speak to a manager", "talk to a manager", "speak with a manager",
    "speak to your manager", "talk to your manager", "get me a manager",
    "speak to a supervisor", "talk to a supervisor", "speak with a supervisor",
    "speak to someone senior", "talk to someone senior",
    "speak to a real person", "talk to a real person", "connect me to a real person",
    "speak to someone else", "talk to someone else",
    "complaint", "not satisfied",
    "insaan se baat", "senior se baat", "shikayat",
    # Urdu script -- same triggers, so a caller who switches to Urdu script
    # mid-call still escalates correctly instead of silently falling through.
    "انسان سے بات", "منیجر سے بات", "سپروائزر سے بات", "شکایت",
]

_DISPUTE_KEYWORDS = [
    "dispute", "refund", "wrong charge", "overcharged", "incorrect",
    "galat", "ghalat", "wapas", "paisa wapas",
    "غلط", "واپس",
]


def detect_escalation_trigger(text: str, session) -> str | None:
    """Check if the utterance triggers an escalation.

    Returns the trigger reason string, or None if no escalation needed.
    """
    lower = text.lower()

    # Trigger 1: Explicit request for human
    if any(kw in lower for kw in _ESCALATION_KEYWORDS):
        return "caller_requested_human"

    # Trigger 3: Charge/billing dispute
    if any(kw in lower for kw in _DISPUTE_KEYWORDS):
        return "charge_dispute"

    # Trigger 5: Low confidence streak
    if hasattr(session, 'low_confidence_count') and session.low_confidence_count >= 3:
        return "low_confidence_streak"

    return None


def should_escalate_failed_lookup(session) -> bool:
    """Trigger 2: Reference not found after 2 attempts."""
    failed_lookups = sum(1 for l in session.lookup_log 
                         if l.get("status") == "not_found")
    return failed_lookups >= 2


# --- Escalation Flow ---

async def create_case(call_id: str, reason: str, *, caller_name: str = "",
                      caller_intent: str = "unknown",
                      transcript: list[dict] | None = None,
                      lead_data: dict | None = None,
                      history: list[dict] | None = None) -> EscalationCase:
    """Create an escalation case with full context.

    Takes primitives rather than a ``CallSession``/``call`` dict pair so it
    can be called both from the in-process turn engine
    (conversation/turn.py) and from the LiveKit agent worker's internal
    HTTP endpoint (a separate OS process with no access to those objects)
    -- the caller is responsible for marking its own session escalated.
    """
    transcript = transcript or []
    excerpt = [f"{t['who']}: {t['text']}" for t in transcript[-5:]]

    priority = "high" if reason in ("charge_dispute", "caller_requested_human") else "normal"

    summary = await _generate_summary(history or [], reason)

    case = EscalationCase(
        call_id=call_id,
        reason=reason,
        summary=summary,
        caller_name=caller_name,
        caller_intent=caller_intent,
        transcript_excerpt=excerpt,
        lead_data=lead_data,
        priority=priority,
    )

    CASES[case.case_id] = case
    while len(CASES) > _MAX_CASES:
        CASES.pop(next(iter(CASES)))

    log.info("Escalation case %s created: %s (priority: %s)",
             case.case_id, reason, priority)
    return case


async def _generate_summary(history: list[dict], reason: str) -> str:
    """Generate a concise case summary using LLM or fallback."""
    from ..llm import available, create_client, Message

    if not available() or not history:
        # Fallback: template summary
        return f"Caller needs human assistance. Reason: {reason}."

    client = create_client()
    convo = "\n".join(m["content"] for m in history[-8:])
    
    response = await client.chat([
        Message(role="user", content=(
            "Summarize this customer call in ONE short sentence for a supervisor. "
            "Be factual, mention the issue and what was discussed. "
            f"Escalation reason: {reason}\n\nConversation:\n{convo}"
        ))
    ], max_tokens=60)
    
    return response.content or f"Call escalated: {reason}"


def format_escalation_speech(case: EscalationCase, language: str = "en") -> str:
    """Format escalation message for the caller, mirroring their language.

    The case number itself is never translated or reworded -- it's read
    back digit-for-digit so the caller (and the specialist picking up the
    case) both anchor on the exact same reference.
    """
    if language == "ur":
        return (
            f"Main samajh sakta hoon ke ismein zaati tawajjo chahiye. Main "
            f"aapko ek senior specialist se connect kar raha hoon jo seedha "
            f"madad kar sakega. Aapka case number hai {case.case_id}, taake "
            f"unhein humari poori conversation ka context mil jaye. Jald hi "
            f"koi aapse rabta karega."
        )
    return (
        f"I understand this needs personal attention. Let me connect you with "
        f"a senior specialist who can help directly. I'm creating case number "
        f"{case.case_id} so they'll have all the context from our conversation. "
        f"Someone will be with you shortly."
    )


# --- API helpers ---

def get_case(case_id: str) -> EscalationCase | None:
    return CASES.get(case_id)


def all_cases() -> list[dict]:
    """All cases sorted by priority then recency."""
    priority_order = {"high": 0, "normal": 1}
    return [asdict(c) for c in sorted(
        CASES.values(),
        key=lambda c: (priority_order.get(c.priority, 1), -c.created_at),
    )]


def pending_cases() -> list[dict]:
    """Only cases needing attention."""
    return [asdict(c) for c in CASES.values() if c.status == "pending"]
