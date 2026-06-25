"""LangGraph pipeline definition for the Coding Agent."""

from langgraph.graph import StateGraph, END

from .state import CodingAgentState
from .nodes import (
    understand_task,
    generate_code,
    detect_dependencies_node,
    create_sandbox_node,
    install_dependencies_node,
    execute_code_node,
    validate_runtime,
    repair_code,
    generate_tests,
    execute_tests_node,
    review_code,
    finalize_output,
    handle_failure,
)


def _route_after_understanding(state: CodingAgentState) -> str:
    """Route after task understanding."""
    if state.get("status") == "understood":
        return "generate"
    return "fail"


def _route_after_generation(state: CodingAgentState) -> str:
    """Route after code generation."""
    if state.get("status") == "failed":
        return "fail"
    return "detect_deps"


def _route_after_sandbox(state: CodingAgentState) -> str:
    """Route after sandbox creation."""
    if state.get("status") == "failed":
        return "fail"
    return "install"


def _route_after_install(state: CodingAgentState) -> str:
    """Route after dependency installation."""
    if state.get("status") == "dependency_failed":
        return "fail"
    return "execute"


def _route_after_execution(state: CodingAgentState) -> str:
    """Route after code execution."""
    exit_code = state.get("exit_code", -1)
    if exit_code == 0:
        return "validate"
    return "validate"  # Still validate to decide repair


def _route_after_validation(state: CodingAgentState) -> str:
    """Route after runtime validation."""
    if state.get("status") == "validated":
        return "generate_tests"
    elif state.get("status") == "needs_repair":
        return "repair"
    return "fail"


def _route_after_repair(state: CodingAgentState) -> str:
    """Route after code repair."""
    status = state.get("status")
    retry_count = state.get("retry_count", 0)

    if status == "failed" or retry_count >= 3:
        return "fail"

    # Re-install dependencies (may have changed) and re-execute
    return "install"


def _route_after_test_execution(state: CodingAgentState) -> str:
    """Route after test execution."""
    tests_passed = state.get("tests_passed", False)
    status = state.get("status")

    if status == "tests_skipped" or tests_passed:
        return "review"
    elif status == "tests_failed":
        # Failed tests trigger code repair
        return "repair_for_tests"
    return "review"


def _route_after_test_repair(state: CodingAgentState) -> str:
    """Route after repairing for test failures."""
    retry_count = state.get("retry_count", 0)
    if retry_count >= 3:
        return "fail"
    # Re-run tests after repair
    return "execute_tests"


def build_coding_agent():
    """Build the Coding Agent graph."""
    graph = StateGraph(CodingAgentState)

    # Register all nodes
    graph.add_node("understand", understand_task)
    graph.add_node("generate", generate_code)
    graph.add_node("detect_deps", detect_dependencies_node)
    graph.add_node("create_sandbox", create_sandbox_node)
    graph.add_node("install", install_dependencies_node)
    graph.add_node("execute", execute_code_node)
    graph.add_node("validate", validate_runtime)
    graph.add_node("repair", repair_code)
    graph.add_node("generate_tests", generate_tests)
    graph.add_node("execute_tests", execute_tests_node)
    graph.add_node("review", review_code)
    graph.add_node("finalize", finalize_output)
    graph.add_node("fail", handle_failure)

    # Entry point
    graph.set_entry_point("understand")

    # Flow: understand → generate
    graph.add_conditional_edges(
        "understand",
        _route_after_understanding,
        {"generate": "generate", "fail": "fail"},
    )

    # Flow: generate → detect_deps
    graph.add_conditional_edges(
        "generate",
        _route_after_generation,
        {"detect_deps": "detect_deps", "fail": "fail"},
    )

    # Flow: detect_deps → create_sandbox
    graph.add_edge("detect_deps", "create_sandbox")

    # Flow: create_sandbox → install
    graph.add_conditional_edges(
        "create_sandbox",
        _route_after_sandbox,
        {"install": "install", "fail": "fail"},
    )

    # Flow: install → execute
    graph.add_conditional_edges(
        "install",
        _route_after_install,
        {"execute": "execute", "fail": "fail"},
    )

    # Flow: execute → validate
    graph.add_conditional_edges(
        "execute",
        _route_after_execution,
        {"validate": "validate"},
    )

    # Flow: validate → generate_tests or repair
    graph.add_conditional_edges(
        "validate",
        _route_after_validation,
        {
            "generate_tests": "generate_tests",
            "repair": "repair",
            "fail": "fail",
        },
    )

    # Flow: repair → install (loop back to reinstall + re-execute)
    graph.add_conditional_edges(
        "repair",
        _route_after_repair,
        {"install": "install", "fail": "fail"},
    )

    # Flow: generate_tests → execute_tests
    graph.add_edge("generate_tests", "execute_tests")

    # Flow: execute_tests → review or repair
    graph.add_conditional_edges(
        "execute_tests",
        _route_after_test_execution,
        {
            "review": "review",
            "repair_for_tests": "repair",
            "fail": "fail",
        },
    )

    # Flow: review → finalize
    graph.add_edge("review", "finalize")

    # Terminal nodes
    graph.add_edge("finalize", END)
    graph.add_edge("fail", END)

    return graph.compile()


# Module-level singleton
coding_agent = build_coding_agent()
