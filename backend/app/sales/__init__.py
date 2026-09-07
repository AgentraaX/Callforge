"""Sales module -- lead capture, booking, and escalation."""
from .leads import Lead, extract, get, all_leads, stats, maybe_extract, score_lead, add_note
from .booking import (
    Booking, available_slots, confirm, cancel, all_bookings,
    format_slots_for_speech, format_confirmation_for_speech, BOOKING_TOOLS,
    BOOKING_INTENT_KEYWORDS, looks_like_booking_response, resolve_slot,
    extract_contact_info, extract_slot_pick, sounds_like_unverified_confirmation,
    booking_confirmed_by_context, is_placeholder_contact,
)
from .escalation import (
    EscalationCase, detect_escalation_trigger, should_escalate_failed_lookup,
    create_case, format_escalation_speech, all_cases, pending_cases,
)
