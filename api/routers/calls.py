"""Call log and transcript endpoints. Built Day 4. Owned by Person 4."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.models import Call, Transcript
from api.schemas.call import CallOut, LiveCallState, PaginatedCalls
from api.schemas.transcript import PaginatedTranscript
from api.services.call_state import get_call_sentiment, get_call_state
from api.services.recording_storage import get_recording_path

router = APIRouter(prefix="/calls", tags=["calls"])

_VALID_STATUSES = {"pending", "active", "completed", "failed", "no-answer"}


@router.get("", response_model=PaginatedCalls)
def list_calls(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(default=None),
):
    if status and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid values: {', '.join(sorted(_VALID_STATUSES))}",
        )

    q = db.query(Call)
    if status:
        q = q.filter(Call.status == status)
    q = q.order_by(Call.created_at.desc())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedCalls(items=items, total=total, page=page, page_size=page_size)


@router.get("/{call_id}", response_model=CallOut)
def get_call(call_id: uuid.UUID, db: Session = Depends(get_db)):
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    return call


@router.get("/{call_id}/live", response_model=LiveCallState)
async def get_live_call_state(call_id: uuid.UUID, db: Session = Depends(get_db)):
    """Redis-backed live state for a dashboard to poll during an active call
    (Section 5 contract: call:{call_id}:state / :sentiment, written by the
    agent - see agent/call_lifecycle.py). `status` is the durable Postgres
    value; `live_status`/`live_updated_at` reflect the last Redis write and
    are None if the call never ran through the agent (or Redis expired it).
    """
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    state = await get_call_state(str(call_id))
    sentiment = await get_call_sentiment(str(call_id))

    return LiveCallState(
        call_id=call_id,
        status=call.status,
        live_status=state.get("status") if state else None,
        live_updated_at=datetime.fromisoformat(state["updated_at"]) if state else None,
        sentiment=sentiment,
    )


@router.get("/{call_id}/recording")
def get_recording(call_id: uuid.UUID, db: Session = Depends(get_db)):
    """Day 11: streams the recording's bytes through our own API - the
    storage directory (api/services/recording_storage.py) is never mounted
    as a static path, so this endpoint is the only way to reach a
    recording, not a raw public URL.

    No authentication check exists here yet, because no auth system exists
    anywhere in this API yet (see docs/API_CONTRACT.md's Auth section) -
    this is the one place a real deployment must add an authorization check
    before going live; it must not ship without one.
    """
    call = db.get(Call, call_id)
    if not call or not call.recording_url:
        raise HTTPException(status_code=404, detail="Recording not found")

    path = get_recording_path(str(call_id))
    if path is None:
        raise HTTPException(status_code=404, detail="Recording not found")

    return FileResponse(path, media_type="audio/wav", filename=f"{call_id}.wav")


@router.get("/{call_id}/transcript", response_model=PaginatedTranscript)
def get_transcript(
    call_id: uuid.UUID,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    call = db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    q = (
        db.query(Transcript)
        .filter(Transcript.call_id == call_id)
        .order_by(Transcript.timestamp.asc())
    )
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedTranscript(items=items, total=total, page=page, page_size=page_size)
