# DECISIONS.md — Architectural Decisions & Degradation Policy

## 1. REST Pagination Deduplication

**Problem:** The REST Resident Index uses an index ordered by `last_contact`, which shifts while we page through results. This causes the `build_pages` logic to slip backwards ~60% of the time, producing 41 duplicate records across 27 pages.

**Decision:** We use a Python dictionary keyed by the resident's `id` field to deduplicate. As we loop through each page, we only insert a resident into the dictionary if their `id` has not been seen before. Duplicates are silently absorbed.

**Why a dictionary and not a set?** A set can only track IDs. A dictionary lets us track the full resident record alongside the ID, so we can deduplicate and collect data in a single pass.

**Trade-off:** We report the number of duplicates found in the `warnings` field of the API response, so the caller knows the data was cleaned. This is transparent and auditable.

---

## 2. XML Retry & Timeout Policy

**Problem:** The XML Benefits Register intentionally sleeps 0.7–2.4 seconds per request and returns a `500 Internal Server Error` on 15% of requests.

**Decision:**
- **Timeout threshold:** 3.0 seconds (server max delay 2.4s + 0.6s network buffer).
- **Retry count:** Up to 3 attempts on 500 errors or timeouts.
- **Retry delay:** 0.5 seconds between attempts.

**Why 3.0 seconds?** Setting it lower (e.g., 1.5s) would cut off successful responses that happen to be slow. Setting it higher (e.g., 10s) would make caseworkers wait too long if the server is truly dead.

**Why 3 retries?** With a 15% failure rate, the probability of failing all 3 attempts is 0.15³ = 0.34%, which is acceptably rare.

---

## 3. Graceful Degradation Policy

**Principle:** Partial data beats an error page. If one source is unavailable, we return what we have with a clear warning.

| Failure Scenario | What the Caller Gets |
| :--- | :--- |
| Both sources respond | `status: "success"`, full data, no warnings |
| REST works, XML fails | `status: "partial_success"`, REST data only + warning explaining XML failure |
| REST works, XML times out | `status: "partial_success"`, REST data only + timeout warning |
| REST fails, XML works | `status: "partial_success"`, XML data only + warning explaining REST failure |
| Both sources fail | `status: "error"`, empty data + warnings for both failures |

---

## 4. Concurrent Fetching

**Decision:** We use `asyncio.gather()` to fetch from REST and XML simultaneously, not sequentially.

**Why?** If we fetched sequentially, the total wait time would be REST time + XML time (potentially 0s + 2.4s = 2.4s). By fetching concurrently, the total wait time is max(REST time, XML time), which is faster because both network calls happen at the same time.

---

## 5. Caching with TTL Expiry

**Problem:** The XML server takes 0.7–2.4 seconds per request. If 50 caseworkers hit our API in the same minute, we would make 50 slow calls to the XML server, causing massive delays.

**Decision:** We cache results in memory with a Time-To-Live (TTL):
- **REST:** 60 seconds — The REST service is fast, and data changes frequently (the `last_contact` field updates often). A short TTL keeps data fresh.
- **XML:** 120 seconds — The XML service is slow and unreliable. Benefit codes and review dates change infrequently. A longer TTL avoids unnecessary slow calls.

**Trade-off:** Cached data may be up to 60–120 seconds stale. For a social services application where caseworkers are reviewing cases (not making real-time transactions), this staleness is acceptable. The `warnings` field transparently tells the caller when data is served from cache.

---

## 6. Circuit Breaker — Dynamic Polling Strategy

**Problem:** When the XML server is completely dead (not just a random 500 error), every caseworker request would waste 3 seconds waiting for a timeout before falling back to REST-only data. With 50 caseworkers, that's 50 × 3 = 150 seconds of collective wasted time.

**Decision:** We implemented a Dynamic Polling circuit breaker with three behaviors:

| Server State | Circuit State | Background Polling | Caseworker Experience |
| :--- | :--- | :--- | :--- |
| Healthy | CLOSED | None (zero wasted traffic) | Full data from both sources |
| Dead | OPEN | Ping `/health` every 1 second | Instant response with REST data + warning |
| Recovering | OPEN → CLOSED | Poller detects `/health` OK, stops | Next request gets full data |

**How it decides "truly dead" vs "random failure":**
When a request fails (500 error or timeout), we don't immediately trip the breaker. We first ping `/health` (which is exempt from the server's slowness and crash traps). If `/health` also fails, the server is truly dead and we trip the breaker. If `/health` succeeds, it was just a random 15% failure and we don't trip.

**Why 1-second polling when OPEN?** The server is dead and nobody else is using it, so aggressive polling doesn't cause harm. It minimizes the recovery "blind spot" to at most 1 second.

**Why no polling when CLOSED?** Zero wasted network traffic when the system is healthy.

