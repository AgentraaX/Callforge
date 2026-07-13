"""Manual testing helper.

Usage:
    python create_test_room.py <room_name>

Creates a room with the voice agent's dispatch attached, so
callforge-voice-agent joins automatically (matches the real
call-creation flow — see docs/API_CONTRACT.md's note on create_room()).
"""

import sys

import asyncio

from livekit_utils import create_room

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python create_test_room.py <room_name>")
        raise SystemExit(1)

    asyncio.run(create_room(sys.argv[1]))
    print(f"Room '{sys.argv[1]}' created — agent should join within ~1s.")
