"""FastAPI app entrypoint. Owned by Person 4."""

from fastapi import FastAPI

app = FastAPI(title="CallForge API")


@app.get("/health")
def health():
    return {"status": "ok"}


# TODO: include routers (campaigns, calls, leads, objections, analytics, auth) — Day 3+
