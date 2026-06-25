# Scriptor — Backend

FastAPI backend for the Class Script Authoring Pipeline.

## Run

```bash
# Install dependencies (first time only)
pip install -r requirements.txt

# Start server
uvicorn main:app --reload --port 8000
```

API → http://localhost:8000  
Swagger UI → http://localhost:8000/docs

## Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/generate` | Takes instructor brief, returns full script |
| POST | `/regenerate` | Takes segment ID + feedback, returns updated segment |
| POST | `/approve` | Records final sign-off |
| GET | `/download/{id}` | Returns script as `.md` file |
| GET | `/health` | Health check |

## Files

```
scriptor_backend/
├── main.py          # All route handlers
├── models.py        # Pydantic request/response schemas
└── requirements.txt
```

## Current State

All endpoints return **stub/mock data** — no real LLM calls yet. Good enough to test the full UI flow end-to-end.
