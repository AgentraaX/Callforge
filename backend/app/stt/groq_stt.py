"""Groq-hosted Whisper STT -- OpenAI-compatible /audio/transcriptions.

Uses its own GROQ_API_KEY, independent of whatever LLM_BASE_URL/LLM_API_KEY
currently point at (confirmed live: falling back to the LLM's key broke STT
outright -- silent 401s on every utterance -- the moment the LLM was
switched to a non-Groq provider). Groq's hosted whisper-large-v3-turbo
transcribes a several-second clip in well under a second, roughly two
orders of magnitude faster than faster-whisper's "small" model on a modest
CPU, which matters directly for how natural a live voice call feels --
but "turbo" is a distilled model that trades accuracy for that speed, and
a live tester reported only ~60% comprehension on Urdu/Sindhi speech.
Defaulting to the full whisper-large-v3 model instead: still well under a
second on Groq's hardware, and noticeably more accurate on lower-resource
languages than the distilled turbo variant.
"""
from __future__ import annotations
import logging
import re
import httpx
from . import STTResult, SALES_HOTWORDS

log = logging.getLogger("callforge.stt.groq")

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=15)
    return _client


# Confirmed live via a real TTS->STT round-trip test: Whisper transliterates
# the spoken English brand name "CallForge" into a phonetic native-script
# guess instead of recognizing it, even with "CallForge" in the hotwords
# prompt (that only nudges the model, it isn't a hard constraint) --
# observed as "کول فوٹ" / "کوھل فوج" (Urdu) and "कोल फोट" (Devanagari,
# roughly "kol fot/fauj"). The LLM then has no way to know the caller asked
# about CallForge at all. Catches the specific garbled renderings seen so
# far; widen this list from real transcripts if new variants show up.
_CALLFORGE_MISHEARD_RE = re.compile(
    r'ک[او]+[ہھ]?ل[ہھ]?\s*فو[ٹجتر]+|क[ोा]ल\s*फो[टज]',
)


def _fix_brand_mishearing(text: str) -> str:
    return _CALLFORGE_MISHEARD_RE.sub("CallForge", text)


class GroqSTTEngine:
    def __init__(self, api_key: str = "", model: str = "whisper-large-v3"):
        if not api_key:
            from ..config import settings
            api_key = settings.groq_api_key
        self.api_key = api_key
        self.model = model

    async def transcribe(self, audio: bytes, mime: str,
                         hotwords: list[str] | None = None,
                         language: str | None = None) -> STTResult:
        if not self.api_key:
            log.warning("Groq STT: no API key configured")
            return STTResult(text="", confidence=0.0)

        hotwords = hotwords or SALES_HOTWORDS
        prompt = ", ".join(hotwords[:15])
        ext = "webm" if "webm" in mime else ("wav" if "wav" in mime else "mp3")

        # Whisper auto-detects language per clip with no hint by default --
        # confirmed live this causes real misrecognition on short Urdu
        # clips (garbled/wrong-language output). When the caller (or
        # persona) is known to be Urdu-first, pinning language="ur" avoids
        # that per-clip guessing game.
        data = {"model": self.model, "response_format": "json", "prompt": prompt}
        if language:
            data["language"] = language

        try:
            resp = await _http().post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (f"audio.{ext}", audio, mime)},
                data=data,
            )
            resp.raise_for_status()
            body = resp.json()
            text = (body.get("text") or "").strip()
            text = _fix_brand_mishearing(text)
            return STTResult(text=text, language=language or "en", confidence=1.0 if text else 0.0)
        except Exception as exc:
            log.warning("Groq STT failed: %s", exc)
            return STTResult(text="", confidence=0.0)
