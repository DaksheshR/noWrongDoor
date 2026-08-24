"""
REST Adapter — Fetches and deduplicates residents from the REST Resident Index.

Handles:
- Paginated fetching (loops through all pages using 'has_more' flag)
- Deduplication (uses a dictionary keyed by 'id' to remove duplicates
  caused by the page-slipping bug in the REST service)
- Network errors (timeout, connection refused) with graceful warnings

Note: No caching for REST. The server is fast and reliable, so we always
fetch fresh data to avoid serving stale 'last_contact' values.
"""

import httpx

REST_BASE_URL = "http://127.0.0.1:8081"
REST_TIMEOUT = 5.0  # seconds — REST is fast, so 5s is generous


async def fetch_all_residents() -> tuple[list[dict], list[str]]:
    """
    Fetches ALL residents from the REST service, page by page,
    and deduplicates them.

    Always fetches fresh data (no caching) because the REST server
    is fast, reliable, and its data changes frequently.

    Returns:
        A tuple of (list_of_unique_residents, list_of_warnings).
        If the REST service is down, returns ([], [warning_message]).
    """
    unique_residents: dict[str, dict] = {}  # keyed by 'id' for deduplication
    warnings: list[str] = []
    page = 1
    duplicates_found = 0

    try:
        async with httpx.AsyncClient(timeout=REST_TIMEOUT) as client:
            while True:
                response = await client.get(
                    f"{REST_BASE_URL}/residents",
                    params={"page": page}
                )
                response.raise_for_status()
                data = response.json()

                for resident in data.get("results", []):
                    resident_id = resident.get("id")
                    if resident_id in unique_residents:
                        duplicates_found += 1
                    else:
                        unique_residents[resident_id] = resident

                # Stop if there are no more pages
                if not data.get("has_more", False):
                    break

                page += 1

        # (Deduplication is successful, so we don't emit a warning. 
        # Emitting a warning here would constantly downgrade the API 
        # to 'partial_success' even when healthy.)

    except httpx.ConnectError:
        warnings.append(
            "REST Resident Index is unreachable. "
            "Could not establish a connection to the service."
        )
    except httpx.TimeoutException:
        warnings.append(
            f"REST Resident Index timed out after {REST_TIMEOUT} seconds."
        )
    except httpx.HTTPStatusError as e:
        warnings.append(
            f"REST Resident Index returned an error: {e.response.status_code}."
        )
    except Exception as e:
        warnings.append(
            f"REST Resident Index encountered an unexpected error: {str(e)}"
        )

    return list(unique_residents.values()), warnings
