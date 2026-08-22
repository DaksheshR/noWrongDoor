# DECISIONS.md — Architectural Decisions & Degradation Policy

## 1. REST Pagination Deduplication

**Problem:** The REST Resident Index uses an index ordered by `last_contact`, which shifts while we page through results. This causes the `build_pages` logic to slip backwards ~60% of the time, producing 41 duplicate records across 27 pages.

**Decision:** We use a Python dictionary keyed by the resident's `id` field to deduplicate. As we loop through each page, we only insert a resident into the dictionary if their `id` has not been seen before. Duplicates are silently absorbed.

**Why a dictionary and not a set?** A set can only track IDs. A dictionary lets us track the full resident record alongside the ID, so we can deduplicate and collect data in a single pass.

**Trade-off:** We report the number of duplicates found in the `warnings` field of the API response, so the caller knows the data was cleaned. This is transparent and auditable.
