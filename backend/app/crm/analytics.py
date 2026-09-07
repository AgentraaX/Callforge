"""Dashboard aggregates -- one round trip per widget, all SQL-side."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import (
    DEAL_OPEN_STAGES,
    Activity,
    CallRecord,
    Contact,
    Deal,
)
from .schemas import AnalyticsOverview, DayCount, StageCount


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def overview(session: AsyncSession, org_id: str) -> AnalyticsOverview:
    now = _now()
    week_ago = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    contacts = int(
        await session.scalar(
            select(func.count()).select_from(Contact).where(Contact.org_id == org_id)
        )
        or 0
    )

    open_deals = int(
        await session.scalar(
            select(func.count())
            .select_from(Deal)
            .where(Deal.org_id == org_id, Deal.stage.in_(DEAL_OPEN_STAGES))
        )
        or 0
    )

    pipeline_value = float(
        await session.scalar(
            select(func.coalesce(func.sum(Deal.amount), 0))
            .where(Deal.org_id == org_id, Deal.stage.in_(DEAL_OPEN_STAGES))
        )
        or 0
    )

    won_this_month = int(
        await session.scalar(
            select(func.count())
            .select_from(Deal)
            .where(Deal.org_id == org_id, Deal.stage == "won", Deal.closed_at >= month_start)
        )
        or 0
    )

    won_total = int(
        await session.scalar(
            select(func.count()).select_from(Deal).where(Deal.org_id == org_id, Deal.stage == "won")
        )
        or 0
    )
    lost_total = int(
        await session.scalar(
            select(func.count()).select_from(Deal).where(Deal.org_id == org_id, Deal.stage == "lost")
        )
        or 0
    )
    decided = won_total + lost_total
    win_rate = round(won_total / decided, 3) if decided else 0.0

    calls_this_week = int(
        await session.scalar(
            select(func.count())
            .select_from(CallRecord)
            .where(CallRecord.org_id == org_id, CallRecord.created_at >= week_ago)
        )
        or 0
    )

    bookings_this_week = int(
        await session.scalar(
            select(func.count())
            .select_from(CallRecord)
            .where(
                CallRecord.org_id == org_id,
                CallRecord.outcome == "booked",
                CallRecord.created_at >= week_ago,
            )
        )
        or 0
    )

    open_tasks = int(
        await session.scalar(
            select(func.count())
            .select_from(Activity)
            .where(
                Activity.org_id == org_id,
                Activity.type == "task",
                Activity.completed_at.is_(None),
            )
        )
        or 0
    )
    overdue_tasks = int(
        await session.scalar(
            select(func.count())
            .select_from(Activity)
            .where(
                Activity.org_id == org_id,
                Activity.type == "task",
                Activity.completed_at.is_(None),
                Activity.due_at.is_not(None),
                Activity.due_at < now,
            )
        )
        or 0
    )

    stage_rows = await session.execute(
        select(Deal.stage, func.count(), func.coalesce(func.sum(Deal.amount), 0))
        .where(Deal.org_id == org_id)
        .group_by(Deal.stage)
    )
    by_stage = {stage: (int(cnt), float(amt)) for stage, cnt, amt in stage_rows}
    deals_by_stage = [
        StageCount(stage=s, count=by_stage.get(s, (0, 0.0))[0], total_amount=by_stage.get(s, (0, 0.0))[1])
        for s in ("new", "qualified", "demo", "proposal", "negotiation", "won", "lost")
    ]

    # 14-day call volume, zero-filled.
    day_rows = await session.execute(
        select(func.date(CallRecord.created_at), func.count())
        .where(CallRecord.org_id == org_id, CallRecord.created_at >= now - timedelta(days=14))
        .group_by(func.date(CallRecord.created_at))
    )
    counts = {str(d): int(c) for d, c in day_rows}
    calls_per_day = []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        calls_per_day.append(DayCount(date=day, count=counts.get(day, 0)))

    return AnalyticsOverview(
        contacts=contacts,
        open_deals=open_deals,
        pipeline_value=pipeline_value,
        won_this_month=won_this_month,
        win_rate=win_rate,
        calls_this_week=calls_this_week,
        bookings_this_week=bookings_this_week,
        open_tasks=open_tasks,
        overdue_tasks=overdue_tasks,
        deals_by_stage=deals_by_stage,
        calls_per_day=calls_per_day,
    )
