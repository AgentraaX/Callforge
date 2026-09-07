"""Call session state machine -- tracks the lifecycle of a single call.

States: idle -> ringing -> greeting -> listening -> thinking -> speaking -> listening (loop)
                                                                         -> hold -> transferring
                                                                         -> end
"""
from __future__ import annotations
import random
import time
from dataclasses import dataclass, field


def _new_case_id() -> str:
    return f"CS-{random.randint(2000, 9899)}"


@dataclass
class CallSession:
    """Tracks all state for one active call."""
    
    # Core state
    state: str = "idle"  # idle|ringing|greeting|listening|thinking|speaking|hold|transferring|end
    call_id: str = ""
    
    # Caller info
    caller_name: str = ""
    caller_email: str = ""
    # Populated opportunistically the moment the caller states a phone
    # number in ANY turn (not just the booking turn) -- a real rep
    # remembers a number mentioned minutes earlier instead of re-asking
    # for it when it's time to actually book.
    caller_phone: str = ""
    caller_id: str | None = None  # persistent browser ID for repeat callers
    
    # Language
    language: str = "en"  # "en" | "ur" -- mirrors the caller
    
    # Agent routing
    specialist_key: str | None = None  # current specialist
    persona_id: str = "mahnoor"  # active persona
    
    # Conversation context
    history: list[dict] = field(default_factory=list)  # LLM chat memory
    intent_log: list[str] = field(default_factory=list)  # intents seen
    lookup_log: list[dict] = field(default_factory=list)  # data lookups performed
    
    # Anti-hallucination
    last_kb_context: str = ""  # KB entries used for last answer
    last_summary: str = ""
    last_spoken: str = ""  # anti-parrot: don't repeat same answer
    
    # Flow control
    case_id: str = field(default_factory=_new_case_id)
    escalated: bool = False
    awaiting_reference: bool = False  # specialist asked for a number
    awaiting_anything_else: bool = False
    awaiting_booking_choice: bool = False
    booking_offer: list[dict] = field(default_factory=list)
    # Set True only by the deterministic confirm-booking path (never by the
    # LLM's own free text) -- lets a post-generation guard catch the model
    # narrating a fake "booking confirmed" with invented details (a wrong
    # date, a fabricated phone number) when nothing was actually booked.
    real_booking_confirmed: bool = False
    
    # Dashscope agent session (multi-turn RAG)
    dashscope_session_id: str | None = None
    
    # Metrics
    started_at: float = field(default_factory=time.time)
    turn_count: int = 0
    empty_count: int = 0  # consecutive empty STT results
    low_confidence_count: int = 0  # consecutive low-confidence turns
    
    def add_to_history(self, role: str, content: str):
        """Add a message to conversation history, capped at 20 turns."""
        self.history.append({"role": role, "content": content})
        if len(self.history) > 20:
            # Keep system prompt + last 18 turns
            self.history = self.history[:1] + self.history[-18:]
    
    def transition(self, new_state: str):
        """Transition to a new state."""
        self.state = new_state
    
    @property
    def duration_s(self) -> float:
        return time.time() - self.started_at
