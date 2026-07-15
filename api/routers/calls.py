"""Call log and transcript endpoints. Built Day 4. Owned by Person 4."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.models import Call, Transcript
from api.schemas.call import CallOut, PaginatedCalls
from api.schemas.transcript import PaginatedTranscript

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
