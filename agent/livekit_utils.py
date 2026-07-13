"""Room creation + access-token helpers for LiveKit. Built Day 2.

Tokens are short-lived (default 10 min) and scoped to a single room via
VideoGrants(room_join=True, room=<name>) — no client should ever receive
a token that lets it join arbitrary rooms.
"""

import logging
from datetime import timedelta

from livekit import api

from config import settings

logger = logging.getLogger("agent.livekit_utils")

DEFAULT_TOKEN_TTL = timedelta(minutes=10)


def create_room_token(room_name: str, identity: str, ttl: timedelta = DEFAULT_TOKEN_TTL) -> str:
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise RuntimeError("LIVEKIT_API_KEY / LIVEKIT_API_SECRET not set")

    token = (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_ttl(ttl)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
    )
    logger.info("Issued room token", extra={"room": room_name, "identity": identity, "ttl": str(ttl)})
    return token.to_jwt()


async def create_room(room_name: str, empty_timeout: int = 300) -> None:
    """Create/confirm a room and request our voice agent be dispatched into it.

    Without an explicit RoomAgentDispatch, LiveKit does not auto-join any
    worker to a new room — dispatch is opt-in per room, not global.
    """
    http_url = settings.LIVEKIT_URL.replace("ws://", "http://").replace("wss://", "https://")
    async with api.LiveKitAPI(http_url, settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET) as lk:
        await lk.room.create_room(
            api.CreateRoomRequest(
                name=room_name,
                empty_timeout=empty_timeout,
                agents=[api.RoomAgentDispatch(agent_name=settings.LIVEKIT_AGENT_NAME)],
            )
        )
        logger.info("Room created, agent dispatch requested", extra={"room": room_name})
