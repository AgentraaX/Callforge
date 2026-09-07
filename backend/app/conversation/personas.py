"""Dynamic sales personas -- user-created, not hardcoded.

Each persona is a full cold-calling identity: who they are, who they
represent, what they're selling, what they're allowed to claim (the
grounding source for anti-hallucination), and what voice they speak with.
In-memory store, same pattern as ``auth.py`` and ``sales/leads.py``
("production would use PostgreSQL").
"""
from __future__ import annotations
import time
import uuid
from dataclasses import asdict, dataclass, field

DEFAULT_EMOTIONS = ("neutral", "warm", "confident", "enthusiastic", "empathetic", "urgent")


@dataclass
class Persona:
    id: str = ""
    owner_email: str = ""
    name: str = ""                     # "Saad" -- whatever the user names it
    company: str = ""                  # who they're calling on behalf of
    product_pitch: str = ""            # what's being sold -- feeds the system prompt
    personality: str = ""              # tone/character description for the LLM prompt
    knowledge_text: str = ""           # facts/pricing/FAQs -- the grounding source
    opening_line: str = ""
    call_goal: str = "book a short follow-up call"
    elevenlabs_voice_id: str = ""
    default_emotion: str = "confident"
    # "auto" mirrors whatever language the caller uses (English, Urdu, or
    # code-switched); "english" forces English only regardless of what the
    # caller speaks; "sindhi" forces genuine Sindhi (distinct vocabulary/
    # grammar from Urdu, not just the shared script) -- a deliberate
    # override for when you want a specific language rather than leaving
    # it to the model's judgment.
    language_mode: str = "auto"
    # Uplift AI voiceId used whenever this persona's Perso-Arabic-script
    # text is routed to Uplift (see tts/uplift.py) -- lets different
    # personas use different native voices (e.g. Urdu vs Sindhi) instead
    # of every persona sharing one hardcoded voice.
    uplift_voice_id: str = "podcast-host"
    # Uplift's native-script Sindhi voices have been confirmed live to
    # mispronounce/garble Perso-Arabic-script Sindhi badly enough that the
    # spoken audio doesn't match the (correct) written text at all. When
    # true, the Sindhi/Urdu text is transliterated to Roman script right
    # before TTS (see tts/uplift.py) -- the written transcript stays in
    # native script throughout, only the audio path changes.
    uplift_roman_script: bool = False
    # "uplift" (default) or "elevenlabs" -- confirmed live that Uplift's
    # Sindhi voices are unclear/unnatural across every voiceId tried and
    # both native and Roman script. "elevenlabs" routes native-script
    # (Urdu/Sindhi) turns to ElevenLabs' eleven_v3 model instead (the only
    # ElevenLabs model with real Sindhi/Urdu support), using this
    # persona's own elevenlabs_voice_id -- an English voice approximating
    # the language rather than a native one, trading accent for clarity.
    native_tts_provider: str = "uplift"
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if self.default_emotion not in DEFAULT_EMOTIONS:
            self.default_emotion = "confident"
        if self.language_mode not in ("auto", "english", "sindhi"):
            self.language_mode = "auto"


# In-memory store, keyed by persona id
PERSONAS: dict[str, Persona] = {}
_MAX_PERSONAS = 500


def create_persona(owner_email: str, **fields) -> Persona:
    persona = Persona(owner_email=owner_email.strip().lower(), **fields)
    PERSONAS[persona.id] = persona
    while len(PERSONAS) > _MAX_PERSONAS:
        PERSONAS.pop(next(iter(PERSONAS)))
    return persona


def update_persona(persona_id: str, owner_email: str, **fields) -> Persona | None:
    persona = PERSONAS.get(persona_id)
    if not persona or persona.owner_email != owner_email.strip().lower():
        return None
    for key, value in fields.items():
        if hasattr(persona, key) and key not in ("id", "owner_email", "created_at"):
            setattr(persona, key, value)
    if persona.default_emotion not in DEFAULT_EMOTIONS:
        persona.default_emotion = "confident"
    return persona


def delete_persona(persona_id: str, owner_email: str) -> bool:
    persona = PERSONAS.get(persona_id)
    if not persona or persona.owner_email != owner_email.strip().lower():
        return False
    del PERSONAS[persona_id]
    return True


def get_persona(persona_id: str) -> Persona | None:
    return PERSONAS.get(persona_id)


def list_personas(owner_email: str) -> list[Persona]:
    owner = owner_email.strip().lower()
    return sorted(
        (p for p in PERSONAS.values() if p.owner_email == owner),
        key=lambda p: -p.created_at,
    )


def persona_payload(p: Persona) -> dict:
    """Serializable persona info -- includes everything the builder UI and
    the call UI need. Superset of the old logistics-era PersonaPayload
    (id/name/role/title/fallback_pitch/fallback_rate kept for frontend
    compatibility during the transition; role/title are synthesized)."""
    return {
        "id": p.id,
        "name": p.name,
        "role": "sales_agent",
        "title": f"calling on behalf of {p.company}" if p.company else "sales agent",
        "company": p.company,
        "product_pitch": p.product_pitch,
        "personality": p.personality,
        "knowledge_text": p.knowledge_text,
        "opening_line": p.opening_line,
        "call_goal": p.call_goal,
        "elevenlabs_voice_id": p.elevenlabs_voice_id,
        "default_emotion": p.default_emotion,
        "language_mode": p.language_mode,
        "uplift_voice_id": p.uplift_voice_id,
        "uplift_roman_script": p.uplift_roman_script,
        "native_tts_provider": p.native_tts_provider,
        "fallback_pitch": 0,
        "fallback_rate": 1.0,
    }


def persona_dict(p: Persona) -> dict:
    return asdict(p)
