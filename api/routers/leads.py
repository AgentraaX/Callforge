"""Lead CSV upload / management endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/leads", tags=["leads"])
