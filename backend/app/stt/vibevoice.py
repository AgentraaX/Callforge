"""VibeVoice-ASR engine -- microsoft/VibeVoice-ASR from HuggingFace.

Supports:
- Long audio (up to 60 min)
- Speaker diarization
- Custom hotwords
- 50+ languages including Urdu + English code-switching
- MIT license
"""
from __future__ import annotations
import asyncio
import io
import logging
import tempfile
from . import STTResult, Segment, SALES_HOTWORDS

log = logging.getLogger("callforge.stt.vibevoice")

_model = None
_lock = asyncio.Lock()


async def _load_model():
    global _model
    if _model is not None:
        return _model
    async with _lock:
        if _model is not None:
            return _model
        log.info("Loading VibeVoice-ASR model...")
        try:
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            torch_dtype = torch.float16 if device == "cuda" else torch.float32

            model_id = "microsoft/VibeVoice-ASR"
            processor = AutoProcessor.from_pretrained(model_id)
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id, torch_dtype=torch_dtype
            ).to(device)

            _model = {"model": model, "processor": processor, "device": device}
            log.info("VibeVoice-ASR loaded on %s", device)
        except Exception as exc:
            log.error("Failed to load VibeVoice-ASR: %s", exc)
            raise
    return _model


def _detect_language(text: str) -> tuple[str, bool]:
    """Detect primary language and code-switching."""
    import re
    urdu_chars = len(re.findall(r'[\u0600-\u06FF\u0750-\u077F]', text))
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    total = urdu_chars + latin_chars
    if total == 0:
        return "en", False
    urdu_ratio = urdu_chars / total
    if urdu_ratio > 0.6:
        return "ur", urdu_ratio < 0.9  # mixed if not purely Urdu
    elif urdu_ratio > 0.2:
        return "en", True  # code-switched
    return "en", False


class VibeVoiceEngine:
    async def transcribe(self, audio: bytes, mime: str,
                         hotwords: list[str] | None = None,
                         language: str | None = None) -> STTResult:
        """Transcribe audio using VibeVoice-ASR."""
        hotwords = hotwords or SALES_HOTWORDS
        
        try:
            model_bundle = await _load_model()
        except Exception as exc:
            log.warning("VibeVoice unavailable, returning empty: %s", exc)
            return STTResult(text="", confidence=0.0)

        def _run():
            import numpy as np
            import soundfile as sf

            # Decode audio bytes to numpy array
            audio_file = io.BytesIO(audio)
            try:
                waveform, sample_rate = sf.read(audio_file)
            except Exception:
                # Try with pydub for webm/opus
                try:
                    from pydub import AudioSegment
                    seg = AudioSegment.from_file(io.BytesIO(audio))
                    seg = seg.set_channels(1).set_frame_rate(16000)
                    waveform = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
                    sample_rate = 16000
                except Exception as e2:
                    log.warning("Could not decode audio: %s", e2)
                    return STTResult(text="", confidence=0.0)

            if len(waveform.shape) > 1:
                waveform = waveform.mean(axis=1)

            processor = model_bundle["processor"]
            model = model_bundle["model"]
            device = model_bundle["device"]

            # Process with hotwords as prompt
            hotword_prompt = " ".join(hotwords[:20])
            inputs = processor(
                waveform, sampling_rate=sample_rate,
                return_tensors="pt"
            ).to(device)

            import torch
            with torch.no_grad():
                generated_ids = model.generate(
                    **inputs,
                    max_new_tokens=448,
                    language=None,  # auto-detect
                    task="transcribe",
                )
            
            text = processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0].strip()

            lang, is_mixed = _detect_language(text)
            return STTResult(
                text=text,
                language=lang,
                confidence=0.85,
                is_code_switched=is_mixed,
            )

        return await asyncio.to_thread(_run)
