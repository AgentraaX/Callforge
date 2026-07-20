"""Morning briefing endpoint. Built Day 9."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from api.services.briefing import generate_briefing_data

router = APIRouter(prefix="/briefing", tags=["briefing"], dependencies=[Depends(get_current_user)])


@router.get("/today")
async def get_todays_briefing():
    """Same data structure the 8 AM email is built from (see
    api/services/briefing.py) - covers yesterday's activity, matching what
    the morning email just sent. Frontend spec requires in-app and emailed
    numbers to match exactly; both read this one generator."""
    target_date = datetime.now(timezone.utc).date() - timedelta(days=1)
    return await generate_briefing_data(target_date)
