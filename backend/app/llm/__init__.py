"""LLM client abstraction -- Protocol + factory."""
from __future__ import annotations
from typing import Protocol, runtime_checkable, Any
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)


@dataclass
class AgentResponse:
    answer: str | None = None
    session_id: str | None = None
    sources: list[str] = field(default_factory=list)


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None
    tool_call_id: str | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]


@runtime_checkable
class LLMClient(Protocol):
    async def chat(self, messages: list[Message], *,
                   json_mode: bool = False,
                   tools: list[Tool] | None = None,
                   max_tokens: int = 160,
                   temperature: float = 0.25) -> LLMResponse: ...


def available() -> bool:
    """Check if any LLM backend is configured."""
    from ..config import settings
    return bool(settings.effective_llm_base_url)


def agent_available() -> bool:
    """Check if Model Studio Agent Application is configured."""
    from ..config import settings
    return bool(settings.dashscope_api_key and settings.dashscope_app_id)


def create_client() -> LLMClient:
    """Factory: create the appropriate LLM client.

    Wires the Groq fallback client in as a retry target -- confirmed live
    that a primary-provider outage (RunPod pod container gone, etc.)
    doesn't raise, it just returns empty content forever, which renders
    as an endless "sorry, could you repeat that" for the rest of the
    call. One automatic retry against Groq keeps a call working instead.
    Skipped when the primary IS already Groq (nothing to fall back to).
    """
    from ..config import settings
    if settings.effective_llm_base_url:
        from .qwen import QwenClient
        fallback = None
        if "groq.com" not in settings.effective_llm_base_url:
            fallback = create_urdu_fallback_client()
        return QwenClient(fallback=fallback)
    from .fallback import FallbackClient
    return FallbackClient()


def create_urdu_fallback_client() -> LLMClient | None:
    """A separate, larger-model LLM client used ONLY for turns detected as
    Urdu -- confirmed live that the small local-GPU model produces broken,
    hallucinated Urdu while Groq's larger model stays fluent and grounded.
    Returns None if no key is configured, so callers fall back to the
    regular (local-GPU) client and English keeps working either way."""
    from ..config import settings
    api_key = settings.urdu_llm_api_key or settings.groq_api_key
    if not api_key:
        return None
    from .qwen import QwenClient
    return QwenClient(
        base_url=settings.urdu_llm_base_url,
        api_key=api_key,
        model=settings.urdu_llm_model,
    )
