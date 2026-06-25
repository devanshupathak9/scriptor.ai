# All LLM prompt templates for the pipeline.
# Uses .format(**kwargs) — escape literal braces as {{ and }}.

PLANNER_PROMPT = """
You are an expert educator and curriculum designer for technical classes.

Given the instructor brief below, create a structured teaching plan.

=== BRIEF ===
Topic: {topic}
Agenda items:
{agenda}
Audience: {beginner_pct}% beginner / {advanced_pct}% advanced
Total duration: {duration} minutes
Content vs Code: {content_pct}% explanation / {code_pct}% live coding
Prior knowledge (students already know this): {prior_topics}

=== YOUR JOB ===
1. Create one "Opening & Hook" segment (5 min) and one "Recap & What's Next" segment (5 min).
2. For each agenda item, create one segment. Reorder items only if it improves teaching flow.
3. Add a short prerequisite segment if something critical is missing but not in prior topics.
4. Allocate time so the total equals {duration} minutes exactly.
5. Decide if each segment needs live coding based on the content/code ratio ({code_pct}% code target).
6. Mark whether each segment should end with a comprehension checkpoint question.

Return ONLY valid JSON — no extra text, no markdown fences:
{{
  "segments": [
    {{
      "id": "opening",
      "title": "Opening & Hook",
      "duration": 5,
      "type": "content",
      "code_required": false,
      "checkpoint": false,
      "position": 0
    }},
    {{
      "id": "segment_1",
      "title": "Why Indexes Exist",
      "duration": 15,
      "type": "content+code",
      "code_required": true,
      "checkpoint": true,
      "position": 1
    }}
  ],
  "planning_notes": "Brief note on key decisions made (reordering, additions, time allocation)"
}}
"""


SEGMENT_PROMPT = """
You are an expert educator writing one segment of a live class script.

=== CLASS CONTEXT ===
Topic: {topic}
Audience: {beginner_pct}% beginner / {advanced_pct}% advanced
Prior knowledge students have: {prior_topics}
Overall content/code mix: {content_pct}% explanation / {code_pct}% live coding

=== WHAT WAS COVERED SO FAR ===
{prev_summary}

=== THIS SEGMENT ===
Title: {title}
Duration: {duration} minutes
Needs live coding: {code_required}
{checkpoint_instruction}
{feedback_section}

=== WRITING INSTRUCTIONS ===
Write content that an instructor can read directly in class. Include:
- A clear explanation appropriate for the audience mix (more foundational if mostly beginner, more depth if mostly advanced)
- At least one concrete analogy or real-world example
- A live code walkthrough if code_required is true (use SQL, Python, or the relevant language with code blocks)
- A 1-2 sentence transition to the next section at the end (unless this is the closing segment)
- Do NOT re-explain topics from "prior knowledge" — reference them briefly instead

Format the content as clean Markdown with ## for the title, ### for subsections.

Return ONLY valid JSON — no extra text, no markdown fences:
{{
  "content": "## {title}\\n\\n[your full markdown content here]",
  "rationale": "2-3 sentence explanation of your pedagogical choices (depth, examples chosen, why this structure)",
  "checkpoint": "A single comprehension question to ask students (or null if checkpoint_instruction says not needed)"
}}
"""


SEGMENT_EVAL_PROMPT = """
You are an expert educational content evaluator assessing one segment of a live class script.

=== SEGMENT ===
Title: {title}
Planned duration: {duration} minutes
Requires live coding: {code_required}
Segment purpose: {segment_purpose}

Content:
{content}

=== CLASS CONTEXT ===
Topic: {topic}
Audience: {beginner_pct}% beginner / {advanced_pct}% advanced

=== RULE-BASED PRE-CHECKS (already run — use these as context) ===
{rule_issues}

=== SCORING RUBRIC ===
Score each dimension 1–5. Be strict — a 4 means genuinely good, 5 is exceptional.

**Sentence Framing**
sentence_framing: Is the language conversational, active-voice, and instructor-ready?
Would a teacher naturally say these words aloud in a live class?

**Pedagogy — Advanced Topic Teaching Quality**
Answer these six questions and score each 1–5:
  concepts_introduced_first: Were ALL concepts introduced/defined BEFORE being used?
    (No term should appear in a sentence before it has been explained.)
  intuition_first: Was enough intuition and motivation built BEFORE formal definitions or code?
    (Students should understand *why* before they see *how*.)
  examples_and_analogies: Are there concrete examples AND analogies grounding abstract ideas?
    (At least one real-world analogy + one worked example.)
  terms_explained: Are difficult technical terms clearly explained the first time they appear?
    (Definitions or plain-English descriptions should precede or accompany each term.)
  builds_on_previous: Does this segment explicitly connect to and build on what came before?
    (References earlier content rather than starting cold.)
  has_checkpoint: Does the segment end with a meaningful comprehension checkpoint question?
    (A real question that tests understanding, not just "any questions?")

**Faithfulness**
faithfulness: Does the content faithfully deliver on the promised title and segment purpose?
Would an instructor feel this segment covered exactly what it said it would?

overall = mean of all 8 scores (sentence_framing + 6 pedagogy + faithfulness).
pass = true if overall >= 3.5

Return ONLY valid JSON — no extra text, no markdown fences:
{{
  "scores": {{
    "sentence_framing": 4.0,
    "pedagogy": {{
      "concepts_introduced_first": 4.0,
      "intuition_first": 3.5,
      "examples_and_analogies": 4.5,
      "terms_explained": 4.0,
      "builds_on_previous": 4.0,
      "has_checkpoint": 5.0
    }},
    "faithfulness": 4.5
  }},
  "overall": 4.2,
  "pass": true,
  "feedback": "Specific, actionable feedback pointing to exact phrases or sections that need to change. Empty string if pass is true."
}}
"""


SCRIPT_EVAL_PROMPT = """
You are an expert curriculum evaluator reviewing a complete class script.

=== BRIEF ===
Topic: {topic}
Duration: {duration} minutes
Audience: {beginner_pct}% beginner / {advanced_pct}% advanced
Required agenda: {agenda}

=== FULL SCRIPT (segment summaries) ===
{script_summary}

=== WHAT TO EVALUATE ===
Look at the script as a whole:
- coverage: Are all agenda items covered adequately?
- flow: Does the class progress naturally from one topic to the next?
- pacing: Is time distributed well across segments?
- level_fit: Is the difficulty consistently right for this audience?
- transitions: Do segments connect smoothly?

overall = average of all five scores.
pass = true if overall >= 3.8

Also identify the index (0-based) of the weakest segment that most needs improvement.

Return ONLY valid JSON — no extra text:
{{
  "scores": {{
    "coverage": 4.5,
    "flow": 4.0,
    "pacing": 4.5,
    "level_fit": 4.0,
    "transitions": 3.5
  }},
  "overall_score": 4.1,
  "pass": true,
  "weakest_segment_idx": 2,
  "improvement_suggestions": "Specific suggestions for the weakest segment. Empty string if pass is true."
}}
"""
