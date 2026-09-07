"""Local knowledge base -- the single source of truth for facts.

Two retrieval paths:
1. Model Studio Agent (cloud RAG) -- when DASHSCOPE_APP_ID is set
2. Local keyword search (this file) -- fallback, zero dependencies

If nothing matches, returns [] -- the agent MUST say "not on file".
"""
from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class KBEntry:
    doc: str      # source document category
    topic: str    # heading / canonical question
    text: str     # the grounded fact(s)
    language: str = "en"  # "en" | "ur" | "mixed"
    tags: tuple[str, ...] = ()


# === Knowledge Base Entries ===
# Mirrors the hackathon plan Section 10.2 document set

KB: list[KBEntry] = [
    # --- Services ---
    KBEntry(
        "services", "Services overview",
        "CallForge logistics terminals offer: Full Container Load (FCL) and "
        "Less than Container Load (LCL) handling, customs clearance (GD filing "
        "on WeBOC, red/green channel risk profiling), bonded and general "
        "warehousing, inland trucking and haulage, reefer (temperature-controlled) "
        "cargo handling, and empty container depot services.",
        tags=("services", "fcl", "lcl", "customs", "warehouse"),
    ),
    # --- Rates ---
    KBEntry(
        "rates", "Indicative FCL terminal handling rates",
        "Indicative terminal handling charge, Karachi terminal, general cargo: "
        "20ft standard container approximately PKR 45,000-55,000; 40ft standard "
        "approximately PKR 65,000-78,000. Reefer containers add a plug-in charge "
        "of approximately PKR 15,000-20,000. These figures are indicative only -- "
        "the exact rate depends on container size, cargo type and the current "
        "tariff schedule, and must be confirmed by a billing specialist.",
        tags=("rates", "pricing", "thc", "terminal"),
    ),
    KBEntry(
        "rates", "What changes the price",
        "Rates vary based on: container size (20ft vs 40ft vs 40ft high cube), "
        "cargo type (general, reefer, hazardous), route (port pair / inland "
        "destination), and free days used (demurrage adds after the free window).",
        tags=("rates", "pricing", "factors"),
    ),
    # --- Documents ---
    KBEntry(
        "documents", "Import clearance documents",
        "For FCL import clearance you need: commercial invoice, packing list, "
        "bill of lading (original or telex release), the import GD filed on "
        "WeBOC, and a Form-I if the cargo is hazardous.",
        tags=("documents", "import", "clearance"),
    ),
    KBEntry(
        "documents", "Export documents",
        "For export you need: commercial invoice, packing list, the export GD "
        "(EIF) filed on WeBOC, and a certificate of origin if the destination "
        "country requires one.",
        tags=("documents", "export"),
    ),
    # --- Booking Process ---
    KBEntry(
        "booking", "Booking and process steps",
        "The booking process: (1) shipper submits booking request with cargo "
        "details, origin/destination and preferred sailing week; (2) shipping "
        "line confirms space and issues booking number; (3) cargo gated in "
        "before cut-off; (4) container loaded, vessel departs, IGM filed on "
        "arrival; (5) GD filed on WeBOC, customs risk-profiles (green/red), "
        "once cleared the delivery order and gate pass are issued for gate-out.",
        tags=("booking", "process", "steps"),
    ),
    # --- FAQs ---
    KBEntry(
        "faq", "How many free days before demurrage starts",
        "Standard free time is 4 days from discharge for import FCL cargo. "
        "Reefer cargo gets 2 free days because of plug-in slot demand. After "
        "free days, demurrage accrues daily per the current tariff.",
        tags=("faq", "demurrage", "free days"),
    ),
    KBEntry(
        "faq", "Demurrage vs detention",
        "Demurrage is charged by the terminal for a container staying in the "
        "yard past free days. Detention is charged by the shipping line for the "
        "container staying out with the consignee past free detention period "
        "after gate-out, until returned empty.",
        tags=("faq", "demurrage", "detention"),
    ),
    KBEntry(
        "faq", "Tracking without calling",
        "Container status, GD status and gate-out readiness can be checked any "
        "time by giving the container number, IGM number, or bill of lading "
        "number to the AI agent, 24/7.",
        tags=("faq", "tracking", "self-service"),
    ),
    # --- Escalation Rules ---
    KBEntry(
        "escalation", "When to escalate to a human",
        "Escalate to a human when: caller disputes a charge or wants a refund, "
        "a reference number cannot be found after one re-check, caller explicitly "
        "asks for a supervisor, or request involves a policy exception such as "
        "a demurrage waiver. Always summarize the conversation and attach case "
        "number when escalating.",
        tags=("escalation", "handoff", "rules"),
    ),
    # --- Glossary ---
    KBEntry(
        "glossary", "What is TEU",
        "TEU means Twenty-foot Equivalent Unit -- the standard measure of "
        "container capacity. One 20ft container = 1 TEU; one 40ft = 2 TEU.",
        tags=("glossary", "teu"),
    ),
    KBEntry(
        "glossary", "What is a Bill of Lading (B/L)",
        "A Bill of Lading is a legal document issued by the shipping line as a "
        "receipt of cargo and title document. Must be surrendered or telex-released "
        "before a delivery order can be issued.",
        tags=("glossary", "bill of lading", "bl"),
    ),
    KBEntry(
        "glossary", "What is a GD (Goods Declaration)",
        "A GD (Goods Declaration) is the customs declaration filed on WeBOC "
        "(Pakistan's customs portal) for every import or export shipment.",
        tags=("glossary", "gd", "weboc"),
    ),
    KBEntry(
        "glossary", "What is an IGM",
        "An IGM (Import General Manifest) is the manifest filed by the shipping "
        "line listing all cargo on an arriving vessel; customs cross-checks it "
        "against each shipper's GD.",
        tags=("glossary", "igm", "manifest"),
    ),
    KBEntry(
        "glossary", "FCL vs LCL",
        "FCL (Full Container Load): cargo filling an entire container booked by "
        "one shipper. LCL (Less than Container Load): smaller shipment "
        "consolidated with other shippers' cargo in one container.",
        tags=("glossary", "fcl", "lcl"),
    ),
]


# --- Search Implementation ---

_STOPWORDS = {
    "the", "a", "an", "is", "are", "for", "to", "of", "and", "or", "in",
    "on", "my", "me", "what", "how", "do", "does", "i", "you", "your",
    "please", "can", "could", "hai", "ka", "ki", "ke", "aap", "kya",
    "kaise", "mein", "about", "this", "that", "it", "was", "were",
}


def _tokens(text: str) -> set[str]:
    """Extract searchable tokens from text."""
    return {w for w in re.findall(r"[a-z0-9]+", text.lower())
            if w not in _STOPWORDS and len(w) > 1}


def search(query: str, top_k: int = 2, min_hits: int = 1) -> list[KBEntry]:
    """Keyword-overlap retrieval.

    Returns [] when nothing clears min_hits -- this is the signal
    to say "not on file" instead of guessing.
    """
    q_tokens = _tokens(query)
    if not q_tokens:
        return []

    scored: list[tuple[float, KBEntry]] = []
    for entry in KB:
        # Score = overlap with topic + text + tags
        entry_text = entry.topic + " " + entry.text + " " + " ".join(entry.tags)
        entry_tokens = _tokens(entry_text)
        overlap = len(q_tokens & entry_tokens)

        # Boost for tag matches
        tag_tokens = _tokens(" ".join(entry.tags))
        tag_overlap = len(q_tokens & tag_tokens)
        score = overlap + (tag_overlap * 0.5)

        if overlap >= min_hits:
            scored.append((score, entry))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [entry for _score, entry in scored[:top_k]]


def get_all_entries() -> list[KBEntry]:
    """Return all KB entries (for upload to Model Studio)."""
    return list(KB)
