"""Manual Day 2 test helper.

Usage:
    python generate_token.py <room_name> <identity>

Prints a short-lived JWT you can hand to `lk room join` (or any LiveKit
client) to verify a test client can join a self-hosted room.
"""

import sys

from livekit_utils import create_room_token

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_token.py <room_name> <identity>")
        raise SystemExit(1)

    room_name, identity = sys.argv[1], sys.argv[2]
    print(create_room_token(room_name, identity))
