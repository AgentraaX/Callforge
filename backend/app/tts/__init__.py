"""TTS engine abstraction -- Strategy pattern with factory."""
from __future__ import annotations
from typing import Protocol, runtime_checkable, AsyncIterator
from dataclasses import dataclass


@dataclass
class TTSResult:
    audio: bytes = b""
    mime: str = "audio/wav"
    duration_ms: int = 0
    # The actual sample rate of ``audio`` -- 0 means "unknown, caller
    # should assume its own default". Confirmed live as a real bug on the
    # LiveKit path: UpliftEngine can silently fall back to a DIFFERENT
    # engine (ElevenLabs at 44100Hz, Edge at 24000Hz) when its own API
    # call fails, but the LiveKit TTS adapter was declaring a single
    # hardcoded sample rate to the audio pipeline regardless of which
    # engine actually produced the bytes -- a real rate mismatch makes
    # playback sound sped up, garbled, or cut off partway through.
    sample_rate: int = 0


@dataclass
class TTSChunk:
    audio: bytes = b""
    mime: str = "audio/wav"
    chunk_index: int = 0


@dataclass(frozen=True)
class VoiceConfig:
    """Per-persona voice configuration."""
    id: str
    name: str
    edge_voice: str = "en-US-AvaMultilingualNeural"
    # ur-PK-AsadNeural -- Microsoft Azure Neural voice natively trained on
    # Pakistani Urdu (not a multilingual model approximating it). Free, no
    # quota, no paid plan -- and confirmed to sound more natural than any
    # ElevenLabs option tried so far, which are all English voices
    # speaking Urdu via eleven_v3's multilingual approximation.
    edge_voice_urdu: str = "ur-PK-AsadNeural"
    elevenlabs_voice: str = ""
    cosyvoice_speaker: str = ""
    uplift_voice_urdu: str = ""  # Uplift AI voiceId, native Pakistani-Urdu
    # Confirmed live: Uplift's native-script Sindhi voices mispronounce/
    # garble Perso-Arabic-script Sindhi badly enough that the spoken audio
    # doesn't match the (correct) written text at all. When true,
    # uplift.py transliterates the text to Roman script right before
    # synthesis -- the written transcript is untouched.
    uplift_roman_script: bool = False
    # "uplift" (default) or "elevenlabs" -- see Persona.native_tts_provider.
    native_tts_provider: str = "uplift"
    # ISO code passed to ElevenLabs eleven_v3 when native_tts_provider is
    # "elevenlabs" -- "sd" for Sindhi, "ur" for Urdu.
    native_language_code: str = "ur"
    reference_audio: str = ""  # path to reference WAV for cloning
    # "mp3_44100_128" for browser playback, "ulaw_8000" for Telnyx (no
    # resampling needed -- ElevenLabs emits 8kHz mulaw natively).
    output_format: str = "mp3_44100_128"


@runtime_checkable
class TTSEngine(Protocol):
    async def synthesize(self, text: str, voice: VoiceConfig,
                         emotion: str = "neutral") -> TTSResult: ...


class StreamingTTSEngine(Protocol):
    async def synthesize_stream(self, chunks: list[str], voice: VoiceConfig,
                                emotion: str = "neutral") -> AsyncIterator[TTSChunk]: ...


# Fallback voice used when a persona has no cloned/selected ElevenLabs
# voice yet, or for engines that don't need a real voice id (mock/edge).
_DEFAULT_VOICE = VoiceConfig(
    id="default", name="Agent",
    elevenlabs_voice="EXAVITQu4vr4xnSDxMaL",
)


def voice_from_persona(persona, *, telephony: bool = False) -> VoiceConfig:
    """Build a VoiceConfig from a dynamic sales Persona.

    ``telephony=True`` selects ulaw_8000 output (Telnyx Media Streaming --
    no resampling needed since ElevenLabs emits 8kHz mulaw natively);
    otherwise mp3 for browser playback.
    """
    voice_id = getattr(persona, "elevenlabs_voice_id", "") or _DEFAULT_VOICE.elevenlabs_voice
    return VoiceConfig(
        id=persona.id,
        name=persona.name,
        elevenlabs_voice=voice_id,
        # Per-persona Uplift voiceId (default "podcast-host", the Urdu pick
        # verified earlier) -- lets different personas use different native
        # voices, e.g. an Urdu persona vs a Sindhi persona, instead of every
        # persona sharing one hardcoded voice.
        uplift_voice_urdu=getattr(persona, "uplift_voice_id", "") or "podcast-host",
        uplift_roman_script=getattr(persona, "uplift_roman_script", False),
        native_tts_provider=getattr(persona, "native_tts_provider", "uplift"),
        native_language_code="sd" if getattr(persona, "language_mode", "auto") == "sindhi" else "ur",
        output_format="ulaw_8000" if telephony else "mp3_44100_128",
    )


def get_voice(persona_id: str) -> VoiceConfig:
    """Fallback voice lookup for callers that only have a persona id on
    hand (e.g. mock/test paths). Prefer voice_from_persona() when the
    full Persona object is available."""
    return _DEFAULT_VOICE


def create_engine(engine_type: str) -> TTSEngine:
    """Factory: create the appropriate TTS engine."""
    if engine_type == "cosyvoice":
        from .cosyvoice import CosyVoiceEngine
        return CosyVoiceEngine()
    elif engine_type == "edge":
        from .edge import EdgeTTSEngine
        return EdgeTTSEngine()
    elif engine_type == "elevenlabs":
        from .elevenlabs import ElevenLabsEngine
        return ElevenLabsEngine()
    elif engine_type == "uplift":
        from .uplift import UpliftEngine
        return UpliftEngine()
    elif engine_type == "remote":
        from .remote import RemoteEngine
        return RemoteEngine()
    else:
        from .mock import MockEngine
        return MockEngine()
