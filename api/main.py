"""FastAPI app entrypoint. Owned by Person 4."""
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from api.routers import briefing, campaigns, calls
from api.services.briefing import send_daily_briefing


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

app.include_router(campaigns.router)
app.include_router(calls.router)
app.include_router(briefing.router)


@app.get("/health")
def health():
    return {"status": "ok"}
