"""
No Wrong Door — Unified Resident API

A single API that returns a unified view of a resident,
assembled from two unreliable mock sources (REST + XML).
"""

import asyncio
from fastapi import FastAPI, HTTPException
from app.adapters.rest_adapter import fetch_all_residents
from app.adapters.xml_adapter import fetch_all_benefits, fetch_single_benefit
from app.matcher import find_matches, find_matches_for_single
from app.models.schemas import (
    UnifiedResident,
    BenefitRecord,
    ResidentsResponse,
    SingleResidentResponse,
)
from app.cache import get_cache_info
from app.circuit_breaker import xml_circuit_breaker

app = FastAPI(
    title="No Wrong Door",
    description="Unified Resident API — One call, one resident, everything known about them.",
    version="1.0.0",
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


@app.get("/status")
async def system_status():
    """
    Returns the health status of all upstream sources,
    the circuit breaker state, and cache information.
    Useful for monitoring and debugging.
    """
    return {
        "service": "no-wrong-door-api",
        "upstream_sources": {
            "rest_resident_index": {
                "url": "http://127.0.0.1:8081",
                "status": "available",
            },
            "xml_benefits_register": {
                "url": "http://127.0.0.1:8082",
                "circuit_breaker": xml_circuit_breaker.get_status(),
            },
        },
        "cache": get_cache_info(),
    }


@app.get("/residents", response_model=ResidentsResponse)
async def get_all_residents():
    """
    Fetches all residents from BOTH the REST Resident Index and
    the XML Benefits Register concurrently.

    Performs identity matching to link REST residents with their
    XML benefit records using a weighted scoring algorithm.

    Returns a unified response with matched and unmatched records.
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

    # Perform identity matching
    matches = find_matches(residents_data, benefits_data)

    # Track which XML records were matched
    matched_xml_refs = set()

    # Build buckets
    matched_data = []
    rest_only_data = []
    xml_only_data = []

    for resident in residents_data:
        resident_id = resident.get("id", "")
        
        if resident_id in matches:
            # Person is in both systems
            matched_benefits = []
            for match in matches[resident_id]:
                if match.get("ref"):
                    matched_xml_refs.add(match["ref"])
                matched_benefits.append(BenefitRecord(**match))
            
            matched_data.append(UnifiedResident(
                **resident,
                matched_benefits=matched_benefits,
            ))
        else:
            # Person is ONLY in REST
            from app.models.schemas import Resident
            rest_only_data.append(Resident(**resident))

    # Find people ONLY in XML
    for benefit in benefits_data:
        if benefit.get("ref") not in matched_xml_refs:
            xml_only_data.append(BenefitRecord(**benefit))

    # Determine status
    if not residents_data and not benefits_data:
        status = "error"
    elif all_warnings:
        status = "partial_success"
    else:
        status = "success"

    return ResidentsResponse(
        status=status,
        total_rest_records=len(residents_data),
        total_xml_records=len(benefits_data),
        total_matched=len(matched_data),
        total_rest_only=len(rest_only_data),
        total_xml_only=len(xml_only_data),
        warnings=all_warnings,
        matched_data=matched_data,
        rest_only_data=rest_only_data,
        xml_only_data=xml_only_data,
    )


@app.get("/residents/search", response_model=ResidentsResponse)
async def search_residents(name: str):
    """
    Searches for residents by name (first or last name) across BOTH
    the REST Resident Index and the XML Benefits Register.

    This is the endpoint a caseworker would actually use — they know
    the resident's name, not their system ID.

    Case-insensitive partial match: searching "whit" would find
    "Whitlock", "Whitney", etc. in both systems.

    Results:
    - `residents`: REST residents matching the name (with matched XML benefits)
    - `unmatched_benefits`: XML-only records matching the name (no REST record)
    """
    from app.matcher import parse_xml_name

    # Fetch from both sources concurrently
    (residents_data, rest_warnings), (benefits_data, xml_warnings) = (
        await asyncio.gather(
            fetch_all_residents(),
            fetch_all_benefits(),
        )
    )

    all_warnings = rest_warnings + xml_warnings

    # Split search term into parts to handle full names (e.g., "Jennifer Whitlock")
    search_parts = name.strip().lower().split()
    
    # Filter REST residents (all search parts must be in the full name)
    filtered_residents = []
    for r in residents_data:
        full_name = f"{r.get('first_name', '')} {r.get('last_name', '')}".lower()
        if all(part in full_name for part in search_parts):
            filtered_residents.append(r)

    # Perform identity matching on filtered REST residents
    matches = find_matches(filtered_residents, benefits_data)

    # Track which XML refs were matched to REST residents
    matched_xml_refs = set()

    # Build buckets for filtered results
    matched_data = []
    rest_only_data = []
    xml_only_data = []

    for resident in filtered_residents:
        resident_id = resident.get("id", "")
        
        if resident_id in matches:
            # Person is in both systems
            matched_benefits = []
            for match in matches[resident_id]:
                if match.get("ref"):
                    matched_xml_refs.add(match["ref"])
                matched_benefits.append(BenefitRecord(**match))
            
            matched_data.append(UnifiedResident(
                **resident,
                matched_benefits=matched_benefits,
            ))
        else:
            # Person is ONLY in REST
            from app.models.schemas import Resident
            rest_only_data.append(Resident(**resident))

    # Also search XML-only records (people who exist in XML but NOT in REST)
    for benefit in benefits_data:
        ref = benefit.get("ref", "")
        # Skip if already matched to a REST resident in our results
        if ref in matched_xml_refs:
            continue

        # Parse the XML name and search it
        xml_first, xml_last = parse_xml_name(benefit.get("name", ""))
        xml_full_name = f"{xml_first} {xml_last}".lower()
        
        if all(part in xml_full_name for part in search_parts):
            xml_only_data.append(BenefitRecord(**benefit))

    # Determine status
    total_found = len(matched_data) + len(rest_only_data) + len(xml_only_data)
    if total_found == 0:
        status = "error"
        all_warnings.append(f"No residents found matching name '{name}'.")
    elif all_warnings:
        status = "partial_success"
    else:
        status = "success"

    # Calculate exactly how many XML records matched the search
    total_xml_found = sum(len(r.matched_benefits) for r in matched_data) + len(xml_only_data)

    return ResidentsResponse(
        status=status,
        total_rest_records=len(filtered_residents),
        total_xml_records=total_xml_found,
        total_matched=len(matched_data),
        total_rest_only=len(rest_only_data),
        total_xml_only=len(xml_only_data),
        warnings=all_warnings,
        matched_data=matched_data,
        rest_only_data=rest_only_data,
        xml_only_data=xml_only_data,
    )


@app.get("/residents/{resident_id}", response_model=SingleResidentResponse)
async def get_single_resident(resident_id: str):
    """
    Fetches a single resident by their ID from the REST Resident Index.

    Also fetches all XML benefit records and performs identity matching
    to find any benefits belonging to this resident.
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

    # Fetch XML benefits and match
    matched_benefits = []
    if resident_data:
        benefits_data, xml_warnings = await fetch_all_benefits()
        warnings.extend(xml_warnings)

        if benefits_data:
            matched = find_matches_for_single(resident_data, benefits_data)
            matched_benefits = [BenefitRecord(**m) for m in matched]

    # Build the unified resident model
    resident = UnifiedResident(
        **resident_data,
        matched_benefits=matched_benefits,
    ) if resident_data else None

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
    )
