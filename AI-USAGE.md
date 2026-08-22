# AI-USAGE.md — AI Tool Usage Disclosure

## Tools Used
- **Antigravity IDE (Claude)** — AI pair-programming assistant used throughout development.

## How AI Was Used

### Phase 1: Foundation
- **Analysis:** AI analyzed the mock service files (`rest_service.py`, `xml_service.py`, `_rest_data.json`, `_xml_data.json`) to understand data structures, traps (pagination duplicates, XML slowness/failures), and population overlaps.
- **Architecture:** AI helped design the project folder structure and the 5-phase implementation plan.
- **Code Generation:** AI generated the FastAPI skeleton (`app/main.py`) with the `/health` endpoint.
- **Documentation:** AI created `DATA_ANALYSIS_AND_TRAPS.md` (personal reference, not submitted) documenting all discovered traps and data relationships.

## Human Contributions
- All architectural decisions were discussed and approved by the developer before implementation.
- The developer manually set up the virtual environment, installed dependencies, created the project folder structure, and tested the mock services.
- The developer proposed the Dynamic Polling strategy for the Circuit Breaker design.
