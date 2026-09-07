"""STT engine abstraction -- Strategy pattern with factory."""
from __future__ import annotations
from typing import Protocol, runtime_checkable
from dataclasses import dataclass, field


@dataclass
class Segment:
    text: str
    start: float  # seconds
    end: float
    confidence: float = 1.0


@dataclass
class STTResult:
    text: str
    language: str = "en"          # ISO 639-1
    confidence: float = 1.0
    segments: list[Segment] = field(default_factory=list)
    is_code_switched: bool = False


@runtime_checkable
class STTEngine(Protocol):
    async def transcribe(self, audio: bytes, mime: str,
                         hotwords: list[str] | None = None,
                         language: str | None = None) -> STTResult: ...


# Hotword registry for CallForge's sales cold-calling domain -- biases
# Whisper's transcription toward the vocabulary actually heard on these
# calls. Previously this was LOGISTICS_HOTWORDS, left over from the
# pre-pivot logistics product (container numbers, "Bill of Lading",
# carrier names, etc.) -- confirmed live those terms were actively
# distorting recognition on real sales calls, contributing to garbled
# transcripts ("Mena Nantaha" instead of a real name, phantom phrases).
SALES_HOTWORDS = [
    "CallForge", "demo", "pricing", "booking", "trial", "subscription",
    "sales", "lead", "follow-up", "callback",
    "Assalam-o-Alaikum", "Walaikum Assalam", "ji", "haan", "nahi", "shukriya",
]


def create_engine(engine_type: str) -> STTEngine:
    """Factory: create the appropriate STT engine based on config."""
    if engine_type == "vibevoice":
        from .vibevoice import VibeVoiceEngine
        return VibeVoiceEngine()
    elif engine_type == "whisper":
        from .whisper import WhisperEngine
        return WhisperEngine()
    elif engine_type == "remote":
        from .remote import RemoteEngine
        return RemoteEngine()
    elif engine_type == "groq":
        from .groq_stt import GroqSTTEngine
        return GroqSTTEngine()
    else:
        from .mock import MockEngine
        return MockEngine()
