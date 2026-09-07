"""Mock TTS engine -- returns minimal valid audio for testing."""
from __future__ import annotations
import logging
import struct
from . import TTSResult, VoiceConfig

log = logging.getLogger("callforge.tts.mock")


def _silent_wav(duration_ms: int = 500, sample_rate: int = 22050) -> bytes:
    """Generate a minimal silent WAV file."""
    num_samples = int(sample_rate * duration_ms / 1000)
    data_size = num_samples * 2  # 16-bit mono
    
    # WAV header
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_size,
        b'WAVE',
        b'fmt ',
        16,       # chunk size
        1,        # PCM format
        1,        # mono
        sample_rate,
        sample_rate * 2,  # byte rate
        2,        # block align
        16,       # bits per sample
        b'data',
        data_size,
    )
    
    # Silent samples
    return header + (b'\x00' * data_size)


class MockEngine:
    """Mock TTS -- returns silent audio for testing without real synthesis."""

    async def synthesize(self, text: str, voice: VoiceConfig,
                         emotion: str = "neutral") -> TTSResult:
        # Estimate duration: ~150ms per word
        word_count = len(text.split())
        duration_ms = max(300, word_count * 150)
        
        log.debug("Mock TTS: '%s...' (%dms)", text[:40], duration_ms)
        
        return TTSResult(
            audio=_silent_wav(duration_ms),
            mime="audio/wav",
            duration_ms=duration_ms,
        )
