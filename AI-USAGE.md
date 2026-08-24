# AI-USAGE.md — AI Tool Usage Disclosure

## Tools Used
- **Antigravity IDE (Claude)** — AI pair-programming assistant used throughout development.

---

## Human Contributions (Developer's Work)

### Analysis & Research
- Manually read and analyzed the hackathon problem document (`3 - No Wrong Door.docx`), the `README.md`, and participant handbook.
- Explored both raw data files (`_rest_data.json`, `_xml_data.json`) in the editor to understand field structures, population sizes, and relationships.
- Identified that `city` (REST) and `town` (XML) fields have matching values — a potential key for identity matching.
- Traced the code logic in `rest_service.py` and `xml_service.py` line by line to understand how the traps work (pagination duplication, `time.sleep`, `random.random() < FAILURE_RATE`, `_pid` deletion).

### Architecture & Design Decisions
- **Proposed the Dynamic Polling circuit breaker strategy:** No background polling when the server is healthy, 1-second aggressive polling when the server is dead, automatic recovery detection via `/health`.
- **Identified the blind spot problem** in active polling (server dies between poll intervals) and proposed combining active polling with passive failure detection.
- **Decided to remove REST caching** — reasoned that the REST server is fast and reliable, so caching would risk serving stale `last_contact` data with no meaningful benefit.
- **Decided to keep XML caching** — reasoned that the XML server's 40% failure rate and 1.55-second average delay justify caching to protect caseworkers from repeated slow/failed requests.
- **Chose 5 retries for Day 2** — calculated the probability of all retries failing at 40% (0.40⁵ = 1.02%) and determined it was acceptable.
- **Questioned cache staleness** — raised the concern that cached data could serve false information if server data changes, leading to a deeper analysis of the trade-off.
- **Proposed the name search endpoint** — identified that caseworkers search by name, not by system ID, making the `GET /residents/{id}` endpoint impractical for real use.
- **Caught the XML-only blind spot** — identified that the initial search implementation only searched REST data, making 200 XML-only people invisible to name searches.
- **Caught the full-name search bug** — identified that the initial search implementation failed when given a full name (e.g., "Jennifer Whitlock") and proposed a robust multi-word matching solution to handle any order.
- **Identified the "Master System" flaw** — realized that embedding XML data inside REST records falsely assumed REST was the primary system. Proposed restructuring the API into neutral buckets (`matched_data`, `rest_only_data`, `xml_only_data`) to honestly report data independently of its source.

### Identity Matching Design (Step 4C)
- **Discovered the address trap independently** — hypothesized that REST and XML addresses differ only in the last word, then asked for data analysis to confirm.
- **Proposed the "drop the last word" address comparison strategy** — split the address into words, ignore the last word (abbreviation vs full), compare the rest.
- **Designed the weighted scoring system** — proposed using Name (30%), DOB (30%), Address (25%), City (15%) with a threshold of ≥ 70%.
- **Identified the DOB missing edge case** — reasoned that some XML records have `born: null`, and these should receive partial credit (5%) rather than being treated as a mismatch.
- **Validated the scoring thresholds** — worked through all edge cases to ensure one wrong field still matches (70%) but two wrong fields do not (40%).
- **Adjusted weights for address vs city** — increased address weight from 20% to 25% and decreased city from 20% to 15% because addresses are more unique than city names.

### Environment Setup
- Created the project folder (`noWrongDoor`), virtual environment (`myvenv`), and Git repository.
- Installed all Python dependencies (`fastapi`, `uvicorn`, `httpx`).
- Copied the 5 organizer service files into the project.
- Decided the folder structure (e.g., placing `run_both.bat` inside `services/` for consistency with `run_both.sh`).

### Testing & Verification
- Manually tested all endpoints via Swagger UI at every phase.
- Tested graceful degradation by killing the XML server and verifying REST data still loads.
- Tested the circuit breaker by killing/restarting the XML server and monitoring the `/status` endpoint.
- Tested the 40% failure rate (Day 2) by disabling caching and hitting the API 30+ times to witness failures.
- Verified identity matching results: 340 matched, `match_score: 100` for complete records, `match_score: 75` for records with missing DOB.
- Performed all Git commits and pushes.

---

## AI Contributions (What the AI Did)

### Research Assistance
- Analyzed mock service source code to quantify traps: 41 REST duplicates, 15% (later 40%) XML failure rate, 0.7–2.4s XML delay range, `_pid` deletion at boot.
- Ran Python commands to determine population sizes: 620 REST residents, 540 XML records, 340 shared across both systems.
- Ran an address analysis script to confirm the developer's hypothesis: all 340 shared records differ only in the last word of the address (5 abbreviation pairs: Ave/Avenue, Dr/Drive, Ln/Lane, Rd/Road, St/Street).

### Code Generation
- Generated all Python source files: `main.py`, `rest_adapter.py`, `xml_adapter.py`, `schemas.py`, `cache.py`, `circuit_breaker.py`, `matcher.py` (including the name search endpoint).
- Generated `run_both.bat` (Windows equivalent of the organizer's `run_both.sh`).
- Generated `.gitignore` with standard Python exclusions.

### Documentation
- Wrote `README.md` with setup instructions, API documentation, and architecture diagram.
- Wrote `DECISIONS.md` with architectural decisions and degradation policies.
- Wrote this `AI-USAGE.md` file.

### Guidance
- Explained every concept, trap, and code block when asked (pagination duplication, `random.random()`, circuit breaker states, XML parsing, etc.).
- Provided step-by-step guidance for each development phase.
- Calculated retry probability tables for different failure rates.
- Presented the developer's scoring weights in table format for easier review.

---

## What AI Did NOT Do
- AI did not make any architectural decisions without the developer's explicit approval.
- AI did not perform any Git operations, environment setup, or manual testing.
- The Dynamic Polling circuit breaker strategy was independently proposed by the developer during a design discussion.
- The decision to remove REST caching was independently proposed by the developer based on data freshness concerns.
- The identity matching scoring system was entirely designed by the developer — including the initial weights, the threshold, the decision to handle missing DOB with partial credit, and the final weight adjustments (Address 25%, City 15%).
- The "drop the last word" address matching strategy was independently proposed by the developer.
- The name search endpoint was proposed by the developer, who also caught the blind spot of XML-only records being invisible.
- All code was reviewed and tested by the developer via Swagger UI before committing.
