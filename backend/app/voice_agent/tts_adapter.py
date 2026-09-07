"""Adapts CallForge's existing Edge TTS engine (app/tts/edge.py) to LiveKit
Agents' TTS plugin protocol -- a free, quota-less fallback for when
ElevenLabs' character quota runs out (confirmed live: ElevenLabs' free tier
is a hard 10,000 characters/month, and every synthesis request fails
outright once it's hit, with no graceful degradation).
"""
from __future__ import annotations
import logging

from livekit.agents import tts
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions

from ..tts import VoiceConfig
from ..tts.edge import EdgeTTSEngine
from ..tts.elevenlabs import ElevenLabsEngine
from ..tts.uplift import UpliftEngine

log = logging.getLogger("callforge.voice_agent.tts_adapter")

SAMPLE_RATE = 24000
NUM_CHANNELS = 1


class EdgeTTS(tts.TTS):
    """Non-streaming (chunked) LiveKit TTS plugin wrapping EdgeTTSEngine."""

    def __init__(self, voice_name: str = "en-US-AndrewMultilingualNeural"):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
        )
        self._engine = EdgeTTSEngine()
        self._voice = VoiceConfig(id="edge", name="edge", edge_voice=voice_name)

    def synthesize(self, text: str, *,
                   conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> "_EdgeChunkedStream":
        return _EdgeChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class _EdgeChunkedStream(tts.ChunkedStream):
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        edge_tts: EdgeTTS = self._tts  # type: ignore[assignment]
        result = await edge_tts._engine.synthesize(self.input_text, edge_tts._voice)
        output_emitter.initialize(
            request_id="edge-tts",
            sample_rate=result.sample_rate or SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            mime_type=result.mime or "audio/mp3",
        )
        if result.audio:
            output_emitter.push(result.audio)
        else:
            log.warning("Edge TTS returned no audio for: %r", self.input_text)
        output_emitter.flush()


UPLIFT_SAMPLE_RATE = 22050


class UpliftTTS(tts.TTS):
    """Non-streaming LiveKit TTS plugin wrapping UpliftEngine -- bilingual
    per-chunk routing (Urdu -> Uplift AI's native voice, English -> the
    configured fallback), same engine the browser-JSON/Telnyx paths use."""

    def __init__(self, urdu_voice_id: str = "podcast-host", english_voice_name: str = "en-US-AndrewMultilingualNeural",
                 elevenlabs_voice_id: str = "", force_urdu: bool = False,
                 roman_script: bool = False, native_tts_provider: str = "uplift",
                 native_language_code: str = "ur"):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=UPLIFT_SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
        )
        self._engine = UpliftEngine(force_urdu=force_urdu)
        self._voice = VoiceConfig(
            id="uplift", name="uplift",
            uplift_voice_urdu=urdu_voice_id,
            edge_voice=english_voice_name,
            # Uplift has no English voice of its own -- English chunks fall
            # through to ElevenLabs (see tts/uplift.py's _fallback_engine).
            # Without a real voice id here that fallback silently returns
            # empty audio, which killed every greeting in production since
            # every persona greeting starts in English.
            elevenlabs_voice=elevenlabs_voice_id or "EXAVITQu4vr4xnSDxMaL",
            # Confirmed live: these two were missing here entirely -- this
            # class builds its own VoiceConfig instead of calling
            # tts.voice_from_persona(), so neither Roman-script nor the
            # ElevenLabs-native-provider override ever reached the actual
            # LiveKit/browser call path, only the older browser-JSON path.
            uplift_roman_script=roman_script,
            native_tts_provider=native_tts_provider,
            native_language_code=native_language_code,
        )

    def synthesize(self, text: str, *,
                   conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> "_UpliftChunkedStream":
        return _UpliftChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class _UpliftChunkedStream(tts.ChunkedStream):
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        uplift_tts: UpliftTTS = self._tts  # type: ignore[assignment]
        result = await uplift_tts._engine.synthesize(self.input_text, uplift_tts._voice)
        # Confirmed live bug: UpliftEngine can silently fall back to a
        # DIFFERENT engine (ElevenLabs at 44100Hz, Edge at 24000Hz) when
        # its own API call fails, but this always declared Uplift's own
        # 22050Hz to the audio pipeline regardless -- the resulting rate
        # mismatch made playback sound sped up/garbled/cut off partway
        # through. Use whatever rate the actual engine that produced this
        # audio reports.
        output_emitter.initialize(
            request_id="uplift-tts",
            sample_rate=result.sample_rate or UPLIFT_SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            mime_type=result.mime or "audio/mpeg",
        )
        if result.audio:
            output_emitter.push(result.audio)
        else:
            log.warning("Uplift TTS returned no audio for: %r", self.input_text)
        output_emitter.flush()


class ElevenLabsHybridTTS(tts.TTS):
    """Non-streaming LiveKit TTS plugin wrapping our own ElevenLabsEngine --
    routes Urdu text to Edge TTS's native Pakistani-Urdu voice, everything
    else to ElevenLabs (see tts/elevenlabs.py). Replaces the raw
    livekit.plugins.elevenlabs.TTS, which has no language-aware routing at
    all -- confirmed live that using it directly meant every Urdu-first
    persona's calls kept speaking Urdu through an English ElevenLabs voice
    no matter what the backend's own TTS engine did, since this LiveKit
    path never actually called into app/tts/elevenlabs.py."""

    def __init__(self, elevenlabs_voice_id: str = "", force_urdu: bool = False):
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
        )
        self._engine = ElevenLabsEngine(force_urdu=force_urdu)
        self._voice = VoiceConfig(
            id="elevenlabs", name="elevenlabs",
            elevenlabs_voice=elevenlabs_voice_id or "EXAVITQu4vr4xnSDxMaL",
        )

    def synthesize(self, text: str, *,
                   conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> "_ElevenLabsHybridChunkedStream":
        return _ElevenLabsHybridChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class _ElevenLabsHybridChunkedStream(tts.ChunkedStream):
    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        hybrid_tts: ElevenLabsHybridTTS = self._tts  # type: ignore[assignment]
        result = await hybrid_tts._engine.synthesize(self.input_text, hybrid_tts._voice)
        output_emitter.initialize(
            request_id="elevenlabs-hybrid-tts",
            sample_rate=result.sample_rate or SAMPLE_RATE,
            num_channels=NUM_CHANNELS,
            mime_type=result.mime or "audio/mpeg",
        )
        if result.audio:
            output_emitter.push(result.audio)
        else:
            log.warning("ElevenLabs hybrid TTS returned no audio for: %r", self.input_text)
        output_emitter.flush()
