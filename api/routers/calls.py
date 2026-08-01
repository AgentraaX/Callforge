"""Call log and transcript endpoints. Built Day 4. Owned by Person 4."""
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.dependencies import get_current_user, user_filter
from api.models import Call, Transcript, User
from api.schemas.call import CallMonitorToken, CallOut, LiveCallState, PaginatedCalls
from api.schemas.transcript import PaginatedTranscript
from api.services.call_state import get_call_sentiment, get_call_state
from api.services.livekit_rooms import create_listener_token, livekit_url
from api.services.recording_storage import get_recording_path

logger = logging.getLogger("api.routers.calls")

router = APIRouter(prefix="/calls", tags=["calls"], dependencies=[Depends(get_current_user)])

_VALID_STATUSES = {"pending", "active", "completed", "failed", "no-answer"}


def _get_user_call(db: Session, user: User, call_id: uuid.UUID) -> Call:
    call = db.get(Call, call_id)
    if not call or call.user_id != user.id:
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@router.get("", response_model=PaginatedCalls)
def list_calls(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(default=None),
):
    if status and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid values: {', '.join(sorted(_VALID_STATUSES))}",
        )

    q = db.query(Call).filter(user_filter(user, Call))
    if status:
        q = q.filter(Call.status == status)
    q = q.order_by(Call.created_at.desc())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedCalls(items=items, total=total, page=page, page_size=page_size)


@router.get("/{call_id}", response_model=CallOut)
def get_call(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _get_user_call(db, user, call_id)


@router.get("/{call_id}/live", response_model=LiveCallState)
async def get_live_call_state(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Redis-backed live state for a dashboard to poll during an active call
    (Section 5 contract: call:{call_id}:state / :sentiment, written by the
    agent - see agent/call_lifecycle.py). `status` is the durable Postgres
    value; `live_status`/`live_updated_at` reflect the last Redis write and
    are None if the call never ran through the agent (or Redis expired it).
    """
    call = _get_user_call(db, user, call_id)

    state = await get_call_state(str(call_id))
    sentiment = await get_call_sentiment(str(call_id))

    return LiveCallState(
        call_id=call_id,
        status=call.status,
        live_status=state.get("status") if state else None,
        live_updated_at=datetime.fromisoformat(state["updated_at"]) if state else None,
        sentiment=sentiment,
    )


@router.post("/{call_id}/monitor", response_model=CallMonitorToken)
async def monitor_call(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Listen-only join: mints a subscribe-only token (can_publish=False)
    for the call's *actual* room, so a manager can hear it live without
    ever being able to speak into it or otherwise affect it.

    This is deliberately NOT Day 10 Ghost Mode (enable_ghost_mode /
    create_manager_whisper_token in agent/livekit_utils.py) - that joins a
    separate "{room}-whisper" room used for a one-way voice-to-text hint
    channel to the AI, with no main-call audio piped into it, so it cannot
    be used to listen to a live call (see api/services/livekit_rooms.py's
    module docstring).

    Room name is derived via the outbound-{lead_id} convention
    (agent/call_lifecycle.py's _OUTBOUND_ROOM_RE) - no room_name column
    exists on Call yet. Full "take over" (speak, replace the AI) is a
    separate, unscoped decision - see docs/API_CONTRACT.md's
    POST /calls/{id}/takeover entry.
    """
    call = _get_user_call(db, user, call_id)
    if call.status != "active":
        raise HTTPException(status_code=409, detail="Call is not active")

    room_name = f"outbound-{call.lead_id}"
    try:
        token = create_listener_token(room_name, identity=f"manager-{user.id}")
        url = livekit_url()
    except RuntimeError as e:
        # LIVEKIT_API_KEY/SECRET not configured.
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Failed to mint listen-only token for call %s", call_id)
        raise HTTPException(status_code=503, detail="LiveKit is unavailable right now")

    return CallMonitorToken(room_name=room_name, token=token, livekit_url=url)


@router.get("/{call_id}/recording")
def get_recording(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Day 11: streams the recording's bytes through our own API - the
    storage directory (api/services/recording_storage.py) is never mounted
    as a static path, so this endpoint is the only way to reach a
    recording, not a raw public URL.
    """
    call = _get_user_call(db, user, call_id)
    if not call.recording_url:
        raise HTTPException(status_code=404, detail="Recording not found")

    path = get_recording_path(str(call_id))
    if path is None:
        raise HTTPException(status_code=404, detail="Recording not found")

    return FileResponse(path, media_type="audio/wav", filename=f"{call_id}.wav")


@router.get("/{call_id}/transcript", response_model=PaginatedTranscript)
def get_transcript(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    _get_user_call(db, user, call_id)

    q = (
        db.query(Transcript)
        .filter(Transcript.call_id == call_id)
        .order_by(Transcript.timestamp.asc())
    )
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedTranscript(items=items, total=total, page=page, page_size=page_size)
