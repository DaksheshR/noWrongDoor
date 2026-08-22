"""
No Wrong Door — Unified Resident API

A single API that returns a unified view of a resident,
assembled from two unreliable mock sources (REST + XML).
"""

from fastapi import FastAPI
from app.adapters.rest_adapter import fetch_all_residents
from app.models.schemas import Resident, ResidentsResponse

app = FastAPI(
    title="No Wrong Door",
    description="Unified Resident API — One call, one resident, everything known about them.",
    version="0.2.0",
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


@app.get("/residents", response_model=ResidentsResponse)
async def get_all_residents():
    """
    Fetches all residents from the REST Resident Index.
    Automatically deduplicates records caused by the pagination bug.
    Returns a unified response with status and warnings.
    """
    residents_data, warnings = await fetch_all_residents()

    # Convert raw dicts to Pydantic Resident models
    residents = [Resident(**r) for r in residents_data]

    # Determine status based on warnings
    if not residents_data:
        status = "error"
    elif warnings:
        status = "partial_success"
    else:
        status = "success"

    return ResidentsResponse(
        status=status,
        total_residents=len(residents),
        warnings=warnings,
        residents=residents,
    )
