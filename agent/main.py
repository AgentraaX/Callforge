import logging

from livekit.agents import JobContext, WorkerOptions, cli

from config import configure_logging, settings

configure_logging()
logger = logging.getLogger("agent.main")


async def entrypoint(ctx: JobContext) -> None:
    """Called by the LiveKit Agents worker for each room it's dispatched to."""
    try:
        await ctx.connect()
    except Exception:
        logger.exception("Failed to join room", extra={"room": ctx.room.name})
        raise

    logger.info("Agent joined room", extra={"room": ctx.room.name})

    # TODO(Day 4): wire STT (pipeline/stt.py) into the room's audio tracks
    # TODO(Day 5): wire LLM (pipeline/llm.py)
    # TODO(Day 6): wire TTS (pipeline/tts.py)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=settings.LIVEKIT_AGENT_NAME,
            ws_url=settings.LIVEKIT_URL,
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
    )
