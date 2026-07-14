"""FastAPI app entrypoint. Owned by Person 4."""
from fastapi import FastAPI

from api.routers import campaigns, calls

app = FastAPI(title="CallForge API")

app.include_router(campaigns.router)
app.include_router(calls.router)


@app.get("/health")
def health():
    return {"status": "ok"}
