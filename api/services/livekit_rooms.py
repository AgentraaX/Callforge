"""LiveKit room/token helpers for the API service - used by:
- POST /calls/{id}/monitor (manager listen-in on a live call)
- POST /demo/call/start (public landing-page "talk to the AI" widget)

Deliberately NOT reusing agent/livekit_utils.py's Ghost Mode functions
(enable_ghost_mode / create_manager_whisper_token) for the monitor case:
those join the manager to a *separate* "{room}-whisper" room used for a
different feature - a one-way voice-to-text channel where the manager's
own speech is transcribed and fed to the AI as a private hint (see
agent/whisper_channel.py). No audio from the main call is ever piped into
that room, so it cannot be used to let a manager listen to the live call.
create_listener_token below mints a token for the *actual* call room
instead, with publish explicitly disabled - a true listen-only join.

create_room/create_participant_token ARE small, deliberate ports of
agent/livekit_utils.py's create_room/create_room_token (same behavior,
default full-duplex grants) - used by the public demo endpoint, which
needs a real two-way conversation.

Everything here is a reimplementation rather than an import of
agent/livekit_utils.py: that module does `from config import settings`,
which only resolves because the agent process runs with WORKDIR
/app/agent (see docker/Dockerfile.agent) - importing it from this service
(run from the repo root) would break that bare import.
"""
import logging
import os
from datetime import timedelta

from livekit import api

logger = logging.getLogger("api.services.livekit_rooms")

DEFAULT_TOKEN_TTL = timedelta(minutes=10)


def _livekit_credentials() -> tuple[str, str, str]:
    url = os.getenv("LIVEKIT_URL", "")
    key = os.getenv("LIVEKIT_API_KEY", "")
    secret = os.getenv("LIVEKIT_API_SECRET", "")
    if not url or not key or not secret:
        raise RuntimeError("LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET not set")
    return url, key, secret


def create_listener_token(room_name: str, identity: str, ttl: timedelta = DEFAULT_TOKEN_TTL) -> str:
    """Subscribe-only token for `room_name` - can_publish/can_publish_data
    are explicitly False (VideoGrants defaults both to True), so a manager
    holding this token can hear the call but never speak into it or
    otherwise affect it. The room isn't (re)created here: an active call
    already has its room created by the agent (agent/livekit_utils.py:
    create_room, called at call start) - this only mints a token for it."""
    _, key, secret = _livekit_credentials()
    token = (
        api.AccessToken(key, secret)
        .with_identity(identity)
        .with_ttl(ttl)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=False,
                can_publish_data=False,
                can_subscribe=True,
            )
        )
    )
    logger.info("Issued listen-only token", extra={"room": room_name, "identity": identity})
    return token.to_jwt()


def livekit_url() -> str:
    url, _, _ = _livekit_credentials()
    return url


def create_participant_token(room_name: str, identity: str, ttl: timedelta = DEFAULT_TOKEN_TTL) -> str:
    """Full-duplex token (default VideoGrants: can_publish/can_subscribe
    both True) - for a real participant in the call, e.g. the public AI
    demo widget's visitor (POST /demo/call/start), who needs to both speak
    and listen. Mirrors agent/livekit_utils.py's create_room_token."""
    _, key, secret = _livekit_credentials()
    token = (
        api.AccessToken(key, secret)
        .with_identity(identity)
        .with_ttl(ttl)
        .with_grants(api.VideoGrants(room_join=True, room=room_name))
    )
    logger.info("Issued participant token", extra={"room": room_name, "identity": identity})
    return token.to_jwt()


async def create_room(room_name: str, empty_timeout: int = 300) -> None:
    """Create/confirm a room and request the voice agent be dispatched into
    it - without an explicit RoomAgentDispatch, LiveKit does not auto-join
    any worker to a new room. Mirrors agent/livekit_utils.py's create_room."""
    url, key, secret = _livekit_credentials()
    http_url = url.replace("ws://", "http://").replace("wss://", "https://")
    agent_name = os.getenv("LIVEKIT_AGENT_NAME", "callforge-voice-agent")

    async with api.LiveKitAPI(http_url, key, secret) as lk:
        await lk.room.create_room(
            api.CreateRoomRequest(
                name=room_name,
                empty_timeout=empty_timeout,
                agents=[api.RoomAgentDispatch(agent_name=agent_name)],
            )
        )
        logger.info("Room created, agent dispatch requested", extra={"room": room_name})
