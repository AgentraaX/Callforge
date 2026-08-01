"""Conversion / objection analytics endpoints. Built Day 12."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.db.session import get_db
from api.dependencies import get_current_user
from api.models import User
from api.services.analytics import compute_conversion_stats, get_objection_stats

router = APIRouter(prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_current_user)])


@router.get("/conversion")
def get_conversion_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """conversion_rate = bookings / total_calls, per campaign and overall -
    see api/services/analytics.py for why total_calls, not completed_calls,
    is the denominator."""
    return compute_conversion_stats(db, user)


@router.get("/objections")
def get_objections(db: Session = Depends(get_db)):
    """Returns the objections playbook (text/response/category/success_rate)
    as-is - a global reference snapshot, not a per-call aggregation. See
    api/services/analytics.py's docstring for why."""
    return get_objection_stats(db)
