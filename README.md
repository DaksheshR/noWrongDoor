# No Wrong Door — Unified Resident API

A single API that gives caseworkers a unified view of a resident from two separate government systems — the **REST Resident Index** and the **XML Benefits Register** — in one call.

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
```bash
cd services
python rest_service.py --port 8081    # Terminal 1
python xml_service.py --port 8082     # Terminal 2
```
Or on Windows, double-click `services\run_both.bat`.

### 5. Start the API
```bash
cd ..
uvicorn app.main:app --reload --port 8000
```

### 6. Open Swagger UI
Go to: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Health check for this API |
| `GET` | `/residents` | Fetch all residents + benefits from both sources |
| `GET` | `/residents/{id}` | Fetch a single resident by ID (e.g., `R-10085`) |

### Example: Get all residents
```bash
curl http://127.0.0.1:8000/residents
```

### Example: Get a single resident
```bash
curl http://127.0.0.1:8000/residents/R-10085
```

### Response Format
Every response includes:
- `status` — `"success"`, `"partial_success"`, or `"error"`
- `warnings` — A list of human-readable warnings if a source failed
- `residents` — REST resident data (deduplicated)
- `benefits` — XML benefit records

---

## Architecture

```
Client (Caseworker)
    │
    ▼
┌──────────────────────┐
│  No Wrong Door API   │   ← Our FastAPI application (port 8000)
│  (app/main.py)       │
└──────┬───────┬───────┘
       │       │
       ▼       ▼
┌──────────┐ ┌──────────┐
│ REST     │ │ XML      │   ← Mock services provided by organizers
│ Adapter  │ │ Adapter  │
│ (8081)   │ │ (8082)   │
└──────────┘ └──────────┘
```

---

## Key Design Decisions

See [DECISIONS.md](DECISIONS.md) for full details on:
- REST pagination deduplication strategy
- XML retry & timeout policy
- Graceful degradation policy
- Concurrent fetching with asyncio
