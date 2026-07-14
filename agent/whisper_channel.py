"""Day 10 Ghost Mode: the manager's whisper channel to the agent.

Architecture: the manager is never a participant in the prospect's call
room at all — they join a *separate* room, "{main_room}-whisper", which
gets its own agent dispatch (agent/livekit_utils.py:create_room), so the
worker runs it as its own independent job with a clean ctx.connect(),
exactly like a normal call.

(Testing turned up two real bugs worth remembering: (1) issuing the
manager's token with VideoGrants(hidden=True) reproducibly broke
subscription — the server never told our agent's whisper-room
connection that a hidden identity existed, so its track arrived before
the participant did and LiveKit logged "received track from an unknown
participant" and silently dropped it; hidden was removed since room
separation already provides the isolation. (2) shared/redis_client.py's
single cached client crashed with "Future attached to a different
loop" the moment two job threads both called get_redis() — fixed there
to cache one client per event loop instead of one global.)

Since the prospect's room and the whisper room share no participants,
there is no permission check or subscription race that could leak
whisper audio to the prospect - isolation holds by construction.

The two jobs coordinate through Redis rather than in-process state,
since they may run in different threads (or, in a multi-worker
deployment, different processes): the whisper job transcribes the
manager's speech and writes the latest note under
ghost_mode:{main_room}:note; the main call's job reads-and-clears it
each turn and folds it into the LLM's context as a private instruction.
"""

import logging

from shared.constants import GHOST_MODE_NOTE_KEY
from shared.redis_client import get_redis

logger = logging.getLogger("agent.whisper_channel")

_WHISPER_SUFFIX = "-whisper"


def is_whisper_room(room_name: str) -> bool:
    return room_name.endswith(_WHISPER_SUFFIX)


def main_room_for(whisper_room_name: str) -> str:
    return whisper_room_name.removesuffix(_WHISPER_SUFFIX)


async def write_manager_note(main_room_name: str, text: str) -> None:
    """Appends rather than overwrites: the manager's speech is transcribed
    in ~2s chunks (same fixed-window STT as the prospect's audio), so a
    whisper longer than one chunk must accumulate, not have each chunk
    clobber the last, or only the final fragment would survive to be read."""
    redis = get_redis()
    key = GHOST_MODE_NOTE_KEY.format(room_name=main_room_name)
    await redis.append(key, text + " ")
    await redis.expire(key, 300)  # in case nobody ever reads it
    logger.info("Manager whisper note appended", extra={"room": main_room_name, "chunk": text})


async def read_and_clear_manager_note(main_room_name: str) -> str | None:
    redis = get_redis()
    key = GHOST_MODE_NOTE_KEY.format(room_name=main_room_name)
    note = await redis.getdel(key)
    return note.strip() if note else None
