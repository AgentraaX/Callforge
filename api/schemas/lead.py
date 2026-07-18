"""Pydantic schemas for Lead endpoints."""
import uuid

from pydantic import BaseModel, ConfigDict


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    name: str
    phone: str
    company: str | None
    status: str


class LeadUploadResult(BaseModel):
    created: int
    skipped: int
    errors: list[str] = []
