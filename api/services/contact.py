"""Landing-page Contact form -> email, via the same generic SMTP setup
already used for the daily briefing (api/services/briefing.py) - works
with any provider (Gmail, Outlook, a company mail server) via SMTP_* in
.env, no new integration needed.
"""
import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

logger = logging.getLogger("api.services.contact")


def _send_contact_email_sync(name: str, email: str, message: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL")
    # Falls back to the briefing recipient (a real, already-configured
    # inbox) rather than requiring a brand-new env var just for this form.
    to_email = os.getenv("CONTACT_RECIPIENT_EMAIL") or os.getenv("BRIEFING_RECIPIENT_EMAIL")

    if not all([host, username, password, from_email, to_email]):
        raise RuntimeError("SMTP not fully configured - see .env's SMTP_*/CONTACT_RECIPIENT_EMAIL vars")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"CallForge contact form: {name}"
    msg["From"] = from_email
    msg["To"] = to_email
    # Lets whoever's inbox this lands in just hit "Reply" to respond to the
    # visitor directly, without the visitor's address needing to be the
    # SMTP envelope sender (most providers reject sending as an arbitrary
    # From address anyway).
    msg["Reply-To"] = formataddr((name, email))

    text_body = f"From: {name} <{email}>\n\n{message}"
    html_body = f"<p><b>From:</b> {name} &lt;{email}&gt;</p><p>{message}</p>"
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(from_email, [to_email], msg.as_string())


async def send_contact_email(name: str, email: str, message: str) -> None:
    await asyncio.to_thread(_send_contact_email_sync, name, email, message)
