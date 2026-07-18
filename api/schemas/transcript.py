"""Pydantic schemas for Transcript endpoints."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TranscriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_id: uuid.UUID
    speaker: str
    text: str
    timestamp: datetime


class PaginatedTranscript(BaseModel):
    items: list[TranscriptOut]
    total: int
    page: int
    page_size: int
