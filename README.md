# No Wrong Door — Unified Resident API

A single API that gives caseworkers a unified view of a resident from two separate government systems — the **REST Resident Index** and the **XML Benefits Register** — in one call.

Built with **FastAPI** (Python), featuring graceful degradation, automatic deduplication, in-memory caching, a circuit breaker with dynamic health polling, and **identity matching** that links residents to their benefits across systems with no shared key.

---

## Quick Start

### 1. Clone the repository
Open a terminal in the folder where you want to save the project, and then run:
```bash
git clone https://github.com/DaksheshR/noWrongDoor.git
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
Open **two separate terminals**, and in each one, navigate to the `noWrongDoor` folder and activate the virtual environment:
```bash
# Terminal 1 (REST Service)
cd <path-to-noWrongDoor>
myvenv\Scripts\activate        # Windows (use source myvenv/bin/activate on Mac/Linux)
cd services
python rest_service.py --port 8081

# Terminal 2 (XML Service - Day 2: 40% failure rate)
cd <path-to-noWrongDoor>
myvenv\Scripts\activate        # Windows
cd services
python xml_service.py --port 8082 --failure-rate 0.40
```
Or on Windows, double-click `services\run_both.bat`.

### 5. Start the API
Open a **third terminal**, navigate to the project root, activate the environment, and start the API:
```bash
# Terminal 3 (API)
cd <path-to-noWrongDoor>
myvenv\Scripts\activate        # Windows
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
| `GET` | `/residents` | Fetch all residents with matched benefits from both sources |
| `GET` | `/residents/search?name=` | Search residents by name (case-insensitive partial match) |
| `GET` | `/residents/{id}` | Fetch a single resident by ID with matched benefits |

### Example Requests

*Note: You can run these `curl` commands in a new, separate terminal. You do not need to activate the virtual environment to run `curl`, but the API (Terminal 3) must be running.*

**Get all residents (with matched benefits):**
```bash
curl http://127.0.0.1:8000/residents
```

**Search by name (how a caseworker would actually use it):**
```bash
curl "http://127.0.0.1:8000/residents/search?name=whitlock"
```

**Get a single resident by ID (with matched benefits):**
```bash
curl http://127.0.0.1:8000/residents/R-10100
```

**Check system status:**
```bash
curl http://127.0.0.1:8000/status
```

### Testing in Swagger UI
If you prefer a visual interface over `curl`, you can test these exact same examples in your browser:
1. Go to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
2. **To search by name:** Open `GET /residents/search`, click **Try it out**, enter `whitlock` in the `name` field, and click **Execute**.
3. **To get a single resident:** Open `GET /residents/{resident_id}`, click **Try it out**, enter `R-10100` in the `resident_id` field, and click **Execute**.

### Response Format
Every response includes:
- `status` — `"success"`, `"partial_success"`, or `"error"`
- `warnings` — Human-readable warnings if a source failed or data is cached
- `total_residents` — Count of deduplicated REST records
- `total_benefits` — Count of XML benefit records
- `total_matched` — Count of residents matched to benefit records via identity matching
- `residents` — Unified resident data with `matched_benefits` attached to each resident
- `unmatched_benefits` — XML benefit records that could not be matched to any REST resident

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
│  │   Cache    │  │   Circuit    │  │
│  │  (TTL)     │  │   Breaker    │  │
│  └────────────┘  └──────────────┘  │
│                                    │
│  ┌────────────┐  ┌──────────────┐  │
│  │   REST     │  │    XML       │  │
│  │  Adapter   │  │   Adapter    │  │
│  └─────┬──────┘  └──────┬───────┘  │
│        │                │          │
│  ┌─────┴────────────────┴───────┐  │
│  │     Identity Matcher         │  │
│  │  (Weighted Scoring Algorithm)│  │
│  └──────────────────────────────┘  │
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

### Stretch Goals (All Implemented ✅)
| Feature | Implementation |
| :--- | :--- |
| **Caching** | In-memory TTL cache (XML: 120s). REST fetched fresh every time. |
| **Circuit Breaker** | Dynamic Polling — no polling when healthy, 1s polling when dead. |
| **System Status** | `/status` endpoint shows circuit breaker state & cache info. |
| **Identity Matching** | Weighted scoring algorithm (Name 30%, DOB 30%, Address 25%, City 15%) matches 340 shared residents with 0 false positives. |
| **Name Search** | `GET /residents/search?name=` — case-insensitive, multi-word matching across both REST and XML databases (supports full names in any order). |

---

## Identity Matching

The two systems have **no shared ID**. We match residents to benefits using a weighted scoring algorithm:

| Field | Weight | How It's Compared |
| :--- | :--- | :--- |
| Name | 30% | XML `"LASTNAME, Firstname"` parsed → title-cased and compared with REST `first_name` + `last_name` |
| Date of Birth | 30% | Direct comparison. If missing (null), 5% partial credit. |
| Address | 25% | Split into words, ignore last word (Ave/Avenue, Ln/Lane, etc.) |
| City / Town | 15% | Case-insensitive comparison |

**Threshold:** ≥ 70% = match. This allows one field to be wrong (typo or missing data) while still correctly linking the records.

**Result:** 340 out of 340 shared people correctly matched, 0 false positives.

---

## Key Design Decisions

See [DECISIONS.md](DECISIONS.md) for full details on:
- REST pagination deduplication strategy
- XML retry & timeout policy (5 retries, 3s timeout)
- Graceful degradation policy (failure matrix table)
- Concurrent fetching with `asyncio.gather()`
- Cache TTL reasoning (XML 120s, REST no cache)
- Circuit Breaker dynamic polling strategy
- Day 2 response (40% failure rate adaptation)
- Identity matching scoring weights and threshold

---

## Tech Stack
- **Python 3.12**
- **FastAPI** — Async web framework
- **Uvicorn** — ASGI server
- **httpx** — Async HTTP client
- **Pydantic** — Data validation
