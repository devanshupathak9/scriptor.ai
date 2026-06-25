"""
All LangGraph node functions for the Coding Agent.
Each function receives the full state dict and returns a dict of fields to update.
"""

import json
import re
import tempfile
import time
import uuid

from dotenv import load_dotenv

load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .state import CodingAgentState
from .prompts import (
    UNDERSTAND_TASK_PROMPT,
    GENERATE_CODE_PROMPT,
    REPAIR_EXECUTION_PROMPT,
    REPAIR_TEST_PROMPT,
    GENERATE_TESTS_PROMPT,
    CODE_REVIEW_PROMPT,
)
from .tools import run_shell, write_file, detect_imports, find_python_binary

MAX_CODE_RETRIES = 3
MAX_TEST_RETRIES = 3

_llm: ChatOpenAI | None = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o", temperature=0.2, max_retries=2)
    return _llm


def _call_llm(system: str, user: str) -> str:
    response = _get_llm().invoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])
    return response.content


def _parse_json(text: str) -> dict:
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    return json.loads(text.strip())


def _parse_code_response(text: str, code_key: str = "code") -> dict:
    """
    Try JSON first; fall back to extracting a python block from markdown.
    Handles cases where the LLM forgets to escape newlines in JSON strings.
    """
    try:
        return _parse_json(text)
    except json.JSONDecodeError:
        match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
        if match:
            return {code_key: match.group(1).strip(), "requirements": []}
        return {code_key: text.strip(), "requirements": []}


# ── Node 1: Understand Task ────────────────────────────────────────────────────

def understand_task(state: CodingAgentState) -> dict:
    print(f"\n[1/10] understand_task")
    print(f"       task: {state['task'][:80]}…")

    prompt = UNDERSTAND_TASK_PROMPT.format(
        task=state["task"],
        language=state["language"],
        version=state["version"],
        dependencies=state.get("dependencies") or [],
        constraints=state.get("constraints") or [],
        expected_output=state.get("expected_output") or "",
    )

    try:
        raw      = _call_llm("You are a senior software architect.", prompt)
        analysis = _parse_json(raw)
        print(f"       complexity={analysis.get('complexity')}  "
              f"components={analysis.get('key_components', [])}")
    except Exception as exc:
        print(f"       LLM failed ({exc}), using defaults.")
        analysis = {
            "summary": state["task"],
            "key_components": [],
            "algorithms": [],
            "edge_cases": [],
            "complexity": "medium",
            "version_notes": "",
        }

    return {"task_analysis": analysis}


# ── Node 2: Generate Code ──────────────────────────────────────────────────────

def generate_code(state: CodingAgentState) -> dict:
    print("\n[2/10] generate_code")

    prompt = GENERATE_CODE_PROMPT.format(
        task=state["task"],
        version=state["version"],
        task_analysis=json.dumps(state.get("task_analysis") or {}, indent=2),
        constraints=state.get("constraints") or [],
        dependencies=state.get("dependencies") or [],
    )

    raw  = _call_llm("You are an expert Python developer.", prompt)
    data = _parse_code_response(raw)

    code = data.get("code") or ""
    reqs = data.get("requirements") or []

    print(f"       {len(code.splitlines())} lines | suggested packages: {reqs}")

    return {"generated_code": code, "llm_requirements": reqs}


# ── Node 3: Detect Dependencies ────────────────────────────────────────────────

def detect_dependencies(state: CodingAgentState) -> dict:
    print("\n[3/10] detect_dependencies")

    user_deps = state.get("dependencies") or []
    llm_reqs  = state.get("llm_requirements") or []
    detected  = detect_imports(state.get("generated_code") or "")

    # Merge with priority: user > LLM > auto-detected, no duplicates
    seen: set[str] = set()
    merged: list[str] = []
    for pkg in user_deps + llm_reqs + detected:
        if pkg and pkg not in seen:
            seen.add(pkg)
            merged.append(pkg)

    print(f"       final requirements: {merged or 'none'}")
    return {"all_requirements": merged}


# ── Node 4: Create Sandbox ─────────────────────────────────────────────────────

def create_sandbox(state: CodingAgentState) -> dict:
    version = state["version"]
    print(f"\n[4/10] create_sandbox  (Python {version})")

    python_bin = find_python_binary(version)
    if not python_bin:
        print(f"       ✗ Python {version} not found on this system!")
        print(f"       Supported versions: 3.10, 3.11, 3.12, 3.13")
        print(f"       Install Python {version} or choose a different version.")
        python_bin = "python3"
        print(f"       ⚠ Falling back to {python_bin} (may cause compatibility issues)")
    else:
        print(f"       using binary: {python_bin}")

    sandbox_dir = tempfile.mkdtemp(prefix=f"coding_agent_{uuid.uuid4().hex[:6]}_")
    print(f"       sandbox: {sandbox_dir}")

    result = run_shell(f"{python_bin} -m venv {sandbox_dir}/.venv")
    if result["exit_code"] != 0:
        print(f"       ⚠ venv creation failed:\n{result['stderr'][:300]}")
    else:
        print("       ✓ venv ready")

    # conftest.py so `import main` always works when pytest runs from sandbox_dir
    write_file(
        f"{sandbox_dir}/conftest.py",
        "import sys, os\n"
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n",
    )

    return {
        "sandbox_dir": sandbox_dir,
        "venv_python": f"{sandbox_dir}/.venv/bin/python",
        "venv_pip":    f"{sandbox_dir}/.venv/bin/pip",
        "venv_pytest": f"{sandbox_dir}/.venv/bin/pytest",
    }


# ── Node 5: Install Dependencies ──────────────────────────────────────────────

def install_dependencies(state: CodingAgentState) -> dict:
    requirements = state.get("all_requirements") or []
    pip         = state["venv_pip"]
    sandbox_dir = state["sandbox_dir"]

    print(f"\n[5/10] install_dependencies")

    # Always upgrade pip silently
    run_shell(f"{pip} install --upgrade pip -q", timeout=60)

    if not requirements:
        print("       no external dependencies")
        return {}

    req_path = f"{sandbox_dir}/requirements.txt"
    write_file(req_path, "\n".join(requirements))
    print(f"       installing: {requirements}")

    result = run_shell(f"{pip} install -r {req_path}", timeout=120)
    if result["exit_code"] != 0:
        print(f"       ⚠ install warning (will retry in repair loop if needed):")
        print(f"       {result['stderr'][-400:]}")
    else:
        print("       ✓ all packages installed")

    return {}


# ── Node 6: Execute Code ───────────────────────────────────────────────────────

def execute_code(state: CodingAgentState) -> dict:
    sandbox_dir = state["sandbox_dir"]
    venv_python = state["venv_python"]
    code        = state["generated_code"]
    attempt     = state.get("code_retry_count", 0) + 1

    print(f"\n[6/10] execute_code  (attempt {attempt}/{MAX_CODE_RETRIES + 1})")

    write_file(f"{sandbox_dir}/main.py", code)

    t0     = time.time()
    result = run_shell(f"{venv_python} {sandbox_dir}/main.py", timeout=30)
    elapsed = round(time.time() - t0, 2)

    success = result["exit_code"] == 0

    if success:
        print(f"       ✓ exit 0  ({elapsed}s)")
        output_preview = result["stdout"].strip()
        if output_preview:
            print(f"       output: {output_preview[:300]}")
    else:
        print(f"       ✗ exit {result['exit_code']}")
        err = (result["stderr"] or result["stdout"]).strip()
        print(f"       {err[-500:]}")

    return {
        "execution_output":  result["stdout"],
        "execution_errors":  result["stderr"],
        "execution_success": success,
        "execution_time":    elapsed,
        "phase":             "execution",
    }


# ── Node 7: Repair Code ────────────────────────────────────────────────────────

def repair_code(state: CodingAgentState) -> dict:
    phase = state.get("phase", "execution")

    if phase == "testing":
        attempt  = state.get("test_retry_count", 0) + 1
        max_r    = MAX_TEST_RETRIES
        error    = (state.get("test_errors") or "") + "\n" + (state.get("test_output") or "")
        template = REPAIR_TEST_PROMPT
        print(f"\n[7/10] repair_code  [test phase, attempt {attempt}/{max_r}]")
    else:
        attempt  = state.get("code_retry_count", 0) + 1
        max_r    = MAX_CODE_RETRIES
        error    = state.get("execution_errors") or state.get("execution_output") or ""
        template = REPAIR_EXECUTION_PROMPT
        print(f"\n[7/10] repair_code  [execution phase, attempt {attempt}/{max_r}]")

    prompt = template.format(
        code=state["generated_code"],
        error=error[-2000:],
        task=state["task"],
        version=state["version"],
        requirements=state.get("all_requirements") or [],
        attempt=attempt,
        max_attempts=max_r,
    )

    try:
        raw  = _call_llm("You are an expert Python debugger.", prompt)
        data = _parse_code_response(raw)

        new_code = data.get("code") or state["generated_code"]
        new_reqs = data.get("requirements") or state.get("all_requirements") or []
        print(f"       fix: {str(data.get('explanation', ''))[:120]}")

        # Re-install if requirements changed
        old_reqs = set(state.get("all_requirements") or [])
        if set(new_reqs) != old_reqs:
            print(f"       requirements updated → {new_reqs}")
            req_path = f"{state['sandbox_dir']}/requirements.txt"
            write_file(req_path, "\n".join(new_reqs))
            run_shell(f"{state['venv_pip']} install -r {req_path} -q", timeout=120)

    except Exception as exc:
        print(f"       LLM repair failed ({exc}), keeping current code")
        new_code = state["generated_code"]
        new_reqs = state.get("all_requirements") or []

    updates: dict = {
        "generated_code":   new_code,
        "all_requirements": new_reqs,
    }
    if phase == "testing":
        updates["test_retry_count"] = attempt
    else:
        updates["code_retry_count"] = attempt

    return updates


# ── Node 8: Generate Tests ─────────────────────────────────────────────────────

def generate_tests(state: CodingAgentState) -> dict:
    print("\n[8/10] generate_tests")

    # Install pytest into the venv if not already there
    run_shell(f"{state['venv_pip']} install pytest -q", timeout=60)

    prompt = GENERATE_TESTS_PROMPT.format(
        code=state["generated_code"],
        task=state["task"],
        version=state["version"],
        requirements=state.get("all_requirements") or [],
    )

    try:
        raw   = _call_llm("You are an expert Python test engineer.", prompt)
        data  = _parse_code_response(raw, code_key="tests")
        tests = data.get("tests") or ""
        print(f"       {len(tests.splitlines())} lines generated")
    except Exception as exc:
        print(f"       LLM failed ({exc}), generating stub")
        tests = "def test_placeholder():\n    assert True\n"

    return {"generated_tests": tests, "phase": "testing"}


# ── Node 9: Run Tests ──────────────────────────────────────────────────────────

def run_tests(state: CodingAgentState) -> dict:
    sandbox_dir = state["sandbox_dir"]
    venv_pytest = state["venv_pytest"]
    attempt     = state.get("test_retry_count", 0) + 1

    print(f"\n[9/10] run_tests  (attempt {attempt}/{MAX_TEST_RETRIES + 1})")

    # Always write current versions of both files before running
    write_file(f"{sandbox_dir}/main.py",      state["generated_code"])
    write_file(f"{sandbox_dir}/test_main.py", state["generated_tests"])

    result = run_shell(
        f"{venv_pytest} test_main.py -v --tb=short",
        cwd=sandbox_dir,
        timeout=60,
    )
    passed = result["exit_code"] == 0
    output = result["stdout"] + result["stderr"]

    if passed:
        m = re.search(r"(\d+) passed", output)
        print(f"       ✓ {m.group(1) if m else '?'} tests passed")
    else:
        print(f"       ✗ tests failed")
        print(f"       {output[-600:].strip()}")

    return {
        "test_output":  result["stdout"],
        "test_errors":  result["stderr"],
        "tests_passed": passed,
    }


# ── Node 10: Code Review ───────────────────────────────────────────────────────

def code_review(state: CodingAgentState) -> dict:
    print("\n[10/10] code_review")

    test_summary = "All tests passed." if state.get("tests_passed") else "Tests failed or skipped."

    prompt = CODE_REVIEW_PROMPT.format(
        code=state["generated_code"],
        task=state["task"],
        version=state["version"],
        test_results=test_summary,
        constraints=state.get("constraints") or [],
    )

    try:
        raw  = _call_llm("You are a senior Python code reviewer.", prompt)
        data = _parse_json(raw)

        score    = float(data.get("score", 4.0))
        notes    = str(data.get("notes", ""))
        approved = bool(data.get("approved", True))

        print(f"       score={score:.1f}/5  approved={approved}")
        for s in (data.get("suggestions") or [])[:2]:
            print(f"       • {s}")

        return {"review_notes": notes, "review_approved": approved}

    except Exception as exc:
        print(f"       review failed ({exc}), auto-approving")
        return {"review_notes": "Review skipped.", "review_approved": True}


# ── Node 11: Finalize ──────────────────────────────────────────────────────────

def finalize(state: CodingAgentState) -> dict:
    success = state.get("execution_success", False)
    status  = "success" if success else "failure"
    err_msg = "" if success else (state.get("execution_errors") or "Unknown error.")

    requirements = state.get("all_requirements") or []
    sandbox_dir  = state.get("sandbox_dir", "")

    if sandbox_dir and requirements:
        write_file(f"{sandbox_dir}/requirements.txt", "\n".join(requirements))

    bar = "═" * 60
    print(f"\n{bar}")
    print(f"  STATUS        {status.upper()}")
    print(f"  Python        {state.get('version')}")
    print(f"  Dependencies  {requirements or 'none'}")
    print(f"  Execution     {'✓ passed' if success else '✗ failed'}")
    print(f"  Tests         {'✓ passed' if state.get('tests_passed') else '✗ failed/skipped'}")
    print(f"  Code retries  {state.get('code_retry_count', 0)}")
    print(f"  Test retries  {state.get('test_retry_count', 0)}")
    print(f"  Sandbox       {sandbox_dir}")
    print(bar)

    return {"status": status, "error_message": err_msg}
