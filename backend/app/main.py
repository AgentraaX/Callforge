"""CallForge AI Sales Voice Agent -- Production API server."""
from __future__ import annotations
import base64
import json
import logging
import re
import uuid
from dataclasses import asdict
from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from . import auth
from .auth import oauth as oauth_auth
from .auth.deps import current_user as _current_user
from .config import settings
from .realtime.ws import handle_call, handle_dashboard, handle_telnyx_media
from .realtime.bus import bus
from .conversation.personas import (
    create_persona, delete_persona, get_persona, list_personas,
    persona_dict, persona_payload, update_persona,
)
from . import db as crm_db
from .crm.routes import router as crm_router
from .crm.ingest import persist_call
from .sales import leads, booking, escalation
from .telephony.telnyx_client import place_call
from .tts import create_engine as create_tts_engine, voice_from_persona
from .tts.elevenlabs import clone_voice, list_voices

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")

logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)
log = logging.getLogger("callforge")

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(crm_router)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "stt_engine": settings.stt_engine,
        "tts_engine": settings.tts_engine,
        "llm_configured": bool(settings.effective_llm_base_url),
        "database_configured": settings.db_configured,
        "db_ok": (await crm_db.ping()) if settings.db_configured else False,
    }

@app.on_event("startup")
async def _startup():
    log.info("CallForge starting: STT=%s TTS=%s LLM=%s",
             settings.stt_engine, settings.tts_engine,
             settings.effective_llm_base_url or "(none)")
    await crm_db.init_db()

@app.on_event("shutdown")
async def _shutdown():
    await crm_db.dispose()


# --- Auth API ---

class SignupBody(BaseModel):
    email: str
    password: str
    name: str = ""
    company: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


@app.post("/api/auth/signup")
def signup(body: SignupBody):
    try:
        user = auth.create_user(body.email, body.password, body.name, body.company)
    except auth.EmailTaken as exc:
        raise HTTPException(409, str(exc))
    except auth.InvalidCredentials as exc:
        raise HTTPException(400, str(exc))
    token = auth.create_session(user.email)
    return {"token": token, "user": auth.user_payload(user)}


@app.post("/api/auth/login")
def login(body: LoginBody):
    try:
        user = auth.verify_user(body.email, body.password)
    except auth.InvalidCredentials as exc:
        raise HTTPException(401, str(exc))
    token = auth.create_session(user.email)
    return {"token": token, "user": auth.user_payload(user)}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.lower().startswith("bearer "):
        auth.revoke_session(authorization[7:].strip())
    return {"status": "ok"}


@app.get("/api/auth/me")
def me(user: auth.UserRecord = Depends(_current_user)):
    return auth.user_payload(user)


# --- OAuth (Google / GitHub) ---
# Full-page browser redirects, not fetch/XHR -- the frontend navigates here
# directly (window.location.href), never calls it with fetch().

@app.get("/api/auth/oauth/{provider}/start")
def oauth_start(provider: str):
    if provider not in oauth_auth.PROVIDERS:
        raise HTTPException(404, "Unknown OAuth provider")
    if not oauth_auth.is_configured(provider):
        return RedirectResponse(
            f"{settings.frontend_url}/login?error=oauth_not_configured&provider={provider}"
        )
    state = oauth_auth.new_state()
    return RedirectResponse(oauth_auth.build_authorize_url(provider, state))


@app.get("/api/auth/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str = "", state: str = "", error: str = ""):
    if provider not in oauth_auth.PROVIDERS:
        raise HTTPException(404, "Unknown OAuth provider")

    if error or not code or not oauth_auth.consume_state(state):
        return RedirectResponse(f"{settings.frontend_url}/login?error=oauth_failed&provider={provider}")

    try:
        access_token = await oauth_auth.exchange_code(provider, code)
        profile = await oauth_auth.fetch_profile(provider, access_token)
        user = oauth_auth.find_or_create_oauth_user(profile["email"], profile["name"])
    except Exception as exc:
        log.warning("OAuth callback failed (%s): %s", provider, exc)
        return RedirectResponse(f"{settings.frontend_url}/login?error=oauth_failed&provider={provider}")

    session_token = auth.create_session(user.email)
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?token={session_token}")


# --- Personas API ---

class PersonaBody(BaseModel):
    name: str
    company: str = ""
    product_pitch: str = ""
    personality: str = ""
    knowledge_text: str = ""
    opening_line: str = ""
    call_goal: str = "book a short follow-up call"
    elevenlabs_voice_id: str = ""
    default_emotion: str = "confident"
    language_mode: str = "auto"  # "auto" (mirror the caller) | "english" (force English) | "sindhi" (force Sindhi)
    uplift_voice_id: str = "podcast-host"  # Uplift AI voiceId for this persona's native-script speech
    uplift_roman_script: bool = False  # transliterate to Roman script right before TTS (see tts/uplift.py)
    native_tts_provider: str = "uplift"  # "uplift" | "elevenlabs" (eleven_v3) for native-script Urdu/Sindhi turns


@app.get("/api/personas")
def get_personas(user: auth.UserRecord = Depends(_current_user)):
    return {"personas": [persona_payload(p) for p in list_personas(user.email)]}


@app.post("/api/personas")
def post_persona(body: PersonaBody, user: auth.UserRecord = Depends(_current_user)):
    if not body.name.strip():
        raise HTTPException(400, "Persona name is required")
    persona = create_persona(user.email, **body.model_dump())
    return persona_payload(persona)


@app.get("/api/personas/{persona_id}")
def get_persona_by_id(persona_id: str, user: auth.UserRecord = Depends(_current_user)):
    persona = get_persona(persona_id)
    if not persona or persona.owner_email != user.email.strip().lower():
        raise HTTPException(404, "Persona not found")
    return persona_payload(persona)


@app.put("/api/personas/{persona_id}")
def put_persona(persona_id: str, body: PersonaBody, user: auth.UserRecord = Depends(_current_user)):
    persona = update_persona(persona_id, user.email, **body.model_dump())
    if not persona:
        raise HTTPException(404, "Persona not found")
    return persona_payload(persona)


@app.delete("/api/personas/{persona_id}")
def delete_persona_endpoint(persona_id: str, user: auth.UserRecord = Depends(_current_user)):
    if not delete_persona(persona_id, user.email):
        raise HTTPException(404, "Persona not found")
    return {"status": "ok"}


_URDU_PREVIEW_LINE = "السلام علیکم، میں سعد بات کر رہا ہوں CallForge AI کی طرف سے -- کیا آپ کے پاس ایک منٹ ہے؟"


@app.post("/api/personas/{persona_id}/preview-voice")
async def preview_persona_voice(persona_id: str, language: str = "en", user: auth.UserRecord = Depends(_current_user)):
    persona = get_persona(persona_id)
    if not persona or persona.owner_email != user.email.strip().lower():
        raise HTTPException(404, "Persona not found")

    if language == "ur":
        if not settings.uplift_api_key:
            raise HTTPException(400, "UPLIFT_API_KEY is not configured")
        tts_engine = create_tts_engine("uplift")
        sample_line = _URDU_PREVIEW_LINE
    else:
        if not settings.elevenlabs_api_key:
            raise HTTPException(400, "ELEVENLABS_API_KEY is not configured")
        tts_engine = create_tts_engine("elevenlabs")
        sample_line = (
            persona.opening_line
            or f"Hi, this is {persona.name} calling from {persona.company or 'our team'} -- got a quick minute?"
        )

    voice = voice_from_persona(persona)
    result = await tts_engine.synthesize(sample_line, voice, persona.default_emotion)
    if not result.audio:
        raise HTTPException(502, "Voice preview failed -- check the persona's voice ID and API key")
    return {"audio": base64.b64encode(result.audio).decode(), "mime": result.mime, "text": sample_line}


@app.get("/api/voices")
async def get_voices(user: auth.UserRecord = Depends(_current_user)):
    return {"voices": await list_voices()}


@app.post("/api/voices/clone")
async def clone_voice_endpoint(name: str, file: UploadFile, user: auth.UserRecord = Depends(_current_user)):
    if not settings.elevenlabs_api_key:
        raise HTTPException(400, "ELEVENLABS_API_KEY is not configured")
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio file")
    voice_id = await clone_voice(name.strip() or "Custom Voice", audio_bytes, file.filename or "reference.mp3")
    if not voice_id:
        raise HTTPException(502, "ElevenLabs voice cloning failed")
    return {"voice_id": voice_id}


class LiveKitTokenBody(BaseModel):
    persona_id: str


@app.post("/api/livekit/token")
def livekit_token(body: LiveKitTokenBody, user: auth.UserRecord = Depends(_current_user)):
    """Issues a LiveKit room token for the browser test-call page. Real
    WebRTC audio flows through LiveKit Cloud; our agent worker
    (app/voice_agent/agent.py) is auto-dispatched into the room."""
    persona = get_persona(body.persona_id)
    if not persona or persona.owner_email != user.email.strip().lower():
        raise HTTPException(404, "Persona not found")
    if not settings.livekit_configured:
        raise HTTPException(400, "LiveKit is not configured on the server")

    from livekit import api as lk_api
    from .voice_agent.constants import AGENT_NAME

    call_id = uuid.uuid4().hex[:10]
    call = bus.open_call(call_id, caller=user.name or "Guest", owner_email=user.email)
    call["agent"] = persona_payload(persona)

    room_name = f"call-{call_id}"
    dispatch_metadata = json.dumps({"call_id": call_id, "persona_id": persona.id})
    token = (
        lk_api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(user.email)
        .with_name(user.name or "Guest")
        .with_grants(lk_api.VideoGrants(room_join=True, room=room_name))
        .with_room_config(
            lk_api.RoomConfiguration(
                agents=[lk_api.RoomAgentDispatch(agent_name=AGENT_NAME, metadata=dispatch_metadata)],
            )
        )
        .to_jwt()
    )

    return {"token": token, "ws_url": settings.livekit_url, "call_id": call_id, "room": room_name}


@app.websocket("/ws/call")
async def ws_call(ws: WebSocket):
    await handle_call(ws)


@app.websocket("/ws/telnyx-media")
async def ws_telnyx_media(ws: WebSocket):
    await handle_telnyx_media(ws)


@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await handle_dashboard(ws)


# --- Dialer / Telephony API (real outbound calls via Telnyx) ---

class DialBody(BaseModel):
    to_number: str
    persona_id: str


@app.post("/api/calls/dial")
def dial_call(body: DialBody, user: auth.UserRecord = Depends(_current_user)):
    if not _E164_RE.match(body.to_number.strip()):
        raise HTTPException(400, "to_number must be in E.164 format, e.g. +14155552671")

    persona = get_persona(body.persona_id)
    if not persona or persona.owner_email != user.email.strip().lower():
        raise HTTPException(404, "Persona not found")

    if not settings.telnyx_configured:
        raise HTTPException(400, "Telnyx is not configured on the server")
    if settings.tts_engine != "elevenlabs":
        raise HTTPException(
            400,
            "Real phone calls require TTS_ENGINE=elevenlabs (only engine that "
            "emits Telnyx-native 8kHz mulaw/PCMU audio without resampling).",
        )

    call_id = uuid.uuid4().hex[:10]
    call = bus.open_call(call_id, caller=body.to_number, owner_email=user.email)
    call["agent"] = persona_payload(persona)

    try:
        place_call(body.to_number.strip(), call_id, persona.id)
    except Exception as exc:
        bus.calls.pop(call_id, None)
        raise HTTPException(502, f"Failed to place call: {exc}")

    return {"call_id": call_id}


_TELNYX_TERMINAL_EVENTS = {"call.hangup", "call.machine.detection.ended.error"}


@app.post("/api/telephony/telnyx-status")
async def telephony_telnyx_status(call_id: str, request: Request):
    body = await request.json()
    event_type = str((body.get("data") or {}).get("event_type", ""))
    call = bus.calls.get(call_id)
    if call and event_type:
        # Telnyx's terminal events -> our call state; in-flight events
        # (call.initiated/call.ringing/call.answered) are already
        # reflected by /ws/telnyx-media once the media stream comes up.
        if event_type in _TELNYX_TERMINAL_EVENTS:
            call["state"] = "ended"
        await bus.update(call)
    return {"status": "ok"}


# --- Leads API ---

@app.get("/api/leads")
def get_leads():
    return {"leads": leads.all_leads()}


@app.get("/api/leads/stats")
def get_lead_stats():
    return leads.stats()


@app.get("/api/leads/{call_id}")
def get_lead(call_id: str):
    lead = leads.get(call_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return asdict(lead)


@app.post("/api/leads/{call_id}/notes")
def add_lead_note(call_id: str, body: dict):
    note = body.get("note", "")
    lead = leads.add_note(call_id, note)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return asdict(lead)


# --- Bookings API ---

@app.get("/api/bookings")
def get_bookings():
    return {"bookings": booking.all_bookings()}


@app.get("/api/bookings/available")
def get_available_slots():
    return {"slots": booking.available_slots()}


@app.post("/api/bookings/confirm")
def confirm_booking(body: dict):
    b = booking.confirm(
        call_id=body.get("call_id", ""),
        slot_id=body.get("slot_id", ""),
        slot_label=body.get("slot_label", ""),
        purpose=body.get("purpose", "consultation"),
        contact_name=body.get("contact_name", ""),
        contact_phone=body.get("contact_phone"),
        lead_id=body.get("lead_id"),
    )
    return asdict(b)


@app.put("/api/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: str):
    b = booking.cancel(booking_id)
    if not b:
        raise HTTPException(404, "Booking not found")
    return asdict(b)


# --- Escalation API ---

@app.get("/api/escalations")
def get_escalations():
    return {"cases": escalation.all_cases()}


@app.get("/api/escalations/pending")
def get_pending_escalations():
    return {"cases": escalation.pending_cases()}


# --- Internal API (LiveKit agent worker <-> backend) ---
#
# The agent worker (app/voice_agent/agent.py) runs as a SEPARATE OS
# process -- it has no access to the in-memory persona/lead/booking/
# escalation/call stores living in this process's memory, so it reaches
# them here instead of importing those modules directly. Guarded by a
# shared secret rather than a user's bearer token, since the worker isn't
# acting as any particular logged-in user.

def _internal_auth(x_internal_key: str | None = Header(default=None)) -> None:
    if not settings.internal_api_key or x_internal_key != settings.internal_api_key:
        raise HTTPException(401, "Invalid internal key")


@app.get("/internal/personas/{persona_id}", dependencies=[Depends(_internal_auth)])
def internal_get_persona(persona_id: str):
    persona = get_persona(persona_id)
    if not persona:
        raise HTTPException(404, "Persona not found")
    return persona_dict(persona)


class InternalTranscriptBody(BaseModel):
    who: str
    name: str
    text: str


@app.post("/internal/calls/{call_id}/transcript", dependencies=[Depends(_internal_auth)])
async def internal_append_transcript(call_id: str, body: InternalTranscriptBody):
    call = bus.calls.get(call_id) or bus.open_call(call_id)
    call["transcript"].append({"who": body.who, "name": body.name, "text": body.text})
    await bus.update(call)
    return {"status": "ok"}


class InternalStateBody(BaseModel):
    state: str


@app.post("/internal/calls/{call_id}/state", dependencies=[Depends(_internal_auth)])
async def internal_update_state(call_id: str, body: InternalStateBody):
    call = bus.calls.get(call_id)
    if call:
        call["state"] = body.state
        await bus.update(call)
    return {"status": "ok"}


class InternalLeadExtractBody(BaseModel):
    text: str
    caller_name: str = ""


@app.post("/internal/calls/{call_id}/lead-extract", dependencies=[Depends(_internal_auth)])
async def internal_lead_extract(call_id: str, body: InternalLeadExtractBody):
    call = bus.calls.get(call_id)
    lead = await leads.extract(call_id, body.text, body.caller_name)
    if call:
        call["lead"] = asdict(lead)
        await bus.update(call)
    return {"status": "ok"}


class InternalEscalateBody(BaseModel):
    reason: str
    caller_name: str = ""


@app.post("/internal/calls/{call_id}/escalate", dependencies=[Depends(_internal_auth)])
async def internal_escalate(call_id: str, body: InternalEscalateBody):
    call = bus.calls.get(call_id) or bus.open_call(call_id)
    case = await escalation.create_case(
        call_id, body.reason,
        caller_name=body.caller_name,
        transcript=call.get("transcript", []),
        lead_data=call.get("lead"),
        history=[{"role": t["who"], "content": t["text"]} for t in call.get("transcript", [])],
    )
    call["escalated"] = True
    call["case_id"] = case.case_id
    await bus.update(call)
    speech = escalation.format_escalation_speech(case, "en")
    return {"case_id": case.case_id, "speech": speech}


class InternalBookingConfirmBody(BaseModel):
    call_id: str
    slot_id: str
    slot_label: str
    contact_name: str
    purpose: str = "consultation"
    contact_phone: str | None = None
    contact_email: str | None = None


@app.post("/internal/bookings/confirm", dependencies=[Depends(_internal_auth)])
def internal_confirm_booking(body: InternalBookingConfirmBody):
    lead = leads.get(body.call_id)
    new_booking = booking.confirm(
        call_id=body.call_id, slot_id=body.slot_id, slot_label=body.slot_label,
        purpose=body.purpose, contact_name=body.contact_name,
        contact_phone=body.contact_phone, contact_email=body.contact_email,
        lead_id=lead.id if lead else None,
    )
    speech = booking.format_confirmation_for_speech(new_booking, "en")
    return {"speech": speech}


@app.post("/internal/calls/{call_id}/finalize", dependencies=[Depends(_internal_auth)])
async def internal_finalize_call(call_id: str):
    """Called by the LiveKit agent worker when its session ends -- mirrors
    the finished call into the CRM, same as the /ws/* teardown paths do."""
    record_id = await persist_call(call_id)
    return {"status": "ok", "call_record_id": record_id}
