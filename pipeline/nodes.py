"""
Pipeline nodes — each function takes the current LangGraph state and returns
a dict of fields to update. Keep each node focused on one job.
"""

import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .state import PipelineState
from .prompts import PLANNER_PROMPT, SEGMENT_PROMPT, SEGMENT_EVAL_PROMPT, SCRIPT_EVAL_PROMPT
from .validators import run_rule_checks, check_segment_rules

MAX_SEGMENT_RETRIES = 2      # How many times to retry a failing segment
SEGMENT_PASS_SCORE  = 3.5   # Min score to accept a segment
SCRIPT_PASS_SCORE   = 3.8   # Min score to accept the full script

# ── LLM setup (lazy) ───────────────────────────────────────────────────────────
# Instantiated on first use so the module can be imported before .env is loaded.
_llm = None

def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o", temperature=0.7, max_retries=2)
    return _llm


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _call_llm(system: str, user: str) -> str:
    """Single LLM call. Returns raw string content."""
    response = _get_llm().invoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])
    return response.content


def _parse_json(text: str) -> dict:
    """Strip markdown code fences (if any) and parse JSON."""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    return json.loads(text.strip())


# ── Node 1: Validate Input ─────────────────────────────────────────────────────

def validate_input(state: PipelineState) -> dict:
    """Check the brief for obvious errors before touching any LLM."""
    brief = state["brief"]
    errors = []

    if not brief.get("topic", "").strip():
        errors.append("Topic is required.")

    agenda = brief.get("agenda", [])
    if not agenda:
        errors.append("Agenda must have at least one item.")
    elif len(agenda) > 20:
        errors.append("Too many agenda items (max 20).")
    else:
        lower = [a.lower().strip() for a in agenda]
        if len(lower) != len(set(lower)):
            errors.append("Agenda contains duplicate items.")

    beg, adv = brief.get("beginner_pct", 0), brief.get("advanced_pct", 0)
    if beg + adv != 100:
        errors.append(f"beginner_pct + advanced_pct must equal 100 (got {beg + adv}).")

    cnt, code = brief.get("content_pct", 0), brief.get("code_pct", 0)
    if cnt + code != 100:
        errors.append(f"content_pct + code_pct must equal 100 (got {cnt + code}).")

    dur = brief.get("duration", 0)
    if not (15 <= dur <= 240):
        errors.append(f"Duration must be 15–240 minutes (got {dur}).")

    if agenda and dur / len(agenda) < 3:
        errors.append(
            f"Only {dur} min for {len(agenda)} agenda items — less than 3 min each. "
            "Reduce the agenda or increase duration."
        )

    print(f"[validate_input] {'PASS' if not errors else 'FAIL: ' + str(errors)}")
    return {"validation_errors": errors}


# ── Node 2: Plan Script ────────────────────────────────────────────────────────

def plan_script(state: PipelineState) -> dict:
    """
    Call GPT-4o to produce a structured segment plan from the brief.
    Falls back to a mechanical plan if the LLM call fails.
    """
    brief = state["brief"]
    agenda_str = "\n".join(f"  {i+1}. {item}" for i, item in enumerate(brief["agenda"]))
    prior = ", ".join(brief.get("prior_topics") or []) or "None specified"

    prompt = PLANNER_PROMPT.format(
        topic=brief["topic"],
        agenda=agenda_str,
        beginner_pct=brief["beginner_pct"],
        advanced_pct=brief["advanced_pct"],
        duration=brief["duration"],
        content_pct=brief["content_pct"],
        code_pct=brief["code_pct"],
        prior_topics=prior,
    )

    print("[plan_script] Calling GPT-4o for segment plan…")
    try:
        raw = _call_llm("You are an expert curriculum designer for technical education.", prompt)
        data = _parse_json(raw)
        plan = data.get("segments", [])
        notes = data.get("planning_notes", "")
        print(f"[plan_script] Plan has {len(plan)} segments. Notes: {notes[:80]}")
    except Exception as e:
        print(f"[plan_script] LLM failed ({e}), using fallback plan.")
        plan = _fallback_plan(brief)

    return {"plan": plan}


def _fallback_plan(brief: dict) -> list:
    """Mechanical plan used if the planner LLM call fails."""
    items = brief["agenda"]
    n = len(items)
    available = brief["duration"] - 10  # subtract open+close
    per_item = max(5, available // max(n, 1))
    code_heavy = brief["code_pct"] >= 40

    plan = [
        {"id": "opening", "title": "Opening & Hook", "duration": 5,
         "type": "content", "code_required": False, "checkpoint": False, "position": 0}
    ]
    for i, item in enumerate(items):
        plan.append({
            "id": f"segment_{i+1}", "title": item, "duration": per_item,
            "type": "content+code" if code_heavy else "content",
            "code_required": code_heavy, "checkpoint": True, "position": i + 1,
        })
    plan.append({
        "id": "closing", "title": "Recap & What's Next", "duration": 5,
        "type": "content", "code_required": False, "checkpoint": False,
        "position": len(plan),
    })
    return plan


# ── Node 3: Generate All Segments ─────────────────────────────────────────────

def generate_segments(state: PipelineState) -> dict:
    """
    Generate all segments in parallel using a thread pool.

    Context for each segment comes from plan stubs (title + duration of prior
    entries) rather than actual generated content — this makes full parallelism
    possible while still giving the LLM a clear picture of topic order.

    Each segment still goes through the full generate → eval → retry loop
    independently inside its own thread.
    """
    brief = state["brief"]
    plan  = state["plan"]

    def _generate_one(args: tuple) -> tuple[int, dict]:
        position, seg_plan = args

        # Build lightweight context from plan (no actual content needed)
        prev_stubs = [
            {"title": p["title"], "estimated_time": p["duration"]}
            for p in plan[:position]
        ]

        feedback = ""
        for attempt in range(MAX_SEGMENT_RETRIES + 1):
            if attempt > 0:
                print(f"  [{seg_plan['title']}] Retry {attempt}")

            segment = generate_single_segment(brief, seg_plan, prev_stubs, feedback)
            score, feedback = _eval_segment(brief, seg_plan, segment, prev_stubs)

            print(f"  [{seg_plan['title']}] Score: {score:.1f} "
                  f"{'✓ pass' if score >= SEGMENT_PASS_SCORE else '✗ fail'}")

            if score >= SEGMENT_PASS_SCORE or attempt == MAX_SEGMENT_RETRIES:
                segment["_eval_score"] = round(score, 2)
                break

        return position, segment

    max_workers = min(len(plan), 5)   # cap at 5 concurrent LLM calls
    print(f"[generate_segments] Generating {len(plan)} segments "
          f"with {max_workers} parallel workers…")

    results: dict[int, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_generate_one, (i, seg_plan)): i
            for i, seg_plan in enumerate(plan)
        }
        for future in as_completed(futures):
            position, segment = future.result()
            results[position] = segment
            print(f"[generate_segments] ✓ '{segment['title']}' done "
                  f"({position + 1}/{len(plan)})")

    # Restore original order (as_completed returns in completion order)
    segments = [results[i] for i in range(len(plan))]
    return {"segments": segments}


def generate_single_segment(
    brief: dict,
    seg_plan: dict,
    previous_segments: list,
    feedback: str = "",
) -> dict:
    """
    Generate one segment. Called both during the main pipeline and from the
    /regenerate API endpoint (which is why it's a standalone function, not private).
    """
    # Build a short summary of what came before so the LLM has context
    if not previous_segments:
        prev_summary = "This is the opening segment — no prior content yet."
    else:
        prev_summary = "\n".join(
            f"- {s['title']} ({s['estimated_time']} min)"
            for s in previous_segments[-3:]  # last 3 is enough context
        )

    checkpoint_instruction = (
        "End with a comprehension checkpoint question for students."
        if seg_plan.get("checkpoint")
        else "No checkpoint needed for this segment."
    )

    feedback_section = (
        f"\n\nPREVIOUS ATTEMPT FEEDBACK (you must address this):\n{feedback}"
        if feedback else ""
    )

    prompt = SEGMENT_PROMPT.format(
        topic=brief["topic"],
        beginner_pct=brief["beginner_pct"],
        advanced_pct=brief["advanced_pct"],
        prior_topics=", ".join(brief.get("prior_topics") or []) or "None",
        content_pct=brief["content_pct"],
        code_pct=brief["code_pct"],
        prev_summary=prev_summary,
        title=seg_plan["title"],
        duration=seg_plan["duration"],
        code_required=seg_plan.get("code_required", False),
        checkpoint_instruction=checkpoint_instruction,
        feedback_section=feedback_section,
    )

    try:
        raw = _call_llm(
            "You are an expert educator writing live class teaching material.",
            prompt,
        )
        data = _parse_json(raw)
    except Exception as e:
        print(f"  [generate_single_segment] LLM/parse failed: {e}")
        data = {
            "content": f"## {seg_plan['title']}\n\n*Content generation failed. Please use the Regenerate button.*",
            "rationale": "Fallback — generation failed.",
            "checkpoint": None,
        }

    return {
        "id": seg_plan.get("id", f"segment_{seg_plan.get('position', 0)}"),
        "title": seg_plan["title"],
        "estimated_time": seg_plan["duration"],
        "content": data.get("content", ""),
        "rationale": data.get("rationale", ""),
        "checkpoint": data.get("checkpoint"),
        "approved": False,
    }


def _eval_segment(
    brief: dict,
    seg_plan: dict,
    segment: dict,
    previous_segments: list | None = None,
) -> tuple:
    """
    Two-stage segment evaluation. Returns (score: float, feedback: str).

    Stage 1 — rule-based: fast checks for examples, definitions, checkpoint,
               transition, code blocks, and connection to prior material.
    Stage 2 — LLM: scores sentence framing, 6 pedagogy dimensions, and
               faithfulness. Rule check issues are fed in as context.
    """
    prev = previous_segments or []

    # ── Stage 1: rule checks ───────────────────────────────────────────────────
    rules = check_segment_rules(segment, seg_plan, prev)
    if rules["issues"]:
        print(f"  [eval_segment] Rule issues: {rules['issues']}")
    rule_issues_str = (
        "\n".join(f"- {issue}" for issue in rules["issues"])
        if rules["issues"]
        else "None — all rule checks passed."
    )

    # ── Stage 2: LLM eval ─────────────────────────────────────────────────────
    segment_purpose = seg_plan.get("type", "content") + (
        " — includes live coding" if seg_plan.get("code_required") else ""
    )

    prompt = SEGMENT_EVAL_PROMPT.format(
        title=segment["title"],
        duration=seg_plan["duration"],
        content=segment["content"][:3000],
        topic=brief["topic"],
        beginner_pct=brief["beginner_pct"],
        advanced_pct=brief["advanced_pct"],
        code_required=seg_plan.get("code_required", False),
        segment_purpose=segment_purpose,
        rule_issues=rule_issues_str,
    )

    try:
        raw  = _call_llm("You are an expert educational content evaluator.", prompt)
        data = _parse_json(raw)

        # Compute overall from the nested structure if the model didn't
        scores   = data.get("scores", {})
        pedagogy = scores.get("pedagogy", {})
        flat     = (
            [scores.get("sentence_framing", 4.0), scores.get("faithfulness", 4.0)]
            + list(pedagogy.values())
        )
        llm_score = float(data.get("overall", sum(flat) / len(flat) if flat else 4.0))
        feedback  = data.get("feedback", "")

        # Blend rule issues into LLM feedback
        if rules["issues"]:
            rule_note = "Rule checks flagged: " + "; ".join(rules["issues"])
            feedback  = (feedback + "\n\n" + rule_note).strip() if feedback else rule_note

        # Small penalty for each rule failure (caps at -0.5)
        if not rules["rule_pass"]:
            penalty   = min(0.5, len(rules["issues"]) * 0.15)
            llm_score = max(1.0, llm_score - penalty)

        # Store the full breakdown on the segment for persistence
        segment["_eval"] = {
            "rule_report": rules,
            "llm_scores":  scores,
            "overall":     round(llm_score, 2),
        }

        return llm_score, feedback

    except Exception as e:
        print(f"  [eval_segment] LLM eval failed ({e}), defaulting to pass.")
        return 4.0, ""


# ── Node 4: Merge Script ───────────────────────────────────────────────────────

def merge_script(state: PipelineState) -> dict:
    """Assemble the final Script object from the generated segments."""
    brief    = state["brief"]
    segments = state["segments"]
    script_id = state.get("script_id") or str(uuid.uuid4())

    total_time = sum(s["estimated_time"] for s in segments)

    script = {
        "script_id": script_id,
        "topic": brief["topic"],
        "metadata": {
            "duration": brief["duration"],
            "beginner_pct": brief["beginner_pct"],
            "advanced_pct": brief["advanced_pct"],
            "content_pct": brief["content_pct"],
            "code_pct": brief["code_pct"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_time_generated": total_time,
        },
        "validation": {
            "agenda_coverage": True,
            "timing_ok": True,
            "code_ratio_ok": True,
            "prior_topics_ok": True,
            "llm_score": 4.0,   # placeholder — updated in validate_and_eval
        },
        "segments": segments,
    }

    print(f"[merge_script] Merged {len(segments)} segments. Total time: {total_time} min.")
    return {"script": script, "script_id": script_id}


# ── Node 5: Validate & Evaluate Full Script ────────────────────────────────────

def validate_and_eval(state: PipelineState) -> dict:
    """
    1. Run deterministic rule checks.
    2. Run LLM evaluation on the whole script.
    3. If score is below threshold and we haven't retried yet,
       regenerate the single weakest segment.
    """
    brief    = state["brief"]
    script   = state["script"]
    plan     = state["plan"]
    segments = script["segments"]

    # Step 1 — rule checks (no LLM)
    print("[validate_and_eval] Running rule checks…")
    rule_report = run_rule_checks(segments, brief)
    print(f"  agenda_coverage={rule_report['agenda_coverage']}  "
          f"timing_ok={rule_report['timing_ok']}  "
          f"code_ratio_ok={rule_report['code_ratio_ok']}")

    # Step 2 — LLM evaluation of the whole script
    print("[validate_and_eval] Running full-script LLM eval…")
    eval_report = _eval_full_script(brief, script)
    overall     = eval_report.get("overall_score", 4.0)
    print(f"  Overall score: {overall:.1f}  pass={eval_report.get('pass', True)}")

    # Step 3 — Update the script's validation block with real values
    updated_script = {
        **script,
        "validation": {
            "agenda_coverage": rule_report.get("agenda_coverage", True),
            "timing_ok":       rule_report.get("timing_ok", True),
            "code_ratio_ok":   rule_report.get("code_ratio_ok", True),
            "prior_topics_ok": rule_report.get("prior_topics_ok", True),
            "llm_score":       round(overall, 1),
        },
    }

    result = {
        "rule_report": rule_report,
        "eval_report": eval_report,
        "script": updated_script,
    }

    # Step 4 — One-shot weakest-segment regen if overall score is too low
    already_retried = state.get("script_retried", False)
    if overall < SCRIPT_PASS_SCORE and not already_retried:
        weakest_idx = eval_report.get("weakest_segment_idx", -1)
        suggestion  = eval_report.get("improvement_suggestions", "")

        if 0 <= weakest_idx < len(segments):
            print(f"[validate_and_eval] Score {overall:.1f} < {SCRIPT_PASS_SCORE}. "
                  f"Regenerating weakest segment [{weakest_idx}]: '{segments[weakest_idx]['title']}'")

            seg_plan = plan[weakest_idx] if weakest_idx < len(plan) else {
                "title": segments[weakest_idx]["title"],
                "duration": segments[weakest_idx]["estimated_time"],
                "code_required": "```" in segments[weakest_idx].get("content", ""),
                "checkpoint": bool(segments[weakest_idx].get("checkpoint")),
            }

            new_seg = generate_single_segment(
                brief, seg_plan, segments[:weakest_idx], suggestion
            )
            new_segments = segments.copy()
            new_segments[weakest_idx] = new_seg

            updated_script["segments"] = new_segments
            result["script"]         = updated_script
            result["script_retried"] = True

    return result


def _eval_full_script(brief: dict, script: dict) -> dict:
    """Call GPT-4o to evaluate the whole script as a teaching experience."""
    segments = script["segments"]
    # Build a compact summary — full content would exceed context window for long scripts
    script_summary = "\n\n".join(
        f"[{i}] {s['title']} ({s['estimated_time']} min):\n"
        f"{s['content'][:600]}…"
        for i, s in enumerate(segments)
    )

    prompt = SCRIPT_EVAL_PROMPT.format(
        topic=brief["topic"],
        duration=brief["duration"],
        beginner_pct=brief["beginner_pct"],
        advanced_pct=brief["advanced_pct"],
        agenda=", ".join(brief.get("agenda", [])),
        script_summary=script_summary,
    )

    try:
        raw  = _call_llm("You are an expert curriculum evaluator.", prompt)
        data = _parse_json(raw)
        return data
    except Exception as e:
        print(f"  [eval_full_script] Failed ({e}), defaulting to pass.")
        return {"overall_score": 4.0, "pass": True, "weakest_segment_idx": -1,
                "improvement_suggestions": ""}
