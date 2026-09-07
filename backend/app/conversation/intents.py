"""Intent detection -- classifies caller utterances into actionable intents.

Uses LLM-based classification when available, falls back to keyword matching.
Includes entity extraction (container numbers, vessel names, etc.).
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

log = logging.getLogger("callforge.conversation.intents")

# Full intent taxonomy
INTENTS = [
    "rate_inquiry",        # Asking about pricing/rates
    "container_tracking",  # Track a specific container
    "vessel_schedule",     # Vessel ETA/berthing info
    "billing_query",       # Invoice/payment questions
    "document_info",       # Required docs for import/export
    "book_meeting",        # Schedule an appointment
    "escalate_human",      # Wants to talk to a real person
    "general_faq",         # General logistics question
    "greeting",            # Hello/salaam
    "end_call",            # Goodbye/thanks
    "other",              # Unclassified
]


@dataclass
class IntentResult:
    intent: str = "other"
    confidence: float = 0.0
    entities: dict[str, str] = field(default_factory=dict)
    language: str = "en"


# --- Entity extraction patterns ---

# Container number: 4 uppercase letters + 7 digits (e.g., CMAU2384719)
_CONTAINER_RE = re.compile(r'\b([A-Z]{4})\s*(\d{7})\b', re.IGNORECASE)

# Invoice number: INV-YYYY-NNNN pattern
_INVOICE_RE = re.compile(r'\b(INV[-/]?\d{4}[-/]?\d{3,5})\b', re.IGNORECASE)

# Vessel name: "vessel <Name>" or common shipping line prefixes
_VESSEL_RE = re.compile(
    r'\b(?:vessel|ship|mv|m\.v\.)\s+([A-Z][A-Za-z\s]{2,25}?)(?:\s|$|,|\.|;)',
    re.IGNORECASE,
)

# Bill of Lading
_BL_RE = re.compile(r'\b(BL|B/L|B\.L\.?)[-\s]?(\w{5,20})\b', re.IGNORECASE)

# IGM number
_IGM_RE = re.compile(r'\bIGM[-\s]?(\d{4,10})\b', re.IGNORECASE)


def extract_entities(text: str) -> dict[str, str]:
    """Extract logistics entities from text."""
    entities: dict[str, str] = {}

    m = _CONTAINER_RE.search(text)
    if m:
        entities["container_no"] = (m.group(1) + m.group(2)).upper()

    m = _INVOICE_RE.search(text)
    if m:
        entities["invoice_no"] = m.group(1).upper()

    m = _VESSEL_RE.search(text)
    if m:
        entities["vessel_name"] = m.group(1).strip()

    m = _BL_RE.search(text)
    if m:
        entities["bl_no"] = (m.group(1) + "-" + m.group(2)).upper()

    m = _IGM_RE.search(text)
    if m:
        entities["igm_no"] = m.group(1)

    return entities


# --- Keyword-based classification (fallback) ---

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "rate_inquiry": [
        "rate", "price", "cost", "charge", "quote", "kitna", "kharcha", "fees", "tariff",
    ],
    "container_tracking": [
        "container", "track", "where", "kahan", "status", "reached", "gate out", "gate-out",
    ],
    "vessel_schedule": [
        "vessel", "ship", "eta", "berth", "sailing", "schedule", "load board",
    ],
    "billing_query": [
        "invoice", "bill", "payment", "refund", "receipt", "amount", "paid",
    ],
    "document_info": [
        "document", "papers", "clearance", "weboc", "gd", "customs", "dastawez",
    ],
    "book_meeting": [
        "book", "meeting", "appointment", "schedule", "visit", "milna",
    ],
    "escalate_human": [
        "human", "supervisor", "manager", "person", "real", "escalate", "complaint", "insaan",
    ],
    "general_faq": [
        "what is", "explain", "how does", "tell me about", "difference", "samjhao",
    ],
    "greeting": [
        "hello", "hi", "assalam", "salam", "good morning", "good afternoon",
    ],
    "end_call": [
        "bye", "goodbye", "thank", "shukriya", "khuda hafiz", "that's all", "done",
    ],
}


def classify_by_keywords(text: str) -> IntentResult:
    """Fast keyword-based intent classification."""
    lower = text.lower()
    entities = extract_entities(text)

    # Entity-based shortcuts (high confidence)
    if entities.get("container_no"):
        return IntentResult("container_tracking", 0.9, entities)
    if entities.get("invoice_no"):
        return IntentResult("billing_query", 0.9, entities)
    if entities.get("vessel_name"):
        return IntentResult("vessel_schedule", 0.9, entities)
    if entities.get("bl_no") or entities.get("igm_no"):
        return IntentResult("container_tracking", 0.85, entities)

    # Keyword scoring
    scores: dict[str, float] = {}
    for intent, keywords in _INTENT_KEYWORDS.items():
        score = sum(1.0 for kw in keywords if kw in lower)
        if score > 0:
            scores[intent] = score

    if not scores:
        return IntentResult("other", 0.3, entities)

    best_intent = max(scores, key=scores.get)
    confidence = min(0.85, scores[best_intent] / 3.0 + 0.4)

    return IntentResult(best_intent, confidence, entities)


async def classify_with_llm(text: str, context: str = "") -> IntentResult:
    """LLM-based intent classification with entity extraction.

    Falls back to keyword classification if LLM is unavailable.
    """
    from ..llm import available
    from ..llm.qwen import classify_json

    if not available():
        return classify_by_keywords(text)

    prompt = (
        f"Classify this customer utterance into exactly ONE intent and extract entities.\n"
        f"Intents: {', '.join(INTENTS)}\n"
        f"Context: {context}\n"
        f'Utterance: "{text}"\n\n'
        f'Reply as JSON: {{"intent": "<intent>", "confidence": <0.0-1.0>, '
        f'"entities": "container_no": null, "vessel_name": null, "invoice_no": null, '
        f'"language": "en"|"ur"}}'
    )

    result = await classify_json(prompt)

    if result and result.get("intent") in INTENTS:
        entities = extract_entities(text)  # always run regex too
        llm_entities = result.get("entities", {})
        # Merge: regex entities take priority (more reliable for numbers)
        merged = {k: v for k, v in (llm_entities or {}).items() if v and v != "null"}
        merged.update(entities)

        return IntentResult(
            intent=result["intent"],
            confidence=float(result.get("confidence", 0.7)),
            entities=merged,
            language=result.get("language", "en"),
        )

    # Fallback to keywords
    return classify_by_keywords(text)


async def classify(
    text: str,
    session_context: str = "",
    use_llm: bool = True,
) -> IntentResult:
    """Main classification entry point.

    Args:
        text: The caller's utterance
        session_context: Additional context (e.g., "specialist just asked for reference number")
        use_llm: Whether to attempt LLM classification
    """
    if use_llm:
        return await classify_with_llm(text, session_context)
    return classify_by_keywords(text)
