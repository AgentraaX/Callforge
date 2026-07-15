"""Pydantic schemas for Campaign endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CampaignCreate(BaseModel):
    name: str
    pitch_variant_a: str | None = None
    pitch_variant_b: str | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    pitch_variant_a: str | None = None
    pitch_variant_b: str | None = None


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status: str
    pitch_variant_a: str | None
    pitch_variant_b: str | None
    created_at: datetime
    updated_at: datetime
