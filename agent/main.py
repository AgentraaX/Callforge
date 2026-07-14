import asyncio
import logging

from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli

from config import configure_logging, settings
from enrichment import get_enrichment_for_room
from pipeline.llm import QwenLLM
from pipeline.stt import WhisperSTT
from pipeline.tts import SAMPLE_RATE, KokoroTTS

configure_logging()
logger = logging.getLogger("agent.main")

# Loaded once per worker process and reused across every job (jobs run as
# threads by default), not once per call.
stt = WhisperSTT()
tts = KokoroTTS()
llm = QwenLLM()


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
        transcribe_task = asyncio.create_task(_conversation_loop(ctx, track, audio_source))
        transcribe_task.add_done_callback(lambda t: _log_task_exception(t, context="conversation_loop"))


async def _conversation_loop(ctx: JobContext, track: rtc.Track, audio_source: rtc.AudioSource) -> None:
    enrichment = await get_enrichment_for_room(ctx.room.name)
    if enrichment:
        logger.info("Loaded lead enrichment", extra={"room": ctx.room.name, "enrichment": enrichment})

    async for text in stt.transcribe_track(track):
        logger.info("Transcript", extra={"room": ctx.room.name, "text": text})

        decision = await llm.generate(text, enrichment=enrichment)
        logger.info(
            "LLM decision",
            extra={"room": ctx.room.name, "action": decision.action, "reply": decision.message},
        )
        # TODO(Day 6/joint with P4): route decision.action through graph/state_machine.py
        # instead of always just speaking decision.message

        if decision.message:
            await tts.synthesize_to_track(decision.message, audio_source)


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
