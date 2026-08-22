# AI-USAGE.md — AI Tool Usage Disclosure

## Tools Used
- **Antigravity IDE (Claude)** — AI pair-programming assistant used throughout development.

## How AI Was Used

### Research & Analysis Phase
- **Data Discovery:** AI analyzed the mock service files (`rest_service.py`, `xml_service.py`, `_rest_data.json`, `_xml_data.json`) to map data structures, population sizes (620 REST, 540 XML, 340 shared), and field relationships.
- **Trap Identification:** AI identified 6 key traps embedded by the organizers: REST pagination duplicates (41 records), XML intentional slowness (0.7–2.4s), XML 15% failure rate, hidden `_pid` deletion, `/health` exemption, and the Linux-only shell script.
- **Documentation:** AI created a personal reference document (`DATA_ANALYSIS_AND_TRAPS.md`) summarizing all findings.

### Architecture & Design Phase
- **Implementation Plan:** AI drafted a 5-phase implementation plan, which was reviewed and approved by the developer before any code was written.
- **Circuit Breaker Strategy:** The Dynamic Polling strategy (no polling when healthy, 1-second aggressive polling when dead) was **proposed by the developer** during a collaborative design discussion. AI refined and implemented the design.
- **Folder Structure:** AI suggested the project folder structure, which the developer reviewed and adjusted (e.g., placing `run_both.bat` inside `services/` for consistency).

### Implementation Phase
- **Code Generation:** AI generated the initial code for all Python files (`main.py`, `rest_adapter.py`, `xml_adapter.py`, `schemas.py`, `cache.py`, `circuit_breaker.py`).
- **Testing Guidance:** AI guided the developer through manual testing via Swagger UI at each phase, including graceful degradation testing (killing the XML server).
- **Documentation:** AI wrote `README.md`, `DECISIONS.md`, and this file.

### What AI Did NOT Do
- AI did not make any decisions without developer approval.
- The developer manually created the virtual environment, installed dependencies, copied service files, and performed all Git operations.
- The developer independently designed the Dynamic Polling circuit breaker strategy.
- All code was tested and verified by the developer via Swagger UI before committing.

## Human Contributions
- **All architectural decisions** were discussed and approved by the developer before implementation.
- **Dynamic Polling strategy** was independently proposed by the developer.
- **Virtual environment setup**, dependency installation, project folder creation, and Git operations were all performed manually by the developer.
- **Manual testing** of all endpoints, graceful degradation, and circuit breaker recovery was done by the developer through Swagger UI.
