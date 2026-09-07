"""Whisper STT engine -- faster-whisper, CPU-capable."""
from __future__ import annotations
import asyncio
import io
import logging
import tempfile
from . import STTResult, Segment, SALES_HOTWORDS

log = logging.getLogger("callforge.stt.whisper")

_model = None
_lock = asyncio.Lock()


class WhisperEngine:
    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    async def _get_model(self):
        global _model
        if _model is not None:
            return _model
        async with _lock:
            if _model is not None:
                return _model
            log.info("Loading faster-whisper model '%s'...", self.model_size)
            from faster_whisper import WhisperModel
            _model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            log.info("Whisper model loaded.")
            return _model

    async def transcribe(self, audio: bytes, mime: str,
                         hotwords: list[str] | None = None,
                         language: str | None = None) -> STTResult:
        model = await self._get_model()
        hotwords = hotwords or SALES_HOTWORDS
        hotword_prompt = (
            "CallForge sales call: " + ", ".join(hotwords[:15])
        )

        def _run():
            # Write audio to temp file for faster-whisper
            suffix = ".webm" if "webm" in mime else ".wav"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(audio)
                f.flush()
                tmp_path = f.name

            try:
                segments_iter, info = model.transcribe(
                    tmp_path,
                    initial_prompt=hotword_prompt,
                    language=language,  # None = auto-detect
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                )
                segments = []
                full_text = []
                for seg in segments_iter:
                    segments.append(Segment(
                        text=seg.text.strip(),
                        start=seg.start,
                        end=seg.end,
                        confidence=seg.avg_logprob,
                    ))
                    full_text.append(seg.text.strip())

                text = " ".join(full_text)
                lang = info.language if info.language else "en"
                # Map detected language codes
                if lang in ("ur", "urdu"):
                    lang = "ur"
                else:
                    lang = "en"

                # Detect code-switching
                import re
                urdu_chars = len(re.findall(r'[\u0600-\u06FF]', text))
                is_mixed = urdu_chars > 0 and len(text) - urdu_chars > 5

                return STTResult(
                    text=text,
                    language=lang,
                    confidence=min(1.0, max(0.0, info.language_probability)),
                    segments=segments,
                    is_code_switched=is_mixed,
                )
            finally:
                import os
                os.unlink(tmp_path)

        return await asyncio.to_thread(_run)


def preload(model_size: str = "small", device: str = "auto",
            compute_type: str = "int8"):
    """Pre-load the whisper model at startup."""
    engine = WhisperEngine(model_size, device, compute_type)
    asyncio.get_event_loop().run_until_complete(engine._get_model())
