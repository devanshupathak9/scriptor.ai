"""
LangGraph pipeline definition.

Flow:
  validate_input → plan_script → generate_segments → merge_script → validate_and_eval
                                                                           │
                                              ┌────── score < 3.8 ────────┘
                                              ▼    (first time only)
                                  regenerate_weak_segment
                                              │
                                              └──────────────────────────────┐
                                                                             ▼
                                                                     validate_and_eval → END
                                                               (script_retried=True, always exits)

  validate_input short-circuits to END if the brief fails validation.
"""

from langgraph.graph import StateGraph, END

from .state import PipelineState
from .nodes import (
    validate_input,
    plan_script,
    generate_segments,
    merge_script,
    validate_and_eval,
    regenerate_weak_segment,
    route_after_eval,
)


def _route_after_validation(state: PipelineState) -> str:
    return "error" if state.get("validation_errors") else "ok"


def build_pipeline():
    graph = StateGraph(PipelineState)

    graph.add_node("validate_input",          validate_input)
    graph.add_node("plan_script",             plan_script)
    graph.add_node("generate_segments",       generate_segments)
    graph.add_node("merge_script",            merge_script)
    graph.add_node("validate_and_eval",       validate_and_eval)
    graph.add_node("regenerate_weak_segment", regenerate_weak_segment)

    graph.set_entry_point("validate_input")

    graph.add_conditional_edges(
        "validate_input",
        _route_after_validation,
        {"ok": "plan_script", "error": END},
    )

    graph.add_edge("plan_script",       "generate_segments")
    graph.add_edge("generate_segments", "merge_script")
    graph.add_edge("merge_script",      "validate_and_eval")

    # After eval: retry the weakest segment once if score is below threshold
    graph.add_conditional_edges(
        "validate_and_eval",
        route_after_eval,
        {"regenerate": "regenerate_weak_segment", "done": END},
    )

    # After regen: re-evaluate (script_retried=True guarantees exit to END)
    graph.add_edge("regenerate_weak_segment", "validate_and_eval")

    return graph.compile()


# Module-level singleton — import and call this from main.py
pipeline = build_pipeline()
