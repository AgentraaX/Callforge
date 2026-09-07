"""Structured sales lead capture -- extracts and scores leads in real-time.

Runs as a fire-and-forget background task per caller turn so extraction
never adds to the caller's perceived turn latency.
"""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field

log = logging.getLogger("callforge.sales.leads")


@dataclass
class Lead:
    id: str = ""
    call_id: str = ""
    company: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    pain_point: str | None = None     # what problem/need they mentioned
    budget_signal: str | None = None  # any budget/spend indication
    next_step: str | None = None      # "callback" | "demo" | "send_info" | "not_interested" | None
    urgency: str = "exploring"        # "urgent" | "normal" | "exploring"
    score: str = "cold"               # "hot" | "warm" | "cold"
    notes: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source_transcript: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]


# In-memory store (production would use PostgreSQL)
LEADS: dict[str, Lead] = {}  # keyed by call_id
_MAX_LEADS = 200


def score_lead(lead: Lead) -> str:
    """Score a lead based on filled fields, urgency, and stated next step."""
    if lead.next_step == "not_interested":
        return "cold"
    filled = sum(1 for f in [lead.company, lead.contact_name,
                              lead.pain_point, lead.budget_signal] if f)
    if lead.next_step in ("demo", "callback") and filled >= 1:
        return "hot"
    if lead.urgency == "urgent" and filled >= 2:
        return "hot"
    if filled >= 3 or (lead.urgency in ("urgent", "normal") and filled >= 2):
        return "warm"
    return "cold"


async def extract(call_id: str, text: str, caller_name: str = "") -> Lead:
    """Extract lead fields from a single utterance using LLM.

    Merges with existing lead data for this call (accumulates over turns).
    """
    from ..llm.qwen import classify_json

    lead = LEADS.get(call_id) or Lead(call_id=call_id, contact_name=caller_name or None)

    result = await classify_json(
        "Extract any sales-lead fields from this ONE caller utterance on a "
        "cold sales call. Only fill a field if actually stated -- never guess.\n"
        'Reply as JSON: {"company": "<company/business name or null>", '
        '"pain_point": "<problem or need they mentioned, short phrase, or null>", '
        '"budget_signal": "<any budget/spend indication or null>", '
        '"next_step": "<one of callback|demo|send_info|not_interested, or null>", '
        '"urgency": "<one of urgent|normal|exploring, or null>"}\n'
        f'Utterance: "{text}"'
    )

    if result:
        for field_name, attr_name in [("company", "company"), ("pain_point", "pain_point"),
                                       ("budget_signal", "budget_signal"),
                                       ("next_step", "next_step"), ("urgency", "urgency")]:
            value = result.get(field_name)
            if value and str(value).strip().lower() not in ("null", "none", ""):
                setattr(lead, attr_name, str(value).strip()[:80])

    if caller_name and not lead.contact_name:
        lead.contact_name = caller_name

    lead.score = score_lead(lead)
    lead.updated_at = time.time()
    lead.source_transcript.append(text[:200])

    LEADS[call_id] = lead
    while len(LEADS) > _MAX_LEADS:
        LEADS.pop(next(iter(LEADS)))

    return lead


def get(call_id: str) -> Lead | None:
    return LEADS.get(call_id)


def all_leads() -> list[dict]:
    """All leads sorted by most recently updated."""
    return [asdict(lead) for lead in
            sorted(LEADS.values(), key=lambda l: -l.updated_at)]


def stats() -> dict:
    """Lead score summary."""
    hot = sum(1 for l in LEADS.values() if l.score == "hot")
    warm = sum(1 for l in LEADS.values() if l.score == "warm")
    cold = sum(1 for l in LEADS.values() if l.score == "cold")
    return {"hot": hot, "warm": warm, "cold": cold, "total": len(LEADS)}


def add_note(call_id: str, note: str) -> Lead | None:
    """Add a manual note to a lead."""
    lead = LEADS.get(call_id)
    if lead:
        existing = lead.notes or ""
        lead.notes = (existing + "\n" + note).strip()
        lead.updated_at = time.time()
    return lead


# --- Background extraction (fire-and-forget) ---

EXTRACT_STATES = {"greeting", "listening", "thinking", "speaking"}


def maybe_extract(session, call: dict, text: str) -> None:
    """Fire-and-forget extraction. Skips if no LLM, wrong state, or the
    utterance is too short to plausibly carry a lead field -- halves LLM
    token usage per turn (a real constraint on Groq's free-tier rate
    limit) without losing signal, since one- or two-word fillers ("yeah",
    "sure", "okay fine") never contain extractable company/pain-point/
    budget/contact info anyway."""
    from ..llm import available
    if not available() or session.state not in EXTRACT_STATES:
        return
    if len(text.split()) < 4:
        return
    asyncio.create_task(_extract_bg(session, call, text))


async def _extract_bg(session, call: dict, text: str) -> None:
    try:
        lead = await extract(call["id"], text, session.caller_name)
    except Exception as exc:
        log.warning("Lead extraction failed: %s", exc)
        return
    call["lead"] = asdict(lead)
    from ..realtime.bus import bus
    await bus.update(call)
