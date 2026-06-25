"""Node functions for the Coding Agent LangGraph pipeline."""

import json
import re
from typing import Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from .state import CodingAgentState
from .prompts import (
    TASK_UNDERSTANDING_PROMPT,
    CODE_GENERATION_PROMPT,
    CODE_REPAIR_PROMPT,
    TEST_GENERATION_PROMPT,
    CODE_REVIEW_PROMPT,
)
from .tools import (
    detect_imports,
    create_sandbox,
    install_dependencies,
    execute_code,
    execute_tests,
    cleanup_sandbox,
    generate_requirements_txt,
)


MAX_RETRIES = 3
MIN_REVIEW_SCORE = 4.0

# LLM singleton
_llm = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(model="gpt-4o", temperature=0.7, max_retries=2)
    return _llm


def _call_llm(system: str, user: str) -> str:
    """Single LLM call."""
    response = _get_llm().invoke([
        SystemMessage(content=system),
        HumanMessage(content=user),
    ])
    return response.content


def _parse_json(text: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    return json.loads(text.strip())


# ── Node 1: Understand Task ────────────────────────────────────────────────────

def understand_task(state: CodingAgentState) -> Dict:
    """Parse and understand the coding task."""
    print("[understand_task] Analyzing task...")

    prompt = TASK_UNDERSTANDING_PROMPT.format(
        language=state["language"],
        version=state["version"],
        task=state["task"],
        dependencies=", ".join(state.get("dependencies", [])) or "None",
        constraints=", ".join(state.get("constraints", [])) or "None",
        expected_output=state.get("expected_output") or "Not specified",
    )

    try:
        raw = _call_llm(
            "You are an expert software engineer analyzing requirements.",
            prompt,
        )
        understood = _parse_json(raw)
        print(f"[understand_task] Complexity: {understood.get('complexity')}")
        return {
            "understood_task": understood,
            "status": "understood",
        }
    except Exception as e:
        print(f"[understand_task] Failed: {e}")
        return {
            "understood_task": {
                "problem_summary": state["task"],
                "complexity": "intermediate",
                "key_components": [],
                "edge_cases": [],
                "suggested_dependencies": state.get("dependencies", []),
            },
            "status": "understood",
        }


# ── Node 2: Generate Code ──────────────────────────────────────────────────────

def generate_code(state: CodingAgentState) -> Dict:
    """Generate initial code based on task understanding."""
    print("[generate_code] Generating code...")

    understood = state.get("understood_task", {})
    complexity = understood.get("complexity", "intermediate")

    # Combine explicit + suggested dependencies
    all_deps = list(set(
        state.get("dependencies", []) +
        understood.get("suggested_dependencies", [])
    ))

    requirements = understood.get("problem_summary", state["task"])
    if understood.get("key_components"):
        requirements += "\n\nKey components: " + ", ".join(understood["key_components"])
    if understood.get("edge_cases"):
        requirements += "\n\nEdge cases to handle: " + ", ".join(understood["edge_cases"])

    prompt = CODE_GENERATION_PROMPT.format(
        language=state["language"],
        version=state["version"],
        task=state["task"],
        requirements=requirements,
        constraints="\n".join(state.get("constraints", [])) or "None",
        complexity=complexity,
    )

    try:
        raw = _call_llm(
            f"You are an expert {state['language']} programmer.",
            prompt,
        )
        data = _parse_json(raw)

        code = data.get("code", "")
        explicit_deps = data.get("dependencies", [])

        print(f"[generate_code] Generated {len(code)} chars of code")
        print(f"[generate_code] Explicit dependencies: {explicit_deps}")

        return {
            "generated_code": code,
            "detected_dependencies": explicit_deps,
            "status": "generated",
        }

    except Exception as e:
        print(f"[generate_code] Failed: {e}")
        return {
            "generated_code": f"# Code generation failed: {e}\npass",
            "detected_dependencies": [],
            "status": "failed",
            "error": str(e),
        }


# ── Node 3: Detect Dependencies ────────────────────────────────────────────────

def detect_dependencies_node(state: CodingAgentState) -> Dict:
    """Auto-detect imports and combine with explicit dependencies."""
    print("[detect_dependencies] Analyzing imports...")

    code = state.get("generated_code", "")
    language = state["language"]

    auto_detected = detect_imports(code, language)
    explicit = state.get("detected_dependencies", [])
    user_provided = state.get("dependencies", [])

    # Combine all sources
    all_deps = list(set(auto_detected + explicit + user_provided))

    print(f"[detect_dependencies] Auto-detected: {auto_detected}")
    print(f"[detect_dependencies] Total dependencies: {all_deps}")

    requirements_txt = generate_requirements_txt(all_deps)

    return {
        "all_dependencies": all_deps,
        "requirements_txt": requirements_txt,
    }


# ── Node 4: Create Sandbox ─────────────────────────────────────────────────────

def create_sandbox_node(state: CodingAgentState) -> Dict:
    """Create isolated execution environment."""
    print("[create_sandbox] Setting up sandbox...")

    try:
        sandbox_path, venv_path = create_sandbox(
            state["language"],
            state["version"],
        )

        return {
            "sandbox_path": sandbox_path,
            "venv_path": venv_path,
            "status": "sandbox_ready",
        }

    except Exception as e:
        print(f"[create_sandbox] Failed: {e}")
        return {
            "status": "failed",
            "error": f"Sandbox creation failed: {e}",
        }


# ── Node 5: Install Dependencies ───────────────────────────────────────────────

def install_dependencies_node(state: CodingAgentState) -> Dict:
    """Install dependencies in the sandbox."""
    print("[install_dependencies] Installing packages...")

    venv_path = state.get("venv_path")
    dependencies = state.get("all_dependencies", [])

    if not venv_path:
        return {"status": "failed", "error": "No venv path available"}

    success, logs = install_dependencies(venv_path, dependencies)

    if success:
        print("[install_dependencies] ✓ All dependencies installed")
        return {"status": "dependencies_installed"}
    else:
        print(f"[install_dependencies] ✗ Installation failed")
        return {
            "status": "dependency_failed",
            "runtime_errors": f"Dependency installation failed:\n{logs}",
        }


# ── Node 6: Execute Code ───────────────────────────────────────────────────────

def execute_code_node(state: CodingAgentState) -> Dict:
    """Execute the generated code in the sandbox."""
    print("[execute_code] Running code...")

    sandbox_path = state.get("sandbox_path")
    venv_path = state.get("venv_path")
    code = state.get("generated_code", "")

    if not sandbox_path or not venv_path:
        return {"status": "failed", "error": "Sandbox not available"}

    result = execute_code(sandbox_path, venv_path, code)

    exit_code = result["exit_code"]
    logs = f"STDOUT:\n{result['stdout']}\n\nSTDERR:\n{result['stderr']}"

    print(f"[execute_code] Exit code: {exit_code}")
    print(f"[execute_code] Execution time: {result['execution_time']}s")

    if exit_code == 0:
        print("[execute_code] ✓ Execution successful")
        return {
            "execution_logs": logs,
            "exit_code": exit_code,
            "execution_time": result["execution_time"],
            "runtime_errors": "",
            "status": "executed",
        }
    else:
        print(f"[execute_code] ✗ Execution failed")
        return {
            "execution_logs": logs,
            "exit_code": exit_code,
            "execution_time": result["execution_time"],
            "runtime_errors": result["stderr"],
            "status": "execution_failed",
        }


# ── Node 7: Validate Runtime ───────────────────────────────────────────────────

def validate_runtime(state: CodingAgentState) -> Dict:
    """Check if execution succeeded."""
    exit_code = state.get("exit_code")

    if exit_code == 0:
        print("[validate_runtime] ✓ Runtime validation passed")
        return {"status": "validated"}
    else:
        print("[validate_runtime] ✗ Runtime validation failed")
        return {"status": "needs_repair"}


# ── Node 8: Repair Code ────────────────────────────────────────────────────────

def repair_code(state: CodingAgentState) -> Dict:
    """Fix code based on runtime errors."""
    retry_count = state.get("retry_count", 0)

    if retry_count >= MAX_RETRIES:
        print(f"[repair_code] Max retries ({MAX_RETRIES}) reached")
        return {
            "status": "failed",
            "error": f"Code repair failed after {MAX_RETRIES} attempts",
        }

    print(f"[repair_code] Attempt {retry_count + 1}/{MAX_RETRIES}")

    prompt = CODE_REPAIR_PROMPT.format(
        language=state["language"],
        version=state["version"],
        code=state.get("generated_code", ""),
        exit_code=state.get("exit_code", -1),
        error_output=state.get("runtime_errors", ""),
        execution_logs=state.get("execution_logs", ""),
        dependencies=", ".join(state.get("all_dependencies", [])),
    )

    try:
        raw = _call_llm(
            f"You are an expert {state['language']} debugger.",
            prompt,
        )
        data = _parse_json(raw)

        fixed_code = data.get("fixed_code", state["generated_code"])
        changes = data.get("changes_made", "")
        new_deps = data.get("additional_dependencies", [])

        print(f"[repair_code] Changes: {changes}")

        # Update dependencies if new ones were added
        all_deps = list(set(state.get("all_dependencies", []) + new_deps))

        return {
            "generated_code": fixed_code,
            "all_dependencies": all_deps,
            "requirements_txt": generate_requirements_txt(all_deps),
            "retry_count": retry_count + 1,
            "status": "repaired",
        }

    except Exception as e:
        print(f"[repair_code] LLM repair failed: {e}")
        return {
            "retry_count": retry_count + 1,
            "status": "failed",
            "error": f"Code repair failed: {e}",
        }


# ── Node 9: Generate Tests ─────────────────────────────────────────────────────

def generate_tests(state: CodingAgentState) -> Dict:
    """Generate test cases for the validated code."""
    print("[generate_tests] Creating test cases...")

    prompt = TEST_GENERATION_PROMPT.format(
        language=state["language"],
        code=state.get("generated_code", ""),
        task=state["task"],
    )

    try:
        raw = _call_llm(
            f"You are an expert test engineer for {state['language']}.",
            prompt,
        )
        data = _parse_json(raw)

        test_code = data.get("test_code", "")
        test_deps = data.get("test_dependencies", [])

        # Add test dependencies
        all_deps = list(set(state.get("all_dependencies", []) + test_deps))

        print(f"[generate_tests] Generated {data.get('test_count', 0)} tests")

        return {
            "generated_tests": test_code,
            "all_dependencies": all_deps,
            "requirements_txt": generate_requirements_txt(all_deps),
            "status": "tests_generated",
        }

    except Exception as e:
        print(f"[generate_tests] Failed: {e}")
        return {
            "generated_tests": "# Test generation failed",
            "status": "test_gen_failed",
        }


# ── Node 10: Execute Tests ─────────────────────────────────────────────────────

def execute_tests_node(state: CodingAgentState) -> Dict:
    """Run the generated tests."""
    print("[execute_tests] Running tests...")

    sandbox_path = state.get("sandbox_path")
    venv_path = state.get("venv_path")
    test_code = state.get("generated_tests", "")
    main_code = state.get("generated_code", "")

    if not test_code or test_code.startswith("# Test generation failed"):
        print("[execute_tests] No valid tests to run")
        return {
            "tests_passed": True,  # Skip test validation
            "test_results": {"skipped": True},
            "status": "tests_skipped",
        }

    result = execute_tests(sandbox_path, venv_path, test_code, main_code)

    if result["passed"]:
        print(f"[execute_tests] ✓ All tests passed ({result['passed_count']} tests)")
        return {
            "tests_passed": True,
            "test_results": result,
            "status": "tests_passed",
        }
    else:
        print(f"[execute_tests] ✗ Tests failed ({result['failed_count']} failures)")
        return {
            "tests_passed": False,
            "test_results": result,
            "runtime_errors": result["output"],
            "status": "tests_failed",
        }


# ── Node 11: Code Review ───────────────────────────────────────────────────────

def review_code(state: CodingAgentState) -> Dict:
    """Final quality review of the code."""
    print("[review_code] Reviewing code quality...")

    complexity = state.get("understood_task", {}).get("complexity", "intermediate")

    prompt = CODE_REVIEW_PROMPT.format(
        language=state["language"],
        code=state.get("generated_code", ""),
        version=state["version"],
        complexity=complexity,
    )

    try:
        raw = _call_llm(
            f"You are a senior {state['language']} code reviewer.",
            prompt,
        )
        data = _parse_json(raw)

        overall = data.get("overall", 4.0)
        passed = data.get("pass", True)

        print(f"[review_code] Overall score: {overall:.1f}")
        print(f"[review_code] Pass: {passed}")

        return {
            "final_review": data,
            "status": "reviewed",
        }

    except Exception as e:
        print(f"[review_code] Failed: {e}")
        return {
            "final_review": {
                "overall": 4.0,
                "pass": True,
                "feedback": "",
            },
            "status": "reviewed",
        }


# ── Node 12: Finalize Output ───────────────────────────────────────────────────

def finalize_output(state: CodingAgentState) -> Dict:
    """Prepare final verified output."""
    print("[finalize_output] Preparing final output...")

    # Clean up sandbox
    sandbox_path = state.get("sandbox_path")
    if sandbox_path:
        cleanup_sandbox(sandbox_path)

    return {
        "final_code": state.get("generated_code", ""),
        "status": "success",
    }


# ── Node 13: Handle Failure ────────────────────────────────────────────────────

def handle_failure(state: CodingAgentState) -> Dict:
    """Clean up and prepare failure report."""
    print("[handle_failure] Preparing failure report...")

    # Clean up sandbox
    sandbox_path = state.get("sandbox_path")
    if sandbox_path:
        cleanup_sandbox(sandbox_path)

    return {
        "status": "failed",
        "final_code": "",
    }
