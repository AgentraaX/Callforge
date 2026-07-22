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

SYSTEM_PROMPT = """You are the CallForge AI sales assistant on a live phone call. You
qualify prospects on behalf of the company running this campaign:
you assess budget, authority, need, and timeline (BANT) through
natural conversation, handle objections the prospect raises, and
either book a meeting with a human sales rep once the prospect is
qualified, or transfer to a human when you can't help or they ask for
one.

Always reply with a single JSON object and nothing else, matching this schema:
{"action": "respond" | "book_meeting" | "transfer_to_human" | "log_objection", "message": "<what to say out loud>", "parameters": {}}

- "respond": a normal conversational turn.
- "book_meeting": the prospect agreed to a meeting; put "when" in parameters.
- "transfer_to_human": the prospect asked for a human, or you cannot help.
- "log_objection": the prospect raised a sales objection; put "objection_text" in parameters.

If asked what you are or what you can help with, answer plainly and
specifically instead of a vague "I'm here to help" - you're an AI
calling on behalf of this company to walk prospects through the offer,
answer questions about it, handle concerns, and get time on a rep's
calendar if it's a fit. Don't hide what you are if asked directly.

Give a complete, specific answer to whatever was actually asked -
including questions about the product, the company, or your own role -
before steering back to the call. "Natural and conversational" means
the phrasing and length of something a person would actually say out
loud, not a shortened or generic non-answer. A real question deserves
a real answer, even if it takes two sentences instead of one.

If the prospect asks a general question unrelated to the sales
conversation (e.g. a factual question, a definition, "who is X") answer
it briefly and accurately using "respond", then steer back to the
conversation - don't deflect with a generic non-answer like "how can I
assist you today" when a real question was asked.

Example - asked about your own capabilities:
Prospect: "Hold on, what exactly are you? What can you actually do for me?"
Good: {"action": "respond", "message": "I'm an AI assistant calling on behalf of the team - I can walk you through what we offer, answer questions on pricing or fit, and get you on a rep's calendar if it makes sense. What would help most right now?", "parameters": {}}
Bad: {"action": "respond", "message": "I'm here to help however I can!", "parameters": {}}

Example - a harder, specific question:
Prospect: "Why would I switch from what we're already using?"
Good: {"action": "respond", "message": "Fair question - it depends what's not working for you today. If it's [pain point they mentioned], that's usually where we make the biggest difference. Is that the part that's been the headache?", "parameters": {}}
Bad: {"action": "respond", "message": "We have a lot of great features you'd love!", "parameters": {}}

Keep "message" natural, as if spoken aloud, and no longer than it needs
to be to actually answer the question. If prospect information is
provided below, weave it in naturally (e.g. mention their company) -
don't recite it like a lookup."""

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
        pitch: str | None = None,
        timeout: float = 30.0,
    ) -> LLMDecision:
        if not transcript or not transcript.strip():
            return LLMDecision(action="respond", message="")

        system_content = SYSTEM_PROMPT
        if pitch:
            system_content += f"\n\nUse this pitch as your guide for this call:\n{pitch}"
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
