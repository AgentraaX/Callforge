"""Mock STT engine -- deterministic responses for testing."""
from __future__ import annotations
import logging
from . import STTResult

log = logging.getLogger("callforge.stt.mock")

# Rotating mock transcripts for testing a cold-call conversation
_MOCK_RESPONSES = [
    "Hi, who's calling?",
    "What exactly does this include?",
    "I'm honestly not that interested.",
    "How much does it cost?",
    "Can you just send me something by email instead?",
    "We're already using a competitor for this.",
    "Okay, that actually sounds useful -- tell me more.",
    "Can I speak to a supervisor please?",
]

_counter = 0


class MockEngine:
    async def transcribe(self, audio: bytes, mime: str,
                         hotwords: list[str] | None = None,
                         language: str | None = None) -> STTResult:
        global _counter
        text = _MOCK_RESPONSES[_counter % len(_MOCK_RESPONSES)]
        _counter += 1

        log.info("Mock STT: %r", text)
        return STTResult(
            text=text,
            language="en",
            confidence=0.95,
            is_code_switched=False,
        )
