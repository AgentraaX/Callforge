"""Call logs, transcript, Ghost Mode takeover, live stream endpoints. Built Day 4."""

from fastapi import APIRouter

router = APIRouter(prefix="/calls", tags=["calls"])
