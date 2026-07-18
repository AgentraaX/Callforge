"""Pydantic schemas for Lead endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    campaign_id: uuid.UUID
    name: str
    phone: str
    email: str | None
    company: str | None
    status: str
    created_at: datetime


class PaginatedLeads(BaseModel):
    items: list[LeadOut]
    total: int
    page: int
    page_size: int


class LeadUpdate(BaseModel):
    status: str


class LeadUploadResult(BaseModel):
    created: int
    skipped: int
    errors: list[str] = []
