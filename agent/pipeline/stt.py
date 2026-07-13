"""Speech-to-text: faster-whisper wrapper streamed from a LiveKit audio track.

Chunk-based (fixed window), not silence-triggered — Day 12's VAD work
replaces this with real utterance boundaries and barge-in support.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from faster_whisper import WhisperModel
from livekit import rtc

logger = logging.getLogger("agent.pipeline.stt")

SAMPLE_RATE = 16000
CHUNK_SECONDS = 2.0

_executor = ThreadPoolExecutor(max_workers=1)


class WhisperSTT:
    def __init__(self, model_size: str = "base.en") -> None:
        logger.info("Loading Whisper model", extra={"model_size": model_size})
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    async def _transcribe(self, audio: np.ndarray) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._transcribe_sync, audio)

    def _transcribe_sync(self, audio: np.ndarray) -> str:
        segments, _ = self._model.transcribe(audio, language="en", beam_size=1, vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments).strip()

    async def transcribe_track(self, track: rtc.Track):
        """Yield transcribed text in fixed ~2s chunks from a room audio track."""
        stream = rtc.AudioStream(track, sample_rate=SAMPLE_RATE, num_channels=1)
        chunk_samples = int(SAMPLE_RATE * CHUNK_SECONDS)
        buffer = np.empty(0, dtype=np.int16)

        try:
            async for event in stream:
                samples = np.frombuffer(event.frame.data, dtype=np.int16)
                buffer = np.concatenate([buffer, samples])

                while len(buffer) >= chunk_samples:
                    chunk, buffer = buffer[:chunk_samples], buffer[chunk_samples:]
                    audio = chunk.astype(np.float32) / 32768.0
                    text = await self._transcribe(audio)
                    if text:
                        yield text
        finally:
            await stream.aclose()
