"""Speech-to-text: faster-whisper wrapper streamed from a LiveKit audio track.

Silence-triggered utterance segmentation, not a fixed window - transcribes
as soon as the prospect stops talking instead of waiting for an arbitrary
buffer to fill (the old fixed 2s window added up to 2s of pure buffering
latency before STT even started). Uses the same lightweight RMS-energy
check as vad.py's barge-in detector, just watching for the END of speech
instead of the start.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from faster_whisper import WhisperModel
from livekit import rtc

logger = logging.getLogger("agent.pipeline.stt")

SAMPLE_RATE = 16000

# Deliberately NOT the same value as vad.py's barge-in threshold, despite
# both being RMS checks on the same audio - they have opposite failure
# costs. Barge-in false-triggering on noise cancels a reply outright, so
# it needs to be strict (1800). This threshold gates "is this frame part
# of the utterance I'm buffering" - set it too high and ordinary quieter
# syllables/consonants momentarily drop below it mid-sentence, which
# _SILENCE_MS then reads as the utterance ending, chopping a single
# sentence into multiple fragments sent to the LLM out of context (this
# is what caused "Elon Musk worth in numbers." / "in a trillion or
# billion and finally." to arrive as two unrelated turns instead of one
# question). Keep this sensitive; let _SILENCE_MS's duration do the work
# of not cutting on brief pauses.
_ENERGY_THRESHOLD = 500.0
# How much trailing silence confirms the utterance actually ended, vs. a
# brief mid-sentence pause. Long enough to tolerate natural pauses
# between words/clauses without fragmenting a sentence.
_SILENCE_MS = 700.0
# Safety cap: flush even without silence after this long, so one
# continuous utterance (or sustained noise) can't buffer forever.
_MAX_UTTERANCE_SECONDS = 12.0
# Don't bother calling Whisper on a couple of frames of noise/click.
_MIN_UTTERANCE_SECONDS = 0.3

_executor = ThreadPoolExecutor(max_workers=1)

# Biases the decoder toward vocabulary/spellings expected on these calls
# (product name, qualification terminology) - doesn't guarantee an unseen
# prospect name transcribes correctly, but raises its odds by shaping the
# decoder's prior instead of leaving it fully generic.
_INITIAL_PROMPT = (
    "CallForge sales call. Terms that may come up: budget, authority, need, "
    "timeline, pricing, demo, onboarding, integration, subscription, "
    "enterprise, procurement, stakeholder, renewal."
)


class WhisperSTT:
    # Day 14 benchmarked tiny.en as ~1.7x faster than base.en (1064ms vs
    # 1843ms mean, n=5) with an identical transcript on that test audio -
    # but a live call today had tiny.en fail to transcribe a prospect's
    # name ("Elon Musk" -> "that all must be"), retrying through all 6
    # fallback temperatures (0.0-1.0) without ever meeting its own
    # confidence threshold. tiny.en's capacity just isn't enough for
    # less-common proper nouns. Moved up to base.en for the accuracy;
    # ~1.7x slower per the same Day 14 numbers, so worth watching on this
    # CPU-only box if STT latency becomes the bottleneck instead.
    def __init__(self, model_size: str = "base.en") -> None:
        logger.info("Loading Whisper model", extra={"model_size": model_size})
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    async def _transcribe(self, audio: np.ndarray) -> str:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._transcribe_sync, audio)

    def _transcribe_sync(self, audio: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio, language="en", beam_size=1, vad_filter=True, initial_prompt=_INITIAL_PROMPT
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    async def transcribe_track(self, track: rtc.Track):
        """Yield transcribed text as soon as the prospect pauses, instead of
        waiting for a fixed-size buffer to fill."""
        stream = rtc.AudioStream(track, sample_rate=SAMPLE_RATE, num_channels=1)
        utterance = np.empty(0, dtype=np.int16)
        silence_ms = 0.0
        speaking = False

        try:
            async for event in stream:
                samples = np.frombuffer(event.frame.data, dtype=np.int16)
                if len(samples) == 0:
                    continue
                frame_ms = len(samples) / SAMPLE_RATE * 1000.0

                rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
                if rms > _ENERGY_THRESHOLD:
                    speaking = True
                    silence_ms = 0.0
                    utterance = np.concatenate([utterance, samples])
                elif speaking:
                    silence_ms += frame_ms
                    utterance = np.concatenate([utterance, samples])

                utterance_seconds = len(utterance) / SAMPLE_RATE
                should_flush = speaking and (
                    silence_ms >= _SILENCE_MS or utterance_seconds >= _MAX_UTTERANCE_SECONDS
                )

                if should_flush:
                    speaking = False
                    silence_ms = 0.0
                    if utterance_seconds >= _MIN_UTTERANCE_SECONDS:
                        audio = utterance.astype(np.float32) / 32768.0
                        text = await self._transcribe(audio)
                        if text:
                            yield text
                    utterance = np.empty(0, dtype=np.int16)
        finally:
            await stream.aclose()
