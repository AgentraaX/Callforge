"""Public Contact form endpoint. No auth - a landing-page visitor isn't
logged in."""
import logging

from fastapi import APIRouter, HTTPException

from api.schemas.contact import ContactRequest, ContactResponse
from api.services.contact import send_contact_email

logger = logging.getLogger("api.routers.contact")

router = APIRouter(prefix="/contact", tags=["contact"])


@router.post("", response_model=ContactResponse)
async def submit_contact_form(payload: ContactRequest):
    try:
        await send_contact_email(payload.name, payload.email, payload.message)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Failed to send contact email")
        raise HTTPException(status_code=502, detail="Could not send your message. Please try again.")

    return ContactResponse()
