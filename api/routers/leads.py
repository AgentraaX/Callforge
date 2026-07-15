"""Lead listing/detail/status-update endpoints."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.models import Lead
from api.schemas.lead import LeadOut, LeadUpdate, PaginatedLeads

router = APIRouter(prefix="/leads", tags=["leads"])

_VALID_STATUSES = {"new", "contacted", "qualified", "booked", "disqualified"}


@router.get("", response_model=PaginatedLeads)
def list_leads(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    campaign_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
):
    if status and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid values: {', '.join(sorted(_VALID_STATUSES))}",
        )

    q = db.query(Lead)
    if campaign_id:
        q = q.filter(Lead.campaign_id == campaign_id)
    if status:
        q = q.filter(Lead.status == status)
    q = q.order_by(Lead.created_at.desc())

    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedLeads(items=items, total=total, page=page, page_size=page_size)


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(lead_id: uuid.UUID, payload: LeadUpdate, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if payload.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid values: {', '.join(sorted(_VALID_STATUSES))}",
        )

    lead.status = payload.status
    db.commit()
    db.refresh(lead)
    return lead
