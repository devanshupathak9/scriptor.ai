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
python test_coding_agent.py

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
validate_input → plan_script → generate_segments → merge_script → validate_and_eval → END
```

- **validate_input**: Fast deterministic checks (topic, agenda, percentages, timing constraints)
- **plan_script**: GPT-4o creates segment structure from brief; falls back to mechanical plan if LLM fails
- **generate_segments**: Parallelized generation of all segments (5 concurrent workers max)
  - Each segment runs its own generate → eval → retry loop (up to 2 retries)
  - Uses plan stubs (title + duration) for context instead of full content, enabling full parallelization
- **merge_script**: Assembles final script object with metadata
- **validate_and_eval**: Two-stage validation
  1. Rule checks (deterministic: agenda coverage, timing, code ratio, transitions, examples)
  2. LLM evaluation of full script (coverage, flow, pacing, level_fit, transitions)
  3. One-shot weakest-segment regeneration if overall score < 3.8

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

**Two-tier quality control:**

1. **Per-segment** (`nodes.py:_eval_segment`):
   - **Stage 1 (Rule-based)**: Fast checks for examples, definitions, checkpoints, transitions, code blocks, prior-material references
   - **Stage 2 (LLM)**: Scores sentence framing + 6 pedagogy dimensions + faithfulness (pass threshold: 3.5/5.0)
   - Rule failures incur small score penalty (0.15 per issue, capped at -0.5)
   - Retry loop: regenerates with feedback until pass or max retries (2)

2. **Full-script** (`nodes.py:_eval_full_script`):
   - Evaluates coverage, flow, pacing, level_fit, transitions (pass threshold: 3.8/5.0)
   - Identifies weakest segment for targeted regen if script fails

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

### Parallelization

- **Segment generation**: ThreadPoolExecutor with 5 max workers (`nodes.py:generate_segments`)
- Each segment is independently generated and evaluated before merging
- Context for each segment = plan stubs (title + duration) of prior segments, NOT full content — this design choice enables true parallelism

### LLM Configuration

- **Model**: GPT-4o (defined in `nodes.py:_get_llm`)
- **Temperature**: 0.7 (balance between creativity and consistency)
- **Max retries**: 2 (built into ChatOpenAI client)
- Lazy initialization — LLM instantiated on first use so module can be imported before `.env` loads

## Key Design Decisions

1. **Linear graph with internal retry loops** (not complex conditional edges) — easier to debug, trace, and reason about
2. **Parallel generation with plan-stub context** (not sequential with full content) — 5× faster on typical 5-segment scripts
3. **Two-tier evaluation** (fast rules + LLM judgment) — catches common issues deterministically before expensive LLM calls
4. **One-shot weakest-segment regen** (not full-script retry) — targeted fixes are cheaper and preserve good segments
5. **File-based persistence** (not database) — simple for prototype, easy to inspect, version-controllable

## Common Modification Patterns

**Adjusting quality thresholds:**
- Edit constants at top of `pipeline/nodes.py`: `MAX_SEGMENT_RETRIES`, `SEGMENT_PASS_SCORE`, `SCRIPT_PASS_SCORE`

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
from coding_agent import coding_agent

initial_state = {
    "language": "python",
    "version": "3.11",
    "task": "Write a binary search function",
    "dependencies": [],
    "constraints": ["Readable for beginners"],
    # ... (see test_coding_agent.py for full state)
}

result = coding_agent.invoke(initial_state)

if result["status"] == "success":
    print(result["final_code"])
    print(result["requirements_txt"])
```

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
