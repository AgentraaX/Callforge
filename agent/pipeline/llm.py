"""LLM: Qwen2.5 via an OpenAI-compatible endpoint (Ollama locally, vLLM in prod).

Constrained to JSON-mode structured output only, per the spec doc's Week 1
hallucination risk note - no free-form generation until the playbook (Day 6
LangGraph work) is proven.
"""

import asyncio
import json
import logging

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from config import settings

logger = logging.getLogger("agent.pipeline.llm")

SYSTEM_PROMPT = """You are the CallForge AI sales assistant on a live phone call.
Always reply with a single JSON object and nothing else, matching this schema:
{"action": "respond" | "book_meeting" | "transfer_to_human" | "log_objection", "message": "<what to say out loud>", "parameters": {}}

- "respond": a normal conversational turn.
- "book_meeting": the prospect agreed to a meeting; put "when" in parameters.
- "transfer_to_human": the prospect asked for a human, or you cannot help.
- "log_objection": the prospect raised a sales objection; put "objection_text" in parameters.

Keep "message" short and natural, as if spoken aloud. If prospect
information is provided below, weave it in naturally (e.g. mention their
company) - don't recite it like a lookup."""

_FALLBACK_MESSAGE = "Sorry, could you say that again?"


class LLMDecision(BaseModel):
    action: str = "respond"
    message: str = ""
    parameters: dict = {}


class QwenLLM:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY)

    # CPU-only Qwen2.5:7B via Ollama runs 5-20s per turn on this laptop
    # (no GPU); a real vLLM+AWQ endpoint targets ~150ms. Timeout is generous
    # to match the current hardware, not the eventual latency budget.
    async def generate(
        self,
        transcript: str,
        enrichment: dict | None = None,
        manager_note: str | None = None,
        timeout: float = 30.0,
    ) -> LLMDecision:
        if not transcript or not transcript.strip():
            return LLMDecision(action="respond", message="")

        system_content = SYSTEM_PROMPT
        if enrichment:
            system_content += f"\n\nKnown information about this prospect: {json.dumps(enrichment)}"
        if manager_note:
            system_content += (
                f"\n\nYour manager is privately listening and just told you: "
                f'"{manager_note}". Factor this into your reply, but never reveal '
                f"that a manager is involved or that you received guidance."
            )

        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=settings.LLM_MODEL,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": transcript},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    # Ollama-specific: keep the model resident so a gap between
                    # calls doesn't force a ~20s cold reload on the next turn.
                    # Ignored by a real OpenAI-compatible vLLM server.
                    extra_body={"keep_alive": "30m"},
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.error("LLM request timed out", extra={"transcript": transcript, "timeout": timeout})
            return LLMDecision(action="respond", message=_FALLBACK_MESSAGE)
        except Exception:
            logger.exception("LLM request failed", extra={"transcript": transcript})
            return LLMDecision(action="respond", message=_FALLBACK_MESSAGE)

        raw = response.choices[0].message.content
        try:
            decision = LLMDecision(**json.loads(raw))
        except (json.JSONDecodeError, ValidationError, TypeError):
            logger.error("LLM returned invalid JSON", extra={"raw": raw})
            return LLMDecision(action="respond", message=_FALLBACK_MESSAGE)

        return decision
