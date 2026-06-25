# Coding Agent

A standalone LangGraph agent that generates Python code, validates it in an isolated venv, fixes errors automatically, runs tests, and returns only verified code.

## Supported Python Versions

**The agent generates code ONLY for these Python versions:**
- ✅ Python 3.10
- ✅ Python 3.11  
- ✅ Python 3.12
- ✅ Python 3.13 (default)

Code is generated with version-specific syntax and features. The agent will attempt to find and use the exact Python version you specify.

---

## Setup

```bash
cd scriptor_backend
cp .env.example .env     # add OPENAI_API_KEY
pip install -r requirements.txt
```

---

## Run

```bash
python run_agent.py                                           # built-in example
python run_agent.py "write a linked list implementation"      # plain text task
python run_agent.py '{"task": "...", "version": "3.13", "constraints": ["beginner friendly"]}'
```

---

## Input

| Field | Required | Example |
|---|---|---|
| `task` | yes | `"Write a binary search"` |
| `version` | no (default `3.13`) | `"3.11"`, `"3.12"`, `"3.13"` |
| `dependencies` | no | `["numpy", "pandas"]` |
| `constraints` | no | `["Readable for beginners"]` |
| `expected_output` | no | `"Returns index or -1"` |

---

## Workflow

### Complete Pipeline (11 Nodes)

```
┌─────────────────────────────────────────────────────────────────┐
│ [1] UNDERSTAND TASK                                             │
│     LLM analyzes: complexity, components, edge cases, algorithms│
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ [2] GENERATE CODE                                               │
│     LLM writes Python code for specified version + suggests deps│
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ [3] DETECT DEPENDENCIES                                         │
│     Merge: user-provided + LLM-suggested + auto-detected imports│
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ [4] CREATE SANDBOX                                              │
│     Create temp directory + Python venv for specified version   │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ [5] INSTALL DEPENDENCIES                                        │
│     pip install all packages in isolated venv                   │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ [6] EXECUTE CODE                                                │
│     Run main.py in venv, capture stdout/stderr/exit_code        │
└────────┬──────────────────────┬─────────────────────────────────┘
         │                      │
      SUCCESS                FAILURE
         │                      │
         ↓                      ↓
  ┌──────────────┐      ┌─────────────────────┐
  │ [8] GENERATE │      │ [7] REPAIR CODE     │
  │     TESTS    │      │     (LLM fixes)     │
  └──────┬───────┘      └──────┬──────────────┘
         │                     │
         │              code_retry_count < 3? YES → back to [5]
         │              code_retry_count = 3? NO  → [11] finalize
         ↓
  ┌──────────────────┐
  │ [9] RUN TESTS    │
  │     (pytest)     │
  └────┬────────┬────┘
       │        │
    PASS      FAIL
       │        │
       ↓        └──→ [7] REPAIR CODE (fix to pass tests)
  ┌──────────────┐         │
  │ [10] CODE    │  test_retry_count < 3? YES → back to [9]
  │     REVIEW   │  test_retry_count = 3? NO  → continue
  └──────┬───────┘
         ↓
  ┌─────────────────────────────────────────────────────────────┐
  │ [11] FINALIZE                                               │
  │      Return verified code + tests + requirements.txt        │
  └─────────────────────────────────────────────────────────────┘
```

### Key Points

- ✅ **Execution loop**: Repairs code up to 3 times if execution fails
- ✅ **Testing loop**: Repairs code up to 3 times if tests fail
- ✅ **Same repair node**: Handles both loops using `phase` field
- ✅ **Version-specific**: All code generated for specified Python version
- ✅ **Isolated**: Each run gets fresh sandbox with correct Python version

---

## Output

On success you get:

- **Generated code** (`main.py` in the sandbox)
- **Generated tests** (`test_main.py` in the sandbox)
- **`requirements.txt`** with all installed packages
- **Code review notes** with a quality score
- **Sandbox path** — inspect or delete after use

---

## Retry Logic

| Loop | Max retries | On exhaustion |
|---|---|---|
| Execution | 3 | returns failure |
| Tests | 3 | proceeds to code review anyway |

The same `repair_code` node handles both loops — it uses the current `phase` (`"execution"` or `"testing"`) to pick the right prompt and route back correctly.

---

## Important Notes

### Python Version Handling

The agent will:
1. Look for `python{version}` binary (e.g., `python3.11`)
2. Fall back to `python3` if not found (with warning)
3. Generate code specifically for the requested version (3.10, 3.11, 3.12, or 3.13)

**Always specify a supported version** (3.10-3.13) for best results.

### Sandbox Management

- Sandbox is **not auto-deleted** — inspect files at the printed path, then remove manually if needed
- Each run creates a fresh isolated environment
- Location printed in output: `Sandbox: /tmp/coding_agent_abc123/`

### Independence

- No changes to the main Script Authoring Pipeline
- This agent is fully standalone and can be used independently
- Import with: `from coding_agent import run_agent`
