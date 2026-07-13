"""Whisper.cpp streaming STT wrapper. Built Day 4."""

import logging

logger = logging.getLogger("agent.pipeline.stt")


class WhisperSTT:
    def __init__(self) -> None:
        raise NotImplementedError("Wire up whisper.cpp streaming client — Day 4")

    async def transcribe_stream(self, audio_chunk: bytes):
        raise NotImplementedError
