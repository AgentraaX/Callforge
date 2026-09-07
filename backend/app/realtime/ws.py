"""WebSocket endpoints -- browser test calls, real Telnyx phone calls, and
the dashboard live feed.

/ws/call and /ws/telnyx-media are two transports over the SAME turn engine
(``conversation.turn.run_turn``) -- see conversation/turn.py for why.
"""
from __future__ import annotations
import asyncio
import audioop
import base64
import io
import json
import logging
import uuid
import wave

from fastapi import WebSocket, WebSocketDisconnect

from ..config import settings
from ..stt import create_engine as create_stt
from ..tts import create_engine as create_tts, voice_from_persona
from ..llm import create_client as create_llm
from ..conversation.session import CallSession
from ..conversation.personas import get_persona, list_personas, persona_payload
from ..conversation.turn import run_turn, generate_greeting
from .bus import bus

log = logging.getLogger("callforge.realtime.ws")


async def _persist_call_safe(call_id: str) -> None:
    """Mirror the finished call into the CRM. Never raises into teardown."""
    try:
        from ..crm.ingest import persist_call

        await persist_call(call_id)
    except Exception as exc:  # pragma: no cover -- defensive
        log.warning("CRM persist_call(%s) failed: %s", call_id, exc)


async def handle_call(ws: WebSocket):
    """Browser test-call WebSocket -- text or recorded audio in, base64
    audio blobs out. Used by the dashboard's Test a Call page."""
    await ws.accept()

    session = CallSession()
    call_id = uuid.uuid4().hex[:10]
    session.call_id = call_id
    session.transition("ringing")

    call = bus.open_call(call_id)
    await bus.update(call)
    await ws.send_json({"type": "call_meta", "call_id": call_id})

    stt_engine = create_stt(settings.stt_engine)
    tts_engine = create_tts(settings.tts_engine)
    llm_client = create_llm()

    persona = None
    greeting_task: asyncio.Task | None = None

    async def emit_chunk(chunk_text: str, audio: bytes, mime: str, index: int) -> None:
        await ws.send_json({
            "type": "speak",
            "text": chunk_text,
            "audio": base64.b64encode(audio).decode() if audio else None,
            "mime": mime,
            "agent": persona_payload(persona) if persona else None,
            "append": index > 0,
        })

    log.info("Call %s connected", call_id)

    try:
        while True:
            msg = await ws.receive_json()
            mtype = msg.get("type")

            if mtype == "hello":
                user = msg.get("user") or {}
                session.caller_name = str(user.get("name", "")).strip()[:40] or "Guest"
                session.caller_email = str(user.get("email", "")).strip()
                session.caller_id = msg.get("caller_id")
                call["caller"] = session.caller_name
                if session.caller_email:
                    call["owner_email"] = session.caller_email

                requested_id = msg.get("persona_id")
                if requested_id:
                    persona = get_persona(requested_id)
                if not persona and session.caller_email:
                    owned = list_personas(session.caller_email)
                    persona = owned[0] if owned else None

                if not persona:
                    await ws.send_json({
                        "type": "error",
                        "message": "No persona found -- create a sales persona first.",
                    })
                    await ws.close()
                    return

                session.persona_id = persona.id
                greeting_task = asyncio.create_task(generate_greeting(session, persona, tts_engine, llm_client))

            elif mtype == "start":
                if persona is None:
                    await ws.send_json({"type": "error", "message": "Send 'hello' first."})
                    continue
                session.transition("greeting")
                if greeting_task is None:
                    greeting_task = asyncio.create_task(generate_greeting(session, persona, tts_engine, llm_client))
                greeting_text, greeting_audio, greeting_mime = await greeting_task

                call["state"] = "live"
                call["agent"] = persona_payload(persona)
                call["transcript"].append({
                    "who": "agent", "name": persona.name, "text": greeting_text,
                })
                await bus.update(call)

                await ws.send_json({
                    "type": "speak",
                    "text": greeting_text,
                    "audio": base64.b64encode(greeting_audio).decode() if greeting_audio else None,
                    "mime": greeting_mime,
                    "agent": persona_payload(persona),
                    "append": False,
                })
                await ws.send_json({"type": "turn_end"})
                session.transition("listening")

            elif mtype in ("audio", "text"):
                if persona is None:
                    continue
                session.transition("thinking")
                await ws.send_json({"type": "state", "value": "thinking"})
                session.turn_count += 1

                if mtype == "audio":
                    audio_bytes = base64.b64decode(msg["data"])
                    stt_result = await stt_engine.transcribe(audio_bytes, msg.get("mime", "audio/webm"))
                    text = stt_result.text
                    if stt_result.language:
                        session.language = stt_result.language
                else:
                    text = (msg.get("text") or "").strip()

                if not text:
                    session.empty_count += 1
                    if session.empty_count == 1:
                        retry_line = "Sorry, the line broke up for a second -- could you say that again?"
                        voice = voice_from_persona(persona)
                        result = await tts_engine.synthesize(retry_line, voice, "apologetic")
                        await ws.send_json({
                            "type": "speak", "text": retry_line,
                            "audio": base64.b64encode(result.audio).decode() if result.audio else None,
                            "mime": result.mime,
                            "agent": persona_payload(persona),
                            "append": False,
                        })
                    await ws.send_json({"type": "turn_end"})
                    session.transition("listening")
                    continue

                session.empty_count = 0

                await ws.send_json({
                    "type": "transcript", "who": "caller",
                    "name": session.caller_name or "You", "text": text,
                })

                await run_turn(session, call, text, persona, llm_client, tts_engine, emit_chunk)
                await ws.send_json({"type": "turn_end"})

            elif mtype == "pause":
                call["state"] = "paused"
                await bus.update(call)

            elif mtype == "resume":
                call["state"] = "live"
                await bus.update(call)

            elif mtype == "hangup":
                break

    except WebSocketDisconnect:
        pass
    finally:
        if greeting_task and not greeting_task.done():
            greeting_task.cancel()
        call["state"] = "ended"
        call["language"] = session.language
        call["escalated"] = session.escalated
        await bus.close_call(call_id)
        await _persist_call_safe(call_id)
        log.info("Call %s ended (duration %.1fs, %d turns)",
                 call_id, session.duration_s, session.turn_count)


# --- Telnyx Media Streaming bridge (real outbound phone calls) ---

_SILENCE_MS = 700          # trailing silence that ends a caller's turn
_RMS_THRESHOLD = 400       # 16-bit PCM amplitude floor -- below this counts as silence
_BYTES_PER_MS = 8          # 8kHz mulaw, 1 byte/sample -> 8 bytes = 1ms of audio


def _mulaw_to_wav(mulaw_bytes: bytes) -> bytes:
    """Wrap raw 8kHz mulaw samples in a standard PCM16 WAV container so the
    existing (batch-oriented) STT engines can transcribe it without any
    changes to their interface."""
    pcm16 = audioop.ulaw2lin(mulaw_bytes, 2)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(pcm16)
    return buf.getvalue()


async def handle_telnyx_media(ws: WebSocket):
    """Telnyx Media Streaming WebSocket -- the real-phone-call transport.

    Wire protocol (Telnyx's, not ours): JSON frames with
    "event": "connected" | "start" | "media" | "stop" | "dtmf" | "error".
    We dial with stream_track="both_tracks", so "media" frames carry BOTH
    the caller's audio (track="inbound") and an echo of what we're
    currently playing to them (track="outbound") on the same socket --
    only "inbound" is fed to STT/VAD. Outbound playback frames need no
    stream/session id (unlike Twilio's streamSid), just
    {"event": "media", "media": {"payload": <base64 PCMU>}}. Inbound
    audio is continuous, so turn boundaries are detected via a silence
    timeout rather than a client Send button.
    """
    await ws.accept()

    call_id = ws.query_params.get("call_id", "")
    persona_id = ws.query_params.get("persona_id", "")
    persona = get_persona(persona_id) if persona_id else None

    if not call_id or persona is None:
        log.warning("Telnyx media stream missing call_id/persona_id -- closing")
        await ws.close()
        return

    session = CallSession()
    session.call_id = call_id
    session.persona_id = persona.id
    session.caller_name = "Guest"
    session.transition("ringing")

    call = bus.calls.get(call_id) or bus.open_call(call_id)
    call["state"] = "live"
    call["agent"] = persona_payload(persona)
    await bus.update(call)

    stt_engine = create_stt(settings.stt_engine)
    tts_engine = create_tts(settings.tts_engine)
    llm_client = create_llm()

    stream_started = False
    speech_buffer = bytearray()
    speaking = False
    silence_ms = 0

    async def emit_chunk(chunk_text: str, audio: bytes, mime: str, index: int) -> None:
        if not audio or not stream_started:
            return
        await ws.send_text(json.dumps({
            "event": "media",
            "media": {"payload": base64.b64encode(audio).decode()},
        }))

    async def process_utterance(mulaw_bytes: bytes) -> None:
        wav_bytes = _mulaw_to_wav(mulaw_bytes)
        stt_result = await stt_engine.transcribe(wav_bytes, "audio/wav")
        text = stt_result.text.strip()
        if not text:
            return
        await run_turn(session, call, text, persona, llm_client, tts_engine,
                       emit_chunk, telephony=True)

    try:
        # Greet as soon as the media stream is up.
        greeting_text, greeting_audio, greeting_mime = await generate_greeting(
            session, persona, tts_engine, llm_client, telephony=True,
        )
        call["transcript"].append({"who": "agent", "name": persona.name, "text": greeting_text})
        await bus.update(call)

        while True:
            raw = await ws.receive_text()
            frame = json.loads(raw)
            event = frame.get("event")

            if event == "start":
                stream_started = True
                # Greeting was synthesized before the stream was confirmed up -- send it now.
                await emit_chunk(greeting_text, greeting_audio, greeting_mime, 0)
                session.transition("listening")

            elif event == "media":
                if frame.get("media", {}).get("track") == "outbound":
                    continue  # our own TTS echoed back -- not caller audio
                if session.state == "speaking":
                    continue  # simple half-duplex: ignore caller audio while agent is talking
                payload = frame.get("media", {}).get("payload", "")
                if not payload:
                    continue
                mulaw_chunk = base64.b64decode(payload)
                pcm16 = audioop.ulaw2lin(mulaw_chunk, 2)
                rms = audioop.rms(pcm16, 2)
                frame_ms = len(mulaw_chunk) / _BYTES_PER_MS

                if rms > _RMS_THRESHOLD:
                    speaking = True
                    silence_ms = 0
                    speech_buffer.extend(mulaw_chunk)
                elif speaking:
                    silence_ms += frame_ms
                    speech_buffer.extend(mulaw_chunk)
                    if silence_ms >= _SILENCE_MS:
                        utterance = bytes(speech_buffer)
                        speech_buffer = bytearray()
                        speaking = False
                        silence_ms = 0
                        await process_utterance(utterance)

            elif event == "stop":
                break

    except WebSocketDisconnect:
        pass
    finally:
        call["state"] = "ended"
        call["language"] = session.language
        call["escalated"] = session.escalated
        await bus.close_call(call_id)
        await _persist_call_safe(call_id)
        log.info("Telnyx call %s ended (duration %.1fs, %d turns)",
                 call_id, session.duration_s, session.turn_count)


async def handle_dashboard(ws: WebSocket):
    """WebSocket handler for /ws/dashboard -- read-only feed."""
    await ws.accept()
    await bus.attach(ws)
    try:
        while True:
            await ws.receive_text()  # drain pings
    except WebSocketDisconnect:
        pass
    finally:
        bus.detach(ws)
