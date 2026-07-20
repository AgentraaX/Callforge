"""Public "talk to the AI" widget for the landing page. No auth - a
visitor isn't logged in.

Not rate-limited: every call here creates a real LiveKit room and
dispatches the actual voice-AI pipeline (LLM + TTS), which costs real
money and compute per invocation. Fine for an internal/dev pass; before
this is exposed on the open internet it needs a per-IP or similar
throttle - flagged here, not solved in this pass.
"""
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.livekit_rooms import create_participant_token, create_room, livekit_url

logger = logging.getLogger("api.routers.demo")

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoCallToken(BaseModel):
    room_name: str
    token: str
    livekit_url: str


@router.post("/call/start", response_model=DemoCallToken)
async def start_demo_call():
    room_name = f"demo-{uuid.uuid4()}"
    identity = f"visitor-{uuid.uuid4()}"

    try:
        await create_room(room_name)
        token = create_participant_token(room_name, identity=identity)
        url = livekit_url()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Failed to create demo room")
        raise HTTPException(status_code=503, detail="LiveKit is unavailable right now")

    return DemoCallToken(room_name=room_name, token=token, livekit_url=url)
