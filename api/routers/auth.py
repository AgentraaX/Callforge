"""Auth endpoints (login, session)."""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
