"""Campaign CRUD endpoints. Built Day 3."""
import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.dependencies import get_current_user
from api.models import Campaign, Lead
from api.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignOut
from api.schemas.lead import LeadUploadResult

router = APIRouter(prefix="/campaigns", tags=["campaigns"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    return db.query(Campaign).order_by(Campaign.created_at.desc()).all()


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    campaign = Campaign(**payload.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: uuid.UUID, payload: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/{campaign_id}/leads", response_model=LeadUploadResult, status_code=201)
def upload_leads(campaign_id: uuid.UUID, file: UploadFile = File(...), db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB cap
    raw_bytes = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV file too large (max 5MB)")

    raw = raw_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))

    required_cols = {"name", "phone"}
    if not required_cols.issubset(set(reader.fieldnames or [])):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must include columns: {', '.join(required_cols)}",
        )

    created, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):  # row 1 is header
        name = (row.get("name") or "").strip()
        phone = (row.get("phone") or "").strip()
        if not name or not phone:
            skipped += 1
            errors.append(f"Row {i}: missing name or phone")
            continue

        lead = Lead(
            campaign_id=campaign_id,
            name=name,
            phone=phone,
            email=(row.get("email") or "").strip() or None,
            company=(row.get("company") or "").strip() or None,
        )
        db.add(lead)
        created += 1

    db.commit()
    return LeadUploadResult(created=created, skipped=skipped, errors=errors)