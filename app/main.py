"""
No Wrong Door — Unified Resident API

A single API that returns a unified view of a resident,
assembled from two unreliable mock sources (REST + XML).
"""

import asyncio
from fastapi import FastAPI, HTTPException
from app.adapters.rest_adapter import fetch_all_residents
from app.adapters.xml_adapter import fetch_all_benefits, fetch_single_benefit
from app.models.schemas import (
    Resident,
    BenefitRecord,
    ResidentsResponse,
    SingleResidentResponse,
)

app = FastAPI(
    title="No Wrong Door",
    description="Unified Resident API — One call, one resident, everything known about them.",
    version="0.3.0",
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
    Fetches all residents from BOTH the REST Resident Index and
    the XML Benefits Register concurrently.

    Returns a unified response with:
    - Deduplicated REST residents
    - XML benefit records
    - Status indicator (success / partial_success / error)
    - Warnings for any issues encountered
    """
    # Fetch from both sources concurrently using asyncio.gather
    (residents_data, rest_warnings), (benefits_data, xml_warnings) = (
        await asyncio.gather(
            fetch_all_residents(),
            fetch_all_benefits(),
        )
    )

    # Combine all warnings
    all_warnings = rest_warnings + xml_warnings

    # Convert raw dicts to Pydantic models
    residents = [Resident(**r) for r in residents_data]
    benefits = [BenefitRecord(**b) for b in benefits_data]

    # Determine status
    if not residents_data and not benefits_data:
        status = "error"
    elif all_warnings:
        status = "partial_success"
    else:
        status = "success"

    return ResidentsResponse(
        status=status,
        total_residents=len(residents),
        total_benefits=len(benefits),
        warnings=all_warnings,
        residents=residents,
        benefits=benefits,
    )


@app.get("/residents/{resident_id}", response_model=SingleResidentResponse)
async def get_single_resident(resident_id: str):
    """
    Fetches a single resident by their ID from the REST Resident Index.

    Also attempts to find any matching benefit records from the
    XML Benefits Register (matched by name, not by ID — since the
    two systems do not share a key).
    """
    import httpx

    warnings: list[str] = []
    resident_data = None

    # Fetch the single resident from REST
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"http://127.0.0.1:8081/residents/{resident_id}"
            )
            if response.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Resident '{resident_id}' not found in the Resident Index."
                )
            response.raise_for_status()
            resident_data = response.json()

    except httpx.ConnectError:
        warnings.append("REST Resident Index is unreachable.")
    except httpx.TimeoutException:
        warnings.append("REST Resident Index timed out.")
    except HTTPException:
        raise  # Re-raise the 404
    except Exception as e:
        warnings.append(f"REST error: {str(e)}")

    if resident_data is None and not warnings:
        raise HTTPException(status_code=404, detail="Resident not found.")

    # Build the resident model
    resident = Resident(**resident_data) if resident_data else None

    # Determine status
    if resident is None:
        status = "error"
    elif warnings:
        status = "partial_success"
    else:
        status = "success"

    return SingleResidentResponse(
        status=status,
        warnings=warnings,
        resident=resident,
        benefits=[],  # Benefits matching will be added in Phase 4 (stretch goal)
    )
