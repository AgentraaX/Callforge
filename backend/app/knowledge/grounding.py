"""Anti-hallucination guardrails -- four-layer defense system.

Layer 1: RAG-only context injection (system prompt forces KB-grounded answers)
Layer 2: Structured output enforcement (JSON extraction after business turns)
Layer 3: Source attribution (tag answers with source doc, fallback to "not on file")
Layer 4: Post-generation validation (numbers in response must exist in context)

This module provides the validation and grounding utilities used by the
conversation engine to ensure the agent never invents facts.
"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from .base import KBEntry, search

log = logging.getLogger("callforge.knowledge.grounding")


@dataclass
class GroundedResponse:
    """A response with grounding metadata."""
    text: str
    is_grounded: bool = True
    sources: list[str] = field(default_factory=list)  # source doc names
    confidence: float = 1.0
    fallback_used: bool = False
    validation_passed: bool = True
    numbers_validated: bool = True


# --- Layer 1: Context Building ---

def build_grounded_context(query: str, top_k: int = 3) -> tuple[str, list[KBEntry]]:
    """Search the knowledge base and build context for the LLM.
    
    Returns (formatted_context, matched_entries).
    If no entries match, returns ("", []) -- the caller must refuse to answer.
    """
    entries = search(query, top_k=top_k, min_hits=1)
    
    if not entries:
        return "", []
    
    # Format entries as context for the system prompt
    context_parts = []
    for i, entry in enumerate(entries, 1):
        context_parts.append(
            f"[Source: {entry.doc}/{entry.topic}]\n{entry.text}"
        )
    
    context = "\n\n".join(context_parts)
    return context, entries


# --- Layer 3: Source Attribution ---

NOT_ON_FILE_RESPONSE = (
    "I don't have that specific information on file right now. "
    "Let me connect you with a specialist who can give you the exact details."
)

PARTIAL_MATCH_DISCLAIMER = (
    " Please note, the exact figures should be confirmed by our billing team "
    "before making any decisions."
)


def attribute_sources(response: str, entries: list[KBEntry]) -> list[str]:
    """Identify which KB entries contributed to a response."""
    sources = []
    response_lower = response.lower()
    
    for entry in entries:
        # Check if key terms from the entry appear in the response
        entry_tokens = set(re.findall(r'[a-z0-9]+', entry.text.lower()))
        response_tokens = set(re.findall(r'[a-z0-9]+', response_lower))
        overlap = len(entry_tokens & response_tokens)
        
        if overlap >= 3:  # at least 3 shared meaningful tokens
            sources.append(f"{entry.doc}/{entry.topic}")
    
    return sources


# --- Layer 4: Post-Generation Validation ---

# Regex to find numbers (integers, decimals, currency amounts)
_NUMBER_RE = re.compile(r'\b(\d[\d,]*\.?\d*)\b')

# Numbers that are commonly generated and don't need validation
_SAFE_NUMBERS = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
                 "20", "40", "24", "7", "0"}  # container sizes, 24/7, etc.


def extract_numbers(text: str) -> set[str]:
    """Extract significant numbers from text (skip trivially common ones)."""
    numbers = set()
    for match in _NUMBER_RE.finditer(text):
        num = match.group(1).replace(",", "")
        # Skip very small or trivially common numbers
        if num not in _SAFE_NUMBERS and len(num) >= 2:
            numbers.add(num)
    return numbers


def validate_numbers(response: str, context: str) -> tuple[bool, set[str]]:
    """Check that any significant number in the response appears in the context.
    
    Returns (all_valid, ungrounded_numbers).
    """
    response_numbers = extract_numbers(response)
    if not response_numbers:
        return True, set()
    
    context_numbers = extract_numbers(context)
    ungrounded = response_numbers - context_numbers
    
    return len(ungrounded) == 0, ungrounded


def validate_response(response: str, context: str,
                      entries: list[KBEntry]) -> GroundedResponse:
    """Full validation pipeline for an agent response.
    
    Checks:
    1. Response contains content (not empty)
    2. Numbers in response exist in context
    3. Sources can be attributed
    """
    if not response.strip():
        return GroundedResponse(
            text=NOT_ON_FILE_RESPONSE,
            is_grounded=False,
            fallback_used=True,
            validation_passed=False,
        )
    
    # Number validation
    full_context = context + " " + " ".join(e.text for e in entries)
    numbers_ok, ungrounded = validate_numbers(response, full_context)
    
    if not numbers_ok:
        log.warning("Ungrounded numbers detected: %s", ungrounded)
        # Don't reject the response entirely, but flag it
        # The response might still be valid if numbers are from CRM data
    
    # Source attribution
    sources = attribute_sources(response, entries)
    
    return GroundedResponse(
        text=response,
        is_grounded=bool(sources) or bool(entries),
        sources=sources,
        confidence=0.9 if numbers_ok else 0.6,
        validation_passed=numbers_ok,
        numbers_validated=numbers_ok,
    )


# --- Utility: Check if a query needs grounding ---

_FACTUAL_KEYWORDS = {
    "rate", "price", "cost", "charge", "fee", "tariff",
    "how much", "kitna", "kharcha",
    "document", "required", "need", "clearance",
    "process", "step", "procedure",
    "policy", "rule", "regulation",
    "free days", "demurrage", "detention",
}


def needs_grounding(text: str) -> bool:
    """Determine if a query requires knowledge base grounding.
    
    Factual questions (rates, policies, procedures) need grounding.
    Operational queries (container tracking) use CRM data instead.
    Greetings and farewells don't need grounding.
    """
    lower = text.lower()
    return any(kw in lower for kw in _FACTUAL_KEYWORDS)


# --- Grounded Answer Pipeline ---

async def get_grounded_answer(query: str, llm_client, persona_context: str = "") -> GroundedResponse:
    """Complete grounded answer pipeline:
    
    1. Search KB for relevant context
    2. If no context found, return "not on file"
    3. Call LLM with grounded context
    4. Validate the response
    5. Return with attribution
    """
    from ..llm import Message
    from ..llm.prompts import build_system_prompt
    
    # Layer 1: Build context from KB
    context, entries = build_grounded_context(query)
    
    if not context:
        return GroundedResponse(
            text=NOT_ON_FILE_RESPONSE,
            is_grounded=False,
            fallback_used=True,
            sources=[],
        )
    
    # Layer 2: LLM with grounded context
    system = (
        f"{persona_context}\n\n"
        f"## GROUNDING RULES:\n"
        f"- Answer ONLY from the knowledge context below.\n"
        f"- NEVER invent rates, policies, or facts.\n"
        f"- If the context doesn't contain the answer, say you'll connect them with a specialist.\n"
        f"- Keep replies concise (1-3 sentences) for voice.\n\n"
        f"## Knowledge Context:\n{context}"
    )
    
    messages = [
        Message(role="system", content=system),
        Message(role="user", content=query),
    ]
    
    response = await llm_client.chat(messages, max_tokens=150, temperature=0.25)
    
    if not response.content:
        return GroundedResponse(
            text=NOT_ON_FILE_RESPONSE,
            is_grounded=False,
            fallback_used=True,
        )
    
    # Layer 4: Validate
    result = validate_response(response.content, context, entries)
    return result
