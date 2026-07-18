"""Day 11: call recording storage.

No live-call audio capture exists yet - that's a separate, unbuilt piece
(LiveKit Egress or a custom audio-mixing capture during the call). This is
the storage side only: given recording bytes, store them access-controlled
and link calls.recording_url; given a call_id, retrieve them back through
our own API - never a raw public path.

Section 11 of the spec doc flags recordings/transcripts as containing real
prospect data needing access control "from Day 1, don't retrofit security
at the end" - this is why _STORAGE_DIR is never mounted as a static
directory. The only way to reach a file here is through
api/routers/calls.py's GET /{id}/recording, which streams bytes through our
own code. That endpoint has no authentication yet, because no auth system
exists anywhere in this API yet (POST /auth/login is still "not yet built"
per docs/API_CONTRACT.md) - flagged here plainly rather than left implicit,
since it's the one thing a real deployment must not skip.
"""

import logging
import uuid
from pathlib import Path

from api.db.session import SessionLocal
from api.models import Call

logger = logging.getLogger("api.services.recording_storage")

_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "recordings"


def _ensure_storage_dir() -> None:
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def save_recording(call_id: str, audio_bytes: bytes) -> str:
    """Writes audio_bytes for call_id, updates calls.recording_url, and
    returns the retrieval URL - a route on our own API, not a raw file path
    or a publicly reachable link."""
    call_uuid = uuid.UUID(call_id)  # deliberately not swallowed - a bad id shouldn't silently no-op
    _ensure_storage_dir()

    path = _STORAGE_DIR / f"{call_id}.wav"
    path.write_bytes(audio_bytes)

    recording_url = f"/calls/{call_id}/recording"
    with SessionLocal() as session:
        call = session.get(Call, call_uuid)
        if call is not None:
            call.recording_url = recording_url
            session.commit()

    logger.info("Recording saved", extra={"call_id": call_id, "bytes": len(audio_bytes)})
    return recording_url


def get_recording_path(call_id: str) -> Path | None:
    """Returns the local file path for call_id's recording, or None if it
    doesn't exist. Callers must stream the file's bytes through a
    controlled response, never return or redirect to this path directly."""
    path = _STORAGE_DIR / f"{call_id}.wav"
    return path if path.is_file() else None
