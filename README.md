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

## Pipeline Workflow

```
validate_input → plan_script → generate_segments → merge_script → validate_and_eval
                                                                        │
                                                             ┌── score < 3.8 ──┐
                                                             ▼                 │
                                                   regenerate_weak_segment     │
                                                             │                 │
                                                             └──► validate_and_eval → END
```

**Nodes:**

- **validate_input** — Checks brief for errors (duplicate agenda items, % sums, duration range). Aborts to END on failure.
- **plan_script** — GPT-4o turns the brief into a structured segment plan (titles, durations, code/checkpoint flags). Falls back to a mechanical plan if LLM fails.
- **generate_segments** — Generates all segments in parallel (up to 5 workers). Each segment runs its own generate → eval → retry loop (max 2 retries, pass score ≥ 3.5).
- **merge_script** — Assembles segments into the final Script object with metadata.
- **validate_and_eval** — Rule checks (timing, coverage, code ratio) + GPT-4o full-script eval. Scores 5 dimensions; result decides the next edge.
- **regenerate_weak_segment** — Regenerates the single lowest-scoring segment with targeted feedback. Runs at most once (`script_retried` flag prevents looping).

**Per-segment evaluation (inside `generate_segments`):**

Two-stage for each segment:
1. **Rule checks** — examples, definitions, checkpoint, transition, code block, gradual steps, worked example, beginner aids
2. **LLM eval** — 12 dimensions: sentence framing, 10 pedagogy scores (concepts-before-use, intuition-before-formalism, prerequisite coverage, gradual complexity, worked example, beginner comprehension, etc.), faithfulness

Scripts persist to `data/{script_id}.json`.
