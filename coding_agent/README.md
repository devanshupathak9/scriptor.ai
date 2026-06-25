# Coding Agent

A standalone LangGraph agent that generates Python code, validates it in an isolated venv, fixes errors automatically, runs tests, and returns only verified code.

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

```
[1] understand_task       — LLM analyzes the task, identifies components and edge cases
[2] generate_code         — LLM writes Python code + suggests pip packages
[3] detect_dependencies   — merges user deps + LLM deps + auto-detected imports
[4] create_sandbox        — creates a temp dir + Python venv
[5] install_dependencies  — pip installs all packages into the venv
[6] execute_code          — runs main.py inside the venv
      │
      ├── ✓ pass → [8] generate_tests
      └── ✗ fail → [7] repair_code → back to [6]  (max 3 retries)
                        if retries exhausted → [11] finalize (failure)

[8] generate_tests        — LLM writes pytest test cases for the code
[9] run_tests             — runs pytest inside the venv
      │
      ├── ✓ pass → [10] code_review
      └── ✗ fail → [7] repair_code → back to [9]  (max 3 retries)
                        if retries exhausted → [10] code_review (flagged)

[10] code_review          — LLM scores readability, correctness, best practices
[11] finalize             — prints summary, writes final requirements.txt
```

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

## Notes

- Sandbox is **not auto-deleted** — inspect files at the printed path, then remove manually.
- If your requested Python version isn't installed, the agent falls back to `python3`.
- No changes to the main Script Authoring Pipeline — this agent is fully independent.
