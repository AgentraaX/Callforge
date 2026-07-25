"""Barge-in detection: a lightweight, low-latency voice-activity monitor
on the prospect's incoming audio, used to interrupt the agent's TTS the
moment they start talking.

Deliberately not reusing the STT pipeline's ~2s chunked faster-whisper
loop for this — that's far too slow for a ~300ms barge-in budget. This
is a separate, cheap RMS-energy check on raw ~20ms frames, subscribed
to the same track independently of stt.py's own AudioStream.
"""

import logging

import numpy as np
from livekit import rtc

logger = logging.getLogger("agent.pipeline.vad")

SAMPLE_RATE = 16000

# int16 RMS threshold for "this frame has speech-level energy", and how
# many *consecutive* frames must clear it before we call it real speech
# rather than a click/pop. Frames are ~20ms, so 5 in a row is ~100ms of
# confirmation - still well inside the ~300ms budget even with the
# callback's own overhead on top.
#
# Raised from 500/3: with earbuds (acoustic echo ruled out), 500 was
# still tripping on ordinary mic self-noise / room ambience a couple of
# seconds into nearly every reply, cancelling it before the prospect ever
# heard it - the barge-in was firing on background noise, not real speech.
_ENERGY_THRESHOLD = 1800.0
_CONFIRM_FRAMES = 5


class BargeInDetector:
    def __init__(self, energy_threshold: float = _ENERGY_THRESHOLD, confirm_frames: int = _CONFIRM_FRAMES) -> None:
        self._energy_threshold = energy_threshold
        self._confirm_frames = confirm_frames

    async def watch(self, track: rtc.Track, on_speech_started) -> None:
        """Runs until the track ends; calls on_speech_started() (sync,
        fire-and-forget) the first time sustained energy is detected
        after a period of silence, then keeps watching for the next one."""
        stream = rtc.AudioStream(track, sample_rate=SAMPLE_RATE, num_channels=1)
        consecutive = 0
        triggered = False
        try:
            async for event in stream:
                samples = np.frombuffer(event.frame.data, dtype=np.int16).astype(np.float32)
                rms = float(np.sqrt(np.mean(samples**2))) if len(samples) else 0.0

                if rms > self._energy_threshold:
                    consecutive += 1
                    if consecutive >= self._confirm_frames and not triggered:
                        triggered = True
                        on_speech_started()
                else:
                    consecutive = 0
                    triggered = False  # silence again - arm for the next barge-in
        finally:
            await stream.aclose()
