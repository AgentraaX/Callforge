"""Remote STT engine -- proxies to a GPU pod running Whisper large-v3-turbo."""
from __future__ import annotations
import asyncio
import logging
import httpx
from . import STTResult, SALES_HOTWORDS

log = logging.getLogger("callforge.stt.remote")


class RemoteEngine:
    def __init__(self, base_url: str = "", token: str = ""):
        # Import config lazily to avoid circular imports
        if not base_url:
            from ..config import settings
            base_url = settings.voice_speech_base_url
            token = settings.voice_ai_token
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30,
                limits=httpx.Limits(max_keepalive_connections=5),
            )
        return self._client

    async def transcribe(self, audio: bytes, mime: str,
                         hotwords: list[str] | None = None,
                         language: str | None = None) -> STTResult:
        if not self.base_url:
            log.warning("Remote STT not configured")
            return STTResult(text="", confidence=0.0)

        hotwords = hotwords or SALES_HOTWORDS
        hotword_prompt = "CallForge sales call: " + ", ".join(hotwords[:15])

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        data = {"initial_prompt": hotword_prompt}
        if language:
            data["language"] = language

        try:
            resp = await self._http().post(
                f"{self.base_url}/stt",
                headers=headers,
                files={"audio": ("audio.webm", audio, mime)},
                data=data,
            )
            resp.raise_for_status()
            data = resp.json()
            
            text = data.get("text", "").strip()
            lang = data.get("language", "en")
            if lang in ("ur", "urdu"):
                lang = "ur"
            
            return STTResult(
                text=text,
                language=lang,
                confidence=data.get("confidence", 0.8),
                is_code_switched=data.get("is_code_switched", False),
            )
        except Exception as exc:
            log.warning("Remote STT failed: %s", exc)
            return STTResult(text="", confidence=0.0)
