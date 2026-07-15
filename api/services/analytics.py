"""Day 12: analytics aggregation - conversion and objection stats.

conversion_rate is bookings / total_calls, not completed_calls: a booking
can exist for a call that was never independently transitioned to
"completed" (test data proved this - 11 bookings against only 4 completed
calls out of 15 total, which would give a nonsensical >100% rate against
the completed-call denominator). total_calls is the correct, always-sane
denominator.

Objection-success analytics can't be computed from real per-call event
data yet - the `objections` table is a playbook (text/response/category/
success_rate), not a per-call log (see agent/graph/tools.py::log_objection's
docstring for why that table was deliberately never written to per-call).
get_objection_stats() returns the playbook as-is; it's a static reference
snapshot, not an aggregation over real call outcomes, and is empty until
someone seeds the playbook.
"""

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from api.models import Booking, Call, Campaign, Lead, Objection


def compute_conversion_stats(db: Session) -> dict:
    rows = (
        db.query(
            Campaign.id,
            Campaign.name,
            func.count(func.distinct(Call.id)).label("total_calls"),
            func.count(func.distinct(case((Call.status == "completed", Call.id)))).label("completed_calls"),
            func.count(func.distinct(Booking.id)).label("bookings"),
        )
        .outerjoin(Lead, Lead.campaign_id == Campaign.id)
        .outerjoin(Call, Call.lead_id == Lead.id)
        .outerjoin(Booking, Booking.call_id == Call.id)
        .group_by(Campaign.id, Campaign.name)
        .order_by(Campaign.name)
        .all()
    )

    per_campaign = []
    total_calls_all = completed_all = bookings_all = 0

    for campaign_id, campaign_name, total_calls, completed, bookings in rows:
        conversion_rate = bookings / total_calls if total_calls else 0.0
        per_campaign.append(
            {
                "campaign_id": str(campaign_id),
                "campaign_name": campaign_name,
                "total_calls": total_calls,
                "completed_calls": completed,
                "bookings": bookings,
                "conversion_rate": round(conversion_rate, 4),
            }
        )
        total_calls_all += total_calls
        completed_all += completed
        bookings_all += bookings

    overall_rate = bookings_all / total_calls_all if total_calls_all else 0.0

    return {
        "overall": {
            "total_calls": total_calls_all,
            "completed_calls": completed_all,
            "bookings": bookings_all,
            "conversion_rate": round(overall_rate, 4),
        },
        "by_campaign": per_campaign,
    }


def get_objection_stats(db: Session) -> list[dict]:
    """Returns the objections playbook as-is - a static/manually-curated
    reference, not an aggregation over real per-call objections (see this
    module's docstring). Empty until someone seeds the playbook."""
    objections = db.query(Objection).order_by(Objection.success_rate.desc().nullslast()).all()
    return [
        {
            "id": str(o.id),
            "text": o.text,
            "response": o.response,
            "category": o.category,
            "success_rate": float(o.success_rate) if o.success_rate is not None else None,
        }
        for o in objections
    ]
