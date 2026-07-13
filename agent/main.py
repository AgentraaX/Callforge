import asyncio
import logging

from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli

from config import configure_logging, settings
from pipeline.stt import WhisperSTT

configure_logging()
logger = logging.getLogger("agent.main")

# Loaded once per worker process and reused across every job (jobs run as
# threads by default), not once per call.
stt = WhisperSTT()


async def entrypoint(ctx: JobContext) -> None:
    """Called by the LiveKit Agents worker for each room it's dispatched to."""
    try:
        await ctx.connect()
    except Exception:
        logger.exception("Failed to join room", extra={"room": ctx.room.name})
        raise

    logger.info("Agent joined room", extra={"room": ctx.room.name})

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        logger.info(
            "Audio track subscribed",
            extra={"room": ctx.room.name, "participant": participant.identity},
        )
        asyncio.create_task(_transcribe_loop(ctx, track))

    # TODO(Day 5): wire LLM (pipeline/llm.py)
    # TODO(Day 6): wire TTS (pipeline/tts.py)


async def _transcribe_loop(ctx: JobContext, track: rtc.Track) -> None:
    async for text in stt.transcribe_track(track):
        logger.info("Transcript", extra={"room": ctx.room.name, "text": text})
        # TODO(Day 5): pass this transcript into pipeline/llm.py + graph/state_machine.py


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
