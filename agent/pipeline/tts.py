"""Text-to-speech: Kokoro (ONNX, CPU) streamed into a LiveKit audio track.

Model files (~120MB) aren't committed to git - run
agent/models/download_models.ps1 once to fetch them.
"""

import logging
import os

import numpy as np
from kokoro_onnx import Kokoro
from kokoro_onnx.config import SAMPLE_RATE
from livekit import rtc

logger = logging.getLogger("agent.pipeline.tts")

_MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
_MODEL_PATH = os.path.join(_MODELS_DIR, "kokoro-v1.0.int8.onnx")
_VOICES_PATH = os.path.join(_MODELS_DIR, "voices-v1.0.bin")


class KokoroTTS:
    def __init__(self, voice: str = "af_heart") -> None:
        logger.info("Loading Kokoro TTS model", extra={"model_path": _MODEL_PATH})
        self._kokoro = Kokoro(_MODEL_PATH, _VOICES_PATH)
        self._voice = voice

    async def synthesize_to_track(self, text: str, source: rtc.AudioSource) -> None:
        """Stream synthesized speech straight into a published AudioSource.

        Uses create_stream() rather than create() so playback of the first
        audio chunk can start before the rest of the sentence has finished
        synthesizing.
        """
        async for audio_chunk, sample_rate in self._kokoro.create_stream(text, voice=self._voice):
            if sample_rate != source.sample_rate:
                raise ValueError(
                    f"Kokoro sample rate {sample_rate} != AudioSource sample rate {source.sample_rate}"
                )
            int16_samples = np.clip(audio_chunk * 32767.0, -32768, 32767).astype(np.int16)
            frame = rtc.AudioFrame.create(sample_rate, 1, len(int16_samples))
            np.frombuffer(frame.data, dtype=np.int16)[:] = int16_samples
            await source.capture_frame(frame)


__all__ = ["KokoroTTS", "SAMPLE_RATE"]
