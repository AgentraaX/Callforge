import asyncio
import logging

from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli

from config import configure_logging, settings
from pipeline.stt import WhisperSTT
from pipeline.tts import SAMPLE_RATE, KokoroTTS

configure_logging()
logger = logging.getLogger("agent.main")

# Loaded once per worker process and reused across every job (jobs run as
# threads by default), not once per call.
stt = WhisperSTT()
tts = KokoroTTS()


def _log_task_exception(task: asyncio.Task, *, context: str) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("Background task failed", extra={"context": context}, exc_info=exc)


async def entrypoint(ctx: JobContext) -> None:
    """Called by the LiveKit Agents worker for each room it's dispatched to."""
    try:
        await ctx.connect()
    except Exception:
        logger.exception("Failed to join room", extra={"room": ctx.room.name})
        raise

    logger.info("Agent joined room", extra={"room": ctx.room.name})

    audio_source = rtc.AudioSource(sample_rate=SAMPLE_RATE, num_channels=1)
    audio_track = rtc.LocalAudioTrack.create_audio_track("agent-voice", audio_source)
    await ctx.room.local_participant.publish_track(
        audio_track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )
    logger.info("Published agent audio track", extra={"room": ctx.room.name})

    # TODO(Day 5): replace this fixed greeting with the LLM's generated reply
    greeting_task = asyncio.create_task(
        tts.synthesize_to_track(
            "Hello, this is the CallForge assistant, checking that the voice pipeline works.",
            audio_source,
        )
    )
    greeting_task.add_done_callback(lambda t: _log_task_exception(t, context="tts_greeting"))

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        logger.info(
            "Audio track subscribed",
            extra={"room": ctx.room.name, "participant": participant.identity},
        )
        transcribe_task = asyncio.create_task(_transcribe_loop(ctx, track))
        transcribe_task.add_done_callback(lambda t: _log_task_exception(t, context="transcribe_loop"))

    # TODO(Day 5): wire LLM (pipeline/llm.py) between the transcript and the TTS reply


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
