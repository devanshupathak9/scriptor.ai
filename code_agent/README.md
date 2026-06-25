# Coding Agent

A standalone LangGraph-based agent that generates, validates, and tests code in isolated sandboxes.

## Features

- **Multi-version Python support** (3.10, 3.11, 3.12)
- **Automatic dependency detection** from imports
- **Isolated sandbox execution** with virtual environments
- **Self-healing code generation** with retry loops (max 3 attempts)
- **Automated test generation and execution**
- **Code quality review** before delivery
- **Execution-driven validation** (only returns verified, working code)

## Architecture

```
User Request
    ↓
Understand Task (LLM analyzes requirements)
    ↓
Generate Code (LLM writes initial implementation)
    ↓
Detect Dependencies (auto-detect imports + explicit deps)
    ↓
Create Sandbox (isolated tempdir + venv)
    ↓
Install Dependencies (pip install in venv)
    ↓
Execute Code (run in sandbox, capture output)
    ↓
  ┌─────┴─────┐
Pass        Fail
  │           │
  ↓           ↓
Generate    Repair Code (LLM fixes errors)
Tests         │
  │           └──→ Re-install & Re-execute (loop max 3×)
  ↓
Execute Tests (pytest in sandbox)
  │
  ┌─────┴─────┐
Pass        Fail
  │           │
  ↓           ↓
Code        Repair Code
Review        │
  │           └──→ Re-execute Tests
  ↓
Finalize Output (cleanup sandbox, return verified code)
```

## Usage

### Standalone Testing

```bash
# Run the test suite
python test_coding_agent.py
```

### Programmatic Usage

```python
from coding_agent import coding_agent

initial_state = {
    "language": "python",
    "version": "3.11",
    "task": "Write a binary search function",
    "dependencies": [],
    "constraints": ["Readable for beginners"],
    "expected_output": None,
    # ... (see test_coding_agent.py for full state structure)
}

result = coding_agent.invoke(initial_state)

if result["status"] == "success":
    print("✓ Code:", result["final_code"])
    print("✓ Dependencies:", result["requirements_txt"])
    print("✓ Tests passed:", result["tests_passed"])
else:
    print("✗ Error:", result["error"])
```

## Input Schema

| Field | Type | Description |
|-------|------|-------------|
| `language` | str | Programming language (currently only "python") |
| `version` | str | Language version ("3.10", "3.11", "3.12") |
| `task` | str | Problem statement / what to generate |
| `dependencies` | list[str] | Optional explicit dependencies |
| `constraints` | list[str] | Optional constraints (e.g., "beginner-friendly") |
| `expected_output` | str | Optional expected output for validation |

## Output Schema

| Field | Type | Description |
|-------|------|-------------|
| `status` | str | "success" or "failed" |
| `final_code` | str | Verified, executable code |
| `requirements_txt` | str | Dependencies in requirements.txt format |
| `generated_tests` | str | Test code (pytest) |
| `tests_passed` | bool | Whether tests passed |
| `final_review` | dict | Code quality scores and feedback |
| `retry_count` | int | Number of repair attempts |
| `execution_logs` | str | stdout/stderr from execution |
| `error` | str | Error message if failed |

## Nodes

1. **understand_task** — Parse requirements, detect complexity
2. **generate_code** — LLM writes initial implementation
3. **detect_dependencies_node** — Auto-detect imports + combine with explicit deps
4. **create_sandbox_node** — Create tempdir + venv
5. **install_dependencies_node** — pip install in venv
6. **execute_code_node** — Run code, capture output
7. **validate_runtime** — Check exit code
8. **repair_code** — LLM fixes errors (max 3 retries)
9. **generate_tests** — LLM writes pytest tests
10. **execute_tests_node** — Run tests in sandbox
11. **review_code** — Final quality review (readability, best practices, etc.)
12. **finalize_output** — Cleanup sandbox, return results
13. **handle_failure** — Cleanup on failure

## Retry Logic

### Execution Loop
```
Generate → Execute → Fail? → Repair → Re-execute (max 3×)
```

### Testing Loop
```
Generate Tests → Run Tests → Fail? → Repair Code → Re-run Tests (max 3×)
```

If still failing after 3 attempts, returns failure report with last error.

## Success Criteria

Code is only returned when:
- ✓ Executes without errors (exit code 0)
- ✓ Dependencies install successfully
- ✓ Generated tests pass (if tests were generated)
- ✓ Code review score ≥ 4.0 / 5.0

## Configuration

Edit constants in `nodes.py`:
- `MAX_RETRIES = 3` — Maximum repair attempts
- `MIN_REVIEW_SCORE = 4.0` — Minimum code quality score
- `MAX_EXECUTION_TIME = 30` — Timeout for code execution (seconds)

## Supported Python Versions

The agent checks for these Python executables:
- `python3.10`
- `python3.11`
- `python3.12`

Falls back to `python3` if specific version not found.

## Dependency Mapping

The agent automatically maps common import names to pip packages:
- `sklearn` → `scikit-learn`
- `cv2` → `opencv-python`
- `PIL` → `Pillow`
- `yaml` → `pyyaml`

See `tools.py:map_import_to_package()` for the full mapping.

## Sandbox Isolation

Each execution creates a fresh temporary directory with:
- Isolated virtual environment
- Sandboxed pip installations
- Code written to `main.py`
- Tests written to `test_main.py`

Sandboxes are automatically cleaned up after execution (success or failure).

## Extending

### Add support for other languages

1. Update `tools.py:detect_imports()` to parse imports for the new language
2. Update `tools.py:create_sandbox()` to set up the language environment
3. Update `tools.py:execute_code()` to use the correct interpreter
4. Add language-specific test framework support in `tools.py:execute_tests()`

### Customize prompts

Edit templates in `prompts.py`:
- `TASK_UNDERSTANDING_PROMPT`
- `CODE_GENERATION_PROMPT`
- `CODE_REPAIR_PROMPT`
- `TEST_GENERATION_PROMPT`
- `CODE_REVIEW_PROMPT`

### Add custom validation

Add new nodes in `nodes.py` and update the graph routing in `graph.py`.

## Testing

The `test_coding_agent.py` script includes three test cases:

1. **Hello World** — Simplest possible test
2. **Binary Search** — Algorithm implementation with tests
3. **Data Processing** — Script with external dependencies (pandas)

Run individually or all together to validate the agent.

## Known Limitations

- Currently only supports Python
- Test generation uses pytest (other frameworks not yet supported)
- Maximum 3 repair attempts (hard-coded)
- No support for multi-file projects (single-file only)
- No persistent caching between invocations

## Future Enhancements

- [ ] Multi-language support (JavaScript, Go, Rust)
- [ ] Multi-file project generation
- [ ] Incremental refinement (user feedback loop)
- [ ] Performance benchmarking
- [ ] Security scanning (dependency vulnerabilities)
- [ ] Code style enforcement (black, ruff, etc.)
