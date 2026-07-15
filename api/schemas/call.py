"""Pydantic schemas for Call endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lead_id: uuid.UUID
    direction: str
    status: str
    sentiment: str | None
    duration: int | None
    recording_url: str | None
    created_at: datetime


class PaginatedCalls(BaseModel):
    items: list[CallOut]
    total: int
    page: int
    page_size: int


class LiveCallState(BaseModel):
    call_id: uuid.UUID
    status: str
    live_status: str | None  # from Redis call:{call_id}:state - may lag/be absent between turns
    live_updated_at: datetime | None
    sentiment: str | None
