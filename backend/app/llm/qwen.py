"""Qwen-Plus LLM client via OpenAI-compatible API (Alibaba Cloud Model Studio)."""
from __future__ import annotations
import asyncio
import json
import logging
import httpx
from . import LLMResponse, Message, Tool, ToolCall, TokenUsage

log = logging.getLogger("callforge.llm.qwen")

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=15,
            limits=httpx.Limits(max_keepalive_connections=5),
        )
    return _client


async def _post_retry(url: str, **kw) -> httpx.Response:
    """One retry on transient transport errors."""
    try:
        return await _http().post(url, **kw)
    except httpx.TransportError:
        await asyncio.sleep(0.4)
        return await _http().post(url, **kw)


class QwenClient:
    """OpenAI-compatible chat client pointing at Qwen-Plus."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, fallback: "QwenClient | None" = None):
        from ..config import settings
        self.base_url = (base_url or settings.effective_llm_base_url).rstrip("/")
        self.api_key = api_key or settings.effective_llm_api_key
        self.model = model or settings.llm_model
        self.timeout = settings.llm_timeout_s
        # Confirmed live: a provider outage (RunPod pod container gone,
        # Groq 429, etc.) doesn't raise up to the caller -- chat() below
        # already catches it and returns empty content, which the turn
        # engine then renders as an endless "sorry, could you repeat that"
        # for the rest of the call. One automatic retry against a second
        # provider turns a dead call into a degraded-but-working one.
        self.fallback = fallback

    async def chat(self, messages: list[Message], *,
                   json_mode: bool = False,
                   tools: list[Tool] | None = None,
                   tool_choice: str | None = None,
                   max_tokens: int = 160,
                   temperature: float = 0.25) -> LLMResponse:
        result = await self._chat_once(
            messages, json_mode=json_mode, tools=tools, tool_choice=tool_choice,
            max_tokens=max_tokens, temperature=temperature,
        )
        if not result.content and not result.tool_calls and self.fallback is not None:
            log.warning("Primary LLM (%s) returned empty, retrying via fallback", self.base_url)
            result = await self.fallback.chat(
                messages, json_mode=json_mode, tools=tools, tool_choice=tool_choice,
                max_tokens=max_tokens, temperature=temperature,
            )
        return result

    async def _chat_once(self, messages: list[Message], *,
                         json_mode: bool = False,
                         tools: list[Tool] | None = None,
                         tool_choice: str | None = None,
                         max_tokens: int = 160,
                         temperature: float = 0.25) -> LLMResponse:
        body: dict = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tool_choice:
            body["tool_choice"] = tool_choice
        # Groq's gpt-oss/qwen3 models are reasoning models -- by default they
        # spend an uncapped share of max_tokens on a hidden "reasoning" field
        # before emitting visible content, which can burn the entire budget
        # and return empty content on a short-reply budget like ours. Capping
        # reasoning effort keeps latency and token usage predictable for a
        # real-time voice turn.
        if "groq.com" in self.base_url:
            body["reasoning_effort"] = "low"
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        if tools:
            body["tools"] = [{
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            } for t in tools]

        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/chat/completions"

        try:
            r = await _post_retry(url, headers=headers, json=body, timeout=self.timeout)
            if r.status_code >= 400 and json_mode:
                body.pop("response_format", None)
                r = await _post_retry(url, headers=headers, json=body, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()

            choice = data["choices"][0]
            msg = choice["message"]
            content = msg.get("content", "") or ""
            if not content and not msg.get("tool_calls"):
                log.warning("LLM returned empty content: finish_reason=%s reasoning=%r usage=%s",
                            choice.get("finish_reason"), msg.get("reasoning", "")[:300], data.get("usage"))

            # Parse tool calls if present
            tool_calls = []
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc.get("function", {})
                    args = fn.get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, ValueError):
                            args = {}
                    tool_calls.append(ToolCall(
                        id=tc.get("id", ""),
                        name=fn.get("name", ""),
                        arguments=args,
                    ))

            usage_data = data.get("usage", {})
            usage = TokenUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

            return LLMResponse(content=content.strip(), tool_calls=tool_calls, usage=usage)

        except Exception as exc:
            log.warning("LLM call failed: %s", exc)
            return LLMResponse(content="", tool_calls=[], usage=TokenUsage())


async def classify_json(prompt: str) -> dict | None:
    """One-shot JSON classification utility."""
    client = QwenClient()
    response = await client.chat(
        [Message(role="user", content=prompt)],
        json_mode=True,
        max_tokens=180,
    )
    if not response.content:
        return None
    try:
        raw = response.content
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < 0:
            return None
        return json.loads(raw[start:end + 1])
    except (ValueError, AttributeError):
        log.warning("LLM returned unparseable JSON: %r", response.content)
        return None
