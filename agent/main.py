import asyncio
import logging

from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli

from ab_testing import assign_variant_for_room
from config import configure_logging, settings
from enrichment import get_enrichment_for_room
from pipeline.llm import QwenLLM
from pipeline.stt import WhisperSTT
from pipeline.tts import SAMPLE_RATE, KokoroTTS
from pipeline.vad import BargeInDetector
from whisper_channel import is_whisper_room, main_room_for, read_and_clear_manager_note, write_manager_note

configure_logging()
logger = logging.getLogger("agent.main")

# Loaded once per worker process and reused across every job (jobs run as
# threads by default), not once per call.
stt = WhisperSTT()
tts = KokoroTTS()
llm = QwenLLM()
vad = BargeInDetector()


def _log_task_exception(task: asyncio.Task, *, context: str) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("Background task failed", extra={"context": context}, exc_info=exc)


def _speak(text: str, audio_source: rtc.AudioSource, current_tts: dict) -> asyncio.Task:
    """Starts TTS and records it as the currently-playing utterance, so a
    barge-in can cancel exactly this task (not some earlier finished one)."""
    task = asyncio.create_task(tts.synthesize_to_track(text, audio_source))
    current_tts["task"] = task
    task.add_done_callback(lambda t: _log_task_exception(t, context="tts"))
    return task


def _on_prospect_speech_started(room_name: str, audio_source: rtc.AudioSource, current_tts: dict) -> None:
    # The VAD re-fires on every micro-pause within the prospect's own
    # utterance (natural gaps between words), not just once per utterance -
    # only act, and only log, when the agent actually has something playing
    # to interrupt, so a burst of re-triggers is a silent no-op rather than
    # noisy repeated cancellations.
    task = current_tts.get("task")
    if task is None or task.done():
        return
    task.cancel()
    audio_source.clear_queue()  # drop anything already queued but not yet played
    logger.info("Barge-in: prospect started talking, agent interrupted", extra={"room": room_name})


async def entrypoint(ctx: JobContext) -> None:
    """Called by the LiveKit Agents worker for each room it's dispatched to."""
    try:
        await ctx.connect()
    except Exception:
        logger.exception("Failed to join room", extra={"room": ctx.room.name})
        raise

    if is_whisper_room(ctx.room.name):
        await _whisper_job(ctx)
        return

    await _call_job(ctx)


async def _call_job(ctx: JobContext) -> None:
    """The normal path: agent talks with the prospect."""
    logger.info("Agent joined room", extra={"room": ctx.room.name})

    audio_source = rtc.AudioSource(sample_rate=SAMPLE_RATE, num_channels=1)
    audio_track = rtc.LocalAudioTrack.create_audio_track("agent-voice", audio_source)
    await ctx.room.local_participant.publish_track(
        audio_track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )
    logger.info("Published agent audio track", extra={"room": ctx.room.name})

    # Assigned once, before anything is spoken, so the A/B variant actually
    # decides the opening line the prospect hears - not just background
    # context for later turns.
    variant = await assign_variant_for_room(ctx.room.name)
    pitch = variant["pitch"] if variant else None
    opening_line = pitch or "Hello, this is the CallForge assistant, checking that the voice pipeline works."

    current_tts: dict = {"task": None}  # per-call, local scope - tracks whichever utterance is playing right now
    _speak(opening_line, audio_source, current_tts)

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        logger.info(
            "Audio track subscribed",
            extra={"room": ctx.room.name, "participant": participant.identity},
        )
        transcribe_task = asyncio.create_task(_conversation_loop(ctx, track, audio_source, pitch, current_tts))
        transcribe_task.add_done_callback(lambda t: _log_task_exception(t, context="conversation_loop"))

        barge_in_task = asyncio.create_task(
            vad.watch(track, lambda: _on_prospect_speech_started(ctx.room.name, audio_source, current_tts))
        )
        barge_in_task.add_done_callback(lambda t: _log_task_exception(t, context="barge_in_watch"))


async def _conversation_loop(
    ctx: JobContext,
    track: rtc.Track,
    audio_source: rtc.AudioSource,
    pitch: str | None,
    current_tts: dict,
) -> None:
    enrichment = await get_enrichment_for_room(ctx.room.name)
    if enrichment:
        logger.info("Loaded lead enrichment", extra={"room": ctx.room.name, "enrichment": enrichment})

    async for text in stt.transcribe_track(track):
        logger.info("Transcript", extra={"room": ctx.room.name, "text": text})

        note = await read_and_clear_manager_note(ctx.room.name)
        if note:
            logger.info("Applying manager whisper note", extra={"room": ctx.room.name, "note": note})

        decision = await llm.generate(text, enrichment=enrichment, manager_note=note, pitch=pitch)
        logger.info(
            "LLM decision",
            extra={"room": ctx.room.name, "action": decision.action, "reply": decision.message},
        )
        # TODO(Day 6/joint with P4): route decision.action through graph/state_machine.py
        # instead of always just speaking decision.message

        if decision.message:
            reply_task = _speak(decision.message, audio_source, current_tts)
            try:
                await reply_task
            except asyncio.CancelledError:
                # Barge-in cancelled this specific reply - the conversation
                # loop itself keeps running to hear what the prospect said.
                logger.info("Reply interrupted by barge-in", extra={"room": ctx.room.name})


async def _whisper_job(ctx: JobContext) -> None:
    """Ghost Mode: this job's only role is to transcribe whatever the
    manager says in the whisper room and hand it to the main call's job
    via Redis - see whisper_channel.py for why this is two jobs, not one."""
    main_room = main_room_for(ctx.room.name)
    logger.info("Agent joined whisper room", extra={"whisper_room": ctx.room.name, "main_room": main_room})

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        logger.info(
            "Manager whisper track subscribed",
            extra={"whisper_room": ctx.room.name, "manager": participant.identity},
        )
        task = asyncio.create_task(_transcribe_whisper(track, main_room))
        task.add_done_callback(lambda t: _log_task_exception(t, context="whisper_transcribe"))


async def _transcribe_whisper(track: rtc.Track, main_room: str) -> None:
    async for text in stt.transcribe_track(track):
        await write_manager_note(main_room, text)


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
