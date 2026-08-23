# No Wrong Door — Unified Resident API

A single API that gives caseworkers a unified view of a resident from two separate government systems — the **REST Resident Index** and the **XML Benefits Register** — in one call.

Built with **FastAPI** (Python), featuring graceful degradation, automatic deduplication, in-memory caching, and a circuit breaker with dynamic health polling.

---

## Quick Start

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd noWrongDoor
```

### 2. Set up the virtual environment
```bash
python -m venv myvenv
myvenv\Scripts\activate        # Windows
# source myvenv/bin/activate   # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the mock services
Open **two separate terminals** and run:
```bash
# Terminal 1
cd services
python rest_service.py --port 8081

# Terminal 2 (Day 2: 40% failure rate)
cd services
python xml_service.py --port 8082 --failure-rate 0.40
```
Or on Windows, double-click `services\run_both.bat`.

### 5. Start the API
```bash
uvicorn app.main:app --reload --port 8000
```

### 6. Open Swagger UI
Go to: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check for this API |
| `GET` | `/status` | System status: circuit breaker state, cache info, upstream health |
| `GET` | `/residents` | Fetch all residents + benefits from both sources (deduplicated) |
| `GET` | `/residents/{id}` | Fetch a single resident by ID (e.g., `R-10085`) |

### Example Requests

**Get all residents:**
```bash
curl http://127.0.0.1:8000/residents
```

**Get a single resident:**
```bash
curl http://127.0.0.1:8000/residents/R-10085
```

**Check system status:**
```bash
curl http://127.0.0.1:8000/status
```

### Response Format
Every response includes:
- `status` — `"success"`, `"partial_success"`, or `"error"`
- `warnings` — Human-readable warnings if a source failed or data is cached
- `total_residents` — Count of deduplicated REST records
- `total_benefits` — Count of XML benefit records
- `residents` — REST resident data
- `benefits` — XML benefit records

---

## Architecture

```
Client (Caseworker / Swagger UI)
        │
        ▼
┌────────────────────────────────────┐
│     No Wrong Door API (FastAPI)    │  Port 8000
│                                    │
│  ┌────────────┐  ┌──────────────┐  │
│  │   Cache     │  │   Circuit    │  │
│  │  (TTL)      │  │   Breaker   │  │
│  └────────────┘  └──────────────┘  │
│                                    │
│  ┌────────────┐  ┌──────────────┐  │
│  │   REST     │  │    XML       │  │
│  │  Adapter   │  │   Adapter    │  │
│  └─────┬──────┘  └──────┬───────┘  │
└────────┼─────────────────┼─────────┘
         │                 │
         ▼                 ▼
   ┌───────────┐    ┌───────────┐
   │   REST    │    │    XML    │
   │  Service  │    │  Service  │
   │ Port 8081 │    │ Port 8082 │
   └───────────┘    └───────────┘
```

---

## Features

### Floor Requirements (All Met ✅)
| Requirement | Implementation |
| :--- | :--- |
| **Graceful Degradation** | If XML fails, returns REST data + warning. Never a bare error. |
| **Retry-Safe & Idempotent** | GET-only API, no writes, same request = same result. |
| **Duplicate Handling** | Dictionary keyed by `id` removes 41 REST pagination duplicates. |
| **Runs From Clean Clone** | This README provides complete setup instructions. |

### Stretch Goals (Implemented ✅)
| Feature | Implementation |
| :--- | :--- |
| **Caching** | In-memory TTL cache (REST: 60s, XML: 120s). |
| **Circuit Breaker** | Dynamic Polling — no polling when healthy, 1s polling when dead. |
| **System Status** | `/status` endpoint shows circuit breaker state & cache info. |

---

## Key Design Decisions

See [DECISIONS.md](DECISIONS.md) for full details on:
- REST pagination deduplication strategy
- XML retry & timeout policy (3 retries, 3s timeout)
- Graceful degradation policy (failure matrix table)
- Concurrent fetching with `asyncio.gather()`
- Cache TTL expiry reasoning (60s REST, 120s XML)
- Circuit Breaker dynamic polling strategy

---

## Tech Stack
- **Python 3.12**
- **FastAPI** — Async web framework
- **Uvicorn** — ASGI server
- **httpx** — Async HTTP client
- **Pydantic** — Data validation
