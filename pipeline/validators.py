# Deterministic (no LLM) rule-based checks on generated script segments.


def check_segment_rules(segment: dict, seg_plan: dict, previous_segments: list) -> dict:
    """
    Fast rule-based pedagogical checks on a single segment — no LLM needed.
    Runs BEFORE the LLM evaluator so issues are surfaced as context to the model.

    Checks:
      1. Examples and analogies present
      2. Technical terms defined before/when first used
      3. Comprehension checkpoint present (non-structural segments)
      4. Transition to next section (non-closing segments)
      5. Code block present when the plan requires it
      6. Builds on previously covered material
      7. Minimum content length
    """
    content       = segment.get("content", "")
    content_lower = content.lower()
    checkpoint    = segment.get("checkpoint")
    seg_id        = segment.get("id", "")
    is_structural = seg_id in ("opening", "closing")

    issues = []

    # 1. Examples / analogies
    example_markers = [
        "for example", "for instance", "e.g.", "such as", "imagine",
        "think of it", "consider", "like a ", "analogy", "analogous",
        "similar to", "just like", "picture this",
    ]
    has_examples = any(m in content_lower for m in example_markers)
    if not has_examples:
        issues.append("No concrete examples or analogies found.")

    # 2. Technical terms defined when first used
    definition_markers = [
        " is a ", " is an ", " means ", " refers to ", " is defined as ",
        " we call ", " known as ", " also called ", "in other words", "that is,",
    ]
    has_definitions = any(m in content_lower for m in definition_markers)
    has_code   = "```" in content
    has_jargon = any(w in content_lower for w in [
        "algorithm", "function", "class", "method", "index", "query",
        "schema", "interface", "async", "cache", "buffer", "pointer",
        "recursion", "complexity", "protocol", "serializ",
    ])
    if (has_code or has_jargon) and not has_definitions:
        issues.append("Technical terms used without explanation/definition markers.")

    # 3. Checkpoint present (non-structural segments that require one)
    has_checkpoint = bool(checkpoint) and bool(str(checkpoint).strip())
    if not is_structural and seg_plan.get("checkpoint", True) and not has_checkpoint:
        issues.append("Missing comprehension checkpoint question.")

    # 4. Transition to next section (check last 300 chars; skip closing)
    transition_markers = [
        "next ", "now that", "in the next", "we'll ", "we will ",
        "moving on", "coming up", "up next", "let's move", "let us move",
    ]
    has_transition = any(m in content_lower[-300:] for m in transition_markers)
    if seg_id != "closing" and not has_transition:
        issues.append("Missing transition phrase at the end of the segment.")

    # 5. Code block present when the plan requires it
    code_required  = seg_plan.get("code_required", False)
    has_code_block = "```" in content
    if code_required and not has_code_block:
        issues.append("Live coding required but no fenced code block found.")

    # 6. Builds on previously covered material (skip first segment)
    if previous_segments:
        prev_titles = [s.get("title", "").lower() for s in previous_segments[-2:]]
        ref_words   = [w for t in prev_titles for w in t.split() if len(w) > 4]
        builds_on_prev = any(w in content_lower for w in ref_words)
        if not builds_on_prev and not is_structural:
            issues.append("No apparent reference to previously covered material.")
    else:
        builds_on_prev = True

    # 7. Minimum length
    min_ok = len(content.strip()) >= 200
    if not min_ok:
        issues.append(f"Content too short ({len(content.strip())} chars, need ≥ 200).")

    # 8. Worked example or practical demonstration
    #    Require either a code block with surrounding explanation, or explicit walkthrough language.
    worked_example_markers = [
        "let's walk through", "let me show", "let's trace", "worked example",
        "step by step", "here's how", "in practice", "let's see this",
        "let's try", "consider this example", "take a look at",
    ]
    has_worked_example = (
        any(m in content_lower for m in worked_example_markers)
        or (has_code_block and len(content.strip()) > 400)  # code block with real context around it
    )
    if not is_structural and not has_worked_example:
        issues.append("No worked example or practical demonstration found.")

    # 9. Gradual complexity — content should build up step-by-step, not dump everything at once
    gradual_markers = [
        "first,", "first ", "to start", "to begin", "starting with",
        "then,", "then ", "next,", "next ", "after that",
        "finally,", "building on", "now that we", "once you understand",
        "let's start", "let's begin", "step 1", "step 2",
    ]
    gradual_hit_count = sum(1 for m in gradual_markers if m in content_lower)
    has_gradual_steps = (
        gradual_hit_count >= 2
        or bool(__import__("re").search(r"\b\d+\.\s", content))  # numbered list
    )
    if not is_structural and not has_gradual_steps:
        issues.append("Content does not appear to build complexity gradually (missing step markers or numbered progression).")

    # 10. Beginner comprehension aids — recap, summary, or checkpoint before moving on
    recap_markers = [
        "to recap", "in summary", "to summarize", "let's review",
        "in short", "so far we've", "we've covered", "remember that",
        "key takeaway", "the main point", "to put it simply",
    ]
    has_recap = any(m in content_lower for m in recap_markers)
    beginner_ok = has_checkpoint or has_recap or has_definitions
    if not is_structural and not beginner_ok:
        issues.append("No beginner comprehension aids found (missing recap, checkpoint, or jargon definitions).")

    return {
        "has_examples":           has_examples,
        "has_definitions":        has_definitions,
        "has_checkpoint":         has_checkpoint,
        "has_transition":         has_transition,
        "has_code_when_required": not code_required or has_code_block,
        "builds_on_previous":     builds_on_prev,
        "min_length_ok":          min_ok,
        "has_worked_example":     has_worked_example,
        "has_gradual_steps":      has_gradual_steps,
        "beginner_aids_ok":       beginner_ok,
        "issues":                 issues,
        "rule_pass":              len(issues) == 0,
    }


def run_rule_checks(segments: list, brief: dict) -> dict:
    """Run all structural checks. Returns a report dict."""
    report = {}

    # 1. Agenda coverage — every agenda item should appear somewhere in the script
    agenda_items = [a.lower().strip() for a in brief.get("agenda", [])]
    all_text = " ".join(
        (s.get("title", "") + " " + s.get("content", "")).lower()
        for s in segments
    )
    missing = [item for item in agenda_items if item not in all_text]
    report["agenda_coverage"] = len(missing) == 0
    report["missing_agenda_items"] = missing

    # 2. Timing — total segment time should be within 15% of requested duration
    total_time = sum(s.get("estimated_time", 0) for s in segments)
    requested = brief.get("duration", 90)
    tolerance = requested * 0.15
    report["timing_ok"] = abs(total_time - requested) <= tolerance
    report["total_time"] = total_time
    report["requested_time"] = requested
    report["timing_delta"] = total_time - requested

    # 3. Code ratio — count segments that contain a code block
    segs_with_code = sum(1 for s in segments if "```" in s.get("content", ""))
    total = len(segments) or 1
    actual_code_pct = round(segs_with_code / total * 100)
    expected_code_pct = brief.get("code_pct", 0)
    report["code_ratio_ok"] = abs(actual_code_pct - expected_code_pct) <= 35
    report["actual_code_pct"] = actual_code_pct
    report["expected_code_pct"] = expected_code_pct

    # 4. Prior topics — check they're not being re-taught (basic heuristic)
    prior = [p.lower().strip() for p in (brief.get("prior_topics") or [])]
    re_taught = []
    for p in prior:
        for s in segments:
            title = s.get("title", "").lower()
            # Flag if a whole segment is titled after a prior topic
            if p in title and p not in ["opening", "closing", "recap"]:
                re_taught.append(p)
                break
    report["prior_topics_ok"] = len(re_taught) == 0
    report["re_taught_topics"] = re_taught

    # 5. Structure checks
    titles_lower = [s.get("title", "").lower() for s in segments]
    ids_lower = [s.get("id", "").lower() for s in segments]

    report["has_opening"] = any(
        "opening" in t or "hook" in t or "welcome" in t
        for t in titles_lower + ids_lower
    )
    report["has_closing"] = any(
        "closing" in t or "recap" in t or "wrap" in t or "next" in t
        for t in titles_lower + ids_lower
    )
    report["no_empty_segments"] = all(
        len(s.get("content", "").strip()) >= 50 for s in segments
    )
    report["all_have_checkpoints"] = all(
        s.get("checkpoint") for s in segments
        if s.get("id") not in ("opening", "closing")
    )

    return report
