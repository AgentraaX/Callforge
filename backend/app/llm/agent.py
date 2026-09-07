"""Alibaba Cloud Model Studio Agent Application -- RAG-powered agent.

This is the 'agent + knowledge base' flow that hackathon judges evaluate.
Falls back gracefully if dashscope SDK is missing or quota exceeded.
"""
from __future__ import annotations
import asyncio
import logging
from . import AgentResponse

log = logging.getLogger("callforge.llm.agent")


async def ask_agent(prompt: str, session_id: str | None = None) -> AgentResponse:
    """Call the Model Studio Agent Application.

    Returns AgentResponse with answer and session_id for multi-turn.
    Returns empty AgentResponse on any failure -- caller falls back to local KB.
    """
    from ..config import settings

    if not settings.dashscope_api_key or not settings.dashscope_app_id:
        return AgentResponse()

    try:
        import dashscope

        def _call():
            return dashscope.Application.call(
                api_key=settings.dashscope_api_key,
                app_id=settings.dashscope_app_id,
                prompt=prompt,
                session_id=session_id,
            )

        resp = await asyncio.to_thread(_call)

        if getattr(resp, "status_code", None) != 200:
            log.warning("Model Studio agent call failed: %s",
                        getattr(resp, "message", resp))
            return AgentResponse()

        output = resp.output
        text = getattr(output, "text", None) or (
            output.get("text") if isinstance(output, dict) else None)
        new_sid = getattr(output, "session_id", None) or (
            output.get("session_id") if isinstance(output, dict) else None)

        # Extract sources if available
        sources = []
        refs = getattr(output, "doc_references", None)
        if refs:
            sources = [r.get("title", "") for r in refs if r.get("title")]

        return AgentResponse(
            answer=text.strip() if text else None,
            session_id=new_sid,
            sources=sources,
        )
    except Exception as exc:
        log.warning("Model Studio agent unavailable: %s", exc)
        return AgentResponse()
