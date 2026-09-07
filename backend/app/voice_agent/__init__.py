"""LiveKit voice agent worker -- powers the browser test-call voice
pipeline with real WebRTC, VAD-based turn detection, and barge-in.

This is a separate long-running process (see docker-compose.yml's
``livekit_agent`` service), not part of the FastAPI app. It connects OUT
to LiveKit Cloud (LIVEKIT_URL) -- no inbound ports needed.
"""
