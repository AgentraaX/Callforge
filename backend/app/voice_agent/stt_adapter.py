"""Adapts CallForge's existing batch STT engines (Whisper, GPU-remote --
see app/stt/) to LiveKit Agents' STT plugin protocol.

LiveKit's own Silero VAD does speech segmentation upstream and hands this
adapter one complete utterance's audio, which maps directly onto our
engines' existing batch ``transcribe(audio: bytes, mime: str)`` interface
-- no changes needed to stt/whisper.py or stt/remote.py, and no new STT
vendor to configure.
"""
from __future__ import annotations
import io
import logging
import wave

import numpy as np
from livekit.agents import stt, utils
from livekit.agents.types import NOT_GIVEN, APIConnectOptions, NotGivenOr

log = logging.getLogger("callforge.voice_agent.stt_adapter")

# Below this RMS (of int16 full-scale 32767), treat the clip as silence/
# background noise and never send it to STT at all. Whisper-family models
# (this includes Groq's hosted whisper-large-v3-turbo) are well known to
# hallucinate stock phrases -- "Thank you.", "Thanks for watching!" -- on
# near-silent audio rather than returning empty text, and its own
# confidence score doesn't reliably flag this (verified: a clip of pure
# digital silence still comes back with avg_logprob=-0.29, no_speech_prob=0,
# both well within Whisper's normal "confident" range). VAD upstream
# (Silero) triggers on brief noise it mistakes for speech, so this is the
# only reliable place to catch it -- before the hallucination can happen.
_SILENCE_RMS_THRESHOLD = 700

# Defense in depth: audio that's quiet-but-not-silent (background hum,
# distant noise, a mic pop) can still trigger the exact same Whisper
# hallucination even above the RMS floor above. These are the well-known
# stock phrases Whisper-family models fall back on -- if that's ALL that
# came back, treat it the same as silence rather than trusting it.
_HALLUCINATION_PHRASES = {
    "thank you", "thank you.", "thanks for watching", "thanks for watching!",
    "please subscribe", "subscribe", "bye", "bye.", "bye bye", "you",
    "thank you for watching", "thank you for watching!", ".", "",
}


def _frame_to_wav(frame) -> bytes:
    """LiveKit's AudioFrame.data is already linear PCM16 -- just needs a
    WAV header for our engines (faster-whisper, the GPU-remote engine)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(frame.num_channels)
        w.setsampwidth(2)
        w.setframerate(frame.sample_rate)
        w.writeframes(bytes(frame.data))
    return buf.getvalue()


def _rms(frame) -> float:
    samples = np.frombuffer(bytes(frame.data), dtype=np.int16)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


class ExistingEngineSTT(stt.STT):
    """Wraps whichever engine ``stt.create_engine(settings.stt_engine)``
    returns as a non-streaming ("recognize once") LiveKit STT plugin."""

    def __init__(self, engine, default_language: str | None = None):
        super().__init__(capabilities=stt.STTCapabilities(streaming=False, interim_results=False))
        self._engine = engine
        # Whisper auto-detects language per clip with no hint by default --
        # confirmed live this misrecognizes short Urdu clips (garbled/wrong-
        # language output). Personas known to be Urdu-first pin this so
        # every clip on the call is decoded as Urdu instead of guessed.
        self._default_language = default_language

    async def _recognize_impl(
        self,
        buffer: utils.AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        frame = utils.audio.combine_frames(buffer)
        rms = _rms(frame)
        if rms < _SILENCE_RMS_THRESHOLD:
            log.warning("STT skipped (near-silent, rms=%.0f < %.0f)", rms, _SILENCE_RMS_THRESHOLD)
            return stt.SpeechEvent(
                type=stt.SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[stt.SpeechData(text="", language="en")],
            )
        wav_bytes = _frame_to_wav(frame)
        result = await self._engine.transcribe(wav_bytes, "audio/wav", language=self._default_language)
        text = result.text
        if text.strip().lower() in _HALLUCINATION_PHRASES:
            log.warning("STT result %r (rms=%.0f) matches known hallucination phrase -- dropping", text, rms)
            text = ""
        else:
            log.warning("STT result %r (rms=%.0f)", text, rms)
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(text=text, language=result.language or "en")],
        )
