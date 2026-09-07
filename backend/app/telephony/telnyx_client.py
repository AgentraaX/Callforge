"""Thin Telnyx wrapper -- places the real outbound call via Telnyx's Call
Control API, with bidirectional audio streaming straight to our
/ws/telnyx-media WebSocket. Unlike Twilio, Telnyx starts streaming as soon
as the call is dialed (stream_url/stream_track/stream_bidirectional_* are
call-create parameters) -- no separate TwiML-style answer webhook needed.

Calls always originate from CallForge's own Telnyx number (settings.
telnyx_from_number). Bringing your own caller ID is a Telnyx Verified
Caller ID flow, deferred to Phase 2 (see SALES_AGENT_SPEC.md).
"""
from __future__ import annotations
import logging

import httpx

log = logging.getLogger("callforge.telephony.telnyx")


def place_call(to_number: str, call_id: str, persona_id: str) -> str:
    """Places the real outbound call via the Telnyx Call Control API.

    Returns the Telnyx call_control_id. Raises RuntimeError if Telnyx
    isn't configured or the API call fails -- callers should turn this
    into a clean 4xx/5xx for the dialer UI, not a silent failure mid-call.
    """
    from ..config import settings

    if not settings.telnyx_configured:
        raise RuntimeError("Telnyx is not configured (API key/connection ID/from number).")
    if not settings.public_base_url:
        raise RuntimeError("PUBLIC_BASE_URL is not set -- Telnyx can't reach our webhooks/media stream.")

    ws_base = settings.public_base_url.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_base}/ws/telnyx-media?call_id={call_id}&persona_id={persona_id}"
    webhook_url = f"{settings.public_base_url}/api/telephony/telnyx-status?call_id={call_id}"

    resp = httpx.post(
        "https://api.telnyx.com/v2/calls",
        headers={"Authorization": f"Bearer {settings.telnyx_api_key}"},
        json={
            "connection_id": settings.telnyx_connection_id,
            "to": to_number,
            "from": settings.telnyx_from_number,
            "webhook_url": webhook_url,
            "stream_url": stream_url,
            "stream_track": "both_tracks",
            "stream_bidirectional_mode": "rtp",
            "stream_bidirectional_codec": "PCMU",
        },
        timeout=15,
    )
    if resp.status_code >= 400:
        log.warning("Telnyx call failed: %s %s", resp.status_code, resp.text)
        raise RuntimeError(f"Telnyx rejected the call ({resp.status_code}): {resp.text[:200]}")

    call_control_id = resp.json()["data"]["call_control_id"]
    log.info("Telnyx call placed: call_id=%s call_control_id=%s to=%s", call_id, call_control_id, to_number)
    return call_control_id
