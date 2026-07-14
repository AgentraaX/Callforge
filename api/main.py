"""FastAPI app entrypoint. Owned by Person 4."""
from fastapi import FastAPI

from api.routers import campaigns

app = FastAPI(title="CallForge API")

app.include_router(campaigns.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# TODO: include remaining routers (calls, leads, objections, analytics, auth) — Day 4+
