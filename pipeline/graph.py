"""
LangGraph pipeline definition.

The graph is deliberately linear — retry logic lives inside the nodes
(as plain Python loops) rather than as complex graph edges. This makes
the code much easier to read and debug.

Flow:
  validate_input → plan_script → generate_segments → merge_script → validate_and_eval → END
  (validate_input short-circuits to END if there are validation errors)
"""

from langgraph.graph import StateGraph, END

from .state import PipelineState
from .nodes import (
    validate_input,
    plan_script,
    generate_segments,
    merge_script,
    validate_and_eval,
)


def _route_after_validation(state: PipelineState) -> str:
    """Short-circuit to END if input validation failed."""
    if state.get("validation_errors"):
        return "error"
    return "ok"


def build_pipeline():
    graph = StateGraph(PipelineState)

    # Register nodes
    graph.add_node("validate_input",   validate_input)
    graph.add_node("plan_script",      plan_script)
    graph.add_node("generate_segments", generate_segments)
    graph.add_node("merge_script",     merge_script)
    graph.add_node("validate_and_eval", validate_and_eval)

    # Entry point
    graph.set_entry_point("validate_input")

    # After validation: proceed or abort
    graph.add_conditional_edges(
        "validate_input",
        _route_after_validation,
        {"ok": "plan_script", "error": END},
    )

    # Linear flow
    graph.add_edge("plan_script",       "generate_segments")
    graph.add_edge("generate_segments", "merge_script")
    graph.add_edge("merge_script",      "validate_and_eval")
    graph.add_edge("validate_and_eval", END)

    return graph.compile()


# Module-level singleton — import and call this from main.py
pipeline = build_pipeline()
