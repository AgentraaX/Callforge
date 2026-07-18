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


def create_manager_whisper_token(
    main_room_name: str, identity: str, ttl: timedelta = DEFAULT_TOKEN_TTL
) -> str:
    """Day 10 Ghost Mode: a token scoped to the *whisper* room only.

    A manager is never issued a token for the main call room at all —
    isolation is by room membership, not a permission flag that could
    race.

    Deliberately NOT setting `hidden=True` here: testing showed a hidden
    participant's track subscription silently breaks — the server never
    tells other participants (including our own agent, in a *different*
    job/thread, subscribing from the whisper room) that a hidden
    identity exists, so the track arrives before the participant does
    and LiveKit logs "received track from an unknown participant" and
    drops it. Since the manager already can't be seen by the prospect
    (they're never in the same room), `hidden` would only have been
    extra defense-in-depth — not worth it given it breaks the feature.
    """
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise RuntimeError("LIVEKIT_API_KEY / LIVEKIT_API_SECRET not set")

    whisper_room = f"{main_room_name}-whisper"
    token = (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_ttl(ttl)
        .with_grants(api.VideoGrants(room_join=True, room=whisper_room))
    )
    logger.info("Issued manager whisper token", extra={"whisper_room": whisper_room, "identity": identity})
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


async def enable_ghost_mode(main_room_name: str) -> None:
    """Day 10: creates the whisper room (with its own agent dispatch) for a
    call that's already in progress, so a manager can start listening in.

    This is what a "join call silently" button on the dashboard would
    trigger — the manager is only ever issued a token for the room this
    creates (create_manager_whisper_token), never the main call room.
    """
    await create_room(f"{main_room_name}-whisper", empty_timeout=300)
