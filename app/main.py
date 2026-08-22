"""
No Wrong Door — Unified Resident API

A single API that returns a unified view of a resident,
assembled from two unreliable mock sources (REST + XML).
"""

from fastapi import FastAPI

app = FastAPI(
    title="No Wrong Door",
    description="Unified Resident API — One call, one resident, everything known about them.",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for our own API.
    Returns the status of this service.
    """
    return {
        "status": "ok",
        "service": "no-wrong-door-api",
    }
