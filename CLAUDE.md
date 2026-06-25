# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Scriptor is a FastAPI backend for an AI-powered Class Script Authoring Pipeline. It generates complete teaching scripts from instructor briefs using a multi-stage LangGraph workflow with built-in validation and self-correction.

**Two main components:**
1. **Script Authoring Pipeline** (`pipeline/`) — Generates teaching scripts from instructor briefs
2. **Coding Agent** (`coding_agent/`) — Standalone agent that generates, validates, and tests code in isolated sandboxes

## Development Commands

```bash
# Install dependencies (first time setup)
pip install -r requirements.txt

# Start development server
uvicorn main:app --reload --port 8000

# Test standalone Coding Agent
python run_agent.py

# Access points
# - API: http://localhost:8000
# - Swagger docs: http://localhost:8000/docs
```

## Environment Setup

Create a `.env` file from `.env.example` with your OpenAI API key:
```bash
cp .env.example .env
# Then edit .env and add: OPENAI_API_KEY=sk-your-actual-key
```

## Architecture

### Pipeline Flow (LangGraph)

The core generation pipeline (`pipeline/graph.py`) follows a **deliberately linear architecture** — retry logic lives inside nodes as Python loops rather than complex graph edges. This makes debugging significantly easier.

**Flow:**
```
validate_input → plan_script → generate_and_eval_segments → merge_script → END
```

- **validate_input**: Fast deterministic checks (topic, agenda, percentages, timing constraints)
- **plan_script**: GPT-4o creates segment structure from brief; falls back to mechanical plan if LLM fails
- **generate_and_eval_segments**: SEQUENTIAL generation with per-segment evaluation loop
  - Generates segments ONE AT A TIME (not parallel)
  - Each segment sees actual content from previous segments (not just stubs)
  - Per-segment evaluation loop (max 3 retries):
    1. Generate content
    2. Two-stage evaluation:
       - Rule checks (examples, definitions, transitions, code blocks)
       - LLM pedagogy evaluation (9 dimensions including level-fit)
    3. If fails (score < 4.0): regenerate with detailed feedback
    4. If passes: move to next segment
  - Only proceeds when ALL segments pass quality threshold
- **merge_script**: Assembles final script with metadata and validation summary

**Key Quality Controls:**
- **Concepts before use**: Terms must be defined before appearing in examples
- **Intuition first**: Motivation explained before showing code/formulas
- **Examples & analogies**: Concrete examples + real-world analogies required
- **Level adaptivity**: 80% beginner content reads differently from 80% advanced
- **Builds on previous**: Each segment must reference prior material
- **Checkpoint questions**: Meaningful comprehension checks (not "any questions?")

### State Management

`pipeline/state.py` defines `PipelineState` — the shared state dict that flows through all nodes:
- `brief`: Original instructor input
- `validation_errors`: Input validation failures (short-circuits to END if non-empty)
- `plan`: Segment specifications from planner
- `segments`: Generated segment objects (with embedded eval scores)
- `script`: Final merged script with validation metadata
- `rule_report`, `eval_report`: Validation results
- `script_retried`: Tracks whether weakest-segment regen already happened

### Evaluation Strategy

**Per-segment evaluation with retry loop** (`nodes.py:_eval_segment`):

**Two-stage evaluation:**

1. **Rule-based checks** (deterministic):
   - Examples and analogies present
   - Technical terms defined before use
   - Comprehension checkpoint present
   - Transition phrases to next section
   - Code blocks when required
   - References to prior material
   - Minimum content length

2. **LLM pedagogy evaluation** (9 dimensions, pass threshold: 4.0/5.0):
   - `sentence_framing`: Conversational, instructor-ready language
   - `concepts_introduced_first`: Terms defined before use (strict check)
   - `intuition_first`: Motivation before formal definitions
   - `examples_and_analogies`: Concrete examples + real-world analogies
   - `terms_explained`: Plain-English definitions when terms first appear
   - `builds_on_previous`: Explicit references to prior segments
   - `has_checkpoint`: Meaningful comprehension question
   - `level_fit`: Matches beginner/advanced ratio (critical for adaptivity)
   - `faithfulness`: Delivers on promised title/purpose

**Retry mechanism:**
- If score < 4.0: regenerate with detailed, actionable feedback
- Max 3 attempts per segment
- Feedback includes specific line references and exact problems
- Only moves to next segment when current passes or max retries exhausted

**Why sequential, not parallel:**
- Each segment needs actual content from previous segments (not stubs)
- Enables "builds on previous" pedagogy check
- Ensures strong narrative coherence
- Quality gate before proceeding forward

### Data Persistence

Scripts are stored as JSON files in `data/{script_id}.json`. Each file contains:
- `brief`: Original instructor input
- `plan`: Segment specifications
- `script`: Complete script with segments
- `rule_report`, `eval_report`: Quality metrics
- `approved`: Boolean flag set by `/approve` endpoint
- Timestamps: `created_at`, `approved_at`, `updated_at`

### API Endpoints

| Endpoint | Purpose | Key Behavior |
|----------|---------|--------------|
| `POST /generate` | Run full pipeline | Returns script, saves to `data/{id}.json` |
| `POST /regenerate` | Single segment regen | Takes segment_id + feedback, updates stored script |
| `POST /approve` | Mark script approved | Sets approval flag + timestamp |
| `GET /download/{id}` | Export as Markdown | Compiles all segments into downloadable .md file |
| `GET /health` | Health check | Returns status + version |

### Sequential Generation (Not Parallel)

**Why sequential:**
- Each segment uses actual content from prior segments (not just stubs)
- Enables strong pedagogical coherence ("As we saw in the previous section...")
- Quality gate before moving forward (can't proceed until current segment passes)
- Ensures level adaptivity is consistent across the entire script

**Trade-off:**
- Slower than parallel (segments generated one-by-one)
- BUT produces higher quality with better narrative flow
- Typical 5-segment script: ~3-5 minutes vs ~1-2 minutes for parallel
- Quality improvement justifies the extra time

### LLM Configuration

- **Model**: GPT-4o (defined in `nodes.py:_get_llm`)
- **Temperature**: 0.7 (balance between creativity and consistency)
- **Max retries**: 2 (built into ChatOpenAI client)
- Lazy initialization — LLM instantiated on first use so module can be imported before `.env` loads

## Key Design Decisions

1. **Linear graph with internal retry loops** (not complex conditional edges) — easier to debug, trace, and reason about
2. **Sequential generation with actual prior content** (not parallel with stubs) — stronger pedagogy, better narrative coherence
3. **Per-segment evaluation loop** (not post-generation batch eval) — quality gate before proceeding, prevents cascading errors
4. **Strict pass threshold (4.0/5.0)** — ensures only high-quality segments move forward
5. **Level adaptivity enforced** — explicit `level_fit` dimension checks beginner/advanced ratio is respected
6. **Concepts-before-use checking** — terms must be defined before appearing in examples
7. **Two-tier evaluation** (fast rules + LLM judgment) — catches common issues deterministically before expensive LLM calls
8. **File-based persistence** (not database) — simple for prototype, easy to inspect, version-controllable

## Common Modification Patterns

**Adjusting quality thresholds:**
- Edit constants at top of `pipeline/nodes.py`:
  - `MAX_SEGMENT_RETRIES = 3` (attempts per segment)
  - `SEGMENT_PASS_SCORE = 4.0` (minimum score to accept segment)
  - `SCRIPT_PASS_SCORE = 3.8` (kept for backwards compatibility, not actively used)

**Changing prompts:**
- All prompt templates live in `pipeline/prompts.py`
- Use `.format()` syntax — escape literal braces as `{{` and `}}`

**Adding new rule checks:**
- Per-segment: `pipeline/validators.py:check_segment_rules`
- Full-script: `pipeline/validators.py:run_rule_checks`

**Modifying LLM config:**
- Model, temperature, retries: `pipeline/nodes.py:_get_llm()`

**Adding API endpoints:**
- Route handlers in `main.py`
- Request/response schemas in `models.py`

---

## Coding Agent (`coding_agent/`)

A **standalone LangGraph agent** that generates executable code, validates it in isolated sandboxes, automatically fixes errors, and runs generated tests. Independent of the Script Authoring Pipeline.

### Architecture

**Execution-driven validation** — the agent loops until code actually runs correctly:

```
Understand Task → Generate Code → Detect Dependencies → Create Sandbox
→ Install Dependencies → Execute Code
  ├─ Pass → Generate Tests → Execute Tests
  │   ├─ Pass → Code Review → Finalize Output ✓
  │   └─ Fail → Repair Code → (loop back)
  └─ Fail → Repair Code → (loop back to Install)
```

**Key features:**
- Multi-version Python support (3.10, 3.11, 3.12)
- Automatic import detection + pip package mapping
- Isolated sandboxes (tempdir + venv per execution)
- Self-healing with max 3 repair attempts
- Auto-generated pytest tests
- Code quality review before delivery

### Files

- `state.py` — State definition for the graph
- `prompts.py` — LLM prompt templates for all stages
- `tools.py` — Sandbox creation, execution, dependency management
- `nodes.py` — Node functions (understand, generate, repair, test, review)
- `graph.py` — LangGraph pipeline with routing logic
- `README.md` — Detailed documentation

### Usage

```python
from coding_agent import run_agent

result = run_agent(
    task="Write a binary search function",
    language="python",
    version="3.11",  # MUST be 3.10, 3.11, 3.12, or 3.13
    dependencies=[],
    constraints=["Readable for beginners"],
)

if result["status"] == "success":
    print(result["code"])
    print(result["requirements_txt"])
```

**Python version validation:**
- Only supports: 3.10, 3.11, 3.12, 3.13
- Raises `ValueError` for any other version (e.g., 3.9, 3.14)
- Version check happens at entry before any work starts

### Success Criteria

Code is only returned when:
- ✓ Executes without errors (exit code 0)
- ✓ Dependencies install successfully
- ✓ Generated tests pass
- ✓ Code review score ≥ 4.0/5.0

### Retry Loops

**Execution loop:** Generate → Execute → Fail? → Repair → Re-execute (max 3×)  
**Testing loop:** Generate Tests → Run Tests → Fail? → Repair → Re-run Tests (max 3×)

If still failing after 3 attempts, returns failure report with last error.

### Configuration

Constants in `coding_agent/nodes.py`:
- `MAX_RETRIES = 3`
- `MIN_REVIEW_SCORE = 4.0`
- `MAX_EXECUTION_TIME = 30` seconds

### Sandbox Isolation

Each execution creates:
- Fresh temporary directory
- Isolated virtual environment
- Code written to `main.py`
- Tests written to `test_main.py`
- Automatic cleanup after completion

### Extending

**Add language support:**
1. Update `tools.py:detect_imports()` for the language
2. Update `tools.py:create_sandbox()` for environment setup
3. Update `tools.py:execute_code()` for interpreter
4. Add test framework support in `tools.py:execute_tests()`

**Customize behavior:**
- Edit prompt templates in `prompts.py`
- Add custom validation nodes in `nodes.py`
- Update routing logic in `graph.py`

See `coding_agent/README.md` for detailed documentation.
