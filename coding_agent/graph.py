"""
Coding Agent — LangGraph graph.

Flow:
    understand_task → generate_code → detect_dependencies →
    create_sandbox  → install_dependencies → execute_code

    execute_code ──► success              → generate_tests
                 ──► fail, retry left     → repair_code → execute_code
                 ──► fail, retries done   → finalize (failure)

    generate_tests → run_tests

    run_tests    ──► pass                 → code_review
                 ──► fail, retry left     → repair_code → run_tests
                 ──► fail, retries done   → code_review (flagged)

    code_review → finalize → END
"""

from langgraph.graph import StateGraph, END

from .state import CodingAgentState
from .nodes import (
    understand_task,
    generate_code,
    detect_dependencies,
    create_sandbox,
    install_dependencies,
    execute_code,
    repair_code,
    generate_tests,
    run_tests,
    code_review,
    finalize,
    MAX_CODE_RETRIES,
    MAX_TEST_RETRIES,
)

# Supported Python versions - code will ONLY be generated for these versions
SUPPORTED_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]


def _route_after_execution(state: CodingAgentState) -> str:
    if state.get("execution_success"):
        return "generate_tests"
    if state.get("code_retry_count", 0) >= MAX_CODE_RETRIES:
        return "finalize"
    return "repair_code"


def _route_after_repair(state: CodingAgentState) -> str:
    return "run_tests" if state.get("phase") == "testing" else "execute_code"


def _route_after_tests(state: CodingAgentState) -> str:
    if state.get("tests_passed"):
        return "code_review"
    if state.get("test_retry_count", 0) >= MAX_TEST_RETRIES:
        return "code_review"
    return "repair_code"


def build_graph():
    g = StateGraph(CodingAgentState)

    for name, fn in [
        ("understand_task",      understand_task),
        ("generate_code",        generate_code),
        ("detect_dependencies",  detect_dependencies),
        ("create_sandbox",       create_sandbox),
        ("install_dependencies", install_dependencies),
        ("execute_code",         execute_code),
        ("repair_code",          repair_code),
        ("generate_tests",       generate_tests),
        ("run_tests",            run_tests),
        ("code_review",          code_review),
        ("finalize",             finalize),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("understand_task")

    # Linear spine
    g.add_edge("understand_task",      "generate_code")
    g.add_edge("generate_code",        "detect_dependencies")
    g.add_edge("detect_dependencies",  "create_sandbox")
    g.add_edge("create_sandbox",       "install_dependencies")
    g.add_edge("install_dependencies", "execute_code")

    # Execution loop
    g.add_conditional_edges(
        "execute_code",
        _route_after_execution,
        {
            "generate_tests": "generate_tests",
            "repair_code":    "repair_code",
            "finalize":       "finalize",
        },
    )

    # Repair routes back based on phase
    g.add_conditional_edges(
        "repair_code",
        _route_after_repair,
        {
            "execute_code": "execute_code",
            "run_tests":    "run_tests",
        },
    )

    # Test loop
    g.add_edge("generate_tests", "run_tests")

    g.add_conditional_edges(
        "run_tests",
        _route_after_tests,
        {
            "code_review": "code_review",
            "repair_code": "repair_code",
        },
    )

    # Final
    g.add_edge("code_review", "finalize")
    g.add_edge("finalize",    END)

    return g.compile()


# Module-level compiled graph — import and invoke from anywhere
agent = build_graph()


def run_agent(
    task: str,
    language: str = "python",
    version: str = "3.13",
    dependencies: list | None = None,
    constraints: list | None = None,
    expected_output: str = "",
) -> dict:
    """
    Invoke the coding agent and return a clean output dict.

    Args:
        task:            Natural-language description of what to build.
        language:        Programming language (currently only "python" is supported).
        version:         Target Python version string. MUST be one of: 3.10, 3.11, 3.12, 3.13
        dependencies:    Explicit pip packages to include.
        constraints:     Free-text constraints (e.g. "Readable for beginners").
        expected_output: Optional description of expected program output.

    Returns:
        {
            status, python_version, dependencies, requirements_txt,
            execution_passed, tests_passed,
            code, tests, execution_output,
            review_notes, sandbox_dir, error_message
        }

    Raises:
        ValueError: If version is not in SUPPORTED_VERSIONS (3.10, 3.11, 3.12, 3.13)
    """
    # Validate Python version upfront
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported Python version: {version}\n"
            f"Supported versions: {', '.join(SUPPORTED_VERSIONS)}\n"
            f"The coding agent generates code ONLY for these specific versions."
        )
    initial: CodingAgentState = {
        "task":              task,
        "language":          language,
        "version":           version,
        "dependencies":      dependencies or [],
        "constraints":       constraints or [],
        "expected_output":   expected_output,
        "task_analysis":     {},
        "generated_code":    "",
        "llm_requirements":  [],
        "all_requirements":  [],
        "generated_tests":   "",
        "sandbox_dir":       "",
        "venv_python":       "",
        "venv_pip":          "",
        "venv_pytest":       "",
        "execution_output":  "",
        "execution_errors":  "",
        "execution_success": False,
        "execution_time":    0.0,
        "test_output":       "",
        "test_errors":       "",
        "tests_passed":      False,
        "phase":             "execution",
        "code_retry_count":  0,
        "test_retry_count":  0,
        "review_notes":      "",
        "review_approved":   False,
        "status":            "pending",
        "error_message":     "",
    }

    final = agent.invoke(initial)

    return {
        "status":            final["status"],
        "python_version":    final["version"],
        "dependencies":      final["all_requirements"],
        "requirements_txt":  "\n".join(final["all_requirements"]),
        "execution_passed":  final["execution_success"],
        "tests_passed":      final["tests_passed"],
        "code":              final["generated_code"],
        "tests":             final["generated_tests"],
        "execution_output":  final["execution_output"],
        "review_notes":      final["review_notes"],
        "sandbox_dir":       final["sandbox_dir"],
        "error_message":     final.get("error_message", ""),
    }
