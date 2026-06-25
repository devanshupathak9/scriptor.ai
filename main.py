import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from models import Brief, RegenerateRequest, ApproveRequest

# Load OPENAI_API_KEY from .env before importing anything that uses it
load_dotenv()

from pipeline.graph import pipeline                          # noqa: E402
from pipeline.nodes import generate_single_segment          # noqa: E402

# ── App setup ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Scriptor API",
    description="Class Script Authoring Pipeline",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Data storage (JSON files, one per script) ──────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def _save(script_id: str, data: dict) -> None:
    (DATA_DIR / f"{script_id}.json").write_text(json.dumps(data, indent=2))


def _load(script_id: str) -> dict | None:
    path = DATA_DIR / f"{script_id}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _build_markdown(script: dict, brief: dict) -> str:
    """Compile all segment content into a single Markdown document."""
    lines = [
        f"# {script['topic']}",
        "",
        f"**Duration:** {brief['duration']} min  |  "
        f"**Audience:** {brief['beginner_pct']}% Beginner / {brief['advanced_pct']}% Advanced  |  "
        f"**Content/Code:** {brief['content_pct']}% / {brief['code_pct']}%",
        "",
        "---",
        "",
    ]
    for seg in script["segments"]:
        lines += [
            f"## {seg['title']} *({seg['estimated_time']} min)*",
            "",
            seg["content"].strip(),
            "",
        ]
        if seg.get("checkpoint"):
            lines += [f"> **Checkpoint:** {seg['checkpoint']}", ""]
        lines += ["---", ""]
    return "\n".join(lines)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/generate")
async def generate_script(brief: Brief):
    """
    Run the full LangGraph pipeline:
      validate → plan → generate segments (with per-segment retry) →
      merge → rule checks → LLM eval (with one-shot weak-segment regen)
    Saves result to data/{script_id}.json and returns the script.
    """
    script_id = str(uuid.uuid4())

    initial_state = {
        "brief":             brief.model_dump(),
        "validation_errors": [],
        "plan":              [],
        "segments":          [],
        "script":            {},
        "script_id":         script_id,
        "rule_report":       {},
        "eval_report":       {},
        "script_retried":    False,
        "error":             None,
    }

    # Run the sync pipeline in a thread so the async event loop isn't blocked
    result = await asyncio.to_thread(pipeline.invoke, initial_state)

    # Surface validation errors cleanly
    if result.get("validation_errors"):
        raise HTTPException(status_code=422, detail=result["validation_errors"])

    script = result.get("script")
    if not script or not script.get("segments"):
        raise HTTPException(status_code=500, detail="Pipeline failed to produce a script.")

    # Persist everything to disk
    _save(script_id, {
        "brief":        brief.model_dump(),
        "plan":         result.get("plan", []),
        "script":       script,
        "rule_report":  result.get("rule_report", {}),
        "eval_report":  result.get("eval_report", {}),
        "approved":     False,
        "approved_at":  None,
        "created_at":   datetime.now(timezone.utc).isoformat(),
    })

    return script


@app.post("/regenerate")
async def regenerate_segment(req: RegenerateRequest):
    """
    Regenerate a single segment with instructor feedback.
    Loads the script from disk, replaces the segment, saves back.
    """
    stored = _load(req.script_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Script not found.")

    brief    = stored["brief"]
    plan     = stored.get("plan", [])
    segments = stored["script"]["segments"]

    # Find the segment by id
    seg_idx = next((i for i, s in enumerate(segments) if s["id"] == req.segment_id), None)
    if seg_idx is None:
        raise HTTPException(status_code=404, detail="Segment not found.")

    # Match to original plan entry (or reconstruct a minimal one)
    seg_plan = (
        plan[seg_idx] if seg_idx < len(plan)
        else {
            "id":           segments[seg_idx]["id"],
            "title":        segments[seg_idx]["title"],
            "duration":     segments[seg_idx]["estimated_time"],
            "code_required": "```" in segments[seg_idx].get("content", ""),
            "checkpoint":   bool(segments[seg_idx].get("checkpoint")),
        }
    )

    new_segment = await asyncio.to_thread(
        generate_single_segment,
        brief, seg_plan, segments[:seg_idx], req.feedback,
    )

    # Update persisted script
    segments[seg_idx] = new_segment
    stored["script"]["segments"] = segments
    stored["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save(req.script_id, stored)

    return new_segment


@app.post("/approve")
async def approve_script(req: ApproveRequest):
    """Mark a script as instructor-approved."""
    stored = _load(req.script_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Script not found.")

    stored["approved"]    = True
    stored["approved_at"] = datetime.now(timezone.utc).isoformat()
    _save(req.script_id, stored)

    return {
        "success":     True,
        "script_id":   req.script_id,
        "approved_at": stored["approved_at"],
        "message":     "Script approved and ready for use.",
    }


@app.get("/download/{script_id}")
async def download_script(script_id: str):
    """Compile the stored script into a Markdown file and return it."""
    stored = _load(script_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Script not found.")

    script   = stored["script"]
    brief    = stored["brief"]
    markdown = _build_markdown(script, brief)
    filename = script["topic"].lower().replace(" ", "-") + "-script.md"

    return PlainTextResponse(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
