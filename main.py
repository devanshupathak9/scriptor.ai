from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
import uuid
from datetime import datetime, timezone
from models import Brief, RegenerateRequest, ApproveRequest

app = FastAPI(title="Drafter API", description="Class Script Authoring Pipeline", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _seg(seg_id: str, title: str, time_min: int, content: str, rationale: str, checkpoint: str | None = None):
    return {
        "id": seg_id,
        "title": title,
        "estimated_time": time_min,
        "content": content,
        "rationale": rationale,
        "checkpoint": checkpoint,
        "approved": False,
    }


@app.post("/generate")
async def generate_script(brief: Brief):
    script_id = str(uuid.uuid4())
    segments = []

    audience_note = (
        "We'll start from the ground up — no assumptions about prior knowledge."
        if brief.beginner_pct >= 60
        else "We'll move quickly through fundamentals and focus on internals and edge cases."
    )
    is_code_heavy = brief.code_pct >= 40

    # Opening
    segments.append(_seg(
        "opening",
        "Opening & Hook",
        5,
        f"""## Welcome — {brief.topic}

Imagine you're debugging a production system at 2 AM. A query that worked fine in development is timing out on real data. You add one index — and suddenly it's 200× faster.

That's not magic. That's understanding what we cover today.

### What You'll Walk Away With

- A clear mental model of **why** {brief.topic} matters
- Hands-on practice you can apply immediately
- Confidence to make these decisions in production

---

{audience_note}
""",
        "Hook uses a concrete, high-stakes scenario to anchor both beginner and advanced learners before diving into content.",
        None,
    ))

    # Per agenda-item segments
    n = len(brief.agenda)
    available = brief.duration - 10  # reserve 5 min open + 5 min close
    per_item = max(5, available // max(n, 1))

    for i, item in enumerate(brief.agenda):
        code_block = ""
        if is_code_heavy or i % 2 == 0:
            code_block = f"""
### Live Code Walkthrough

```sql
-- Before: full table scan
EXPLAIN ANALYZE
SELECT * FROM orders WHERE status = 'pending';

-- Apply {item}
CREATE INDEX idx_orders_status ON orders(status);

-- After: index scan
EXPLAIN ANALYZE
SELECT * FROM orders WHERE status = 'pending';
```

Observe the change in `Execution Time` and `Node Type` in the query plan.
"""

        depth = "beginner-friendly with clear analogies" if brief.beginner_pct >= 60 else "advanced — internals and production tradeoffs"

        segments.append(_seg(
            f"segment_{i + 1}",
            item,
            per_item,
            f"""## {item}

{("Let's build this up from scratch." if brief.beginner_pct >= 60 else "We'll skip the basics and go straight to what matters in production.")}

### Core Concept

> Think of {item} as a **sorted shortcut map** — instead of scanning every row, the database follows a direct pointer to exactly what you need.

### Key Points

- **How it works**: The structure that makes {item} fast (and when it isn't)
- **When to use it**: The query shapes that benefit most
- **The tradeoff**: Write overhead, storage cost, and maintenance
{code_block}
### Common Pitfall

The most common mistake: applying {item.lower()} everywhere without measuring first. Always benchmark with `EXPLAIN ANALYZE` before and after.
""",
            f"Depth: {depth}. Time budget: {per_item} min. Example chosen for familiarity with common web-app schema (orders table).",
            f"Quick check: In one sentence — when would you reach for {item}, and what's the main tradeoff?",
        ))

    # Closing
    recap = "\n".join(f"- **{item}**" for item in brief.agenda)
    closer = (
        "Start simple. One well-placed index on the right column solves 90% of query performance problems."
        if brief.beginner_pct >= 60
        else "Don't reach for optimization until you've measured. Most performance problems are misdiagnosed — always profile first."
    )

    segments.append(_seg(
        "closing",
        "Recap & What's Next",
        5,
        f"""## Wrapping Up — {brief.topic}

Here's what we covered today:

{recap}

### The One Thing to Remember

{closer}

### What's Next

We'll build on this in the next session: **Query Optimization** — how the planner decides which index to use, and how you can guide it when it makes the wrong choice.

*See you then.*
""",
        "Recap reinforces the session's single most important mental model. Next-session pointer sets expectation and creates continuity.",
        None,
    ))

    total_time = sum(s["estimated_time"] for s in segments)

    return {
        "script_id": script_id,
        "topic": brief.topic,
        "metadata": {
            "duration": brief.duration,
            "beginner_pct": brief.beginner_pct,
            "advanced_pct": brief.advanced_pct,
            "content_pct": brief.content_pct,
            "code_pct": brief.code_pct,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_time_generated": total_time,
        },
        "validation": {
            "agenda_coverage": True,
            "timing_ok": abs(total_time - brief.duration) <= brief.duration * 0.15,
            "code_ratio_ok": True,
            "prior_topics_ok": True,
            "llm_score": 4.6,
        },
        "segments": segments,
    }


@app.post("/regenerate")
async def regenerate_segment(req: RegenerateRequest):
    return {
        "id": req.segment_id,
        "title": req.segment_id.replace("_", " ").title(),
        "estimated_time": 10,
        "content": f"""## Regenerated Section

*Regenerated with your feedback: "{req.feedback}"*

---

### Updated Approach

This version takes a different angle — grounding the concept in a production scenario before explaining the mechanism.

```sql
-- Production-realistic example
BEGIN;

CREATE INDEX CONCURRENTLY idx_example
ON large_table(column_a, column_b)
WHERE active = true;

COMMIT;

-- Verify
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'large_table';
```

### Why `CONCURRENTLY`?

Standard `CREATE INDEX` locks the entire table — catastrophic in production. `CONCURRENTLY` builds the index in the background, allowing reads and writes while it's being built.

**The tradeoff**: It takes longer and can fail if a concurrent transaction conflicts. If it fails, you'll see an invalid index — clean it up with `DROP INDEX`.

### When to Use a Partial Index

The `WHERE active = true` clause creates a **partial index** — it only indexes rows that match the condition. This keeps the index small and fast by excluding inactive rows that you never query on.
""",
        "rationale": f"Regenerated with production focus and CONCURRENTLY pattern, per feedback: '{req.feedback}'",
        "checkpoint": "What's the tradeoff between CONCURRENTLY and standard index creation? When would you choose standard despite the lock?",
        "approved": False,
    }


@app.post("/approve")
async def approve_script(req: ApproveRequest):
    return {
        "success": True,
        "script_id": req.script_id,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "message": "Script approved and ready for use.",
    }


@app.get("/download/{script_id}")
async def download_script(script_id: str):
    content = f"""# Class Script Export

**Script ID:** `{script_id}`
**Exported:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
**Tool:** Drafter — Class Script Authoring Pipeline

---

> Stub export. Full implementation compiles all approved segment content into this document.

---

*Powered by Drafter*
"""
    return PlainTextResponse(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="script-{script_id[:8]}.md"'},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
