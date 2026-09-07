"""Real-time event bus -- broadcasts call state to dashboard WebSocket clients."""
from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import Any
from fastapi import WebSocket

log = logging.getLogger("callforge.realtime.bus")


class EventBus:
    """Manages active calls and broadcasts updates to dashboard clients."""

    def __init__(self):
        self.calls: dict[str, dict] = {}  # call_id -> call doc
        self._dashboards: list[WebSocket] = []
        self.caller_memory: dict[str, dict] = {}  # caller_id -> memory

    def open_call(self, call_id: str, caller: str = "Unknown",
                  owner_email: str = "", org_id: str | None = None) -> dict:
        """Create a new call document.

        ``owner_email`` / ``org_id`` (set by the authenticated dial/token
        request) let the CRM ingest hook attribute the finished call to the
        right org -- see ``app/crm/ingest.py``.
        """
        call = {
            "id": call_id,
            "state": "ringing",
            "caller": caller,
            "owner_email": owner_email,
            "org_id": org_id,
            "agent": None,
            "transcript": [],
            "lead": None,
            "intents": [],
            "lookups": [],
            "escalated": False,
            "case_id": None,
            "language": "en",
            "summary": None,
            "has_recording": False,
            "transfers": 0,
            "started_at": time.time(),
            "rating": None,
        }
        self.calls[call_id] = call
        return call

    async def update(self, call: dict):
        """Broadcast updated call state to all dashboard clients."""
        msg = json.dumps({"type": "call_update", "call": call}, default=str)
        dead = []
        for ws in self._dashboards:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._dashboards.remove(ws)

    async def close_call(self, call_id: str):
        """Mark a call as ended and notify dashboards."""
        call = self.calls.get(call_id)
        if call:
            call["state"] = "ended"
            await self.update(call)

    async def rate_call(self, call_id: str, stars: int):
        """Record a caller rating."""
        call = self.calls.get(call_id)
        if call:
            call["rating"] = stars
            await self.update(call)

    async def attach(self, ws: WebSocket):
        """Attach a dashboard client and send current state."""
        self._dashboards.append(ws)
        # Send current snapshot
        snapshot = json.dumps({
            "type": "snapshot",
            "calls": list(self.calls.values()),
        }, default=str)
        await ws.send_text(snapshot)

    def detach(self, ws: WebSocket):
        """Remove a dashboard client."""
        if ws in self._dashboards:
            self._dashboards.remove(ws)


# Singleton
bus = EventBus()
