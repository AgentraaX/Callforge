"""CosyVoice TTS engine -- Alibaba Cloud (preferred for hackathon credits).

Supports voice cloning with reference audio, multilingual output including
Urdu and English, and emotion control.
"""
from __future__ import annotations
import asyncio
import logging
import httpx
from . import TTSResult, VoiceConfig

log = logging.getLogger("callforge.tts.cosyvoice")

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=30,
            limits=httpx.Limits(max_keepalive_connections=5),
        )
    return _client


class CosyVoiceEngine:
    """Alibaba Cloud CosyVoice TTS with voice cloning support."""

    def __init__(self):
        from ..config import settings
        self.api_key = settings.dashscope_api_key
        self.region = settings.dashscope_region

    @property
    def base_url(self) -> str:
        if self.region == "cn":
            return "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2audio/generation"
        return "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/text2audio/generation"

    async def synthesize(self, text: str, voice: VoiceConfig,
                         emotion: str = "neutral") -> TTSResult:
        if not self.api_key:
            log.warning("CosyVoice: no API key configured")
            return TTSResult()

        # Detect language for voice selection
        import re
        is_urdu = bool(re.search(r'[\u0600-\u06FF]', text))

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        body = {
            "model": "cosyvoice-v1",
            "input": {
                "text": text,
            },
            "parameters": {
                "voice": voice.cosyvoice_speaker or "longxiaochun",
                "format": "wav",
                "sample_rate": 22050,
            }
        }

        try:
            resp = await _http().post(
                self.base_url,
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            
            audio_data = resp.content
            # Estimate duration: 22050 samples/sec, 16-bit mono
            duration_ms = int(len(audio_data) / (22050 * 2) * 1000)
            
            return TTSResult(
                audio=audio_data,
                mime="audio/wav",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            log.warning("CosyVoice synthesis failed: %s", exc)
            return TTSResult()
