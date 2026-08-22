"""
XML Adapter — Fetches and parses benefit records from the XML Benefits Register.

Handles:
- XML parsing using xml.etree.ElementTree
- Retry logic (up to 3 attempts) for the 15% random 500 errors
- Timeout at 3.0 seconds (XML server max delay is 2.4s + 0.6s buffer)
- Caching (returns cached data if available and not expired)
- Circuit Breaker (instantly returns when server is known to be dead)
- Graceful degradation — returns empty list + warning if all retries fail
"""

import xml.etree.ElementTree as ET
import httpx
import asyncio
from app.cache import get_from_cache, set_in_cache
from app.circuit_breaker import xml_circuit_breaker

XML_BASE_URL = "http://127.0.0.1:8082"
XML_TIMEOUT = 3.0   # seconds — server max delay is 2.4s + 0.6s buffer
MAX_RETRIES = 3      # retry up to 3 times on 500 errors
RETRY_DELAY = 0.5    # seconds to wait between retries
CACHE_KEY = "xml_benefits"


def _parse_records_xml(xml_text: str) -> list[dict]:
    """
    Parses XML text into a list of benefit record dictionaries.

    Handles both single-record and multi-record responses.
    """
    records = []
    try:
        root = ET.fromstring(xml_text)

        # Find all <Record> elements (works for both <Records><Record>...
        # and standalone <Record>)
        record_elements = root.findall(".//Record")
        if root.tag == "Record":
            record_elements = [root]

        for record in record_elements:
            parsed = {}
            # Extract each field, using None if the element doesn't exist
            ref_el = record.find("Ref")
            parsed["ref"] = ref_el.text if ref_el is not None else None

            name_el = record.find("Name")
            parsed["name"] = name_el.text if name_el is not None else None

            born_el = record.find("Born")
            parsed["born"] = born_el.text if born_el is not None else None

            addr_el = record.find("Addr")
            parsed["address"] = addr_el.text if addr_el is not None else None

            town_el = record.find("Town")
            parsed["town"] = town_el.text if town_el is not None else None

            benefit_el = record.find("BenefitCode")
            parsed["benefit_code"] = benefit_el.text if benefit_el is not None else None

            review_el = record.find("ReviewDue")
            parsed["review_due"] = review_el.text if review_el is not None else None

            records.append(parsed)

    except ET.ParseError as e:
        # If XML is malformed, return empty list (handled by caller)
        pass

    return records


async def fetch_all_benefits() -> tuple[list[dict], list[str]]:
    """
    Fetches ALL benefit records from the XML service.
    Retries up to 3 times on 500 errors.

    Returns cached data if available and not expired.
    Instantly returns if the circuit breaker is OPEN.

    Returns:
        A tuple of (list_of_benefit_records, list_of_warnings).
        If the XML service is completely down, returns ([], [warning_message]).
    """
    # Check circuit breaker first — if OPEN, don't even try
    if xml_circuit_breaker.is_open:
        return [], [
            "XML Benefits Register circuit breaker is OPEN. "
            "Server is known to be down. Benefits data is unavailable."
        ]

    # Check cache second
    cached = get_from_cache(CACHE_KEY)
    if cached is not None:
        benefits, original_warnings = cached
        cache_warnings = ["XML data served from cache."]
        return benefits, cache_warnings

    warnings: list[str] = []
    last_error: str = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=XML_TIMEOUT) as client:
                response = await client.get(f"{XML_BASE_URL}/records")

                if response.status_code == 500:
                    last_error = (
                        f"XML Benefits Register returned a 500 error "
                        f"(attempt {attempt}/{MAX_RETRIES})."
                    )
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    else:
                        # All retries exhausted — check if server is truly dead
                        await xml_circuit_breaker.check_health_and_trip()
                        warnings.append(
                            f"XML Benefits Register failed after {MAX_RETRIES} "
                            f"retries (500 errors). Benefits data is unavailable."
                        )
                        return [], warnings

                response.raise_for_status()
                records = _parse_records_xml(response.text)

                # Store in cache (only if we got data)
                if records:
                    set_in_cache(CACHE_KEY, (records, warnings))

                return records, warnings

        except httpx.ConnectError:
            # Server is completely unreachable — trip the circuit breaker
            await xml_circuit_breaker.check_health_and_trip()
            warnings.append(
                "XML Benefits Register is unreachable. "
                "Could not establish a connection to the service."
            )
            return [], warnings

        except httpx.TimeoutException:
            last_error = (
                f"XML Benefits Register timed out after {XML_TIMEOUT} seconds "
                f"(attempt {attempt}/{MAX_RETRIES})."
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                # All retries exhausted — check if server is truly dead
                await xml_circuit_breaker.check_health_and_trip()
                warnings.append(
                    f"XML Benefits Register timed out after {MAX_RETRIES} "
                    f"retries. Benefits data is unavailable."
                )
                return [], warnings

        except Exception as e:
            warnings.append(
                f"XML Benefits Register encountered an unexpected error: {str(e)}"
            )
            return [], warnings

    return [], warnings


async def fetch_single_benefit(ref: str) -> tuple[dict | None, list[str]]:
    """
    Fetches a single benefit record by its reference ID.
    Retries up to 3 times on 500 errors.

    Returns:
        A tuple of (benefit_record_or_None, list_of_warnings).
    """
    # Check circuit breaker first
    if xml_circuit_breaker.is_open:
        return None, [
            "XML Benefits Register circuit breaker is OPEN. Server is down."
        ]

    warnings: list[str] = []

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=XML_TIMEOUT) as client:
                response = await client.get(f"{XML_BASE_URL}/records/{ref}")

                if response.status_code == 500:
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    else:
                        await xml_circuit_breaker.check_health_and_trip()
                        warnings.append(
                            f"XML Benefits Register failed after {MAX_RETRIES} "
                            f"retries for record '{ref}'."
                        )
                        return None, warnings

                if response.status_code == 404:
                    return None, warnings  # Record simply doesn't exist

                response.raise_for_status()
                records = _parse_records_xml(response.text)
                if records:
                    return records[0], warnings
                return None, warnings

        except httpx.ConnectError:
            await xml_circuit_breaker.check_health_and_trip()
            warnings.append(
                "XML Benefits Register is unreachable."
            )
            return None, warnings

        except httpx.TimeoutException:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                await xml_circuit_breaker.check_health_and_trip()
                warnings.append(
                    f"XML Benefits Register timed out after {MAX_RETRIES} retries."
                )
                return None, warnings

        except Exception as e:
            warnings.append(f"XML error: {str(e)}")
            return None, warnings

    return None, warnings
