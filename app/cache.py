"""
In-Memory Cache with TTL (Time-To-Live) Expiry.

Caches the results of REST and XML fetches so we don't
hammer the slow/unreliable services on every single request.

TTL Policy:
- REST: 60 seconds  (fast service, data updates frequently)
- XML:  120 seconds  (slow service, data updates less often)
"""

import time
from typing import Any

# Cache storage: key -> (data, timestamp)
_cache: dict[str, tuple[Any, float]] = {}

# TTL values in seconds
REST_CACHE_TTL = 60.0
XML_CACHE_TTL = 120.0


def get_from_cache(key: str) -> Any | None:
    """
    Retrieves data from the cache if it exists and hasn't expired.

    Returns:
        The cached data if valid, or None if expired/missing.
    """
    if key not in _cache:
        return None

    data, timestamp = _cache[key]
    ttl = REST_CACHE_TTL if key == "rest_residents" else XML_CACHE_TTL

    # Check if the cached data has expired
    if time.time() - timestamp > ttl:
        # Expired — remove from cache and return None
        del _cache[key]
        return None

    return data


def set_in_cache(key: str, data: Any) -> None:
    """
    Stores data in the cache with the current timestamp.
    """
    _cache[key] = (data, time.time())


def clear_cache(key: str | None = None) -> None:
    """
    Clears the cache. If a key is provided, only that entry is cleared.
    If no key is provided, the entire cache is cleared.
    """
    if key is None:
        _cache.clear()
    elif key in _cache:
        del _cache[key]


def get_cache_info() -> dict:
    """
    Returns information about the current cache state.
    Useful for the /status endpoint.
    """
    info = {}
    for key, (data, timestamp) in _cache.items():
        ttl = REST_CACHE_TTL if key == "rest_residents" else XML_CACHE_TTL
        age = time.time() - timestamp
        info[key] = {
            "age_seconds": round(age, 1),
            "ttl_seconds": ttl,
            "expires_in_seconds": round(max(0, ttl - age), 1),
            "is_valid": age <= ttl,
        }
    return info
