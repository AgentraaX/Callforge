"""Shared data contracts between backend modules."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class STTResult:
    text: str
    language: str = "en"
    confidence: float = 1.0
    segments: list[dict] = field(default_factory=list)
    is_code_switched: bool = False

@dataclass
class TTSResult:
    audio: bytes = b""
    mime: str = "audio/wav"
    duration_ms: int = 0

@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=dict)

@dataclass
class AgentResponse:
    answer: str | None = None
    session_id: str | None = None
    sources: list[str] = field(default_factory=list)

@dataclass
class IntentResult:
    intent: str = "other"
    confidence: float = 0.0
    entities: dict[str, str] = field(default_factory=dict)
    language: str = "en"

@dataclass
class Lead:
    id: str = ""
    call_id: str = ""
    company: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    cargo_type: str | None = None
    route: str | None = None
    volume: str | None = None
    urgency: str = "exploring"
    score: str = "cold"
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""
    source_transcript: list[str] = field(default_factory=list)

@dataclass
class Booking:
    booking_id: str = ""
    call_id: str = ""
    lead_id: str | None = None
    slot: str = ""
    slot_label: str = ""
    purpose: str = "consultation"
    contact_name: str = ""
    contact_phone: str | None = None
    status: str = "confirmed"
    created_at: str = ""

@dataclass
class EscalationCase:
    case_id: str = ""
    call_id: str = ""
    reason: str = ""
    summary: str = ""
    caller_name: str = ""
    caller_intent: str = ""
    transcript_excerpt: list[str] = field(default_factory=list)
    lead: Lead | None = None
    priority: str = "normal"
    created_at: str = ""
    status: str = "pending"

@dataclass
class LanguageInfo:
    primary: str = "en"
    is_mixed: bool = False
    script: str = "latin"
