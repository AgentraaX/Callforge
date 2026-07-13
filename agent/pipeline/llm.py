"""vLLM (Qwen2.5-7B-AWQ) client, JSON-mode / function-calling only. Built Day 5."""

import logging

logger = logging.getLogger("agent.pipeline.llm")


class QwenLLM:
    def __init__(self) -> None:
        raise NotImplementedError("Wire up vLLM OpenAI-compatible client — Day 5")

    async def generate(self, transcript: str, tools: list):
        raise NotImplementedError
