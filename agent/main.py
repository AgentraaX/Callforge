import logging

from config import configure_logging, settings

configure_logging()
logger = logging.getLogger("agent.main")


def main() -> None:
    logger.info("CallForge agent starting", extra={"livekit_url": settings.LIVEKIT_URL})
    # Day 2 room/token flow lives in livekit_utils.py (create_room, create_room_token)
    # TODO(Day 3): auto-join room via LiveKit Agents framework (worker/job pattern)
    logger.info("CallForge agent boot sequence complete")


if __name__ == "__main__":
    main()
