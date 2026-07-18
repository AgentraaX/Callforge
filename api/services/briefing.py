"""Day 9: morning briefing - generates real call/booking stats and emails
them via generic SMTP (works with any provider - Gmail, Outlook, a company
mail server, etc; see .env's SMTP_* vars), scheduled daily at 8 AM.

GET /briefing/today (api/routers/briefing.py) reads generate_briefing_data()
directly, and render_briefing_email() builds both the plain-text and HTML
email bodies from that same dict - the in-app and emailed numbers can't
drift apart, matching the frontend spec's Day 6 requirement.
"""

import asyncio
import logging
import os
import smtplib
from datetime import date, datetime, time as dtime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

from api.db.session import SessionLocal
from api.models import Booking, Call, Campaign
from shared.constants import BRIEFING_SENT_KEY
from shared.redis_client import get_redis

# Mirrors api/services/calendar.py's own load_dotenv() call - this module
# has no guarantee agent/config.py (which also calls it) ran first.
load_dotenv()

logger = logging.getLogger("api.services.briefing")


def _day_bounds_utc(target_date: date) -> tuple[datetime, datetime]:
    start = datetime.combine(target_date, dtime.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _generate_briefing_data_sync(target_date: date) -> dict:
    start, end = _day_bounds_utc(target_date)
    with SessionLocal() as session:
        calls = session.query(Call).filter(Call.created_at >= start, Call.created_at < end).all()
        by_status: dict[str, int] = {}
        for call in calls:
            by_status[call.status] = by_status.get(call.status, 0) + 1

        bookings = session.query(Booking).filter(Booking.created_at >= start, Booking.created_at < end).all()
        active_campaigns = session.query(Campaign).filter(Campaign.status == "active").count()

    return {
        "date": target_date.isoformat(),
        "total_calls": len(calls),
        "calls_by_status": by_status,
        "bookings_made": len(bookings),
        "booking_times": [b.scheduled_at.isoformat() for b in bookings],
        "active_campaigns": active_campaigns,
    }


async def generate_briefing_data(target_date: date) -> dict:
    return await asyncio.to_thread(_generate_briefing_data_sync, target_date)


def render_briefing_email(data: dict) -> tuple[str, str, str]:
    """Returns (subject, plain_text_body, html_body)."""
    subject = f"CallForge Morning Briefing - {data['date']}"

    status_lines = "\n".join(
        f"  - {status}: {count}" for status, count in sorted(data["calls_by_status"].items())
    ) or "  - no calls"

    text_body = (
        f"Morning Briefing for {data['date']}\n"
        f"{'=' * 40}\n\n"
        f"Total calls: {data['total_calls']}\n"
        f"By status:\n{status_lines}\n\n"
        f"Meetings booked: {data['bookings_made']}\n"
        f"Active campaigns: {data['active_campaigns']}\n"
    )

    status_rows = "".join(
        f"<tr><td>{status}</td><td>{count}</td></tr>" for status, count in sorted(data["calls_by_status"].items())
    ) or "<tr><td colspan='2'>no calls</td></tr>"

    html_body = f"""
    <html><body>
      <h2>CallForge Morning Briefing &mdash; {data['date']}</h2>
      <p><b>Total calls:</b> {data['total_calls']}</p>
      <table border="1" cellpadding="4" cellspacing="0">
        <tr><th>Status</th><th>Count</th></tr>
        {status_rows}
      </table>
      <p><b>Meetings booked:</b> {data['bookings_made']}</p>
      <p><b>Active campaigns:</b> {data['active_campaigns']}</p>
    </body></html>
    """

    return subject, text_body, html_body


def _send_email_sync(subject: str, text_body: str, html_body: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL")
    to_email = os.getenv("BRIEFING_RECIPIENT_EMAIL")

    if not all([host, username, password, from_email, to_email]):
        raise RuntimeError("SMTP not fully configured - see .env's SMTP_*/BRIEFING_RECIPIENT_EMAIL vars")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(from_email, [to_email], msg.as_string())


async def send_daily_briefing(target_date: date | None = None) -> bool:
    """Generates + emails the briefing for target_date (default: yesterday,
    matching an 8 AM job summarizing the day that just ended).

    Idempotent per the acceptance criteria: a second call for the same date
    - whether the real 8 AM schedule or a manual trigger - is a no-op
    (returns False), via a Redis SETNX lock. If the send itself fails, the
    lock is released so a genuine retry can still go through; only a
    confirmed send keeps the lock held.
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date() - timedelta(days=1)

    redis = get_redis()
    key = BRIEFING_SENT_KEY.format(date=target_date.isoformat())
    acquired = await redis.set(key, "1", nx=True, ex=60 * 60 * 24 * 2)
    if not acquired:
        logger.info("Briefing already sent for this date, skipping", extra={"date": target_date.isoformat()})
        return False

    data = await generate_briefing_data(target_date)
    subject, text_body, html_body = render_briefing_email(data)

    try:
        await asyncio.to_thread(_send_email_sync, subject, text_body, html_body)
    except Exception:
        logger.exception("Failed to send briefing email, releasing lock for retry", extra={"date": target_date.isoformat()})
        await redis.delete(key)
        return False

    logger.info("Briefing email sent", extra={"date": target_date.isoformat(), "total_calls": data["total_calls"]})
    return True
