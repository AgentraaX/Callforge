"""Edge TTS engine -- free Microsoft neural voices, no GPU needed.

Perfect for local development and as a reliable fallback.
Supports multilingual voices including Urdu.
"""
from __future__ import annotations
import asyncio
import io
import logging
import re
from . import TTSResult, VoiceConfig

log = logging.getLogger("callforge.tts.edge")

_URDU_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F]')


def _is_urdu(text: str) -> bool:
    """Detect if text contains significant Urdu script."""
    urdu_chars = len(_URDU_RE.findall(text))
    return urdu_chars > len(text) * 0.3


class EdgeTTSEngine:
    """Microsoft Edge neural TTS -- free, high quality, multilingual."""

    async def synthesize(self, text: str, voice: VoiceConfig,
                         emotion: str = "neutral") -> TTSResult:
        try:
            import edge_tts
        except ImportError:
            log.error("edge-tts not installed")
            return TTSResult()

        # Select voice based on language
        voice_name = voice.edge_voice_urdu if _is_urdu(text) else voice.edge_voice

        from ..config import settings

        try:
            communicate = edge_tts.Communicate(text, voice_name, rate=settings.tts_speaking_rate)
            audio_buffer = io.BytesIO()
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])

            audio_data = audio_buffer.getvalue()
            if not audio_data:
                log.warning("Edge TTS returned empty audio")
                return TTSResult()

            # Estimate duration from MP3 data size (~16kbps for speech)
            duration_ms = int(len(audio_data) / 2000 * 1000)

            return TTSResult(
                audio=audio_data,
                mime="audio/mp3",
                duration_ms=duration_ms,
                sample_rate=24000,  # Edge/Azure Neural voices' default output rate
            )
        except Exception as exc:
            log.warning("Edge TTS failed: %s", exc)
            return TTSResult()
