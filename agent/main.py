import asyncio
import logging

from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli

from ab_testing import assign_variant_for_room
from call_lifecycle import persist_transcript_turn, resolve_call_id_for_room, set_call_status
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


def _on_conversation_loop_done(task: asyncio.Task, *, call_id: str | None, room_name: str, call_finished: dict) -> None:
    _log_task_exception(task, context="conversation_loop")
    if task.cancelled():
        return
    call_finished["done"] = True
    status = "failed" if task.exception() is not None else "completed"
    finish_task = asyncio.create_task(set_call_status(call_id, status))
    finish_task.add_done_callback(lambda t: _log_task_exception(t, context="call_status_finish"))
    logger.info("Call ended", extra={"room": room_name, "call_id": call_id, "status": status})


_BARGE_IN_GRACE_PERIOD_S = 0.8


def _speak(text: str, audio_source: rtc.AudioSource, current_tts: dict) -> asyncio.Task:
    """Starts TTS and records it as the currently-playing utterance, so a
    barge-in can cancel exactly this task (not some earlier finished one)."""
    task = asyncio.create_task(tts.synthesize_to_track(text, audio_source))
    current_tts["task"] = task
    current_tts["started_at"] = asyncio.get_event_loop().time()
    task.add_done_callback(lambda t: _log_task_exception(t, context="tts"))
    return task


def _on_prospect_speech_started(room_name: str, audio_source: rtc.AudioSource, current_tts: dict) -> None:
    # On slow (CPU-only) hardware, Kokoro can take longer than the ~243ms
    # barge-in budget to produce its first audio chunk - without this grace
    # window, ambient mic noise right as a reply starts cancels it before
    # the prospect ever hears a sound, every time. Once a reply has been
    # playing past the grace period, cancellation is instant as designed.
    started_at = current_tts.get("started_at")
    if started_at is not None and asyncio.get_event_loop().time() - started_at < _BARGE_IN_GRACE_PERIOD_S:
        return

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

    # None for inbound test rooms (no "outbound-{lead_id}" room-name
    # convention to resolve) - every downstream call_lifecycle call already
    # no-ops cleanly on None, same as enrichment/ab_testing's lookups.
    call_id = await resolve_call_id_for_room(ctx.room.name)
    await set_call_status(call_id, "active")

    current_tts: dict = {"task": None}  # per-call, local scope - tracks whichever utterance is playing right now
    _speak(opening_line, audio_source, current_tts)

    # Only set once, by whichever of {conversation loop ends, room
    # disconnects} happens first - so an abrupt disconnect after a normal
    # completion (or vice versa) can't flip a call's final status back and
    # forth.
    call_finished: dict = {"done": False}

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        logger.info(
            "Audio track subscribed",
            extra={"room": ctx.room.name, "participant": participant.identity},
        )
        transcribe_task = asyncio.create_task(
            _conversation_loop(ctx, track, audio_source, pitch, current_tts, call_id)
        )
        transcribe_task.add_done_callback(
            lambda t: _on_conversation_loop_done(
                t, call_id=call_id, room_name=ctx.room.name, call_finished=call_finished
            )
        )

        barge_in_task = asyncio.create_task(
            vad.watch(track, lambda: _on_prospect_speech_started(ctx.room.name, audio_source, current_tts))
        )
        barge_in_task.add_done_callback(lambda t: _log_task_exception(t, context="barge_in_watch"))

    @ctx.room.on("disconnected")
    def on_disconnected() -> None:
        # Safety net for a room that drops before any track is ever
        # subscribed (e.g. the prospect's side never connects) - without
        # this, call_id would stay "active" forever since the conversation
        # loop's done-callback would never fire.
        if call_finished["done"]:
            return
        call_finished["done"] = True
        logger.warning("Room disconnected with no completed conversation loop", extra={"room": ctx.room.name})
        task = asyncio.create_task(set_call_status(call_id, "failed"))
        task.add_done_callback(lambda t: _log_task_exception(t, context="call_status_disconnect"))


async def _conversation_loop(
    ctx: JobContext,
    track: rtc.Track,
    audio_source: rtc.AudioSource,
    pitch: str | None,
    current_tts: dict,
    call_id: str | None,
) -> None:
    enrichment = await get_enrichment_for_room(ctx.room.name)
    if enrichment:
        logger.info("Loaded lead enrichment", extra={"room": ctx.room.name, "enrichment": enrichment})

    async for text in stt.transcribe_track(track):
        logger.info("Transcript", extra={"room": ctx.room.name, "text": text})
        await persist_transcript_turn(call_id, "prospect", text)

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
            await persist_transcript_turn(call_id, "agent", decision.message)
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
            # Default 0.7 system-CPU load threshold marks this worker
            # "unavailable" and LiveKit silently drops dispatch ("no worker
            # available to handle job") - on this dev machine, ambient load
            # from unrelated processes sits near/above that on its own, so
            # real calls were never even reaching the agent. Raised so
            # dispatch isn't blocked by CPU noise this worker isn't causing.
            load_threshold=0.95,
        )
    )
