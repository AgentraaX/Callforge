"""Barge-in / interruption detection (VAD). Built Day 12."""

import logging

logger = logging.getLogger("agent.pipeline.vad")


class BargeInDetector:
    def __init__(self) -> None:
        raise NotImplementedError("Wire up VAD-based barge-in detection — Day 12")
