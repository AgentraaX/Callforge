"""FastAPI app entrypoint. Owned by Person 4."""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Must run before any other project import - api.db.session and friends
# read DATABASE_URL/etc. via os.getenv() at import time, so .env has to be
# loaded before those modules are first imported (previously only
# api/services/{briefing,calendar,crm}.py called load_dotenv() themselves,
# each admittedly relying on import-order luck rather than a guarantee -
# outside Docker, where env_file supplies these as real OS env vars, that
# luck silently ran out and DB/LiveKit/etc. fell back to hardcoded defaults).
load_dotenv()

from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402
from apscheduler.triggers.cron import CronTrigger  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from api.routers import analytics, auth, briefing, calls, campaigns, contact, demo, leads  # noqa: E402
from api.services.briefing import send_daily_briefing  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Day 9: morning briefing, scheduled daily at 8 AM. send_daily_briefing()
    # is itself idempotent (Redis-locked per date), so this firing more than
    # once for the same day - a restart, a misfire replay - is harmless.
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_briefing, CronTrigger(hour=8, minute=0))
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="CallForge API", lifespan=lifespan)

# The frontend runs as its own Next.js server and proxies almost all
# requests server-side (see callforge_frontend's app/api/* route handlers),
# which doesn't need CORS at all - this exists as defense-in-depth for the
# few things that do call this API directly from a browser (e.g. the
# LiveKit demo/monitor widgets' token fetch, Swagger UI during dev).
_frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(campaigns.router)
app.include_router(calls.router)
app.include_router(leads.router)
app.include_router(briefing.router)
app.include_router(analytics.router)
app.include_router(demo.router)
app.include_router(contact.router)


@app.get("/health")
def health():
    return {"status": "ok"}
