"""Uplift AI TTS engine -- native Pakistani-Urdu voices (~300ms to first audio).

Uplift AI's voice catalog is Urdu/Sindhi/Balochi only (confirmed against
their voice catalog docs -- no English voices exist). CallForge calls are
bilingual, so this engine is a per-chunk router, not a single-language
client:

  - Urdu / code-switched-into-Urdu text (as detected by
    ``conversation.bilingual.detect_language``, which understands both
    Arabic-script and Roman Urdu) is sent to Uplift AI.
  - Pure-English text is delegated to a fallback engine (ElevenLabs if
    configured, else the free Edge engine).

Routing happens on whole chunks from ``tts.splitter.split_for_speech``,
which only ever splits at sentence/clause boundaries -- so a voice switch
between Uplift and the English fallback can only land between sentences,
never mid-word. That boundary discipline is what keeps a language switch
sounding like a deliberate hand-off instead of a glitch.
"""
from __future__ import annotations
import logging
import httpx
from . import TTSResult, VoiceConfig
from ..conversation.bilingual import detect_language

log = logging.getLogger("callforge.tts.uplift")

_API_URL = "https://api.upliftai.org/v1/synthesis/text-to-speech"

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=15,  # Uplift targets ~300ms to first byte; fail fast past that
            limits=httpx.Limits(max_keepalive_connections=5),
        )
    return _client


async def _romanize(text: str) -> str:
    """Transliterate Perso-Arabic-script Sindhi/Urdu to Roman script right
    before TTS -- confirmed live that Uplift's native-script Sindhi voices
    mispronounce/garble the native script badly enough that the spoken
    audio doesn't match the (correct) written text at all. Falls back to
    the original text on any failure -- worse pronunciation is still
    better than silence."""
    from ..llm import Message, create_urdu_fallback_client

    client = create_urdu_fallback_client()
    if not client:
        return text
    prompt = (
        "Transliterate the following Sindhi/Urdu text (written in "
        "Perso-Arabic script) into Roman/Latin script, using the natural "
        "phonetic spelling Sindhi/Urdu speakers actually use when texting "
        "(e.g. \"aayo\", \"tawhan\", \"ahyan\", \"ahe\") -- not formal "
        "linguistic transliteration with diacritics. Leave any word "
        "already in Latin script (like \"CallForge\") exactly as-is. "
        "Reply with ONLY the transliterated line, nothing else -- no "
        "quotes, no explanation, no original-script text alongside it.\n\n"
        f"Text: {text}"
    )
    try:
        # gpt-oss/qwen3 reasoning models spend part of the budget on hidden
        # reasoning before the visible reply (confirmed live: 300 tokens
        # was enough for a short line but starved a longer one, returning
        # empty content with finish_reason "length") -- see the same fix
        # in conversation/turn.py's opener generation.
        response = await client.chat(
            [Message(role="user", content=prompt)],
            max_tokens=600, temperature=0.3,
        )
        romanized = (response.content or "").strip().strip('"')
        return romanized or text
    except Exception as exc:
        log.warning("Sindhi/Urdu romanization failed, using original script: %s", exc)
        return text


class UpliftEngine:
    """Uplift AI for Urdu, with automatic fallback for English chunks."""

    def __init__(self, force_urdu: bool = False):
        from ..config import settings
        self.api_key = settings.uplift_api_key
        self.output_format = settings.uplift_output_format
        self.phrase_config_id = settings.uplift_phrase_replacement_config_id
        # Confirmed live (same bug as tts/elevenlabs.py): per-chunk
        # detection alone lets a short English-classified fragment (a
        # company name, a stray word) fall through to the ElevenLabs
        # fallback voice mid-reply, flipping voice identity audibly. For
        # an Urdu-first persona, pin the whole call to Uplift's native
        # voice instead of re-deciding per chunk.
        self.force_urdu = force_urdu
        self._fallback = None  # lazily built -- see _fallback_engine()
        self._edge = None  # lazily built -- see _edge_engine()

    def _fallback_engine(self):
        """The engine used for English chunks, and as a degrade path if
        an Uplift AI request itself fails (it can still speak the Urdu
        chunk reasonably well, just without Uplift's native prosody)."""
        if self._fallback is not None:
            return self._fallback
        from ..config import settings
        choice = settings.uplift_english_engine
        if choice == "elevenlabs" or (choice == "auto" and settings.elevenlabs_api_key):
            from .elevenlabs import ElevenLabsEngine
            self._fallback = ElevenLabsEngine()
        else:
            from .edge import EdgeTTSEngine
            self._fallback = EdgeTTSEngine()
        return self._fallback

    def _edge_engine(self):
        if self._edge is None:
            from .edge import EdgeTTSEngine
            self._edge = EdgeTTSEngine()
        return self._edge

    async def synthesize(self, text: str, voice: VoiceConfig,
                         emotion: str = "neutral") -> TTSResult:
        lang = detect_language(text)

        if (lang.primary == "ur" or self.force_urdu) and voice.native_tts_provider == "elevenlabs":
            from .elevenlabs import synthesize_native_v3
            return await synthesize_native_v3(text, voice, emotion, voice.native_language_code)

        if lang.primary != "ur" and not self.force_urdu:
            # Pure English chunk -- Uplift has no English voice for this.
            fallback = self._fallback_engine()
            result = await fallback.synthesize(text, voice, emotion)
            if not result.audio and fallback is not self._edge_engine():
                # ElevenLabs fallback came back empty (quota exhausted, bad
                # voice id, etc.) -- confirmed live this silently kills the
                # whole call otherwise, since it's the very first thing
                # spoken. Edge is free/quota-less, so it's a safe last resort.
                log.warning("English fallback returned no audio, retrying with Edge TTS")
                result = await self._edge_engine().synthesize(text, voice, emotion)
            return result

        if not self.api_key:
            log.warning("Uplift AI: no API key configured, falling back")
            return await self._fallback_engine().synthesize(text, voice, emotion)

        voice_id = voice.uplift_voice_urdu
        if not voice_id:
            log.warning("No Uplift AI voice ID for persona %s", voice.id)
            return await self._fallback_engine().synthesize(text, voice, emotion)

        speech_text = text
        if voice.uplift_roman_script:
            speech_text = await _romanize(text)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "voiceId": voice_id,
            "text": speech_text,
            "outputFormat": self.output_format,
        }
        if self.phrase_config_id:
            body["phraseReplacementConfigId"] = self.phrase_config_id

        try:
            resp = await _http().post(_API_URL, headers=headers, json=body)
            resp.raise_for_status()

            audio_data = resp.content
            duration_header = resp.headers.get("x-uplift-ai-audio-duration")
            duration_ms = int(duration_header) if duration_header else int(len(audio_data) / 2000 * 1000)
            sample_rate_header = resp.headers.get("x-uplift-ai-sample-rate")

            return TTSResult(
                audio=audio_data,
                mime="audio/mpeg",
                duration_ms=duration_ms,
                sample_rate=int(sample_rate_header) if sample_rate_header else 22050,
            )
        except Exception as exc:
            log.warning("Uplift AI synthesis failed, falling back: %s", exc)
            return await self._fallback_engine().synthesize(text, voice, emotion)
