"""Day 13: Chatterbox-Turbo voice cloning for a demo voice.

This is a standalone/offline capability (generate a demo sample in a
cloned voice), not wired into the live call pipeline like Kokoro is.
Chatterbox is a diffusion-based model - far heavier than Kokoro, and
with no GPU on this machine, a single utterance can take well over a
minute to synthesize. That's fine for producing a one-off demo clip,
not for a live conversational turn budget.

Consent: the reference clip (audio_prompt_path) must come from someone
who has explicitly consented to having their voice cloned for this
product. Until a real, consented sample is provided, use a synthetic
placeholder (e.g. a Windows SAPI-generated clip, as agent/pipeline/
tests use) - never a real person's voice without their permission.

Every output is watermarked via Resemble AI's Perth watermarker
(bundled as a dependency), so a cloned clip can later be identified as
AI-generated even after re-encoding - see verify_watermark() below.
"""

import logging

logger = logging.getLogger("agent.pipeline.voice_clone")


class ChatterboxVoiceClone:
    def __init__(self, reference_clip_path: str, device: str = "cpu") -> None:
        # Deferred import: chatterbox pulls in torch/transformers/diffusers,
        # multi-GB and slow to import, so don't pay that cost unless this
        # class is actually used.
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        logger.info(
            "Loading Chatterbox-Turbo model (CPU - this can take a while)",
            extra={"device": device, "reference_clip": reference_clip_path},
        )
        self._model = ChatterboxTurboTTS.from_pretrained(device=device)
        self._reference_clip_path = reference_clip_path

    def generate(self, text: str):
        """Returns (waveform_tensor, sample_rate). Slow (CPU, diffusion) -
        expect well over a minute per short sentence on this hardware."""
        logger.info("Synthesizing in cloned voice", extra={"text": text})
        wav = self._model.generate(text, audio_prompt_path=self._reference_clip_path)
        return wav, self._model.sr


def verify_watermark(audio_path: str) -> str | None:
    """Reads back the Perth watermark from a generated clip, proving it's
    identifiable as AI-generated even after the file has been saved/moved."""
    import librosa
    import perth

    audio, sr = librosa.load(audio_path, sr=None)
    watermarker = perth.PerthImplicitWatermarker()
    return watermarker.get_watermark(audio, sample_rate=sr)
