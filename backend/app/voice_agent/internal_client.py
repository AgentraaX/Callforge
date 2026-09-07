"""HTTP client the LiveKit agent worker uses to reach the FastAPI
backend's shared state (personas, leads, bookings, escalations, the live
dashboard bus).

The agent worker is a SEPARATE OS process from the backend (by design --
see SALES_AGENT_SPEC.md, "no inbound ports" is what lets it run anywhere).
That means it cannot import conversation.personas / realtime.bus / sales.*
and expect to see the same data -- those are in-memory stores that only
exist inside the backend process's own memory. Every read/write that
needs to be visible to the REST API or the dashboard goes through here.
"""
from __future__ import annotations
import logging
from types import SimpleNamespace

import httpx

from ..config import settings

log = logging.getLogger("callforge.voice_agent.internal_client")

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=15)
    return _client


def _base_url() -> str:
    return (settings.internal_backend_url or "http://localhost:8000").rstrip("/")


def _headers() -> dict:
    return {"X-Internal-Key": settings.internal_api_key}


async def get_persona(persona_id: str) -> SimpleNamespace | None:
    try:
        resp = await _http().get(f"{_base_url()}/internal/personas/{persona_id}", headers=_headers())
        resp.raise_for_status()
        return SimpleNamespace(**resp.json())
    except Exception as exc:
        log.warning("get_persona(%s) failed: %s", persona_id, exc)
        return None


async def append_transcript(call_id: str, who: str, name: str, text: str) -> None:
    try:
        await _http().post(
            f"{_base_url()}/internal/calls/{call_id}/transcript",
            json={"who": who, "name": name, "text": text}, headers=_headers(),
        )
    except Exception as exc:
        log.warning("append_transcript failed: %s", exc)


async def update_state(call_id: str, state: str) -> None:
    try:
        await _http().post(
            f"{_base_url()}/internal/calls/{call_id}/state",
            json={"state": state}, headers=_headers(),
        )
    except Exception as exc:
        log.warning("update_state failed: %s", exc)


async def finalize_call(call_id: str) -> None:
    """Ask the backend to mirror this finished call into the CRM store."""
    try:
        await _http().post(
            f"{_base_url()}/internal/calls/{call_id}/finalize", headers=_headers(),
        )
    except Exception as exc:
        log.warning("finalize_call failed: %s", exc)


async def extract_lead(call_id: str, text: str, caller_name: str) -> None:
    try:
        await _http().post(
            f"{_base_url()}/internal/calls/{call_id}/lead-extract",
            json={"text": text, "caller_name": caller_name}, headers=_headers(),
        )
    except Exception as exc:
        log.warning("extract_lead failed: %s", exc)


async def escalate(call_id: str, reason: str, caller_name: str) -> str:
    """Returns the pre-formatted escalation speech, ready to speak verbatim."""
    try:
        resp = await _http().post(
            f"{_base_url()}/internal/calls/{call_id}/escalate",
            json={"reason": reason, "caller_name": caller_name}, headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("speech", "")
    except Exception as exc:
        log.warning("escalate failed: %s", exc)
        return (
            "I understand this needs personal attention -- let me connect you "
            "with someone who can help directly."
        )


async def confirm_booking(call_id: str, slot_id: str, slot_label: str,
                          contact_name: str, purpose: str,
                          contact_phone: str | None = None,
                          contact_email: str | None = None) -> str:
    """Returns the pre-formatted booking confirmation, ready to speak verbatim."""
    try:
        resp = await _http().post(
            f"{_base_url()}/internal/bookings/confirm",
            json={
                "call_id": call_id, "slot_id": slot_id, "slot_label": slot_label,
                "contact_name": contact_name, "purpose": purpose,
                "contact_phone": contact_phone, "contact_email": contact_email,
            },
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("speech", "")
    except Exception as exc:
        log.warning("confirm_booking failed: %s", exc)
        return "Sorry, I wasn't able to confirm that booking -- let me follow up separately."
