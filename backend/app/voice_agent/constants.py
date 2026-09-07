"""Constants shared between the FastAPI backend (main.py) and the LiveKit
agent worker (agent.py) -- kept dependency-free so importing this from the
FastAPI process never drags in livekit.plugins (which registers itself at
import time and requires the main thread; FastAPI's sync endpoints run in
a worker thread pool)."""

AGENT_NAME = "callforge-sales-agent"
