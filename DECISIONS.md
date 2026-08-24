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

**Decision:** We cache only XML results in memory with a 120-second TTL. REST data is **not cached** — it is fetched fresh on every request.

- **REST (no cache):** The REST server is fast (instant response) and reliable (0% failure rate). Caching it would risk serving stale `last_contact` values with no meaningful performance benefit.
- **XML (120s cache):** The XML server is slow (0.7–2.4s per request) and unreliable (40% failure rate). Caching avoids both the delay and the risk of failure for 2 minutes after a successful fetch.

**Trade-off:** XML cached data may be up to 120 seconds stale. For benefit codes and review dates that change rarely (monthly), this is acceptable. The `warnings` field transparently tells the caller when data is served from cache.

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

---

## 7. Day 2 Response — XML Failure Rate Increased to 40%

### What Changed
The XML Benefits Register failure rate was permanently increased from 15% to 40% (`--failure-rate 0.40`).

### What We Changed
**Increased `MAX_RETRIES` from 3 to 5** in `xml_adapter.py`.

| Retries | Failure at 15% (Day 1) | Failure at 40% (Day 2) |
| :--- | :--- | :--- |
| 3 retries | 0.15³ = 0.34% | 0.40³ = **6.4%** (1 in 16 — too high) |
| **5 retries** | 0.15⁵ = 0.008% | 0.40⁵ = **1.02%** (1 in 98 — acceptable) |

Even when all 5 retries fail (the rare 1.02% case), graceful degradation ensures the caseworker still receives REST data with a clear warning. The system never crashes.

### What We Chose NOT to Change
- **Timeout (3.0s):** The server's delay range (0.7–2.4s) didn't change, so our 3.0s threshold is still correct.
- **Circuit Breaker:** The circuit breaker distinguishes between "server is dead" (connection refused) and "server is just failing randomly" (500 errors). At 40%, the server is alive but unreliable — the circuit breaker correctly stays CLOSED because `/health` still responds. No change needed.
- **Cache TTL (120s for XML):** Caching becomes even more valuable at 40% failure because once we successfully fetch data, we avoid hitting the unreliable server for the next 2 minutes. No change needed.
- **Retry delay (0.5s):** We considered reducing this to speed up retries, but 0.5s gives the server breathing room between attempts.

### What We Would Have Done Differently
If we had known the failure rate would jump to 40% on Day 1, we would have:
1. **Made `MAX_RETRIES` configurable** via an environment variable (e.g., `XML_MAX_RETRIES=5`) so we could adjust it without a code change.
2. **Calculated the retry count dynamically** based on the target failure probability, using the formula: retries = ceil(log(target_probability) / log(failure_rate)). For a target of ≤1% at 40%: ceil(log(0.01) / log(0.40)) = ceil(5.03) = 5 retries.

---

## 8. Identity Matching — Weighted Scoring Algorithm

**Problem:** The REST Resident Index and XML Benefits Register have no shared key. The `_pid` field (the only link) is deliberately deleted when the servers boot. We need to figure out which REST resident matches which XML benefit record using only their data fields, which use completely different formats.

### Data Format Differences

| Field | REST Format | XML Format |
| :--- | :--- | :--- |
| Name | `first_name: "Jennifer"`, `last_name: "Whitlock"` | `name: "WHITLOCK, Jennifer"` |
| Date of Birth | `date_of_birth: "1985-02-18"` | `born: "1985-02-18"` (sometimes `null`) |
| Address | `address_line: "435 Alder Ave"` | `addr: "435 Alder Avenue"` |
| City | `city: "Weybridge"` | `town: "Weybridge"` |

### The Address Trap

After analyzing all 340 shared records, we found that addresses **always differ in only the last word** — REST uses abbreviations (Ave, Dr, Ln, Rd, St) while XML uses full words (Avenue, Drive, Lane, Road, Street). All preceding words are identical. Our solution: split the address into words and compare everything **except the last word**.

### Scoring Weights

| Field | Match | Missing | Different |
| :--- | :--- | :--- | :--- |
| Name (first + last, case-insensitive) | **30%** | — | 0% |
| Date of Birth | **30%** | **5%** (partial credit) | 0% |
| Address (ignore last word) | **25%** | — | 0% |
| City / Town (case-insensitive) | **15%** | — | 0% |

**Match Threshold: ≥ 70%**

### Why These Weights?

The weights were carefully chosen so that a mismatch in **one** field still allows a match, but a mismatch in **two** fields does not:

| Scenario | Name | DOB | Address | City | Total | Match? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| All match | 30 | 30 | 25 | 15 | **100%** | ✅ |
| Only name different (typo) | 0 | 30 | 25 | 15 | **70%** | ✅ |
| Only DOB different (error) | 30 | 0 | 25 | 15 | **70%** | ✅ |
| DOB missing (null) | 30 | 5 | 25 | 15 | **75%** | ✅ |
| Name AND DOB different | 0 | 0 | 25 | 15 | **40%** | ❌ |
| Name diff + DOB missing | 0 | 5 | 25 | 15 | **45%** | ❌ |

**Reasoning:** One field being wrong could be a data entry error (same person). Two fields being wrong likely means a different person at the same address.

### Results
- **340 out of 340 shared people correctly matched** (verified against `_pid` in raw data files).
- **0 false positives** (no incorrect matches).
- Address had higher weight (25%) than city (15%) because addresses are more unique — many residents share the same city but not the same street address.

---

## 9. Name Search Endpoint — Searching How Caseworkers Actually Work

**Problem:** Our API originally only supported looking up residents by their system ID (`GET /residents/R-10100`). In the real world, a caseworker walks in and says "I need to find Jennifer Whitlock" — they don't know her system ID.

**Decision:** We added a `GET /residents/search?name=` endpoint that accepts a name (first or last) and performs a case-insensitive partial match.

**Why multi-word partial match?** The developer identified a critical bug in the initial implementation: searching for "Jennifer Whitlock" failed because the code checked if the *entire* string was inside the first or last name. We changed the logic to split the search term into parts and verify that *all* parts exist within the resident's full name. This allows caseworkers to type "whit", "jennifer whitlock", or even "whitlock jennifer" and successfully find the resident.

**Why search both databases?** The initial version only searched REST residents. The developer identified that this created a blind spot: 200 people exist **only** in the XML Benefits Register (they have benefits but no REST record). By also parsing and searching XML names (`"LASTNAME, Firstname"` format), we ensure no resident is invisible to a name search regardless of which system they appear in.

**Response structure:**
- `residents` — REST residents matching the name (with matched XML benefits attached)
- `unmatched_benefits` — XML-only records matching the name (people with benefits but no REST record)

---

## 10. Neutral Data Bucketing — Removing the "Master System" Assumption

**Problem:** In the initial implementation, XML benefit records were nested inside the REST resident records (`residents: [ { matched_benefits: [] } ]`). This created an architectural assumption that the REST database was the "master" system and the XML database was just an accessory. The developer identified that this assumption is dangerous — if a person exists only in the XML database, treating REST as the master system means that person is structurally treated as an "orphan" or an error.

**Decision:** We restructured the API response to be completely neutral about the relationship between the two systems. The API now acts as an honest aggregator, sorting data into three explicit buckets:
1. `matched_data` (people who exist in BOTH systems)
2. `rest_only_data` (people who exist ONLY in the REST system)
3. `xml_only_data` (people who exist ONLY in the XML system)

**Why?** This ensures that no data is hidden or treated as secondary. If a caseworker searches for "Eastwood" and Donna Eastwood only exists in the XML system, she is clearly presented in the `xml_only_data` bucket, rather than being buried in an `unmatched_benefits` error array. We also updated all metadata counters (`total_rest_records`, `total_xml_records`, etc.) to perfectly reflect these three buckets.
