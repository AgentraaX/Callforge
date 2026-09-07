"""ElevenLabs TTS engine -- low-latency voices with emotion support and
instant voice cloning, used for both browser test calls and real Telnyx
phone calls."""
from __future__ import annotations
import asyncio
import logging
from dataclasses import replace
import httpx
from . import TTSResult, VoiceConfig
from ..conversation.bilingual import detect_language

log = logging.getLogger("callforge.tts.elevenlabs")

_client: httpx.AsyncClient | None = None


def _sample_rate_from_format(output_format: str) -> int:
    """"mp3_44100_128" -> 44100, "ulaw_8000" -> 8000, etc. -- the LiveKit
    audio pipeline needs the REAL rate the encoded bytes are at, not an
    assumed one, or playback comes out sped up/garbled/cut short."""
    parts = output_format.split("_")
    for part in parts:
        if part.isdigit() and len(part) >= 4:
            return int(part)
    return 44100

# Flash v2.5 trades a sliver of quality for the lowest latency ElevenLabs
# offers (~75-150ms to first byte) -- the single biggest lever for making a
# live cold call feel instant rather than laggy.
MODEL_ID = "eleven_flash_v2_5"

# eleven_v3 is ElevenLabs' ONLY model with real Urdu support (confirmed
# via GET /v1/models -- every other model, including MODEL_ID above, has
# no "ur" entry in its languages list). Not used here: every ElevenLabs
# voice available on the free tier is an English voice approximating Urdu
# through v3's multilingual model, not natively Urdu-trained -- confirmed
# live to sound less natural than Edge TTS's genuine Pakistani-Urdu voice,
# which synthesize() below delegates to instead.


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=30,
            limits=httpx.Limits(max_keepalive_connections=5),
        )
    return _client


# Emotion to ElevenLabs stability/similarity/style settings. Lower
# stability = more expressive/variable delivery; higher style = more
# exaggerated emotional performance.
_EMOTION_SETTINGS = {
    "neutral": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0},
    "warm": {"stability": 0.42, "similarity_boost": 0.8, "style": 0.25},
    "confident": {"stability": 0.48, "similarity_boost": 0.8, "style": 0.35},
    "enthusiastic": {"stability": 0.3, "similarity_boost": 0.8, "style": 0.6},
    "empathetic": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.2},
    "apologetic": {"stability": 0.6, "similarity_boost": 0.7, "style": 0.1},
    "urgent": {"stability": 0.28, "similarity_boost": 0.8, "style": 0.5},
}


class ElevenLabsEngine:
    """ElevenLabs TTS with per-persona voice IDs and emotion control."""

    def __init__(self, force_urdu: bool = False):
        from ..config import settings
        self.api_key = settings.elevenlabs_api_key
        # Confirmed live: per-chunk language detection alone causes the
        # voice to audibly flip mid-reply whenever a short fragment (a
        # company name, a stray English word) gets classified as English
        # -- that one chunk goes to the ElevenLabs voice while the rest
        # goes to Edge's Urdu voice. For an Urdu-first persona, pin the
        # WHOLE call to the Urdu voice instead of re-deciding per chunk.
        self.force_urdu = force_urdu

    async def synthesize(self, text: str, voice: VoiceConfig,
                         emotion: str = "neutral") -> TTSResult:
        if self.force_urdu or detect_language(text).primary == "ur":
            # Native Pakistani-Urdu voice, free, no quota -- confirmed more
            # natural than any ElevenLabs voice available on the free tier
            # (all English voices approximating Urdu via eleven_v3).
            from .edge import EdgeTTSEngine
            if self.force_urdu:
                # EdgeTTSEngine does its OWN per-chunk language check and
                # picks voice.edge_voice (defaults to a FEMALE English
                # voice) for any chunk it decides isn't Urdu enough --
                # confirmed live this caused the voice to flip gender
                # mid-reply even with force_urdu set here. Pin both of
                # its voice slots to the same Urdu voice so that internal
                # check can't matter.
                voice = replace(voice, edge_voice=voice.edge_voice_urdu)
            return await EdgeTTSEngine().synthesize(text, voice, emotion)

        if not self.api_key:
            log.warning("ElevenLabs: no API key configured")
            return TTSResult()

        voice_id = voice.elevenlabs_voice
        if not voice_id:
            log.warning("No ElevenLabs voice ID for persona %s", voice.id)
            return TTSResult()

        settings_dict = _EMOTION_SETTINGS.get(emotion, _EMOTION_SETTINGS["neutral"])
        output_format = voice.output_format or "mp3_44100_128"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        body = {
            "text": text,
            "model_id": MODEL_ID,
            "voice_settings": settings_dict,
        }

        try:
            url = (
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                f"?output_format={output_format}"
            )
            resp = await _http().post(url, headers=headers, json=body)
            resp.raise_for_status()

            audio_data = resp.content
            duration_ms = int(len(audio_data) / 2000 * 1000)  # rough estimate

            mime = "audio/basic" if output_format.startswith("ulaw") else "audio/mpeg"

            return TTSResult(
                audio=audio_data,
                mime=mime,
                duration_ms=duration_ms,
                sample_rate=_sample_rate_from_format(output_format),
            )
        except Exception as exc:
            log.warning("ElevenLabs synthesis failed: %s", exc)
            return TTSResult()


async def synthesize_native_v3(text: str, voice: VoiceConfig, emotion: str = "neutral",
                               language_code: str = "ur") -> TTSResult:
    """ElevenLabs eleven_v3 for native-script Urdu/Sindhi text -- the only
    ElevenLabs model with real support for either language (confirmed via
    GET /v1/models). This is an English voice approximating the target
    language via v3's multilingual model, not a native voice -- a
    deliberate trade of accent for clarity, used when the native-language
    engine (Uplift) has been confirmed live to sound unclear/unnatural
    for a given persona (see Persona.native_tts_provider)."""
    from ..config import settings
    api_key = settings.elevenlabs_api_key
    if not api_key:
        log.warning("ElevenLabs: no API key configured for native_v3 synthesis")
        return TTSResult()

    voice_id = voice.elevenlabs_voice
    if not voice_id:
        log.warning("No ElevenLabs voice ID for persona %s (native_v3)", voice.id)
        return TTSResult()

    settings_dict = _EMOTION_SETTINGS.get(emotion, _EMOTION_SETTINGS["neutral"])
    output_format = voice.output_format or "mp3_44100_128"

    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    body = {
        "text": text,
        "model_id": "eleven_v3",
        "language_code": language_code,
        "voice_settings": settings_dict,
    }
    try:
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
            f"?output_format={output_format}"
        )
        resp = await _http().post(url, headers=headers, json=body)
        resp.raise_for_status()
        audio_data = resp.content
        mime = "audio/basic" if output_format.startswith("ulaw") else "audio/mpeg"
        return TTSResult(
            audio=audio_data,
            mime=mime,
            duration_ms=int(len(audio_data) / 2000 * 1000),
            sample_rate=_sample_rate_from_format(output_format),
        )
    except Exception as exc:
        log.warning("ElevenLabs eleven_v3 native synthesis failed: %s", exc)
        return TTSResult()


async def list_voices() -> list[dict]:
    """GET /v1/voices -- for the persona builder's voice picker.

    Returns [] on any failure (missing key, API error) rather than
    raising -- the picker UI degrades to manual voice-ID entry.
    """
    from ..config import settings
    if not settings.elevenlabs_api_key:
        return []

    headers = {"xi-api-key": settings.elevenlabs_api_key}
    try:
        resp = await _http().get("https://api.elevenlabs.io/v1/voices", headers=headers)
        resp.raise_for_status()
        voices = resp.json().get("voices", [])
        return [
            {
                "voice_id": v.get("voice_id"),
                "name": v.get("name"),
                "category": v.get("category"),
                "preview_url": v.get("preview_url"),
            }
            for v in voices
        ]
    except Exception as exc:
        log.warning("ElevenLabs list_voices failed: %s", exc)
        return []


async def clone_voice(name: str, audio_bytes: bytes, filename: str = "reference.mp3") -> str | None:
    """Instant Voice Cloning -- POST /v1/voices/add.

    Returns the new voice_id on success, None on failure (missing API key,
    ElevenLabs rejecting the sample, network error, etc).
    """
    from ..config import settings
    if not settings.elevenlabs_api_key:
        log.warning("ElevenLabs: no API key configured, cannot clone voice")
        return None

    headers = {"xi-api-key": settings.elevenlabs_api_key}
    files = {"files": (filename, audio_bytes)}
    data = {"name": name}

    try:
        resp = await _http().post(
            "https://api.elevenlabs.io/v1/voices/add",
            headers=headers, files=files, data=data,
        )
        resp.raise_for_status()
        return resp.json().get("voice_id")
    except Exception as exc:
        log.warning("ElevenLabs voice cloning failed: %s", exc)
        return None
