"""Knowledge base module -- grounded facts and anti-hallucination guardrails."""
from .base import KBEntry, search, get_all_entries
from .grounding import (
    GroundedResponse,
    build_grounded_context,
    validate_response,
    needs_grounding,
    get_grounded_answer,
    NOT_ON_FILE_RESPONSE,
)
