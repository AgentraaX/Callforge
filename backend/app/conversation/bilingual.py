"""Bilingual support -- Urdu + English + code-switching.

Handles:
- Language detection per utterance (pure English, pure Urdu, mixed)
- Language mirroring (reply in the caller's language)
- Script detection (Latin vs Arabic vs mixed)
- TTS voice selection based on detected language
- UI hints for RTL rendering
"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass

log = logging.getLogger("callforge.conversation.bilingual")


@dataclass
class LanguageInfo:
    """Language analysis result for a single utterance."""
    primary: str = "en"         # "en" | "ur"
    is_mixed: bool = False      # True if code-switching detected
    script: str = "latin"       # "latin" | "arabic" | "mixed"
    confidence: float = 1.0
    urdu_ratio: float = 0.0     # 0.0-1.0, proportion of Urdu content


# --- Detection Patterns ---

# Urdu script characters (Arabic block used for Urdu)
_URDU_SCRIPT_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]')

# Devanagari script -- confirmed live: Groq/Whisper sometimes transcribes
# actual Urdu speech into Devanagari instead of Arabic script (a known
# Hindi/Urdu confusion, since they're the same spoken language, just
# different scripts -- the exact equivalence CallForge itself exploits for
# XTTS's Hindi-mode fallback). Without this, that transcription silently
# fell through to "primary=en", routing it to the wrong LLM and TTS engine.
_DEVANAGARI_SCRIPT_RE = re.compile(r'[\u0900-\u097F]')

# Common Roman Urdu words (transliterated Urdu in Latin script)
_ROMAN_URDU_WORDS = {
    "kya", "kahan", "kaise", "kyun", "hai", "hain", "nahi", "ji", "haan",
    "mera", "meri", "mere", "aap", "aapka", "tumhara", "humara",
    "kitna", "kitne", "kitni", "kab", "kaun", "konsa",
    "chahiye", "chahte", "chahti", "karna", "karo", "karein",
    "achha", "theek", "shukriya", "meherbani", "please",
    "assalam", "walaikum", "alaikum", "khuda", "hafiz",
    "samajh", "samjha", "samjho", "bataiye", "batao",
    "container", "bill", "invoice", "booking",  # code-switched terms
    "abhi", "pehle", "baad", "mein", "se", "ko", "ka", "ki", "ke",
    "wala", "wali", "wale", "par", "pe",
    "milna", "milein", "ruka", "ruko",
    "paisa", "paise", "rupaye", "lakh",
}

# Common Urdu greetings and phrases
_URDU_PHRASES = [
    "assalam o alaikum", "assalam-o-alaikum", "walaikum assalam",
    "khuda hafiz", "allah hafiz", "jazak allah",
    "kya hal hai", "kya haal hai", "theek hai",
    "shukriya", "meherbani", "mashallah",
    "inshallah", "masha allah",
]


def detect_language(text: str) -> LanguageInfo:
    """Detect language of an utterance.
    
    Handles:
    - Pure English (Latin script, no Urdu indicators)
    - Pure Urdu (Arabic script)
    - Roman Urdu (Urdu words in Latin script)
    - Code-switched (mixed English and Urdu)
    """
    if not text.strip():
        return LanguageInfo()
    
    # Count Arabic-script and Devanagari-script characters -- either one
    # indicates Urdu content (see _DEVANAGARI_SCRIPT_RE above for why).
    urdu_script_chars = len(_URDU_SCRIPT_RE.findall(text))
    devanagari_chars = len(_DEVANAGARI_SCRIPT_RE.findall(text))
    total_chars = len(text.strip())

    # Check for Urdu script (Arabic or Devanagari)
    if total_chars > 0 and (urdu_script_chars + devanagari_chars) / total_chars > 0.5:
        has_latin = bool(re.search(r'[a-zA-Z]{2,}', text))
        script = "devanagari" if devanagari_chars > urdu_script_chars else "arabic"
        return LanguageInfo(
            primary="ur",
            is_mixed=has_latin,
            script="mixed" if has_latin else script,
            confidence=0.95,
            urdu_ratio=(urdu_script_chars + devanagari_chars) / total_chars,
        )
    
    # Check for Roman Urdu (Latin script but Urdu words)
    words = set(re.findall(r'[a-z]+', text.lower()))
    urdu_word_count = len(words & _ROMAN_URDU_WORDS)
    total_words = len(words) if words else 1
    
    # Check for Urdu phrases
    lower_text = text.lower()
    has_urdu_phrase = any(phrase in lower_text for phrase in _URDU_PHRASES)
    
    urdu_word_ratio = urdu_word_count / total_words
    
    if has_urdu_phrase or urdu_word_ratio > 0.4:
        # Roman Urdu or code-switched
        is_mixed = urdu_word_ratio < 0.8  # not purely Urdu words
        return LanguageInfo(
            primary="ur",
            is_mixed=is_mixed,
            script="latin",  # Roman Urdu
            confidence=0.75 if is_mixed else 0.85,
            urdu_ratio=urdu_word_ratio,
        )
    
    if urdu_script_chars > 0 or devanagari_chars > 0 or urdu_word_count > 0:
        # Some Urdu mixed in
        return LanguageInfo(
            primary="en",
            is_mixed=True,
            script="mixed" if (urdu_script_chars > 0 or devanagari_chars > 0) else "latin",
            confidence=0.8,
            urdu_ratio=urdu_word_ratio,
        )
    
    # Pure English
    return LanguageInfo(primary="en", confidence=0.9)


def should_reply_in_urdu(session_language: str, current_utterance: LanguageInfo) -> bool:
    """Determine if the agent should reply in Urdu.
    
    Rules:
    - If caller speaks pure Urdu -> reply in Urdu
    - If caller code-switches -> reply in the same mix
    - Mirror the caller's language choice
    """
    if current_utterance.primary == "ur" and not current_utterance.is_mixed:
        return True
    if session_language == "ur":
        return True
    return False


def get_rtl_direction(text: str) -> str:
    """Determine text direction for UI rendering.
    
    Returns "rtl" for Urdu script, "ltr" for Latin, "auto" for mixed.
    """
    urdu_chars = len(_URDU_SCRIPT_RE.findall(text))
    if urdu_chars == 0:
        return "ltr"
    total = len(text.strip())
    if total > 0 and urdu_chars / total > 0.5:
        return "rtl"
    return "auto"


# --- Language-aware response helpers ---

def get_language_instruction(language_info: LanguageInfo) -> str:
    """Generate LLM instruction for language handling."""
    if language_info.primary == "ur" and not language_info.is_mixed:
        return (
            "The caller is speaking in Urdu. Reply in Urdu (you may use "
            "Roman Urdu / transliteration if needed). Keep technical terms "
            "like container numbers, dates, and amounts in English digits."
        )
    if language_info.is_mixed:
        return (
            "The caller is mixing Urdu and English (code-switching). "
            "Reply naturally in the same mix -- use Urdu for conversational "
            "parts and English for technical/logistics terms. This is natural "
            "Pakistani business speech."
        )
    return "The caller is speaking in English. Reply in clear, professional English."


# Common bilingual responses (English + Urdu equivalents)
BILINGUAL_RESPONSES = {
    "listening": {"en": "Listening...", "ur": "Sun raha hoon..."},
    "thinking": {"en": "Let me check that for you...", "ur": "Abhi check karta hoon..."},
    "not_found": {
        "en": "I couldn't find that in our system. Could you double-check the number?",
        "ur": "System mein nahi mila. Kya aap number dobara check kar sakte hain?",
    },
    "anything_else": {
        "en": "Is there anything else I can help you with?",
        "ur": "Aur koi cheez jismein madad kar sakta hoon?",
    },
    "goodbye": {
        "en": "Thank you for calling. Have a great day!",
        "ur": "Shukriya call karne ka. Allah Hafiz!",
    },
    "hold": {
        "en": "Please hold for a moment while I connect you.",
        "ur": "Ek moment hold karein, main aapko connect karta hoon.",
    },
}


def get_bilingual_response(key: str, language: str) -> str:
    """Get a response in the appropriate language."""
    responses = BILINGUAL_RESPONSES.get(key, {})
    return responses.get(language, responses.get("en", ""))


def is_devanagari_dominant(text: str) -> bool:
    """True if the text is majority Devanagari script."""
    total = len(text.strip())
    if total == 0:
        return False
    return len(_DEVANAGARI_SCRIPT_RE.findall(text)) / total > 0.5


async def ensure_urdu_script(text: str) -> str:
    """Safety net for when the LLM ignores the "always reply in Urdu
    script" instruction and answers in Devanagari anyway (confirmed live:
    happens even with the instruction in place, since the model tends to
    mirror whatever script the caller's -- often STT-garbled -- message
    arrived in). Transliterates Devanagari back to Urdu/Perso-Arabic
    script so the reply is speakable by an Urdu TTS voice and legible as
    Urdu in the transcript. Returns the original text unchanged if it's
    not Devanagari-dominant, or if transliteration fails/is unavailable."""
    if not is_devanagari_dominant(text):
        return text
    from ..llm import Message, create_urdu_fallback_client
    client = create_urdu_fallback_client()
    if not client:
        return text
    prompt = (
        "Transliterate the following Hindi/Devanagari text into Urdu/"
        "Perso-Arabic script, preserving the exact same Hindustani "
        "pronunciation and meaning (do not translate to different "
        "vocabulary, just write the same sentence in Urdu script). Reply "
        f"with ONLY the Urdu-script transliteration, nothing else.\n\n{text}"
    )
    try:
        resp = await client.chat([Message(role="user", content=prompt)], max_tokens=400)
        result = (resp.content or "").strip()
        return result or text
    except Exception as exc:
        log.warning("Devanagari->Urdu transliteration failed, using original text: %s", exc)
        return text
