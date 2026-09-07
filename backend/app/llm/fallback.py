"""Scripted fallback LLM -- used when no LLM backend is configured.

Provides basic conversational responses using templates so the demo
never stalls on a missing model.
"""
from __future__ import annotations
import logging
from . import LLMResponse, Message, Tool, TokenUsage

log = logging.getLogger("callforge.llm.fallback")


# Template responses by detected intent keywords -- used only when no real
# LLM is configured, so a persona's actual pitch/knowledge never reaches
# these; they exist purely so the demo never stalls on a missing model.
_TEMPLATES = {
    "price": "[[emotion:confident]] Happy to walk you through pricing -- what does your team need most out of this?",
    "objection": "[[emotion:empathetic]] Totally fair. Mind if I ask what's driving that, so I'm not wasting your time?",
    "booking": "[[emotion:enthusiastic]] I'd love to set that up -- let me check what times we have open.",
    "escalate": "[[emotion:warm]] Of course -- let me connect you with someone who can go deeper on that.",
    "greeting": "[[emotion:warm]] Hey, thanks for picking up -- got a quick minute?",
    "default": "[[emotion:confident]] Good question -- tell me a bit more about what you're working with?",
}


def _match_template(text: str) -> str:
    """Simple keyword matching for fallback responses."""
    lower = text.lower()
    if any(w in lower for w in ("price", "cost", "charge", "expensive", "budget")):
        return _TEMPLATES["price"]
    if any(w in lower for w in ("not interested", "no time", "busy", "already use")):
        return _TEMPLATES["objection"]
    if any(w in lower for w in ("book", "meeting", "appointment", "schedule", "call back")):
        return _TEMPLATES["booking"]
    if any(w in lower for w in ("human", "supervisor", "manager", "escalat")):
        return _TEMPLATES["escalate"]
    if any(w in lower for w in ("hello", "hi", "hey")):
        return _TEMPLATES["greeting"]
    return _TEMPLATES["default"]


class FallbackClient:
    """Scripted fallback -- no network calls, instant responses."""

    async def chat(self, messages: list[Message], *,
                   json_mode: bool = False,
                   tools: list[Tool] | None = None,
                   max_tokens: int = 160,
                   temperature: float = 0.25) -> LLMResponse:
        # Use the last user message for matching
        user_text = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_text = msg.content
                break

        if json_mode:
            # Return a minimal JSON response
            content = '{"intent": "other", "confidence": 0.5}'
        else:
            content = _match_template(user_text)

        return LLMResponse(content=content, tool_calls=[], usage=TokenUsage())
