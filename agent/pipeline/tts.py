"""Kokoro streaming TTS wrapper. Built Day 6."""

import logging

logger = logging.getLogger("agent.pipeline.tts")


class KokoroTTS:
    def __init__(self) -> None:
        raise NotImplementedError("Wire up Kokoro streaming synthesis — Day 6")

    async def synthesize_stream(self, text: str):
        raise NotImplementedError
