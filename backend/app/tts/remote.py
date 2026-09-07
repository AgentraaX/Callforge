"""Remote TTS engine -- proxies to GPU pod running Sesame CSM or similar."""
from __future__ import annotations
import asyncio
import logging
from typing import AsyncIterator
import httpx
from . import TTSResult, TTSChunk, VoiceConfig

log = logging.getLogger("callforge.tts.remote")

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=90,
            limits=httpx.Limits(max_keepalive_connections=5),
        )
    return _client


async def _post_retry(url: str, **kw) -> httpx.Response:
    """One retry on transient transport errors."""
    try:
        return await _http().post(url, **kw)
    except httpx.TransportError:
        await asyncio.sleep(0.4)
        return await _http().post(url, **kw)


class RemoteEngine:
    """Remote TTS via GPU pod -- supports streaming."""

    def __init__(self):
        from ..config import settings
        self.base_url = (settings.voice_speech_base_url or "").rstrip("/")
        self.token = settings.voice_ai_token

    def _headers(self) -> dict:
        h = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def synthesize(self, text: str, voice: VoiceConfig,
                         emotion: str = "neutral") -> TTSResult:
        if not self.base_url:
            return TTSResult()

        body = {
            "text": text,
            "voice": voice.id,
            "emotion": emotion,
        }

        try:
            resp = await _post_retry(
                f"{self.base_url}/tts",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            audio = resp.content
            mime = resp.headers.get("content-type", "audio/wav")
            duration_ms = int(len(audio) / (22050 * 2) * 1000)

            return TTSResult(audio=audio, mime=mime, duration_ms=duration_ms)
        except Exception as exc:
            log.warning("Remote TTS failed: %s", exc)
            return TTSResult()

    async def synthesize_stream(self, chunks: list[str], voice: VoiceConfig,
                                emotion: str = "neutral") -> AsyncIterator[TTSChunk]:
        """Stream synthesis -- sends all chunks, yields audio as ready."""
        if not self.base_url:
            return

        body = {
            "chunks": chunks,
            "voice": voice.id,
            "emotion": emotion,
        }

        try:
            async with _http().stream(
                "POST", f"{self.base_url}/tts/stream",
                headers=self._headers(),
                json=body,
                timeout=90,
            ) as resp:
                resp.raise_for_status()
                chunk_idx = 0
                async for raw_chunk in resp.aiter_bytes(chunk_size=32768):
                    if raw_chunk:
                        yield TTSChunk(
                            audio=raw_chunk,
                            mime="audio/wav",
                            chunk_index=chunk_idx,
                        )
                        chunk_idx += 1
        except Exception as exc:
            log.warning("Remote TTS stream failed: %s", exc)
